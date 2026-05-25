#!/usr/bin/env python3
"""Verify Supabase RP archive load counts and guard fields."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from typing import Any

from rp_supabase_archive_common import REPORT_ROOT, RPR_POLICY, SupabaseRest, utc_now


def _date_keys(from_date: str, to_date: str) -> set[str]:
    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)
    keys: set[str] = set()
    current = start
    while current <= end:
        keys.add(current.isoformat())
        current += timedelta(days=1)
    return keys


def _row_matches_date_range(row: dict[str, Any], from_date: str, to_date: str, date_keys: set[str]) -> bool:
    source_date = row.get("source_date")
    if source_date:
        return from_date <= str(source_date) <= to_date
    race_key = str(row.get("race_key") or "")
    return any(race_key.startswith(f"rp_archive:{date_key}:") for date_key in date_keys)


def run(from_date: str, to_date: str) -> dict[str, Any]:
    client = SupabaseRest()
    tables = ["rp_meetings", "rp_racecards", "rp_runner_profiles", "rp_runner_signals", "rp_entity_aliases", "raw_payload_archive"]
    date_keys = _date_keys(from_date, to_date)
    racecard_rows = [
        row
        for row in client.select("rp_racecards", {}, select="race_key,source_date", limit=5000)
        if _row_matches_date_range(row, from_date, to_date, date_keys)
    ]
    race_keys = [str(row.get("race_key")) for row in racecard_rows if row.get("race_key")]
    counts: dict[str, int] = {}
    samples: dict[str, list[dict[str, Any]]] = {}
    duplicates: dict[str, int] = {}
    null_critical: dict[str, int] = {}
    for table in tables:
        if table == "rp_entity_aliases":
            rows = client.select(table, {"entity_type": "horse"}, select="*", limit=5000)
        elif table == "raw_payload_archive":
            rows = client.select(table, {"parse_status": "PASS"}, select="*", limit=5000)
            rows = [r for r in rows if str(r.get("endpoint", "")).startswith("local_rp_archive/")]
        elif table in {"rp_runner_profiles", "rp_runner_signals"}:
            rows = []
            for race_key in race_keys:
                rows.extend(client.select(table, {"race_key": race_key}, select="*", limit=1000))
        else:
            rows = racecard_rows if table == "rp_racecards" else client.select(table, {}, select="*", limit=5000)
            rows = [r for r in rows if _row_matches_date_range(r, from_date, to_date, date_keys)]
        counts[table] = len(rows)
        samples[table] = rows[:3]
        if table == "rp_racecards":
            duplicates[table] = sum(v - 1 for v in Counter(r.get("race_key") for r in rows).values() if v > 1)
            null_critical[table] = sum(1 for r in rows if not r.get("race_key"))
        elif table in {"rp_runner_profiles", "rp_runner_signals"}:
            key_counts = Counter((r.get("race_key"), r.get("runner_number"), r.get("horse_name")) for r in rows)
            duplicates[table] = sum(v - 1 for v in key_counts.values() if v > 1)
            null_critical[table] = sum(1 for r in rows if not r.get("race_key") or not r.get("horse_name"))
        else:
            duplicates[table] = 0
            null_critical[table] = 0
    raw_rows = client.select("raw_payload_archive", {"parse_status": "PASS"}, select="payload_json,endpoint", limit=5000)
    archive_raw = [r for r in raw_rows if str(r.get("endpoint", "")).startswith("local_rp_archive/")]
    rpr_false_count = 0
    rpr_leaks = []
    for row in archive_raw:
        payload = row.get("payload_json") or {}
        raw = json.dumps(payload, ensure_ascii=False)
        if "rp_rpr_velo_allowed\": false" in raw or '"rp_rpr_velo_allowed": false' in raw:
            rpr_false_count += 1
        if '"velo_scoring_allowed": true' in raw:
            rpr_leaks.append(row.get("endpoint"))
    payload = {
        "generated_at": utc_now(),
        "from_date": from_date,
        "to_date": to_date,
        "table_counts": counts,
        "duplicate_counts": duplicates,
        "null_critical_counts": null_critical,
        "rp_rpr_velo_allowed_false_payload_count": rpr_false_count,
        "rpr_scoring_leaks": rpr_leaks,
        "rpr_policy": RPR_POLICY,
        "verification_status": "PASS" if not rpr_leaks and all(v == 0 for v in duplicates.values()) else "WARN",
        "samples": samples,
    }
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_ROOT / "rp_supabase_archive_verify_latest.json"
    md_path = REPORT_ROOT / "rp_supabase_archive_verify_latest.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# RP Supabase Archive Verification", "", f"- Status: `{payload['verification_status']}`", f"- RPR leaks: `{len(rpr_leaks)}`", ""]
    for table, count in counts.items():
        lines.append(f"- {table}: `{count}` rows, duplicates `{duplicates[table]}`, null critical `{null_critical[table]}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify RP Supabase archive load.")
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    args = parser.parse_args()
    run(args.from_date, args.to_date)


if __name__ == "__main__":
    main()
