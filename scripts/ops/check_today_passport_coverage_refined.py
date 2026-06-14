import json
from pathlib import Path
from datetime import date
import sys

sys.path.insert(0, ".")
from new_build_velo.passport_lookup import batch_lookup

def check_refined_coverage():
    target_date = "2026_06_03"
    cache_path = Path(f"data/racecards_{target_date}_standard.json")
    
    if not cache_path.exists():
        # Try finding standard JSON in parsed dir
        cache_path = Path(f"data/racing_post_account_parsed/2026-06-03/racecard_injection.json")
        
    if not cache_path.exists():
        print(f"Error: Cache file not found at {cache_path}")
        return

    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        races = data if isinstance(data, list) else data.get("races", [])
        
    uk_ire_runners = []
    intl_runners = []
    
    # June 3 courses
    uk_ire_courses = ["Curragh", "Newton Abbot", "Nottingham", "Ripon", "Warwick"]
    
    for race in races:
        course = race.get("course")
        runners = [{
            "horse_name": runner.get("horse"),
            "horse_rp_uid": runner.get("horse_id"),
            "course": course
        } for runner in race.get("runners", [])]
        
        if course in uk_ire_courses:
            uk_ire_runners.extend(runners)
        else:
            intl_runners.extend(runners)
            
    print(f"Refining coverage for UK/IRE courses: {', '.join(uk_ire_courses)}")
    print(f"UK/IRE Runners: {len(uk_ire_runners)}")
    print(f"Intl Runners:   {len(intl_runners)}")
    
    _, uk_summary = batch_lookup(uk_ire_runners, as_of_date=date(2026, 5, 31))
    
    print("\n=== Refined Passport Coverage Report (May 31 - UK/IRE Only) ===")
    print(f"Total UK/IRE Runners: {uk_summary['total_runners']}")
    print(f"Passport Hits:        {uk_summary['passport_hits']}")
    print(f"Passport Misses:      {uk_summary['passport_misses']}")
    print(f"Coverage %:           {uk_summary['coverage_pct']}%")
    
    if uk_summary['miss_names']:
        print(f"\nSample Misses (UK/IRE): {', '.join(uk_summary['miss_names'][:10])}...")

if __name__ == "__main__":
    check_refined_coverage()
