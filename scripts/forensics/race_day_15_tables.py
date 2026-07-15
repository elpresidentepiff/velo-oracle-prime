#!/usr/bin/env python3
"""Builds the winners/placed/misses/specialist/convergence tables required by
RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01."""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("/mnt/c/Users/puror/velo-race-day-15-proof")
EV = ROOT / "evidence_staging" / "2026-07-15"
OUT = ROOT / "data" / "reports"

MORNING_SNAPSHOT = EV / "data/runner_snapshots_2026_07_15_2026_07_15_aef63056_1784105122721.jsonl"
AFTERNOON_SNAPSHOT = EV / "data/runner_snapshots_2026_07_15_2026_07_15_aef63056_1784124491047.jsonl"
RESULTS = EV / "data/results/rp_results_2026_07_15.json"
NO_RPR = EV / "data/reports/radical_shadow_2026_07_15.json"
NEW_BUILD = EV / "data/new_build/reports/two_lane_readiness_2026_07_15.json"
CHAMPION_CSV = EV / "data/reports/intent_shadow_scorecard_2026_07_15.csv"


def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


morning_rows = load_jsonl(MORNING_SNAPSHOT)
results_doc = json.load(open(RESULTS))
results_by_id = {r["race_id"]: r for r in results_doc["results"]}
no_rpr_doc = json.load(open(NO_RPR))
new_build_doc = json.load(open(NEW_BUILD))
champ_rows = list(csv.DictReader(open(CHAMPION_CSV)))

morning_by_race = defaultdict(list)
for r in morning_rows:
    morning_by_race[r["race_id"]].append(r)


def top_pick(rows):
    return sorted(rows, key=lambda x: (x.get("rank") if x.get("rank") is not None else 999))[0]


def result_lookup(rid, horse):
    res = results_by_id.get(rid)
    if not res:
        return None, None, None
    for rr in res.get("runners", []):
        if rr.get("horse") == horse:
            return rr.get("position"), rr.get("sp_dec"), rr.get("non_runner", False)
    return None, None, False


def morning_sp(rid, horse):
    for row in morning_by_race.get(rid, []):
        if row.get("horse") == horse or row.get("top_pick_name") == horse:
            return row.get("sp_dec")
    return None


# ---------- OLD VELO (morning, timing-proven) ----------
old_velo_rows = []
for rid, rows in sorted(morning_by_race.items(), key=lambda kv: (results_by_id.get(kv[0], {}).get("race_time_raw", "") or "")):
    res = results_by_id.get(rid)
    if not res:
        continue
    pick = top_pick(rows)
    horse = pick.get("top_pick_name")
    pos, final_sp, nr = result_lookup(rid, horse)
    old_velo_rows.append({
        "race_id": rid, "course": res["course"], "off_time": res["off"], "model": "OLD_VELO",
        "lane": "main", "predicted_horse": horse, "prediction_rank": 1,
        "prediction_score": pick.get("velo_prime_prob"), "decision_tier": pick.get("decision_tier"),
        "product": pick.get("assigned_product"), "morning_price": morning_sp(rid, horse),
        "final_sp": final_sp, "bsp": None, "finishing_position": pos, "non_runner": nr,
        "source_artifact": str(MORNING_SNAPSHOT.relative_to(ROOT)),
        "generated_at": pick.get("created_at"), "prediction_run_id": pick.get("run_id"),
        "timing_safety": "MORNING_RUN_PROVEN",
    })

# ---------- NO-RPR (single mutable file, afternoon window) ----------
no_rpr_rows = []
for d in no_rpr_doc["decisions"]:
    rid = d["race_id"]
    res = results_by_id.get(rid)
    if not res:
        continue
    horse = d.get("horse")
    pos, final_sp, nr = result_lookup(rid, horse)
    no_rpr_rows.append({
        "race_id": rid, "course": res["course"], "off_time": res["off"], "model": "NO_RPR_SHADOW",
        "lane": "sqpe_no_rpr_shadow", "predicted_horse": horse, "prediction_rank": 1,
        "prediction_score": d.get("velo_prime_prob"), "decision_tier": d.get("tier"),
        "product": d.get("radical", {}).get("action"), "morning_price": None,
        "final_sp": final_sp, "bsp": None, "finishing_position": pos, "non_runner": nr,
        "source_artifact": str(NO_RPR.relative_to(ROOT)),
        "generated_at": no_rpr_doc["generated_at"], "prediction_run_id": "NO_RUN_SCOPED_ID_AVAILABLE",
        "timing_safety": "MORNING_RUN_UNPROVEN",
    })

# ---------- NEW BUILD (single mutable file, afternoon window) ----------
nb_rows = []
for card in (new_build_doc.get("race_day_scorecards") or []):
    rid = card.get("race_id")
    res = results_by_id.get(rid)
    if not res:
        continue
    lane_a = card.get("lane_a_top3") or []
    top = lane_a[0] if lane_a else None
    horse = top.get("horse") if top else None
    pos, final_sp, nr = result_lookup(rid, horse) if horse else (None, None, None)
    nb_rows.append({
        "race_id": rid, "course": res["course"], "off_time": res["off"], "model": "NEW_BUILD",
        "lane": "lane_a", "predicted_horse": horse, "prediction_rank": 1,
        "prediction_score": top.get("prob") if top else None,
        "decision_tier": top.get("nb_decision_lane") if top else card.get("top_pick_lane"),
        "product": card.get("top_pick_lane"), "morning_price": None,
        "final_sp": final_sp, "bsp": None, "finishing_position": pos, "non_runner": nr,
        "source_artifact": str(NEW_BUILD.relative_to(ROOT)),
        "generated_at": new_build_doc["generated_at"], "prediction_run_id": "NO_RUN_SCOPED_ID_AVAILABLE",
        "timing_safety": "MORNING_RUN_UNPROVEN",
    })

# ---------- CHAMPION INTENT (single mutable CSV, afternoon window) ----------
champ_by_race = defaultdict(list)
for r in champ_rows:
    champ_by_race[r["race_id"]].append(r)

champ_out_rows = []
for rid, rows in champ_by_race.items():
    res = results_by_id.get(rid)
    if not res:
        continue
    top = sorted(rows, key=lambda x: int(x.get("rank_in_race", 999)))[0]
    horse = top.get("horse")
    pos, final_sp, nr = result_lookup(rid, horse)
    champ_out_rows.append({
        "race_id": rid, "course": res["course"], "off_time": res["off"], "model": "CHAMPION_INTENT_SHADOW",
        "lane": "shadow", "predicted_horse": horse, "prediction_rank": 1,
        "prediction_score": top.get("champion_intent_shadow_prob"), "decision_tier": None,
        "product": "SHADOW_ONLY_NOT_SCORING", "morning_price": None,
        "final_sp": final_sp, "bsp": None, "finishing_position": pos, "non_runner": nr,
        "source_artifact": str(CHAMPION_CSV.relative_to(ROOT)),
        "generated_at": None, "prediction_run_id": "NO_RUN_SCOPED_ID_AVAILABLE",
        "timing_safety": "MORNING_RUN_UNPROVEN",
    })

all_rows = old_velo_rows + no_rpr_rows + nb_rows + champ_out_rows
fields = list(all_rows[0].keys())

with open(OUT / "race_day_15_four_model_winners.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in sorted(all_rows, key=lambda x: (x["model"], str(x["off_time"]))):
        if r["finishing_position"] == "1" and not r["non_runner"]:
            w.writerow(r)

with open(OUT / "race_day_15_four_model_placed_only.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in sorted(all_rows, key=lambda x: (x["model"], str(x["off_time"]))):
        if r["finishing_position"] in ("2", "3") and not r["non_runner"]:
            w.writerow(r)

with open(OUT / "race_day_15_four_model_misses.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in sorted(all_rows, key=lambda x: (x["model"], str(x["off_time"]))):
        if r["finishing_position"] not in ("1", "2", "3") and not r["non_runner"]:
            w.writerow(r)

# non-runners / exclusions
with open(OUT / "race_day_15_non_runners_exclusions.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in sorted(all_rows, key=lambda x: (x["model"], str(x["off_time"]))):
        if r["non_runner"]:
            w.writerow(r)

print("winners:", sum(1 for r in all_rows if r["finishing_position"] == "1" and not r["non_runner"]))
for m in ("OLD_VELO", "NO_RPR_SHADOW", "NEW_BUILD", "CHAMPION_INTENT_SHADOW"):
    wins = sum(1 for r in all_rows if r["model"] == m and r["finishing_position"] == "1" and not r["non_runner"])
    total = sum(1 for r in all_rows if r["model"] == m and not r["non_runner"])
    print(m, "wins:", wins, "/", total)

# ---------- Convergence matrix ----------
model_pick_by_race = defaultdict(dict)
for r in all_rows:
    model_pick_by_race[r["race_id"]][r["model"]] = r["predicted_horse"]

conv_rows = []
for rid, res in sorted(results_by_id.items(), key=lambda kv: kv[1]["race_time_raw"]):
    winner = res.get("winner_horse")
    picks = model_pick_by_race.get(rid, {})
    row = {
        "race_id": rid, "course": res["course"], "off_time": res["off"], "winner": winner,
        "old_velo_selected": picks.get("OLD_VELO") == winner,
        "no_rpr_selected": picks.get("NO_RPR_SHADOW") == winner,
        "new_build_selected": picks.get("NEW_BUILD") == winner,
        "champion_intent_selected": picks.get("CHAMPION_INTENT_SHADOW") == winner,
        "favourite_won": None,
    }
    # market favourite = lowest final SP among runners
    runners = res.get("runners", [])
    if runners:
        priced = [r2 for r2 in runners if isinstance(r2.get("sp_dec"), (int, float))]
        if priced:
            fav = min(priced, key=lambda r2: r2["sp_dec"])
            row["favourite_won"] = (fav.get("horse") == winner)
            row["favourite_horse"] = fav.get("horse")
            row["favourite_sp"] = fav.get("sp_dec")
    conv_rows.append(row)

with open(OUT / "race_day_15_winner_convergence_matrix.csv", "w", newline="") as f:
    fieldnames = list(conv_rows[0].keys())
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(conv_rows)

found_all_four = [r for r in conv_rows if r["old_velo_selected"] and r["no_rpr_selected"] and r["new_build_selected"] and r["champion_intent_selected"]]
unique_old_velo = [r for r in conv_rows if r["old_velo_selected"] and not (r["no_rpr_selected"] or r["new_build_selected"] or r["champion_intent_selected"])]
found_by_none = [r for r in conv_rows if not (r["old_velo_selected"] or r["no_rpr_selected"] or r["new_build_selected"] or r["champion_intent_selected"])]
print("found by all four:", len(found_all_four))
print("unique to old velo:", len(unique_old_velo))
print("found by none:", len(found_by_none))

# ---------- Specialist winners ----------
specialist_rows = []
SPECIALIST_FIELDS = {
    "place_prob": ("PLACE_MODEL", "calibrated_model"),
    "longshot_prob": ("LONGSHOT_MODEL", "calibrated_model"),
    "improvement_score": ("IMPROVEMENT_MODEL", "specialist_score"),
    "market_deception_score": ("MARKET_DECEPTION_MODEL", "specialist_score"),
    "rpdc_release_score": ("RPDC_LEADER", "heuristic"),
}
for rid, rows in morning_by_race.items():
    res = results_by_id.get(rid)
    if not res:
        continue
    winner = res.get("winner_horse")
    for field, (label, kind) in SPECIALIST_FIELDS.items():
        candidates = [r for r in rows if r.get(field) is not None]
        if not candidates:
            continue
        top = sorted(candidates, key=lambda x: -(x.get(field) or 0))[0]
        pos, final_sp, nr = result_lookup(rid, top.get("horse") or top.get("top_pick_name"))
        specialist_rows.append({
            "race_id": rid, "course": res["course"], "off_time": res["off"],
            "specialist": label, "signal_type": kind, "predicted_horse": top.get("horse") or top.get("top_pick_name"),
            "score": top.get(field), "actual_winner": winner,
            "hit": (top.get("horse") or top.get("top_pick_name")) == winner,
            "final_sp": final_sp, "source_artifact": str(MORNING_SNAPSHOT.relative_to(ROOT)),
        })

with open(OUT / "race_day_15_specialist_winners.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(specialist_rows[0].keys()))
    w.writeheader()
    w.writerows(specialist_rows)

print("Done writing tables.")
