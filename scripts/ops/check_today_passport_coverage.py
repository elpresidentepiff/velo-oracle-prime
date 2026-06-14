import json
from pathlib import Path
from datetime import date
import sys

sys.path.insert(0, ".")
from new_build_velo.passport_lookup import batch_lookup

def check_today_coverage():
    target_date = "2026_05_31"
    cache_path = Path(f"data/racecards_{target_date}_standard.json")
    
    if not cache_path.exists():
        print(f"Error: Cache file not found at {cache_path}")
        return

    with open(cache_path, "r", encoding="utf-8") as f:
        races = json.load(f)
        
    all_runners = []
    for race in races:
        for runner in race.get("runners", []):
            all_runners.append({
                "horse_name": runner.get("horse"),
                "horse_rp_uid": runner.get("horse_id")
            })
            
    print(f"Total runners in today's card: {len(all_runners)}")
    
    enriched, summary = batch_lookup(all_runners, as_of_date=date(2026, 5, 31))
    
    print("\n=== Passport Coverage Report (May 31) ===")
    print(f"Total Runners:   {summary['total_runners']}")
    print(f"Passport Hits:   {summary['passport_hits']}")
    print(f"Passport Misses: {summary['passport_misses']}")
    print(f"Coverage %:      {summary['coverage_pct']}%")
    
    if summary['miss_names']:
        print(f"\nSample Misses: {', '.join(summary['miss_names'][:10])}...")

if __name__ == "__main__":
    check_today_coverage()
