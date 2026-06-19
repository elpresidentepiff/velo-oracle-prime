import json, pathlib

rp17 = pathlib.Path("data/results/rp_results_2026_06_17.json")
d17 = json.loads(rp17.read_text())
results17 = d17.get("results", [])

# List all courses on June 17
courses = sorted(set(r.get("course","?") for r in results17))
print("Courses June 17: " + str(courses))

# List all races and winners for all courses
print("\n=== All June 17 results ===")
for race in results17:
    off = race.get("off","")
    course = race.get("course","?")
    runners = race.get("runners",[])
    winner = next((r for r in runners if str(r.get("position","")) == "1"), None)
    print(course + " " + str(off) + ": winner=" + str(winner.get("horse","?") if winner else "?") + " SP=" + str(winner.get("sp_decimal","?") if winner else "?"))
    # Check if any of our key horses appear
    for r in runners:
        h = r.get("horse","").lower()
        if any(pick in h for pick in ["galiyan","beauty box","grasmere boy","kingston narcissus","our guide"]):
            pos = r.get("position","?")
            sp = r.get("sp_decimal","?")
            print("  OUR PICK: " + r.get("horse","?") + " pos=" + str(pos) + " SP=" + str(sp))
