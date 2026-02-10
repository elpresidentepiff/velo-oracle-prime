import json
import sys
from collections import Counter

def stress_test():
    print("--- STARTING STRESS TEST ---")
    try:
        with open("/home/ubuntu/velo-oracle-prime/data/wolverhampton_processed.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("FAIL: Data file not found!")
        return

    # 1. Structure Check
    if not data.get("races"):
        print("FAIL: No races found in JSON.")
        return
    
    print(f"PASS: Found {len(data['races'])} races.")

    # 2. Runner Integrity Check
    total_runners = 0
    runners_with_or = 0
    runners_with_rpr = 0
    runners_with_ts = 0
    
    for time, race in data['races'].items():
        runners = race.get("runners", [])
        total_runners += len(runners)
        
        if len(runners) == 0:
            print(f"WARNING: Race at {time} has 0 runners.")
        
        for r in runners:
            if r.get("official_rating") is not None: runners_with_or += 1
            if r.get("rpr") is not None: runners_with_rpr += 1
            if r.get("topspeed") is not None: runners_with_ts += 1

    print(f"PASS: Total Runners: {total_runners}")
    
    # 3. Enrichment Success Rate
    or_rate = (runners_with_or / total_runners) * 100 if total_runners else 0
    rpr_rate = (runners_with_rpr / total_runners) * 100 if total_runners else 0
    ts_rate = (runners_with_ts / total_runners) * 100 if total_runners else 0
    
    print(f"METRIC: OR Coverage: {or_rate:.1f}% ({runners_with_or}/{total_runners})")
    print(f"METRIC: RPR Coverage: {rpr_rate:.1f}% ({runners_with_rpr}/{total_runners})")
    print(f"METRIC: TS Coverage: {ts_rate:.1f}% ({runners_with_ts}/{total_runners})")

    if or_rate < 80:
        print("FAIL: Official Rating coverage is too low (<80%). Enrichment logic is leaky.")
    elif or_rate < 95:
        print("WARNING: Official Rating coverage is acceptable but not perfect.")
    else:
        print("PASS: Official Rating coverage is excellent.")

    # 4. Duplicate Check
    all_horses = []
    for race in data['races'].values():
        for r in race['runners']:
            all_horses.append(r['horse_name'])
            
    duplicates = [item for item, count in Counter(all_horses).items() if count > 1]
    if duplicates:
        print(f"WARNING: Duplicate horses found (might be valid if running twice? Unlikely): {duplicates}")
    else:
        print("PASS: No duplicate horses found across races.")

    print("--- STRESS TEST COMPLETE ---")

if __name__ == "__main__":
    stress_test()
