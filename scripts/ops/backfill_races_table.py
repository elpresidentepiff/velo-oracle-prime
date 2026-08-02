#!/usr/bin/env python3
"""
Backfill Supabase `races` metadata table from a captured racecard_injection.json.

THE GAP THIS SCRIPT EXISTS TO CLOSE
------------------------------------
`races` (course, date, time, race_name, ...) was only ever written by
workers/ingestion_spine/db.py, the Racing API-era ingestion worker. The
Racing API was permanently decommissioned 2026-05-14 and nothing replaced
that writer for the RP HTML/PDF pipeline. `races` has had zero new rows
since 2026-05-06 -- every dashboard publish since then has shown blank
course/time/race_name for every runner, because
publish_daily_predictions_to_dashboard.py joins verdicts to `races` by
race_id to get that metadata and finds nothing.

This script reads the same racecard_injection.json the scoring/dashboard
pipeline already produces (one row per race, with course/off_time/
race_title/going/class/distance already parsed) and upserts it into
`races`, keyed on race_id (the table's primary key) so it's idempotent
and safe to re-run.

Usage:
    PYTHONPATH=. python scripts/ops/backfill_races_table.py --date 2026-07-25 --execute
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def _find_injection_path(date_str: str) -> Path | None:
    """Pick the racecard_injection.json with the most races for this date.

    Multiple capture folders can exist per date (retries, refreshes, merges);
    the richest one (by races_count) is the safest backfill source, not
    whichever sorts last alphabetically.
    """
    date_tag = date_str.replace("-", "_")
    candidates = sorted(set(
        list((ROOT / "data" / "racing_post_account_parsed").glob(f"*{date_tag}*/racecard_injection.json"))
        + list((ROOT / "data" / "racing_post_account_parsed").glob(f"*{date_str}*/racecard_injection.json"))
    ))
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    def _races_count(p: Path) -> int:
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            return len(payload.get("races", []))
        except Exception:
            return -1

    return max(candidates, key=_races_count)


def _parse_prize_money(raw: str | None) -> int | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def build_rows(date_str: str, races: list[dict]) -> list[dict]:
    rows = []
    seen_race_ids: set[str] = set()
    for r in races:
        race_id = r.get("race_id")
        course = r.get("course")
        off_time = r.get("off_time")
        if not off_time:
            # Older capture schema has no off_time field; derive HH:MM from the
            # full ISO race_time instead (e.g. "2026-05-25T12:30:00+01:00").
            race_time_iso = r.get("race_time") or ""
            if "T" in race_time_iso:
                off_time = race_time_iso.split("T", 1)[1][:5]
        if race_id is None or not course or not off_time:
            continue
        if str(race_id) in seen_race_ids:
            continue
        seen_race_ids.add(str(race_id))

        distance_furlongs = r.get("distance_furlongs")
        distance_f = round(distance_furlongs) if isinstance(distance_furlongs, (int, float)) else None

        rows.append({
            "race_id": str(race_id),
            "course": course,
            "date": date_str,
            "time": off_time,
            "race_type": r.get("race_type"),
            "distance_f": distance_f,
            "going": r.get("going"),
            "class": r.get("race_class"),
            "prize_money": _parse_prize_money(r.get("prize_money")),
            "runners_count": r.get("declared_runners") or r.get("number_of_runners"),
            "race_name": r.get("race_title"),
            "join_key": f"{course}|{date_str}|{off_time}".lower(),
            "raw": r,
        })
    return rows


def backfill(date_str: str, execute: bool) -> dict:
    injection_path = _find_injection_path(date_str)
    if not injection_path:
        return {"status": "FAIL", "error": f"No racecard_injection.json found for {date_str}"}

    payload = json.loads(injection_path.read_text(encoding="utf-8"))
    races = payload.get("races", [])
    rows = build_rows(date_str, races)

    result = {
        "status": "DRY_RUN",
        "date": date_str,
        "injection_source": str(injection_path),
        "races_in_injection": len(races),
        "rows_built": len(rows),
        "skipped": len(races) - len(rows),
        "courses": sorted({r["course"] for r in rows}),
    }

    if not execute:
        result["sample_row"] = rows[0] if rows else None
        return result

    from app.core.runtime_env import load_optional_env_file, resolve_supabase_service_key, resolve_supabase_url
    load_optional_env_file(None)
    sb_url = resolve_supabase_url()
    sb_key = resolve_supabase_service_key()
    if not sb_url or not sb_key:
        result["status"] = "FAIL"
        result["error"] = "Supabase credentials not resolved"
        return result

    from supabase import create_client
    db = create_client(sb_url, sb_key)

    upserted = 0
    errors = []
    _CHUNK = 50
    for offset in range(0, len(rows), _CHUNK):
        chunk = rows[offset:offset + _CHUNK]
        try:
            db.table("races").upsert(chunk, on_conflict="race_id").execute()
            upserted += len(chunk)
        except Exception as e:
            errors.append(f"chunk@{offset}: {e}")

    result["status"] = "PASS" if not errors else "PARTIAL"
    result["rows_upserted"] = upserted
    result["errors"] = errors
    return result


def main():
    parser = argparse.ArgumentParser(description="Backfill Supabase races table from racecard_injection.json")
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    parser.add_argument("--execute", action="store_true", help="Actually write to Supabase (default: dry run)")
    args = parser.parse_args()

    result = backfill(args.date, args.execute)
    print(json.dumps(result, indent=2, default=str))
    if result["status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
