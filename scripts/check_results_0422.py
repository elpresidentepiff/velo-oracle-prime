"""
VÉLØ Results Checker — 22 April 2026
"""
import requests
import re

API_USER = "cHHxKCt4ePK3TpFrWNq3sax6"
API_PASS = "D2Zlg9VcD4Sjbjcb7pMzpwwy"
BASE = "https://api.theracingapi.com/v1"

# All plot candidates from VERDICTS_2026-04-22.md
CANDIDATES = {
    "mi sueno":       ("Taunton",   "6.30", "★★★"),
    "miss fedora":    ("Taunton",   "6.30", "★★"),
    "holeshot":       ("Taunton",   "7.00", "★"),
    "almazhar garde": ("Ludlow",    "3.30", "★★★"),
    "zacony rebel":   ("Ludlow",    "3.30", "★★★"),
    "est illic":      ("Ludlow",    "5.05", "★★★"),
    "fix at all":     ("Ludlow",    "5.05", "★★★"),
    "the paddy pie":  ("Ludlow",    "5.05", "★★★"),
    "barmyblade":     ("Catterick", "1.52", "★"),
    "birkenhead":     ("Catterick", "1.52", "★★★"),
    "fortunate star": ("Catterick", "1.52", "★★★"),
    "evocative spark":("Catterick", "3.52", "★★★"),
    "jenni":          ("Catterick", "3.52", "★"),
    "roundhay park":  ("Catterick", "3.52", "★★★"),
    "vince le prince":("Catterick", "3.52", "★★"),
    "aberama gold":   ("Catterick", "4.25", "★★★"),
    "dorney lake":    ("Catterick", "4.25", "★★★"),
    "arctic fox":     ("Catterick", "5.00", "★★★"),
}

def clean_name(n):
    return re.sub(r'\s*\([A-Z]{2,3}\)\s*$', '', n).strip().lower()

# Fetch results for each venue
all_results = {}
for region, limit in [("gb", 200), ("ire", 200)]:
    url = f"{BASE}/results?region={region}&limit={limit}"
    r = requests.get(url, auth=(API_USER, API_PASS))
    if r.status_code != 200:
        continue
    races = r.json().get("results", [])
    for race in races:
        if race.get("date") != "2026-04-22":
            continue
        course = race.get("course", "").lower()
        off = race.get("off", "").replace(":", ".")
        for runner in race.get("runners", []):
            name = clean_name(runner.get("horse", ""))
            pos = str(runner.get("position", ""))
            sp = runner.get("sp", "")
            all_results[name] = {
                "course": race.get("course", ""),
                "off": off,
                "position": pos,
                "sp": sp,
            }

# Cross-reference
winners, placed, unplaced, not_found = [], [], [], []

for horse_lower, (venue, time, rating) in CANDIDATES.items():
    if horse_lower in all_results:
        res = all_results[horse_lower]
        pos = res["position"]
        sp = res["sp"]
        entry = (horse_lower.title(), venue, time, rating, pos, sp)
        if pos == "1":
            winners.append(entry)
        elif pos in ["2", "3"]:
            placed.append(entry)
        else:
            unplaced.append(entry)
    else:
        not_found.append((horse_lower.title(), venue, time, rating))

total_found = len(winners) + len(placed) + len(unplaced)
place_rate = (len(winners) + len(placed)) / total_found * 100 if total_found else 0

print(f"\n{'='*62}")
print(f"  VÉLØ CASH RUN RESULTS — 22 April 2026")
print(f"{'='*62}")
print(f"  Candidates: {len(CANDIDATES)}  |  Matched: {total_found}  |  Not found: {len(not_found)}")
print()

print(f"  ✅ WINNERS ({len(winners)})  —  Strike rate: {len(winners)/total_found*100:.1f}% of matched")
print(f"  {'-'*58}")
for h, v, t, r, pos, sp in winners:
    print(f"    WON  {r:5s}  {v:12s}  {t}  {h}  @ {sp}")

print()
print(f"  🔵 PLACED 2nd/3rd ({len(placed)})")
print(f"  {'-'*58}")
for h, v, t, r, pos, sp in placed:
    print(f"    {pos}rd   {r:5s}  {v:12s}  {t}  {h}  @ {sp}")

print()
print(f"  ❌ UNPLACED ({len(unplaced)})")
print(f"  {'-'*58}")
for h, v, t, r, pos, sp in unplaced:
    print(f"    {pos:4s}  {r:5s}  {v:12s}  {t}  {h}")

if not_found:
    print()
    print(f"  ⚠️  NOT MATCHED ({len(not_found)}) — may not have run")
    print(f"  {'-'*58}")
    for h, v, t, r in not_found:
        print(f"    ?     {r:5s}  {v:12s}  {t}  {h}")

print()
print(f"{'='*62}")
print(f"  SUMMARY")
print(f"  Winners:        {len(winners):3d}  ({len(winners)/total_found*100:.1f}%)" if total_found else "  No results matched")
print(f"  Win or Place:   {len(winners)+len(placed):3d}  ({place_rate:.1f}%)" if total_found else "")
print(f"  Unplaced:       {len(unplaced):3d}  ({len(unplaced)/total_found*100:.1f}%)" if total_found else "")
print(f"{'='*62}")
