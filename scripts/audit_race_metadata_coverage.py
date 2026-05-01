"""
Race Metadata Coverage Audit
=============================

Audits VP30 metadata coverage for a given date.
Pass rule: 100% VP30 metadata coverage (course + off_time resolved).

Usage:
    python scripts/audit_race_metadata_coverage.py --date 2026-05-01

Read-only. No scoring, model, router, or staking changes.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from supabase import create_client

from src.velo.race_metadata_resolver import RaceMetadataResolver

load_dotenv(ROOT / ".env")

VP_THRESHOLD = 0.30


def _sb():
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )


def run_audit(date_str: str) -> bool:
    sb = _sb()

    verdicts = (
        sb.table("velo_verdicts")
        .select("race_id,velo_prime_prob,decision_tier,full_analysis,generated_at")
        .gte("generated_at", f"{date_str}T00:00:00")
        .lt("generated_at", f"{date_str}T23:59:59")
        .order("velo_prime_prob", desc=True)
        .execute()
        .data
    )

    total = len(verdicts)
    vp30 = []
    verdict_map: dict[str, list] = {}
    for v in verdicts:
        vp = float(v.get("velo_prime_prob") or 0)
        fa = v.get("full_analysis") or []
        verdict_map[v["race_id"]] = fa
        if vp >= VP_THRESHOLD:
            vp30.append(v)

    race_ids = [v["race_id"] for v in vp30]
    resolver = RaceMetadataResolver(date=date_str, sb_client=sb)
    meta_map = resolver.resolve_batch(race_ids, verdict_map)

    complete = [rid for rid, m in meta_map.items() if m.metadata_complete]
    incomplete = [rid for rid, m in meta_map.items() if not m.metadata_complete]

    source_counts: Counter = Counter()
    for m in meta_map.values():
        src = m.source_used.split(":")[0] if m.source_used else "unresolved"
        source_counts[src] += 1

    passed = len(incomplete) == 0

    print(f"RACE METADATA COVERAGE AUDIT — {date_str}")
    print()
    print(f"A. Total verdicts:          {total}")
    print(f"B. VP30 count:              {len(vp30)}")
    print(f"C. Metadata complete:       {len(complete)}")
    print(f"D. Missing metadata:        {len(incomplete)}")

    if incomplete:
        print(f"E. Missing race_ids:")
        for rid in incomplete:
            top = (verdict_map.get(rid) or [{}])[0]
            horse = top.get("horse", "?")
            missing = meta_map[rid].missing_fields
            print(f"   {rid}  {horse}  missing={missing}")
    else:
        print(f"E. Missing race_ids:        none")

    print(f"F. Source breakdown:")
    source_labels = {
        "supabase_races": "races table",
        "supabase_race_results": "race_results table",
        "local_standard": "racecards_standard (local)",
        "local_merged": "racecard_merged (local)",
        "local_results": "results (local)",
        "verdict_fallback": "verdict full_analysis fallback",
        "unresolved": "UNRESOLVED",
    }
    for src, label in source_labels.items():
        count = source_counts.get(src, 0)
        if count or src == "unresolved":
            print(f"   {label:<40} {count}")

    status = "PASS" if passed else "FAIL"
    print()
    print(f"G. Status: {status}")
    if not passed:
        print(f"   FAIL reason: {len(incomplete)} VP30 race(s) missing course or off_time")

    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Race metadata coverage audit")
    parser.add_argument("--date", default=str(date.today()), help="YYYY-MM-DD")
    args = parser.parse_args()
    passed = run_audit(args.date)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
