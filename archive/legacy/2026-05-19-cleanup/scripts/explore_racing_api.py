"""Explore Racing API Standard plan to identify all available fields for Plot Engine."""
import json
import requests

BASE = "https://api.theracingapi.com/v1"
AUTH = ("cHHxKCt4ePK3TpFrWNq3sax6", "D2Zlg9VcD4Sjbjcb7pMzpwwy")

def fetch(endpoint):
    resp = requests.get(f"{BASE}/{endpoint}", auth=AUTH, timeout=15)
    print(f"  [{resp.status_code}] {endpoint}")
    if resp.status_code == 200:
        return resp.json()
    return None

# 1. Get tomorrow's racecards
print("=== RACECARDS STANDARD (tomorrow) ===")
data = fetch("racecards/standard?day=2026-04-21")
if data:
    rcs = data.get("racecards", [])
    print(f"  Total races: {len(rcs)}")
    
    # Find a Pontefract race
    pon = [r for r in rcs if "Pontefract" in r.get("course", "")]
    print(f"  Pontefract races: {len(pon)}")
    
    # Show all fields for first runner with headgear
    for rc in rcs:
        for r in rc["runners"]:
            hg = r.get("headgear", "")
            if hg:
                print(f"\n  RUNNER WITH HEADGEAR: {r['horse']} ({rc['course']} {rc['off_time']})")
                print(f"    headgear: '{hg}'")
                print(f"    headgear_run: '{r.get('headgear_run', '')}'")
                print(f"    wind_surgery: '{r.get('wind_surgery', '')}'")
                print(f"    wind_surgery_run: '{r.get('wind_surgery_run', '')}'")
                print(f"    ofr: {r.get('ofr')}  rpr: {r.get('rpr')}  ts: {r.get('ts')}")
                print(f"    form: {r.get('form')}  last_run: {r.get('last_run')}")
                print(f"    medical: {r.get('medical', [])}")
                print(f"    prev_trainers: {r.get('prev_trainers', [])}")
                spotlight = r.get("spotlight", "")
                print(f"    spotlight: '{spotlight[:300]}'")
                break
        else:
            continue
        break
    
    # Count how many runners have spotlight, headgear, wind_surgery
    total_runners = 0
    with_spotlight = 0
    with_headgear = 0
    with_wind_surgery = 0
    with_medical = 0
    with_prev_trainers = 0
    with_quotes = 0
    with_stable_tour = 0
    
    for rc in rcs:
        for r in rc["runners"]:
            total_runners += 1
            if r.get("spotlight"):
                with_spotlight += 1
            if r.get("headgear"):
                with_headgear += 1
            if r.get("wind_surgery"):
                with_wind_surgery += 1
            if r.get("medical"):
                with_medical += 1
            if r.get("prev_trainers"):
                with_prev_trainers += 1
            if r.get("quotes"):
                with_quotes += 1
            if r.get("stable_tour"):
                with_stable_tour += 1
    
    print(f"\n=== FIELD COVERAGE (tomorrow's cards) ===")
    print(f"  Total runners: {total_runners}")
    print(f"  With spotlight: {with_spotlight} ({100*with_spotlight/total_runners:.0f}%)")
    print(f"  With headgear: {with_headgear} ({100*with_headgear/total_runners:.0f}%)")
    print(f"  With wind_surgery: {with_wind_surgery} ({100*with_wind_surgery/total_runners:.0f}%)")
    print(f"  With medical: {with_medical} ({100*with_medical/total_runners:.0f}%)")
    print(f"  With prev_trainers: {with_prev_trainers} ({100*with_prev_trainers/total_runners:.0f}%)")
    print(f"  With quotes: {with_quotes} ({100*with_quotes/total_runners:.0f}%)")
    print(f"  With stable_tour: {with_stable_tour} ({100*with_stable_tour/total_runners:.0f}%)")

# 2. Check horse results endpoint
print("\n=== HORSE RESULTS ===")
# Use a known horse from Pontefract if available, else use Desert Cop
horse_id = "hrs_33644464"
data = fetch(f"horses/{horse_id}/results")
if data:
    results = data if isinstance(data, list) else data.get("results", [])
    print(f"  Results for {horse_id}: {len(results)}")
    if results:
        r = results[-1]
        print(f"  Most recent result fields: {list(r.keys())}")
        for k, v in r.items():
            print(f"    {k}: {v}")

# 3. Check if there's a pro/big-race endpoint
print("\n=== CHECKING OTHER ENDPOINTS ===")
fetch("racecards/big-race")
fetch("racecards/free")
