import json
from pathlib import Path
from datetime import date
import sys

sys.path.insert(0, ".")
from new_build_velo.passport_lookup import batch_lookup

def get_coverage_for_date(date_str, parsed_path):
    if not parsed_path.exists():
        return None
    
    with open(parsed_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        races = data if isinstance(data, list) else data.get("races", [])
        
    runners = []
    race_count = len(races)
    
    for race in races:
        for runner in race.get("runners", []):
            if not runner.get("non_runner"):
                runners.append({
                    "horse_name": runner.get("horse") or runner.get("horse_name"),
                    "horse_rp_uid": runner.get("horse_id"),
                })
    
    if not runners:
        return {
            "date": date_str,
            "races": race_count,
            "runners": 0,
            "passported": 0,
            "pct": 0,
            "missing": 0
        }

    results, summary = batch_lookup(runners)
    
    # Use summary from batch_lookup
    passported = summary["passport_hits"]
    total = len(runners)
    pct = summary["coverage_pct"]
    missing = summary["passport_misses"]
    
    return {
        "date": date_str,
        "races": race_count,
        "runners": total,
        "passported": passported,
        "pct": pct,
        "missing": missing
    }

def main():
    dates = [
        ("2026-06-05", Path("data/racing_post_account_parsed/2026-06-05/racecard_injection.json")),
        ("2026-06-06", Path("data/racing_post_account_parsed/2026-06-06/racecard_injection.json")),
        ("2026-06-07", Path("data/racing_post_account_parsed/2026-06-07/racecard_injection.json")),
        ("2026-06-08", Path("data/racing_post_account_parsed/live-full-racepages-2026-06-08/racecard_injection.json")),
        ("2026-06-09", Path("data/racing_post_account_parsed/live-full-racepages-2026-06-09/racecard_injection.json")),
        ("2026-06-10", Path("data/racing_post_account_parsed/live-full-racepages-2026-06-10/racecard_injection.json")),
    ]
    
    print("┌────────────┬───────┬─────────┬────────────┬─────┬───────────────┐")
    print("│    Date    │ Races │ Runners │ Passported │  %  │ Still Missing │")
    print("├────────────┼───────┼─────────┼────────────┼─────┼───────────────┤")
    
    for date_str, path in dates:
        stats = get_coverage_for_date(date_str, path)
        if stats:
            print(f"│ {stats['date']} │ {str(stats['races']).rjust(5)} │ {str(stats['runners']).rjust(7)} │ {str(stats['passported']).rjust(10)} │ {str(stats['pct']).rjust(3)}% │ {str(stats['missing']).rjust(13)} │")
        else:
            print(f"│ {date_str} │ ERROR │ MISSING │ FILE       │ N/A │ N/A           │")
            
    print("└────────────┴───────┴─────────┴────────────┴─────┴───────────────┘")

if __name__ == "__main__":
    main()
