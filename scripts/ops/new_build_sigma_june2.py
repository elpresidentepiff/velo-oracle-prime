"""
Real New Build sigma for June 2, 2026.
Matches NB top-pick per race against actual results.
Also matches OV top-pick per race.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATE = "2026-06-02"

# Load NB predictions
nb_lines = (ROOT / "data/new_build/paper_predictions/new_build_predictions_2026_06_02.jsonl").read_text("utf-8").splitlines()
nb_rows = [json.loads(l) for l in nb_lines if l.strip()]

# Load OV verdicts
ov_raw = json.loads((ROOT / f"data/velo_prime_verdicts_2026_06_02.json").read_text("utf-8"))

# Load results
results_raw = json.loads((ROOT / "data/results_2026_06_02.json").read_text("utf-8"))
races_results = results_raw["results"]

def norm(s):
    return str(s or "").strip().lower().replace("'", "").replace("-", " ")

# Build result lookup: course+off -> {winner, 2nd, 3rd}
result_lookup = {}
for r in races_results:
    course = norm(r.get("course", ""))
    off = str(r.get("off", "")).strip()
    runners = r.get("runners", [])
    top3 = sorted([x for x in runners if x.get("position") in [1,2,3,"1","2","3"]],
                  key=lambda x: int(x.get("position", 99)))
    result_lookup[(course, off)] = {
        "winner": norm(top3[0]["horse"]) if len(top3) >= 1 else None,
        "2nd":    norm(top3[1]["horse"]) if len(top3) >= 2 else None,
        "3rd":    norm(top3[2]["horse"]) if len(top3) >= 3 else None,
        "course_raw": r.get("course"),
        "race_name": r.get("race_name"),
    }

# NB: top pick per race = rank=1
nb_by_race = {}
for row in nb_rows:
    rid = row.get("race_id")
    rank = int(row.get("champion_rank") or 99)
    if rid not in nb_by_race or rank < nb_by_race[rid].get("_rank", 99):
        nb_by_race[rid] = {**row, "_rank": rank}

# OV: top pick per race = top.horse from verdict
ov_by_key = {}
for v in (ov_raw if isinstance(ov_raw, list) else []):
    course = norm(v.get("course", ""))
    off = str(v.get("off_time", "")).strip()
    top = v.get("top") or {}
    ov_by_key[(course, off)] = {
        "horse": top.get("horse"),
        "vp": top.get("velo_prime_prob"),
        "tier": v.get("tier"),
        "mds": top.get("market_deception_score"),
    }

# Match NB picks
print(f"=== New Build Sigma — {DATE} ===")
print(f"NB predictions: {len(nb_rows)} runners, {len(nb_by_race)} races")
print(f"Result races:   {len(races_results)}")
print()

nb_wins = nb_frame = nb_total = 0
rows = []
for rid, pick in sorted(nb_by_race.items(), key=lambda x: str(x[1].get("off_time",""))):
    course_raw = str(pick.get("course","")).strip()
    off = str(pick.get("off_time","")).strip()
    if "T" in off:
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(off)
            h,m = dt.hour, dt.minute
            if h > 12: h -= 12
            off_key = f"{h}.{m:02d}"
        except Exception:
            off_key = off
    else:
        off_key = off

    horse_nb = norm(pick.get("horse",""))
    prob = pick.get("champion_probability", 0)

    res = result_lookup.get((norm(course_raw), off_key))
    if not res:
        continue

    nb_win = res["winner"] == horse_nb
    nb_fr = horse_nb in [res["winner"], res["2nd"], res["3rd"]]
    nb_wins += nb_win
    nb_frame += nb_fr
    nb_total += 1

    rows.append({
        "course": course_raw, "off": off_key,
        "nb_horse": pick.get("horse"), "nb_prob": round(prob,3),
        "nb_win": nb_win, "nb_frame": nb_fr,
        "actual_winner": res["winner"],
    })

    icon = "WIN" if nb_win else ("FR " if nb_fr else "   ")
    print(f"  [{icon}] {course_raw:<18} {off_key:5}  NB={pick.get('horse'):<28} p={prob:.3f}  Winner={res['winner']}")

print()
print(f"NB: {nb_wins}/{nb_total} wins ({nb_wins/nb_total:.1%} SR)  {nb_frame}/{nb_total} frame ({nb_frame/nb_total:.1%})")

# OV match
print(f"\n=== Old VELO vs same results ===")
ov_wins = ov_frame = ov_total = 0
for (c_norm, off), pick in sorted(ov_by_key.items(), key=lambda x: x[0][1]):
    res = result_lookup.get((c_norm, off))
    if not res or not pick.get("horse"):
        continue
    horse_ov = norm(pick["horse"])
    ov_win = res["winner"] == horse_ov
    ov_fr = horse_ov in [res["winner"], res["2nd"], res["3rd"]]
    ov_wins += ov_win
    ov_frame += ov_fr
    ov_total += 1
    icon = "WIN" if ov_win else ("FR " if ov_fr else "   ")
    tier = pick.get("tier","?")
    print(f"  [{icon}] Tier {tier}  {res.get('course_raw','?'):<18} {off:5}  OV={pick['horse']:<28} VP={pick.get('vp',0):.3f}  Winner={res['winner']}")

print()
print(f"OV: {ov_wins}/{ov_total} wins ({ov_wins/ov_total:.1%} SR)  {ov_frame}/{ov_total} frame ({ov_frame/ov_total:.1%})")

# Save
out = {
    "date": DATE,
    "nb_races_matched": nb_total,
    "nb_wins": nb_wins, "nb_frame": nb_frame,
    "nb_sr": round(nb_wins/nb_total, 4) if nb_total else 0,
    "nb_frame_rate": round(nb_frame/nb_total, 4) if nb_total else 0,
    "ov_races_matched": ov_total,
    "ov_wins": ov_wins, "ov_frame": ov_frame,
    "ov_sr": round(ov_wins/ov_total, 4) if ov_total else 0,
    "ov_frame_rate": round(ov_frame/ov_total, 4) if ov_total else 0,
    "source": "real_reconciliation",
    "rows": rows,
}
out_path = ROOT / "data/new_build/reports/sigma_2026_06_02.json"
out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nSaved: {out_path.name}")
