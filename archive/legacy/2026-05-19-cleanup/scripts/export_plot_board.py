"""
VÉLØ Daily Plot Verdict Board
Export high-conviction plot candidates from Supabase.
"""

import os
import sys
import argparse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.runtime_env import resolve_supabase_url, resolve_supabase_service_key, load_optional_env_file
from supabase import create_client

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    load_optional_env_file(ROOT / ".env")
    url = resolve_supabase_url()
    key = resolve_supabase_service_key()
    if not url or not key:
        print("Error: Supabase credentials not found.")
        return
        
    sb = create_client(url, key)
    
    target_date = args.date
    today_tag = target_date.replace("-", "")
    
    print(f"VÉLØ PLOT VERDICT BOARD — {target_date}")
    print("=" * 60)
    
    # Query all candidates and filter/extract in python due to schema constraints
    res = sb.table("rp_runner_signals") \
        .select("race_key, horse_name, signal_summary, raw_signal_payload") \
        .like("race_key", f"%{target_date}%") \
        .execute()
    
    if not res.data:
        # Try compact date format if ISO like fails
        res = sb.table("rp_runner_signals") \
            .select("race_key, horse_name, signal_summary, raw_signal_payload") \
            .like("race_key", f"%{today_tag}%") \
            .execute()

    rows = []
    for r in res.data:
        payload = r.get("raw_signal_payload") or {}
        conv = payload.get("conviction_analysis") or {}
        stars = conv.get("plot_stars", 0)
        
        if stars >= 1:
            rows.append({
                "race_key": r["race_key"],
                "horse_name": r["horse_name"],
                "signal_summary": r["signal_summary"],
                "star_rating": stars,
                "plot_score": conv.get("plot_conviction_score", 0.0)
            })

    if not rows:
        print("No plot candidates identified for this date.")
        return

    rows.sort(key=lambda x: (-x["star_rating"], -x["plot_score"]))

    for row in rows:
        stars = "★" * int(row["star_rating"])
        horse = row["horse_name"].upper()
        summary = row["signal_summary"]
        
        print(f"| {stars:3s} | {horse:25s} | {row['race_key']} |")
        print(f"  └─ {summary}")
        print("-" * 60)

if __name__ == "__main__":
    main()
