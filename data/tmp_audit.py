import json, pathlib

def load_all_runners(date_tag):
    snaps = sorted(pathlib.Path("data").glob("runner_snapshots_" + date_tag + "*.jsonl"))
    rows = []
    for f in snaps:
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows

r17 = load_all_runners("2026_06_17")
r18 = load_all_runners("2026_06_18")

# Extreme VP breakdown for June 18
extreme = [r for r in r18 if float(r.get("velo_prime_prob") or 0) >= 0.50]
extreme.sort(key=lambda x: float(x.get("velo_prime_prob") or 0), reverse=True)

print("=== EXTREME VP June 18 (VP>=0.50) - component breakdown ===")
for r in extreme:
    vp = float(r.get("velo_prime_prob") or 0)
    sqpe = float(r.get("sqpe_v17_prob") or 0)
    imp = float(r.get("improvement_score") or 0)
    mds = float(r.get("market_deception_score") or 0)
    place = float(r.get("place_prob") or 0)
    active = r.get("active_components", [])
    horse = r.get("horse", "?")
    course = r.get("course", "?")
    off = r.get("off_time", "?")
    tier = r.get("tier", "?")
    mark_comp = r.get("mark_compression_score")
    postdata = r.get("postdata_score")
    spotlight = float(r.get("spotlight_score") or 0)
    longshot = float(r.get("longshot_prob") or 0)
    release = float(r.get("release_day_prob") or 0)
    comment = float(r.get("comment_intel_score") or 0)
    print("  " + str(horse) + " @" + str(course) + " " + str(off) + " tier=" + str(tier))
    print("    VP=" + str(round(vp,3)) + " SQPE=" + str(round(sqpe,3)) + " MDS=" + str(round(mds,3)) + " imp=" + str(round(imp,3)) + " place=" + str(round(place,3)))
    print("    longshot=" + str(round(longshot,3)) + " release=" + str(round(release,3)) + " comment=" + str(round(comment,3)))
    print("    spotlight=" + str(spotlight) + " mark_comp=" + str(mark_comp) + " postdata=" + str(postdata))
    print("    active=" + str(active))
    print()

# Compare SQPE ranges between days
sqpe17 = [float(r.get("sqpe_v17_prob") or 0) for r in r17 if r.get("sqpe_v17_prob")]
sqpe18 = [float(r.get("sqpe_v17_prob") or 0) for r in r18 if r.get("sqpe_v17_prob")]

import statistics
print("=== SQPE v17 distribution comparison ===")
print("Jun 17: n=" + str(len(sqpe17)) + " mean=" + str(round(statistics.mean(sqpe17),3)) + " max=" + str(round(max(sqpe17),3)) + " median=" + str(round(statistics.median(sqpe17),3)))
print("Jun 18: n=" + str(len(sqpe18)) + " mean=" + str(round(statistics.mean(sqpe18),3)) + " max=" + str(round(max(sqpe18),3)) + " median=" + str(round(statistics.median(sqpe18),3)))

# Check MDS and improvement distributions
mds17 = [float(r.get("market_deception_score") or 0) for r in r17 if r.get("market_deception_score")]
mds18 = [float(r.get("market_deception_score") or 0) for r in r18 if r.get("market_deception_score")]
imp17 = [float(r.get("improvement_score") or 0) for r in r17 if r.get("improvement_score")]
imp18 = [float(r.get("improvement_score") or 0) for r in r18 if r.get("improvement_score")]
place17 = [float(r.get("place_prob") or 0) for r in r17 if r.get("place_prob")]
place18 = [float(r.get("place_prob") or 0) for r in r18 if r.get("place_prob")]

print("\n=== Component score distributions ===")
if mds17:
    print("MDS: Jun17 mean=" + str(round(statistics.mean(mds17),3)) + " max=" + str(round(max(mds17),3)) + " n_above_0.5=" + str(sum(1 for x in mds17 if x > 0.5)))
if mds18:
    print("MDS: Jun18 mean=" + str(round(statistics.mean(mds18),3)) + " max=" + str(round(max(mds18),3)) + " n_above_0.5=" + str(sum(1 for x in mds18 if x > 0.5)))
if imp17:
    print("IMP: Jun17 mean=" + str(round(statistics.mean(imp17),3)) + " max=" + str(round(max(imp17),3)) + " n_above_0.40=" + str(sum(1 for x in imp17 if x > 0.40)))
if imp18:
    print("IMP: Jun18 mean=" + str(round(statistics.mean(imp18),3)) + " max=" + str(round(max(imp18),3)) + " n_above_0.40=" + str(sum(1 for x in imp18 if x > 0.40)))
if place17:
    print("PLACE: Jun17 mean=" + str(round(statistics.mean(place17),3)) + " max=" + str(round(max(place17),3)) + " n_above_0.80=" + str(sum(1 for x in place17 if x > 0.80)))
if place18:
    print("PLACE: Jun18 mean=" + str(round(statistics.mean(place18),3)) + " max=" + str(round(max(place18),3)) + " n_above_0.80=" + str(sum(1 for x in place18 if x > 0.80)))
