"""
Fetch all 22 April 2026 results and cross-reference against plot candidates.
"""
import requests
import re
import json

API_USER = "cHHxKCt4ePK3TpFrWNq3sax6"
API_PASS = "D2Zlg9VcD4Sjbjcb7pMzpwwy"
BASE = "https://api.theracingapi.com/v1"
DATE = "2026-04-22"

def clean(name):
    return re.sub(r'\s*\([A-Z]{2,3}\)\s*$', '', name).strip().lower()

def fetch_all_results():
    all_results = {}
    for region in ["gb", "ire"]:
        skip = 0
        while True:
            url = f"{BASE}/results?region={region}&limit=100&skip={skip}"
            r = requests.get(url, auth=(API_USER, API_PASS))
            if r.status_code != 200:
                break
            data = r.json()
            races = data.get("results", [])
            if not races:
                break
            found_date = False
            for race in races:
                if race.get("date") != DATE:
                    continue
                found_date = True
                course = race.get("course", "")
                off = race.get("off", "").replace(":", ".")
                for runner in race.get("runners", []):
                    name = clean(runner.get("horse", ""))
                    pos = str(runner.get("position", ""))
                    sp = runner.get("sp", "")
                    sp_dec = runner.get("sp_dec", "")
                    all_results[name] = {
                        "course": course,
                        "off": off,
                        "position": pos,
                        "sp": sp,
                        "sp_dec": float(sp_dec) if sp_dec else 0.0
                    }
            # If none of the races match our date, stop paginating
            if not found_date and races[0].get("date", "") < DATE:
                break
            if len(races) < 100:
                break
            skip += 100
    return all_results

# Plot candidates from VERDICTS_2026-04-22.md
CANDIDATES = {
    # Taunton
    "mi sueno":         ("Taunton",   "6.30", "★★★"),
    "miss fedora":      ("Taunton",   "6.30", "★★"),
    "holeshot":         ("Taunton",   "7.00", "★"),
    # Gowran Park
    "dark side thunder":("Gowran Park","5.30","★"),
    # Ludlow
    "almazhar garde":   ("Ludlow",    "3.30", "★★★"),
    "zacony rebel":     ("Ludlow",    "3.30", "★★★"),
    "est illic":        ("Ludlow",    "5.05", "★★★"),
    "fix at all":       ("Ludlow",    "5.05", "★★★"),
    "the paddy pie":    ("Ludlow",    "5.05", "★★★"),
    # Catterick
    "barmyblade":       ("Catterick", "1.52", "★"),
    "birkenhead":       ("Catterick", "1.52", "★★★"),
    "fortunate star":   ("Catterick", "1.52", "★★★"),
    "evocative spark":  ("Catterick", "3.52", "★★★"),
    "jenni":            ("Catterick", "3.52", "★"),
    "roundhay park":    ("Catterick", "3.52", "★★★"),
    "vince le prince":  ("Catterick", "3.52", "★★"),
    "aberama gold":     ("Catterick", "4.25", "★★★"),
    "dorney lake":      ("Catterick", "4.25", "★★★"),
    "arctic fox":       ("Catterick", "5.00", "★★★"),
}

print(f"\n{'='*65}")
print(f"  VÉLØ CASH RUN RESULTS — 22 April 2026")
print(f"{'='*65}")
print("  Fetching results from Racing API...")

all_results = fetch_all_results()
print(f"  Total runners found: {len(all_results)}")
courses = sorted(set(v["course"] for v in all_results.values()))
print(f"  Courses: {', '.join(courses)}")

winners, placed, unplaced, not_found = [], [], [], []

for horse_lower, (venue, time, rating) in CANDIDATES.items():
    if horse_lower in all_results:
        res = all_results[horse_lower]
        pos = res["position"]
        sp = res["sp"]
        sp_dec = res["sp_dec"]
        entry = (horse_lower.title(), venue, time, rating, pos, sp, sp_dec)
        if pos == "1":
            winners.append(entry)
        elif pos in ["2", "3"]:
            placed.append(entry)
        else:
            unplaced.append(entry)
    else:
        not_found.append((horse_lower.title(), venue, time, rating))

total = len(winners) + len(placed) + len(unplaced)
place_rate = (len(winners) + len(placed)) / total * 100 if total else 0
strike_rate = len(winners) / total * 100 if total else 0

print(f"\n  ✅ WINNERS ({len(winners)})  —  Strike rate: {strike_rate:.1f}%")
print(f"  {'-'*61}")
for h, v, t, r, pos, sp, sp_dec in sorted(winners, key=lambda x: x[6]):
    print(f"    WON  {r:5s}  {v:15s}  {t}  {h}  @ {sp}")

print(f"\n  🔵 PLACED 2nd/3rd ({len(placed)})")
print(f"  {'-'*61}")
for h, v, t, r, pos, sp, sp_dec in sorted(placed, key=lambda x: x[6]):
    print(f"    {pos}nd/3rd  {r:5s}  {v:15s}  {t}  {h}  @ {sp}")

print(f"\n  ❌ UNPLACED ({len(unplaced)})")
print(f"  {'-'*61}")
for h, v, t, r, pos, sp, sp_dec in unplaced:
    print(f"    {pos:5s}  {r:5s}  {v:15s}  {t}  {h}")

if not_found:
    print(f"\n  ⚠️  NOT MATCHED ({len(not_found)}) — may not have run / name mismatch")
    print(f"  {'-'*61}")
    for h, v, t, r in not_found:
        print(f"    ?      {r:5s}  {v:15s}  {t}  {h}")

print(f"\n{'='*65}")
print(f"  SUMMARY — 22 April 2026")
print(f"  Candidates:     {len(CANDIDATES)}")
print(f"  Matched:        {total}")
print(f"  Winners:        {len(winners)}  ({strike_rate:.1f}%)")
print(f"  Win or Place:   {len(winners)+len(placed)}  ({place_rate:.1f}%)")
print(f"  Unplaced:       {len(unplaced)}")
print(f"{'='*65}")
