#!/usr/bin/env python3
"""Run VÉLØ's existing model stack over FormFav international racecards.

This is SHADOW ONLY. It never writes velo_verdicts, pipeline_runs, selections,
or execution state. The purpose is to study cross-jurisdiction behaviour and
build evidence before any international model promotion.

Two passes per run. First every card is read and its stored market prices are
counted, so the state of each country's price feed is known. Then each race is
either frozen (``PRICED``, ``PARTIAL_MARKET``, ``NO_MARKET``) or deferred
(``AWAITING_PRICES``) because the feed is live for that country, this race has no
price yet, and another hourly run will still happen before the off.

With ``--persist-scorecard`` the run also writes one ``world_pipeline_runs`` row per
country and then settles recent days (``run_world_sigma``). ``--no-settle`` turns the
settlement step off.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.runtime_env import load_optional_env_file
from app.services.velo_prime_service import score_race_velo_prime
from src.velo.formfav_cache_client import CachedFormFavClient
from src.velo.formfav_card_adapter import fetch_formfav_racecards
from src.velo.world_scorecard_store import (
    build_rows,
    build_run_rows,
    decide_freeze,
    persist_rows_detailed,
    persist_run_rows,
    top_tie_size,
    usable_price,
)
from workers.racing_api_normalizer import normalize_race

SETTLE_DAYS = 3


def _name_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _recent_dates(date_str: str, days: int) -> list[str]:
    day = datetime.fromisoformat(date_str).date()
    return [(day - timedelta(days=i)).isoformat() for i in range(days)]


def _racing_dates(date_str: str) -> list[str]:
    day = datetime.fromisoformat(date_str).date()
    return [(day + timedelta(days=d)).isoformat() for d in (-1, 0, 1)]


def _new_stat() -> dict:
    return {
        "seen": 0, "scored": 0, "deferred": 0, "skipped_post_off": 0, "runners_scored": 0,
        "unscorable": 0, "tied_top_races": 0, "identity_blocked": 0, "freeze_states": Counter(), "deferred_keys": [],
    }


def main() -> int:
    load_optional_env_file(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--countries", default="us,ca,fr,au,hk,jp")
    ap.add_argument("--tracks", default="")
    ap.add_argument("--timezone", default="Europe/London")
    ap.add_argument("--no-prices", action="store_true")
    ap.add_argument("--persist-artifact", action="store_true")
    ap.add_argument("--persist-scorecard", action="store_true")
    ap.add_argument("--no-settle", action="store_true")
    args = ap.parse_args()

    date_str = args.date or datetime.now(UTC).date().isoformat()
    countries = {c.strip().lower() for c in args.countries.split(",") if c.strip()}
    tracks = {t.strip() for t in args.tracks.split(",") if t.strip()}

    # Races are stored under their LOCAL racing date (#189). The races that go off on this UTC
    # date carry the racing dates either side of it (an evening US card is the previous racing
    # day; an early Australian card the next one), so scan all three and keep only races whose
    # off falls on this UTC date: the same universe as before, now correctly identified.
    client = CachedFormFavClient(live=None, max_age_hours=36)
    raw_races: list[dict] = []
    fetch_report: dict = {"date": date_str, "racing_dates": {}, "errors": [], "error_detail": [],
                          "identity_blocked": []}
    for racing_date in _racing_dates(date_str):
        try:
            races_d, report_d = fetch_formfav_racecards(
                date_str=racing_date,
                countries=countries,
                timezone=args.timezone,
                include_prices=not args.no_prices,
                tracks=tracks or None,
                client=client,
                utc_date=date_str,
            )
        except Exception as exc:  # noqa: BLE001 - a missing neighbouring date must not stop the run
            fetch_report["errors"].append(f"meetings {racing_date}: {type(exc).__name__}: {exc}")
            continue
        raw_races += races_d
        fetch_report["racing_dates"][racing_date] = {
            k: report_d.get(k) for k in ("meetings_seen", "meetings_in_scope", "races_loaded", "runners_loaded")
        }
        for k in ("errors", "error_detail", "identity_blocked"):
            fetch_report[k] += report_d.get(k) or []

    generated_at = datetime.now(UTC)
    by_country: dict[str, dict] = {}
    for blocked in fetch_report["identity_blocked"]:
        by_country.setdefault(str(blocked.get("country") or "").lower(), _new_stat())["identity_blocked"] += 1

    # Pass 1: which cards are still pre-off, and how many runners already have a dated price.
    candidates = []
    feed_live: dict[str, bool] = {}
    for raw in raw_races:
        cc = str(raw.get("country") or "").lower()
        stat = by_country.setdefault(cc, _new_stat())
        stat["seen"] += 1
        if ((raw.get("_formfav") or {}).get("race_identity") or {}).get("status") != "VERIFIED":
            stat["identity_blocked"] += 1
            continue
        scheduled_off = (raw.get("_formfav") or {}).get("startTime")
        try:
            off_dt = datetime.fromisoformat(str(scheduled_off).replace("Z", "+00:00"))
            if off_dt.tzinfo is None:
                off_dt = off_dt.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            continue
        if off_dt <= generated_at:
            stat["skipped_post_off"] += 1
            continue
        markets = {
            _name_key(r.get("horse")): (r.get("_formfav") or {}).get("market") or {}
            for r in raw.get("runners") or []
        }
        priced = sum(1 for m in markets.values() if usable_price(m, off_dt, generated_at)[0])
        feed_live[cc] = feed_live.get(cc, False) or priced > 0
        candidates.append((raw, cc, scheduled_off, off_dt, markets, priced))

    # Pass 2: freeze or defer, then score what is being frozen.
    races_out = []
    deferred = []
    for raw, cc, scheduled_off, off_dt, markets, priced in candidates:
        stat = by_country[cc]
        meta = raw.get("_formfav") or {}
        minutes_to_off = (off_dt - generated_at).total_seconds() / 60
        freeze, state = decide_freeze(
            priced, len(raw.get("runners") or []), feed_live.get(cc, False), minutes_to_off
        )
        stat["freeze_states"][state] += 1
        if not freeze:
            stat["deferred"] += 1
            stat["deferred_keys"].append(meta.get("provider_race_key"))
            deferred.append({
                "provider_race_key": meta.get("provider_race_key"), "country": cc,
                "state": state, "minutes_to_off": round(minutes_to_off, 1),
            })
            continue
        race = normalize_race(raw)
        preds = score_race_velo_prime(race)
        if not preds:
            stat["unscorable"] += 1
            continue
        # Keep this report compact but preserve the signals we need to study.
        scorecard = []
        real_price: dict[str, float] = {}
        numbers = {
            _name_key(r.get("horse")): (r.get("_formfav") or {}).get("number") for r in raw.get("runners") or []
        }
        for rank, p in enumerate(preds, start=1):
            name = p.get("horse") or p.get("horse_name")
            price, price_at = usable_price(markets.get(_name_key(name)), off_dt, generated_at)
            if price:
                real_price[_name_key(name)] = price
            scorecard.append({
                "rank": rank,
                "horse": name,
                "horse_id": p.get("horse_id"),
                "runner_number": numbers.get(_name_key(name)),
                "velo_prime_prob": p.get("velo_prime_prob"),
                "place_prob": p.get("place_prob"),
                "longshot_prob": p.get("longshot_prob"),
                "improvement_score": p.get("improvement_score"),
                "market_deception_score": p.get("market_deception_score"),
                "confidence_level": p.get("confidence_level"),
                # Model input. Equals 10.0 when the runner had no price: a default, not a price.
                "sp_dec": p.get("sp_dec"),
                "captured_price": price,
                "price_state": "REAL" if price else "MISSING",
                "price_captured_at": price_at,
            })
        top3 = scorecard[:3]
        tie = top_tie_size(scorecard)
        # A longshot needs a real price; the 10.0 default would make every unpriced runner one.
        priced_preds = [p for p in preds if real_price.get(_name_key(p.get("horse") or p.get("horse_name")), 0) >= 6.0]
        longshot = max(priced_preds, key=lambda p: float(p.get("longshot_prob") or 0), default=None)
        races_out.append({
            "race_id": race.get("race_id"),
            "provider_race_key": meta.get("provider_race_key"),
            "race_date": meta.get("race_date"),
            "race_identity": meta.get("race_identity"),
            "race_number": meta.get("raceNumber"),
            "scheduled_off": scheduled_off,
            "course": race.get("course"),
            "off_time": race.get("off_time"),
            "race_name": race.get("race_name"),
            "country": raw.get("country"),
            "field_size": len(race.get("runners") or []),
            "freeze_state": state,
            "priced_runners": len(real_price),
            "top_tie_size": tie,
            "top3": top3,
            "scorecard": scorecard,
            "longshot": ({
                "horse": longshot.get("horse") or longshot.get("horse_name"),
                "horse_id": longshot.get("horse_id"),
                "captured_price": real_price.get(_name_key(longshot.get("horse") or longshot.get("horse_name"))),
                "longshot_prob": longshot.get("longshot_prob"),
                "place_prob": longshot.get("place_prob"),
                "velo_prime_prob": longshot.get("velo_prime_prob"),
            } if longshot else None),
        })
        stat["scored"] += 1
        stat["runners_scored"] += len(scorecard)
        stat["tied_top_races"] += 1 if tie > 1 else 0

    for stat in by_country.values():
        stat["freeze_states"] = dict(stat["freeze_states"])

    payload = {
        "date": date_str,
        "generated_at": generated_at.isoformat(),
        "code_commit": os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT") or "unknown",
        "status": "EXPERIMENTAL_CROSS_JURISDICTION_SHADOW_ONLY",
        "countries": sorted(countries),
        "tracks": sorted(tracks),
        "source": "FormFav",
        "source_contract": "CARDS_FORM_STATS_SCRATCHINGS_PRICES_ONLY",
        "formfav_predictions_consumed": False,
        "scoring_engine": "existing_velo_prime_stack",
        "execution_allowed": False,
        "promotion_allowed": False,
        "canonical_production_write": False,
        "warning": "Existing Velo models were developed primarily on UK/IRE evidence. International outputs are research until independently validated.",
        "fetch_report": fetch_report,
        "race_count": len(races_out),
        "races_skipped_post_off": sum(s["skipped_post_off"] for s in by_country.values()),
        "races_identity_blocked": fetch_report.get("identity_blocked") or [],
        "races_deferred": deferred,
        "by_country": by_country,
        "races": races_out,
    }

    out = ROOT / "data" / "reports" / f"formfav_global_shadow_{date_str.replace('-', '_')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": payload["status"],
        "date": date_str,
        "countries": sorted(countries),
        "races": len(races_out),
        "deferred": len(deferred),
        "identity_blocked": len(fetch_report.get("identity_blocked") or []),
        "output": str(out.relative_to(ROOT)),
        "fetch_errors": len(fetch_report.get("errors") or []),
    }, indent=2))

    if args.persist_artifact:
        cmd = [
            sys.executable, "scripts/ops/persist_daily_artifacts.py",
            "--kind", "reports", "--date", date_str, "--execute",
        ]
        import subprocess
        rc = subprocess.run(cmd, cwd=ROOT, check=False).returncode
        if rc != 0:
            print(f"WARNING: artifact persistence exited {rc}", file=sys.stderr)
    if args.persist_scorecard:
        rows = build_rows(payload)
        inserted: list[dict] = []
        for i in range(0, len(rows), 200):
            inserted += persist_rows_detailed(rows[i:i + 200])
        attempted_by_cc = Counter(r["country"] for r in rows)
        inserted_by_cc = Counter(r["country"] for r in inserted)
        print(
            f"[WORLD-SCORECARD] attempted={len(rows)} inserted={len(inserted)} "
            f"ignored_duplicates={len(rows) - len(inserted)} deferred_races={len(deferred)}",
            flush=True,
        )
        persist_run_rows(build_run_rows(payload, dict(attempted_by_cc), dict(inserted_by_cc)))
        if not args.no_settle:
            try:
                from scripts.ops.run_world_sigma import default_io, settle_dates
                get_json, post_json = default_io()
                report = settle_dates(
                    _recent_dates(date_str, SETTLE_DAYS),
                    get_json=get_json, post_json=post_json, execute=True,
                )
                print(f"[WORLD-SIGMA] {json.dumps(report['totals'])}", flush=True)
            except Exception as exc:  # noqa: BLE001 - settlement must never break the freeze
                print(f"[WORLD-SIGMA] FAILED {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
