"""
MergeAgent (Foundation Layer)

Role: Merge outputs into a single RacePacket.
If alignment fails, emits a diff report, not guesses.

Output: Canonical RacePacket JSON.
"""

import json
import sys
from typing import Dict, List

def merge_data(race_index: Dict, runners: List[Dict], ratings: List[Dict], 
               spotlight: List[Dict], market: Dict) -> Dict:
    """
    Merge all parsed data into RacePacket.
    """
    # Create diff report for mismatches
    diff_report = []
    
    # Check runner-ratings alignment
    runner_names = {r["horse_name"] for r in runners}
    rating_names = {r["horse_name"] for r in ratings}
    
    missing_in_ratings = runner_names - rating_names
    missing_in_runners = rating_names - runner_names
    
    if missing_in_ratings:
        diff_report.append(f"Runners missing in ratings: {missing_in_ratings}")
    if missing_in_runners:
        diff_report.append(f"Ratings missing in runners: {missing_in_runners}")
    
    # Build RacePacket
    race_packet = {
        "venue": race_index.get("venue", "UNKNOWN"),
        "date": race_index.get("date", "UNKNOWN"),
        "races": race_index.get("races", []),
        "runners": runners,
        "ratings": ratings,
        "spotlight": spotlight,
        "market": market,
        "diff_report": diff_report
    }
    
    return race_packet

def main():
    """Entry point: reads JSON from stdin."""
    try:
        data = json.load(sys.stdin)
        
        race_index = data.get("race_index", {})
        runners = data.get("runners", [])
        ratings = data.get("ratings", [])
        spotlight = data.get("spotlight", [])
        market = data.get("market", {})
        
        race_packet = merge_data(race_index, runners, ratings, spotlight, market)
        print(json.dumps(race_packet, indent=2))
    except Exception as e:
        print(f"ERROR in MergeAgent: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
