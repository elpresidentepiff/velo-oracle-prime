import json
d = json.load(open("data/results_2026_06_02.json"))
races = d["results"]
print(f"Result races: {len(races)}")
for r in races[:5]:
    runners = r.get("runners", [])
    winner = next((x for x in runners if str(x.get("position", "")) == "1"), None)
    course = r.get("course", "?")
    off = r.get("off", "?")
    wname = winner.get("horse") if winner else "?"
    print(f"  {course} {off}: winner={wname}")
