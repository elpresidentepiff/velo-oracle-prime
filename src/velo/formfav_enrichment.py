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
import unicodedata
from copy import deepcopy
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.velo.formfav_client import FormFavClient, FormFavError, best_live_prices


def _norm(value: Any) -> str:
    s = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _country(value: Any) -> str:
    key = str(value or "").strip().lower()
    return {"uk": "gb", "eng": "gb", "ire": "ie", "irl": "ie"}.get(key, key)


def _track_norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    raw = re.sub(r"\([^)]*\)", " ", raw)
    tokens = re.findall(r"[a-z0-9]+", raw)
    ignored = {"aw", "park", "racecourse", "race", "course"}
    aliases = {
        "leopardstown": "leopardstown",
        "kempton": "kempton",
        "newcastleupon": "newcastle",
    }
    key = "".join(token for token in tokens if token not in ignored)
    return aliases.get(key, key)


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


def _minute_distance(primary: int, target: int) -> int:
    """Compare clock times while tolerating RP's ambiguous 12-hour dot format."""
    options = {primary}
    if primary < 12 * 60:
        options.add(primary + 12 * 60)
    else:
        options.add(primary - 12 * 60)
    return min(min(abs(option - target), 24 * 60 - abs(option - target)) for option in options)


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
    race_number: Any = None,
    country: Any = None,
    used_race_ids: set[str] | None = None,
    max_minutes: int = 12,
) -> dict[str, Any] | None:
    match, _ = _match_existing_race(
        races,
        track=track,
        start_time=start_time,
        timezone=timezone,
        race_number=race_number,
        country=country,
        used_race_ids=used_race_ids,
        max_minutes=max_minutes,
    )
    return match


def _match_existing_race(
    races: list[dict[str, Any]],
    *,
    track: str,
    start_time: Any,
    timezone: str | None,
    race_number: Any = None,
    country: Any = None,
    used_race_ids: set[str] | None = None,
    max_minutes: int = 12,
) -> tuple[dict[str, Any] | None, str | None]:
    track_key = _track_norm(track)
    candidates = [r for r in races if _track_norm(r.get("course")) == track_key]
    if not candidates:
        # Tolerate genuine provider additions after removing venue suffixes.
        candidates = [
            r for r in races
            if track_key and _track_norm(r.get("course"))
            and (
                track_key in _track_norm(r.get("course"))
                or _track_norm(r.get("course")) in track_key
            )
        ]
    wanted_country = _country(country)
    country_candidates = [
        race for race in candidates
        if not wanted_country
        or not _country(race.get("country") or race.get("region"))
        or _country(race.get("country") or race.get("region")) == wanted_country
    ]
    if country_candidates:
        candidates = country_candidates
    if not candidates:
        return None, None
    available = [
        race for race in candidates
        if not used_race_ids or str(race.get("race_id") or id(race)) not in used_race_ids
    ]
    if not available:
        return None, None
    target = _ff_local_minutes(start_time, timezone)
    if target is not None:
        scored = []
        for race in available:
            local_minutes = _race_local_minutes(race, str(race.get("date") or ""))
            if local_minutes is not None:
                scored.append((_minute_distance(local_minutes, target), race))
        scored.sort(key=lambda item: item[0])
        if scored and scored[0][0] <= max_minutes:
            return scored[0][1], "track_time"

    # MeetingRace.startTime is nullable.  The provider's raceNumber is the
    # authoritative ordinal fallback within an already matched venue/card.
    try:
        ordinal = int(race_number)
    except (TypeError, ValueError):
        ordinal = 0
    ordered = sorted(
        candidates,
        key=lambda race: (
            _race_local_minutes(race, str(race.get("date") or "")) is None,
            _race_local_minutes(race, str(race.get("date") or "")) or 0,
            str(race.get("race_id") or ""),
        ),
    )
    if 1 <= ordinal <= len(ordered):
        selected = ordered[ordinal - 1]
        selected_id = str(selected.get("race_id") or id(selected))
        if not used_race_ids or selected_id not in used_race_ids:
            return selected, "track_race_number"
    if len(available) == 1:
        return available[0], "track_singleton"
    return None, None


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
    include_track_bias: bool = True,
    timezone: str = "Europe/London",
    report_path: Path | None = None,
    client: FormFavClient | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return enriched copies of existing races plus a machine-auditable report."""
    countries = {_country(c) for c in (countries or {"gb", "ie"})}
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
        "races_in_scope": 0,
        "races_matched": 0,
        "races_unmatched": 0,
        "form_calls_ok": 0,
        "price_calls_ok": 0,
        "price_calls_forbidden": 0,
        "track_bias_calls_ok": 0,
        "track_bias_calls_forbidden": 0,
        "track_bias_calls_failed": 0,
        "runners_matched": 0,
        "runners_unmatched": 0,
        "fields_filled": {},
        "matches": [],
        "unmatched_races": [],
        "matching_methods": {},
        "errors": [],
    }

    try:
        client = client or FormFavClient()
        meetings_payload = client.meetings(date_str, timezone=timezone)
    except Exception as exc:
        report["errors"].append(f"meetings: {type(exc).__name__}: {exc}")
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return out, report

    meetings = meetings_payload.get("meetings") or []
    report["meetings_seen"] = len(meetings)
    track_bias_cache: dict[tuple[str, str, str], dict[str, Any] | None] = {}
    used_race_ids: set[str] = set()

    def filled(field: str) -> None:
        report["fields_filled"][field] = int(report["fields_filled"].get(field, 0)) + 1

    for meeting in meetings:
        if not isinstance(meeting, dict):
            continue
        country = _country(meeting.get("country"))
        if country not in countries or meeting.get("abandoned"):
            continue
        report["meetings_in_scope"] += 1
        track = str(meeting.get("track") or "")
        slug = str(meeting.get("slug") or track)
        for mrace in meeting.get("races") or []:
            if not isinstance(mrace, dict) or mrace.get("abandoned"):
                continue
            report["races_in_scope"] += 1
            race_no = mrace.get("raceNumber")
            existing, matching_method = _match_existing_race(
                out,
                track=track,
                start_time=mrace.get("startTime"),
                timezone=mrace.get("timezone") or timezone,
                race_number=race_no,
                country=country,
                used_race_ids=used_race_ids,
            )
            if existing is None:
                report["races_unmatched"] += 1
                if len(report["unmatched_races"]) < 100:
                    report["unmatched_races"].append({
                        "formfav_track": track,
                        "raceNumber": race_no,
                        "startTime": mrace.get("startTime"),
                        "country": country,
                    })
                continue
            if race_no is None:
                continue
            used_race_ids.add(str(existing.get("race_id") or id(existing)))
            report["races_matched"] += 1
            report["matching_methods"][matching_method] = (
                int(report["matching_methods"].get(matching_method, 0)) + 1
            )

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

            # Track bias is distance-specific. Request one exact-distance packet
            # per venue/distance and cache it for the card. Failure is non-fatal.
            track_bias: dict[str, Any] | None = None
            distance_raw = form.get("distance") or mrace.get("distance")
            distance_match = re.search(r"(\d{3,4})", str(distance_raw or ""))
            distance_m = distance_match.group(1) if distance_match else None
            bias_key = (country, _norm(slug), str(distance_m or ""))
            if include_track_bias and distance_m:
                if bias_key not in track_bias_cache:
                    try:
                        track_bias_cache[bias_key] = client.track_bias(
                            venue=slug,
                            country=country,
                            distance=distance_m,
                            window=90,
                        )
                        report["track_bias_calls_ok"] += 1
                    except FormFavError as exc:
                        track_bias_cache[bias_key] = None
                        if "403" in str(exc):
                            report["track_bias_calls_forbidden"] += 1
                        else:
                            report["track_bias_calls_failed"] += 1
                            report["errors"].append(f"track_bias {track} {distance_m}m: {exc}")
                    except Exception as exc:
                        track_bias_cache[bias_key] = None
                        report["track_bias_calls_failed"] += 1
                        report["errors"].append(
                            f"track_bias {track} {distance_m}m: {type(exc).__name__}: {exc}"
                        )
                track_bias = track_bias_cache.get(bias_key)

            existing["_formfav"] = {
                "track": form.get("track") or track,
                "slug": slug,
                "country": country,
                "raceNumber": race_no,
                "startTime": form.get("startTime") or mrace.get("startTime"),
                "timezone": form.get("timezone") or mrace.get("timezone"),
                "condition": form.get("condition") or mrace.get("condition"),
                "weather": form.get("weather") or mrace.get("weather"),
                "paceScenario": form.get("paceScenario") or mrace.get("paceScenario"),
                "numberOfRunners": form.get("numberOfRunners") or mrace.get("numberOfRunners"),
                "prizeMoney": form.get("prizeMoney") or mrace.get("prizeMoney"),
                "distance": distance_raw,
                "trackBias": track_bias,
            }

            price_map = _price_by_runner(prices)
            ff_runners = {
                _norm(r.get("name")): r
                for r in (form.get("runners") or [])
                if isinstance(r, dict) and r.get("name")
            }
            ff_by_number = {
                str(r.get("number")): r
                for r in (form.get("runners") or [])
                if isinstance(r, dict) and r.get("number") not in (None, "")
            }
            matched_names = []
            for runner in existing.get("runners") or []:
                rk = _norm(runner.get("horse") or runner.get("horse_name"))
                ff = ff_runners.get(rk)
                runner_match_method = "name_exact" if ff is not None else None
                if ff is None:
                    number = runner.get("start_number") or runner.get("number") or runner.get("cloth_number")
                    numbered = ff_by_number.get(str(number))
                    candidate_name = _norm((numbered or {}).get("name"))
                    # Saddlecloth is only a tie-breaker, never identity by itself.
                    # Require a strong name relationship before accepting it.
                    if numbered is not None and rk and candidate_name:
                        similarity = SequenceMatcher(None, rk, candidate_name).ratio()
                        if rk in candidate_name or candidate_name in rk or similarity >= 0.82:
                            ff = numbered
                            runner_match_method = "number_name_guarded"
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
                    "identity_match_method": runner_match_method,
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
                "matching_method": matching_method,
                "runner_matches": len(matched_names),
                "formfav_runner_count": len(ff_runners),
                "price_runner_count": len(price_map),
            })

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return out, report
