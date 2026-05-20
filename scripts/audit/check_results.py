#!/usr/bin/env python3
"""Fetch today's results and check where plot candidates finished."""
import json, requests
from pathlib import Path

API_USER = "cHHxKCt4ePK3TpFrWNq3sax6"
API_PASS = "D2Zlg9VcD4Sjbjcb7pMzpwwy"
DATE = "2026-04-21"
MERGED_DIR = Path(__file__).parent.parent.parent / "data" / "racecard_merged"

VENUES = [
    ("PON", "Pontefract"),
    ("FFO", "Ffos Las"),
    ("WOL", "Wolverhampton"),
    ("YAR", "Yarmouth"),
]

# ── 1. Load all plot candidates ───────────────────────────────────────────────
picks = {}  # horse_name_lower -> {venue, race_time, rating, verdict}
for code, name in VENUES:
    fpath = MERGED_DIR / f"racecard_{code}_{DATE}.json"
    if not fpath.exists():
        continue
    data = json.load(open(fpath))
    for race_time, race in data["races"].items():
        for h in race.get("horses", []):
            conv = h.get("plot_conviction", 0) or 0
            if conv < 0.7:
                continue
            hname = h.get("horse_name", "")
            if not hname or "wins plcs" in hname.lower():
                continue
            picks[hname.lower().strip()] = {
                "name": hname,
                "venue": name,
                "race_time": race_time,
                "conv": conv,
                "delta": h.get("or_delta_to_best_win"),
            }

print(f"Loaded {len(picks)} plot candidates\n")

# ── 2. Fetch results from Racing API ─────────────────────────────────────────
resp = requests.get(
    "https://api.theracingapi.com/v1/results",
    params={"start_date": DATE, "end_date": DATE},
    auth=(API_USER, API_PASS),
    timeout=30,
)
results_data = resp.json()
races = results_data.get("results", [])
print(f"Fetched {len(races)} races from Racing API\n")

# ── 3. Cross-reference ────────────────────────────────────────────────────────
found = []
not_found = []

for race in races:
    course = race.get("course", "").lower()
    race_time = race.get("off_time", race.get("off_dt", ""))
    race_name = race.get("race_name", "")

    for runner in race.get("runners", []):
        horse = runner.get("horse", "").lower().strip()
        pos = runner.get("position", "")
        sp = runner.get("sp", "")
        sp_dec = runner.get("sp_dec", "")

        # Strip country codes: "Kaaranah (IRE)" -> "kaaranah"
        import re as _re
        horse_clean = _re.sub(r'\s*\([A-Z]{2,3}\)\s*$', '', runner.get('horse', '')).lower().strip()
        horse = horse_clean
        if horse in picks:
            pick = picks[horse]
            found.append({
                "name": pick["name"],
                "venue": pick["venue"],
                "race_time": pick["race_time"],
                "conv": pick["conv"],
                "delta": pick["delta"],
                "pos": pos,
                "sp": sp,
                "sp_dec": sp_dec,
                "course": race.get("course", ""),
                "race_name": race_name,
            })
            del picks[horse]  # remove from remaining

# Anything left in picks was not found in results (race not run yet or name mismatch)
for k, v in picks.items():
    not_found.append(v)

# ── 4. Report ─────────────────────────────────────────────────────────────────
print("=" * 70)
print(f"VÉLØ PLOT CANDIDATE RESULTS — {DATE}")
print("=" * 70)

# Sort: winners first, then placed, then rest
def sort_key(r):
    try:
        return int(r["pos"])
    except:
        return 99

found.sort(key=sort_key)

wins = [r for r in found if r["pos"] == "1"]
places = [r for r in found if r["pos"] in ("2", "3")]
rest = [r for r in found if r["pos"] not in ("1", "2", "3")]

print(f"\n🏆 WINNERS ({len(wins)}):")
for r in wins:
    delta_str = f"{abs(int(r['delta']))}lb below" if r['delta'] and r['delta'] <= 0 else ""
    print(f"  ✅ {r['name']} ({r['venue']} {r['race_time']}) — WON @ {r['sp']} | {delta_str} | conv {r['conv']:.2f}")

print(f"\n🥈 PLACED ({len(places)}):")
for r in places:
    delta_str = f"{abs(int(r['delta']))}lb below" if r['delta'] and r['delta'] <= 0 else ""
    print(f"  📍 {r['name']} ({r['venue']} {r['race_time']}) — {r['pos']}nd/3rd @ {r['sp']} | {delta_str} | conv {r['conv']:.2f}")

print(f"\n❌ UNPLACED ({len(rest)}):")
for r in rest:
    delta_str = f"{abs(int(r['delta']))}lb below" if r['delta'] and r['delta'] <= 0 else ""
    print(f"  ✗  {r['name']} ({r['venue']} {r['race_time']}) — pos {r['pos']} @ {r['sp']} | {delta_str}")

print(f"\n⏳ NOT YET RUN / NAME MISMATCH ({len(not_found)}):")
for v in not_found:
    print(f"  ?  {v['name']} ({v['venue']} {v['race_time']})")

print(f"\n{'='*70}")
total_found = len(found)
strike = len(wins)
place_rate = len(wins) + len(places)
print(f"SUMMARY: {total_found} results found | {strike} winners | {place_rate} win/place")
if total_found > 0:
    print(f"Strike rate: {strike/total_found*100:.1f}% | Place rate: {place_rate/total_found*100:.1f}%")
