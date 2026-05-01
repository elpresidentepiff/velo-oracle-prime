"""
VP30 Operator Card
==================

Print VP30 suggestions for a given date with fully resolved race metadata.

Usage:
    python scripts/vp30_operator_card.py --date 2026-05-01
    python scripts/vp30_operator_card.py          # defaults to today

Output: VP30 only. No sidecars. No staking. No betting language.
Read-only. No scoring, model, router, or execution changes.
"""

from __future__ import annotations

import argparse
import os
import sys
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


def load_verdicts(sb, date_str: str) -> list[dict]:
    next_day = date_str[:8] + str(int(date_str[8:10]) + 1).zfill(2)
    # handle month rollover simply — use generated_at prefix match
    return (
        sb.table("velo_verdicts")
        .select(
            "race_id,velo_prime_prob,decision_tier,assigned_product,"
            "execution_allowed,full_analysis,generated_at"
        )
        .gte("generated_at", f"{date_str}T00:00:00")
        .lt("generated_at", f"{date_str}T23:59:59")
        .order("velo_prime_prob", desc=True)
        .execute()
        .data
    )


def build_card(date_str: str) -> None:
    sb = _sb()
    verdicts = load_verdicts(sb, date_str)

    vp30 = []
    verdict_map: dict[str, list] = {}
    for v in verdicts:
        vp = float(v.get("velo_prime_prob") or 0)
        fa = v.get("full_analysis") or []
        top = fa[0] if fa else {}
        verdict_map[v["race_id"]] = fa
        if vp >= VP_THRESHOLD:
            vp30.append({
                "race_id": v["race_id"],
                "horse": top.get("horse", "?"),
                "horse_id": top.get("horse_id", ""),
                "vp": vp,
                "tier": v.get("decision_tier", "?"),
                "exec_allowed": v.get("execution_allowed"),
                "product": v.get("assigned_product"),
            })

    race_ids = [r["race_id"] for r in vp30]
    resolver = RaceMetadataResolver(date=date_str, sb_client=sb)
    meta_map = resolver.resolve_batch(race_ids, verdict_map)

    # Attach metadata and sort by off_time asc, then vp desc
    for row in vp30:
        m = meta_map.get(row["race_id"])
        row["course"] = m.course if m else ""
        row["off_time"] = m.off_time if m else ""
        row["race_name"] = m.race_name if m else ""
        row["metadata_source"] = m.source_used if m else "unresolved"
        row["metadata_complete"] = m.metadata_complete if m else False

    vp30.sort(key=lambda r: (r["off_time"] or "99:99", -r["vp"]))

    complete = sum(1 for r in vp30 if r["metadata_complete"])
    missing_rows = [r for r in vp30 if not r["metadata_complete"]]

    print(f"VP30 SUGGESTIONS — {date_str}")
    print()
    print(f"Count: {len(vp30)}")
    print(f"Metadata coverage: {complete}/{len(vp30)}")
    print()

    for i, r in enumerate(vp30, 1):
        time_str = r["off_time"] or "?:??"
        course_str = r["course"] or "?"
        print(f"{i}. {time_str} {course_str} — {r['horse']}")
        print(f"   race_id:                    {r['race_id']}")
        print(f"   horse_id:                   {r['horse_id']}")
        print(f"   VP:                         {r['vp']:.4f}")
        print(f"   tier:                       {r['tier']}")
        print(f"   candidate_execution_allowed:{r['exec_allowed']}")
        print(f"   product:                    {r['product']}")
        print(f"   metadata_source:            {r['metadata_source']}")
        print()

    if missing_rows:
        print("── MISSING_METADATA ──────────────────────────────")
        for r in missing_rows:
            print(f"  {r['race_id']}  {r['horse']}  missing: {meta_map[r['race_id']].missing_fields}")
        print()

    print("---")
    print(f"A. Source: Supabase velo_verdicts ({date_str})")
    print(f"B. Total races scanned: {len(verdicts)}")
    print(f"C. VP30 count: {len(vp30)}")
    print(f"D. Metadata complete: {complete}/{len(vp30)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="VP30 operator card")
    parser.add_argument("--date", default=str(date.today()), help="YYYY-MM-DD")
    args = parser.parse_args()
    build_card(args.date)


if __name__ == "__main__":
    main()
