
"""
VÉLØ Prime Operator Card
========================

Print VP30, MDS_HIGH, and Confluence suggestions for a given date 
with fully resolved race metadata.

Usage:
    python scripts/vp30_operator_card.py --date 2026-05-01
    python scripts/vp30_operator_card.py          # defaults to today

Definitions:
    1. VP30: velo_prime_prob >= 0.30
    2. MDS_HIGH: market_deception_score > 0.50
    3. CONFLUENCE: Both VP30 and MDS_HIGH are true.

Read-only. No scoring, model, router, or execution changes.
No betting or staking language.
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
MDS_THRESHOLD = 0.50


def _sb():
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )


def load_verdicts(sb, date_str: str) -> list[dict]:
    return (
        sb.table("velo_verdicts")
        .select(
            "race_id,velo_prime_prob,market_deception_score,decision_tier,"
            "assigned_product,execution_allowed,full_analysis,generated_at"
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
    mds_high = []
    confluence = []
    
    verdict_map: dict[str, list] = {}
    
    for v in verdicts:
        vp = float(v.get("velo_prime_prob") or 0)
        mds = float(v.get("market_deception_score") or 0)
        fa = v.get("full_analysis") or []
        top = fa[0] if fa else {}
        verdict_map[v["race_id"]] = fa
        
        is_vp30 = vp >= VP_THRESHOLD
        is_mds_high = mds > MDS_THRESHOLD
        
        row = {
            "race_id": v["race_id"],
            "horse": top.get("horse", "?"),
            "horse_id": top.get("horse_id", ""),
            "vp": vp,
            "mds": mds,
            "tier": v.get("decision_tier", "?"),
            "exec_allowed": v.get("execution_allowed"),
            "product": v.get("assigned_product"),
        }
        
        if is_vp30:
            vp30.append(row)
        if is_mds_high:
            mds_high.append(row)
        if is_vp30 and is_mds_high:
            confluence.append(row)

    # Resolve metadata for all unique races in our lists
    all_rows = vp30 + mds_high
    unique_race_ids = list(set(r["race_id"] for r in all_rows))
    
    resolver = RaceMetadataResolver(date=date_str, sb_client=sb)
    meta_map = resolver.resolve_batch(unique_race_ids, verdict_map)

    def hydrate(rows):
        for r in rows:
            m = meta_map.get(r["race_id"])
            r["course"] = m.course if m else ""
            r["off_time"] = m.off_time if m else ""
            r["race_name"] = m.race_name if m else ""
            r["metadata_complete"] = m.metadata_complete if m else False
        rows.sort(key=lambda x: (x["off_time"] or "99:99", -x["vp"]))

    hydrate(vp30)
    hydrate(mds_high)
    hydrate(confluence)

    print(f"VÉLØ PRIME OPERATOR CARD — {date_str}")
    print("=" * 40)
    print(f"Total races scanned: {len(verdicts)}")
    print()

    print(f"1. VP30 + MDS CONFLUENCE — LIVE CONFIDENCE STACK ({len(confluence)})")
    print("-" * 40)
    if confluence:
        for r in confluence:
            print(f"  {r['off_time'] or '?:??'} {r['course'] or '?':<12} | {r['horse']:<20} | VP={r['vp']:.3f} MDS={r['mds']:.3f} | {r['tier']}")
    else:
        print("  (None)")
    print()

    print(f"2. VP30 — LIVE SIGNAL ({len(vp30)})")
    print("-" * 40)
    if vp30:
        for r in vp30:
            print(f"  {r['off_time'] or '?:??'} {r['course'] or '?':<12} | {r['horse']:<20} | VP={r['vp']:.3f} | {r['tier']}")
    else:
        print("  (None)")
    print()

    print(f"3. MDS_HIGH — LIVE SIDECAR ({len(mds_high)})")
    print("-" * 40)
    if mds_high:
        for r in mds_high:
            print(f"  {r['off_time'] or '?:??'} {r['course'] or '?':<12} | {r['horse']:<20} | MDS={r['mds']:.3f} | {r['tier']}")
    else:
        print("  (None)")
    print()

    print("---")
    print(f"A. Source: Supabase velo_verdicts")
    print(f"B. VP Threshold: {VP_THRESHOLD:.2f}")
    print(f"C. MDS Threshold: > {MDS_THRESHOLD:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="VÉLØ Prime operator card")
    parser.add_argument("--date", default=str(date.today()), help="YYYY-MM-DD")
    args = parser.parse_args()
    build_card(args.date)


if __name__ == "__main__":
    main()
