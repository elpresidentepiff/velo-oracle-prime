"""
VÉLØ Daily Plot Verdict Board
Export high-conviction plot candidates from Supabase.
"""

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.runtime_env import create_supabase_service_client, load_optional_env_file

def main():
    load_optional_env_file()
    sb = create_supabase_service_client()
    
    today = date.today().isoformat()
    
    print(f"VÉLØ PLOT VERDICT BOARD — {today}")
    print("=" * 60)
    
    # Query high-conviction runners (1, 2, or 3 stars)
    res = sb.table("rp_runner_signals") \
        .select("course_name, off_time, horse_name, signal_summary, star_rating, raw_signal_payload") \
        .eq("source_date", today) \
        .gte("star_rating", 1) \
        .order("star_rating", desc=True) \
        .execute()
    
    if not res.data:
        print("No plot candidates identified for today.")
        return

    for row in res.data:
        stars = "★" * int(row["star_rating"])
        time = row["off_time"][:5]
        horse = row["horse_name"].upper()
        venue = row["course_name"]
        summary = row["signal_summary"]
        
        print(f"| {time} | {venue:15s} | {stars:3s} | {horse:25s} |")
        print(f"  └─ {summary}")
        print("-" * 60)

if __name__ == "__main__":
    main()
