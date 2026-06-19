import json, pathlib

# Cross-reference June 17 top VP picks with actual results
rp17 = pathlib.Path("data/results/rp_results_2026_06_17.json")
d17 = json.loads(rp17.read_text())
results17 = d17.get("results", [])

# Our June 17 top VP picks
targets = [
    ("galiyan", "ascot", "15:05"),
    ("beauty box", "ripon", "17:57"),
    ("grasmere boy", "ripon", "18:30"),
    ("kingston narcissus", "worcester", "13:35"),
    ("our guide", "worcester", "15:50"),
    ("samba fever", "worcester", None),  # extra picks below 0.30
    ("first class", "hamilton", None),
]

print("=== June 17 top picks vs actual results ===")
hits = []
for race in results17:
    course = race.get("course", "").lower()
    off = str(race.get("off", ""))
    runners = race.get("runners", [])
    winner = next((r for r in runners if str(r.get("position", "")) == "1"), None)

    for horse_name, exp_course, exp_time in targets:
        if exp_course.lower() in course:
            if exp_time is None or exp_time in off:
                our_horse = next((r for r in runners if horse_name in r.get("horse", "").lower()), None)
                if our_horse:
                    pos = our_horse.get("position", "?")
                    sp = our_horse.get("sp_decimal", our_horse.get("sp", "?"))
                    horse = our_horse.get("horse", "?")
                    won = str(pos) == "1"
                    placed = str(pos) in ["1", "2", "3"]
                    hits.append({
                        "horse": horse, "course": course, "off": off,
                        "pos": pos, "sp": sp, "won": won, "placed": placed,
                        "winner": winner.get("horse", "?") if winner else "?"
                    })
                    print("  " + horse + " @" + course + " " + off)
                    print("    position=" + str(pos) + " SP=" + str(sp))
                    if not won:
                        print("    LOST to: " + str(winner.get("horse","?") if winner else "?") + " SP=" + str(winner.get("sp_decimal","?") if winner else "?"))
                    else:
                        print("    WON!")

# Summary
wins = sum(1 for h in hits if h["won"])
places = sum(1 for h in hits if h["placed"])
print("\nSummary: " + str(wins) + "/" + str(len(hits)) + " won, " + str(places) + "/" + str(len(hits)) + " placed")

# Now show all results for Ascot June 17 to find how Galiyan did
print("\n=== Ascot June 17 results ===")
for race in results17:
    if "ascot" in race.get("course","").lower():
        off = race.get("off","")
        runners = race.get("runners", [])
        winner = next((r for r in runners if str(r.get("position","")) == "1"), None)
        second = next((r for r in runners if str(r.get("position","")) == "2"), None)
        print("  " + str(off) + ": winner=" + str(winner.get("horse","?") if winner else "?") +
              " SP=" + str(winner.get("sp_decimal","?") if winner else "?") +
              " | 2nd=" + str(second.get("horse","?") if second else "?"))
        # Check if Galiyan is in the runners
        for r in runners:
            if "galiyan" in r.get("horse","").lower():
                print("    Galiyan: pos=" + str(r.get("position","?")) + " SP=" + str(r.get("sp_decimal","?")))
