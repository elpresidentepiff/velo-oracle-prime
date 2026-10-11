"""Additive FormFav enrichment for existing VÉLØ racecards.

The current Racing API remains the primary source. FormFav is a second source:
- fills genuinely missing fields only;
- attaches its independent stats/market packet under _formfav keys;
- never overwrites an existing primary-source value;
- writes an auditable daily report for durable Supabase persistence.
"""
from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.velo.formfav_client import FormFavClient, FormFavError, best_live_prices


def _norm(value: Any) -> str:
    s = str(value or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _safe_float(v: Any) -> float | None:
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _kg_to_lbs(v: Any) -> int | None:
    f = _safe_float(v)
    return round(f * 2.2046226218) if f is not None and f > 0 else None


def _race_local_minutes(race: dict[str, Any], date_str: str) -> int | None:
    raw = str(race.get("off_time") or race.get("time") or "").strip()
    if not raw:
        return None
    m = re.search(r"(\d{1,2}):(\d{2})", raw)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.search(r"^(\d{1,2})[\.:](\d{2})$", raw)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def _ff_local_minutes(start_time: Any, tz_name: str | None) -> int | None:
    if not start_time:
        return None
    try:
        dt = datetime.fromisoformat(str(start_time).replace("Z", "+00:00"))
        tz = ZoneInfo(tz_name or "Europe/London")
        local = dt.astimezone(tz)
        return local.hour * 60 + local.minute
    except Exception:
        return None


def _closest_existing_race(
    races: list[dict[str, Any]],
    *,
    track: str,
    start_time: Any,
    timezone: str | None,
    max_minutes: int = 12,
) -> dict[str, Any] | None:
    track_key = _norm(track)
    candidates = [r for r in races if _norm(r.get("course")) == track_key]
    if not candidates:
        # tolerate naming additions such as "(AW)" or "Park"
        candidates = [
            r for r in races
            if track_key and _norm(r.get("course"))
            and (track_key in _norm(r.get("course")) or _norm(r.get("course")) in track_key)
        ]
    if not candidates:
        return None
    target = _ff_local_minutes(start_time, timezone)
    if target is None:
        return candidates[0] if len(candidates) == 1 else None
    scored = []
    for r in candidates:
        rm = _race_local_minutes(r, str(r.get("date") or ""))
        if rm is not None:
            scored.append((abs(rm - target), r))
    if not scored:
        return candidates[0] if len(candidates) == 1 else None
    scored.sort(key=lambda x: x[0])
    return scored[0][1] if scored[0][0] <= max_minutes else None


def _price_by_runner(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _norm(r.get("name")): r
        for r in (payload.get("runners") or [])
        if isinstance(r, dict) and r.get("name")
    }


def enrich_existing_racecards(
    *,
    date_str: str,
    races: list[dict[str, Any]],
    countries: set[str] | None = None,
    include_prices: bool = True,
    timezone: str = "Europe/London",
    report_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return enriched copies of existing races plus a machine-auditable report."""
    countries = {c.lower() for c in (countries or {"gb", "ie"})}
    out = deepcopy(races)
    report: dict[str, Any] = {
        "date": date_str,
        "source": "formfav",
        "mode": "additive_enrichment",
        "countries": sorted(countries),
        "primary_source_preserved": True,
        "races_input": len(out),
        "meetings_seen": 0,
        "meetings_in_scope": 0,
        "races_matched": 0,
        "form_calls_ok": 0,
        "price_calls_ok": 0,
        "price_calls_forbidden": 0,
        "runners_matched": 0,
        "runners_unmatched": 0,
        "fields_filled": {},
        "matches": [],
        "errors": [],
    }

    try:
        client = FormFavClient()
        meetings_payload = client.meetings(date_str, timezone=timezone)
    except Exception as exc:
        report["errors"].append(f"meetings: {type(exc).__name__}: {exc}")
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return out, report

    meetings = meetings_payload.get("meetings") or []
    report["meetings_seen"] = len(meetings)

    def filled(field: str) -> None:
        report["fields_filled"][field] = int(report["fields_filled"].get(field, 0)) + 1

    for meeting in meetings:
        if not isinstance(meeting, dict):
            continue
        country = str(meeting.get("country") or "").lower()
        if country not in countries or meeting.get("abandoned"):
            continue
        report["meetings_in_scope"] += 1
        track = str(meeting.get("track") or "")
        slug = str(meeting.get("slug") or track)
        for mrace in meeting.get("races") or []:
            if not isinstance(mrace, dict) or mrace.get("abandoned"):
                continue
            existing = _closest_existing_race(
                out,
                track=track,
                start_time=mrace.get("startTime"),
                timezone=mrace.get("timezone") or timezone,
            )
            if existing is None:
                continue

            race_no = mrace.get("raceNumber")
            if race_no is None:
                continue
            report["races_matched"] += 1

            try:
                form = client.race_form(
                    date=date_str,
                    track=slug,
                    race=int(race_no),
                    country=country,
                    timezone=mrace.get("timezone") or timezone,
                )
                report["form_calls_ok"] += 1
            except Exception as exc:
                report["errors"].append(f"form {track} R{race_no}: {type(exc).__name__}: {exc}")
                continue

            prices: dict[str, Any] = {}
            if include_prices:
                try:
                    prices = client.prices(
                        date=date_str,
                        track=slug,
                        race=int(race_no),
                        country=country,
                        timezone=mrace.get("timezone") or timezone,
                    )
                    report["price_calls_ok"] += 1
                except FormFavError as exc:
                    if "403" in str(exc):
                        report["price_calls_forbidden"] += 1
                    else:
                        report["errors"].append(f"prices {track} R{race_no}: {exc}")
                except Exception as exc:
                    report["errors"].append(f"prices {track} R{race_no}: {type(exc).__name__}: {exc}")

            # Fill race-level holes only.
            race_fill_map = {
                "race_name": form.get("raceName") or mrace.get("raceName"),
                "race_class": form.get("raceClass") or mrace.get("raceClass"),
                "going": form.get("condition") or mrace.get("condition"),
                "distance": form.get("distance") or mrace.get("distance"),
            }
            for key, value in race_fill_map.items():
                if value not in (None, "") and existing.get(key) in (None, ""):
                    existing[key] = value
                    filled(f"race.{key}")

            existing["_formfav"] = {
                "track": form.get("track") or track,
                "slug": slug,
                "country": country,
                "raceNumber": race_no,
                "startTime": form.get("startTime") or mrace.get("startTime"),
                "timezone": form.get("timezone") or mrace.get("timezone"),
                "condition": form.get("condition") or mrace.get("condition"),
                "weather": form.get("weather") or mrace.get("weather"),
                "numberOfRunners": form.get("numberOfRunners") or mrace.get("numberOfRunners"),
                "prizeMoney": form.get("prizeMoney") or mrace.get("prizeMoney"),
            }

            price_map = _price_by_runner(prices)
            ff_runners = {
                _norm(r.get("name")): r
                for r in (form.get("runners") or [])
                if isinstance(r, dict) and r.get("name")
            }
            matched_names = []
            for runner in existing.get("runners") or []:
                rk = _norm(runner.get("horse") or runner.get("horse_name"))
                ff = ff_runners.get(rk)
                if ff is None:
                    report["runners_unmatched"] += 1
                    continue
                report["runners_matched"] += 1
                matched_names.append(ff.get("name"))

                market = best_live_prices(price_map.get(rk, {})) if rk in price_map else {
                    "best_win": None, "best_place": None, "quotes": [], "fresh_quote_count": 0
                }
                runner["_formfav"] = {
                    "number": ff.get("number"),
                    "name": ff.get("name"),
                    "scratched": bool(ff.get("scratched")),
                    "jockey": ff.get("jockey"),
                    "trainer": ff.get("trainer"),
                    "weightKg": ff.get("weight"),
                    "claimKg": ff.get("claim"),
                    "barrier": ff.get("barrier"),
                    "age": ff.get("age"),
                    "sex": ff.get("sex"),
                    "sire": ff.get("sire"),
                    "dam": ff.get("dam"),
                    "country": ff.get("country"),
                    "form": ff.get("form"),
                    "last20Starts": ff.get("last20Starts"),
                    "stats": ff.get("stats") or {},
                    "decorators": ff.get("decorators") or [],
                    "speedMap": ff.get("speedMap"),
                    "classProfile": ff.get("classProfile"),
                    "raceClassFit": ff.get("raceClassFit"),
                    "market": market,
                }

                # Fill missing primary fields. Never overwrite existing values.
                fill_pairs = {
                    "jockey": ff.get("jockey"),
                    "trainer": ff.get("trainer"),
                    "draw": ff.get("barrier"),
                    "age": ff.get("age"),
                    "sex": ff.get("sex"),
                    "form": ff.get("form"),
                }
                for key, value in fill_pairs.items():
                    if value not in (None, "") and runner.get(key) in (None, ""):
                        runner[key] = value
                        filled(f"runner.{key}")

                if runner.get("lbs") in (None, "") and ff.get("weight") not in (None, ""):
                    lbs = _kg_to_lbs(ff.get("weight"))
                    if lbs is not None:
                        runner["lbs"] = lbs
                        filled("runner.lbs")

                # FormFav can safely fill a missing market price, but never replace
                # an existing Racing API quote in this first integration phase.
                if runner.get("odds") in (None, "", [], 0, 0.0) and market.get("best_win"):
                    runner["odds"] = market["best_win"]
                    filled("runner.odds")

            report["matches"].append({
                "race_id": existing.get("race_id"),
                "primary_course": existing.get("course"),
                "formfav_track": track,
                "formfav_slug": slug,
                "raceNumber": race_no,
                "runner_matches": len(matched_names),
                "formfav_runner_count": len(ff_runners),
                "price_runner_count": len(price_map),
            })

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return out, report
