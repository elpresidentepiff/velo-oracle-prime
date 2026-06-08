import json, statistics
lines = open("data/new_build/paper_predictions/new_build_predictions_2026_06_03.jsonl").readlines()
rows = [json.loads(l) for l in lines]
probs = [r["champion_probability"] for r in rows]
print(f"Runners: {len(rows)}")
print(f"Prob range: {min(probs):.3f} - {max(probs):.3f}")
print(f"Prob median: {statistics.median(probs):.3f}")
print(f"VP30+: {sum(1 for p in probs if p>=0.30)}")
print(f"VP20-30: {sum(1 for p in probs if 0.20<=p<0.30)}")
print(f"VP<20: {sum(1 for p in probs if p<0.20)}")
pp_scores = [r.get("passport_strength_score") for r in rows if r.get("passport_strength_score") is not None]
print(f"PP strength range: {min(pp_scores):.2f}-{max(pp_scores):.2f}, median: {statistics.median(pp_scores):.2f}")
print(f"No passport: {sum(1 for r in rows if not r.get('passport_found'))}")
sample = rows[0]
print("Place/rate keys:", [k for k in sample.keys() if "place" in k or "rate" in k or "velocity" in k])
