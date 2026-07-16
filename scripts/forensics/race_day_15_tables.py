#!/usr/bin/env python3
"""P0-19..P0-24 corrected tables builder. Portable (script-relative root)."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def resolve_root(cli_root):
    if cli_root:
        return Path(cli_root).resolve()
    return SCRIPT_DIR.parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=None)
    args = ap.parse_args()
    ROOT = resolve_root(args.repo_root)
    OUT = ROOT / "data" / "reports"

    recount = json.load(open(OUT / "race_day_15_frozen_recount.json"))
    s = recount["sections"]

    old_velo_strict = s["phase6_old_velo"]  # rows not embedded here (summary only); reload raw rows below
    # Re-derive rows directly from the source script's outputs by re-running the
    # same logic would duplicate work; instead we recompute rows here from evidence
    # to keep this file self-contained and avoid relying on Python-object return
    # values from a separate process.

    EV = ROOT / "evidence_staging" / "2026-07-15"
    import sys
    sys.path.insert(0, str(SCRIPT_DIR))
    import importlib.util
    spec = importlib.util.spec_from_file_location("recount_mod", SCRIPT_DIR / "race_day_15_frozen_recount.py")
    recount_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recount_mod)

    ctx = recount_mod.main()
    results_by_id = ctx["results_by_id"]
    old_velo_strict_rows = ctx["old_velo_strict_rows"]
    old_velo_full_rows = ctx["old_velo_full_rows"]
    no_rpr_strict_rows = ctx["no_rpr_strict_rows"]
    nb_rows = ctx["nb_rows"]
    ci_rows = ctx["ci_rows"]

    all_rows = []
    for r in old_velo_strict_rows:
        all_rows.append({
            "race_id": r["race_id"], "course": r["course"], "off_time": r["off_time_local"],
            "model": "OLD_VELO", "lane": "main", "predicted_horse": r["horse"], "horse_id": r["horse_id"],
            "prediction_rank": 1, "prediction_score": r["morning_probability"], "decision_tier": r["tier"],
            "product": r["morning_product"], "final_sp": r["sp_final"], "finishing_position": r["position"],
            "non_runner": r["non_runner"], "source_artifact": "runner_snapshots (morning, immutable)",
            "generated_at": r["generated_at"], "prediction_run_id": r["run_id"],
            "timing_safety": "STRICT_PRE_RACE_PROVEN", "source_row_sha256": r["source_row_sha256"],
        })
    for r in no_rpr_strict_rows:
        all_rows.append({
            "race_id": r["race_id"], "course": r["course"], "off_time": r["off_time_local"],
            "model": "NO_RPR_GENUINE", "lane": "sqpe_no_rpr_shadow", "predicted_horse": r["horse"], "horse_id": r["horse_id"],
            "prediction_rank": 1, "prediction_score": r["no_rpr_score"], "decision_tier": None,
            "product": None, "final_sp": r["sp_final"], "finishing_position": r["position"],
            "non_runner": r["non_runner"], "source_artifact": "runner_snapshots (morning, immutable) sqpe_no_rpr_shadow_prob field",
            "generated_at": r["generated_at"], "prediction_run_id": r["run_id"],
            "timing_safety": "STRICT_PRE_RACE_PROVEN", "source_row_sha256": r["source_row_sha256"],
        })
    for r in nb_rows:
        if r["timing_status"] != "AFTERNOON_PRE_RACE_PROVEN":
            continue
        all_rows.append({
            "race_id": r["race_id"], "course": r["course"], "off_time": r["off_time_local"],
            "model": "NEW_BUILD", "lane": "lane_a", "predicted_horse": r["horse"], "horse_id": None,
            "prediction_rank": 1, "prediction_score": r["score"], "decision_tier": r["lane_decision"],
            "product": r["top_pick_lane_policy"], "final_sp": r["sp_final"], "finishing_position": r["position"],
            "non_runner": r["non_runner"], "source_artifact": "two_lane_readiness_2026_07_15.json (single mutable file)",
            "generated_at": r["generated_at"], "prediction_run_id": "NO_RUN_SCOPED_ID_AVAILABLE",
            "timing_safety": "AFTERNOON_PRE_RACE_PROVEN", "source_row_sha256": None,
        })
    for r in ci_rows:
        if r["timing_status"] != "AFTERNOON_PRE_RACE_PROVEN":
            continue
        all_rows.append({
            "race_id": r["race_id"], "course": r["course"], "off_time": r["off_time_local"],
            "model": "CHAMPION_INTENT_SHADOW", "lane": "shadow", "predicted_horse": r["horse"], "horse_id": None,
            "prediction_rank": 1, "prediction_score": r["score"], "decision_tier": None,
            "product": "SHADOW_ONLY_velo_scoring_allowed_False", "final_sp": r["sp_final"], "finishing_position": r["position"],
            "non_runner": r["non_runner"], "source_artifact": "intent_shadow_scorecard_2026_07_15.csv (single mutable file)",
            "generated_at": r["generated_at"], "prediction_run_id": "NO_RUN_SCOPED_ID_AVAILABLE",
            "timing_safety": "AFTERNOON_PRE_RACE_PROVEN", "source_row_sha256": None,
        })

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

    with open(OUT / "race_day_15_non_runners_exclusions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sorted(all_rows, key=lambda x: (x["model"], str(x["off_time"]))):
            if r["non_runner"]:
                w.writerow(r)

    # timing-excluded races (post-race generated / timing-unproven) -- explicit exclusions table
    excl_rows = []
    for r in old_velo_full_rows:
        if r["race_id"] not in {x["race_id"] for x in old_velo_strict_rows}:
            excl_rows.append({"model": "OLD_VELO", "race_id": r["race_id"], "course": r["course"],
                               "off_time": r["off_time_local"], "reason": "POST_RACE_OR_TIMING_UNRESOLVED_RELATIVE_TO_08_46_SNAPSHOT"})
    for r in nb_rows:
        if r["timing_status"] != "AFTERNOON_PRE_RACE_PROVEN":
            excl_rows.append({"model": "NEW_BUILD", "race_id": r["race_id"], "course": r["course"],
                               "off_time": r["off_time_local"], "reason": r["timing_status"]})
    for r in ci_rows:
        if r["timing_status"] != "AFTERNOON_PRE_RACE_PROVEN":
            excl_rows.append({"model": "CHAMPION_INTENT_SHADOW", "race_id": r["race_id"], "course": r["course"],
                               "off_time": r["off_time_local"], "reason": r["timing_status"]})
    with open(OUT / "race_day_15_timing_excluded_races.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["model", "race_id", "course", "off_time", "reason"])
        w.writeheader()
        w.writerows(excl_rows)

    print("winners:", sum(1 for r in all_rows if r["finishing_position"] == "1" and not r["non_runner"]))
    for m in ("OLD_VELO", "NO_RPR_GENUINE", "NEW_BUILD", "CHAMPION_INTENT_SHADOW"):
        wins = sum(1 for r in all_rows if r["model"] == m and r["finishing_position"] == "1" and not r["non_runner"])
        total = sum(1 for r in all_rows if r["model"] == m and not r["non_runner"])
        print(m, "wins:", wins, "/", total)

    # ---------- Convergence matrix (strict/proven populations only) ----------
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
            "no_rpr_selected": picks.get("NO_RPR_GENUINE") == winner,
            "new_build_selected": picks.get("NEW_BUILD") == winner,
            "champion_intent_selected": picks.get("CHAMPION_INTENT_SHADOW") == winner,
            "old_velo_timing_status": "STRICT_PRE_RACE_PROVEN" if "OLD_VELO" in picks else "EXCLUDED_POST_RACE_OR_UNPROVEN",
            "no_rpr_timing_status": "STRICT_PRE_RACE_PROVEN" if "NO_RPR_GENUINE" in picks else "EXCLUDED_POST_RACE_TIE_OR_UNPROVEN",
            "new_build_timing_status": "AFTERNOON_PRE_RACE_PROVEN" if "NEW_BUILD" in picks else "EXCLUDED_POST_RACE_OR_UNPROVEN",
            "champion_intent_timing_status": "AFTERNOON_PRE_RACE_PROVEN" if "CHAMPION_INTENT_SHADOW" in picks else "EXCLUDED_POST_RACE_OR_UNPROVEN",
        }
        runners = res.get("runners", [])
        priced = [r2 for r2 in runners if isinstance(r2.get("sp_dec"), (int, float))]
        if priced:
            fav = min(priced, key=lambda r2: r2["sp_dec"])
            row["favourite_won"] = (fav.get("horse") == winner)
            row["favourite_horse"] = fav.get("horse")
            row["favourite_sp"] = fav.get("sp_dec")
        conv_rows.append(row)

    with open(OUT / "race_day_15_winner_convergence_matrix.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(conv_rows[0].keys()))
        w.writeheader()
        w.writerows(conv_rows)

    found_all_four = [r for r in conv_rows if r["old_velo_selected"] and r["no_rpr_selected"] and r["new_build_selected"] and r["champion_intent_selected"]]
    print("found by all four (within their respective timing-proven populations):", len(found_all_four))

    # ---------- Specialist winners (from immutable morning snapshot, timing-safe subset) ----------
    strict_ids = {r["race_id"] for r in old_velo_strict_rows}
    specialist_rows = []
    SPECIALIST_FIELDS = {
        "place_prob": ("PLACE_MODEL", "calibrated_model"),
        "longshot_prob": ("LONGSHOT_MODEL", "calibrated_model"),
        "improvement_score": ("IMPROVEMENT_MODEL", "specialist_score"),
        "market_deception_score": ("MARKET_DECEPTION_MODEL", "specialist_score"),
        "rpdc_release_score": ("RPDC_LEADER", "heuristic"),
    }
    for rid, rows in ctx["morning_by_race"].items():
        if rid not in strict_ids:
            continue
        res = results_by_id.get(rid)
        if not res:
            continue
        winner = res.get("winner_horse")
        for field, (label, kind) in SPECIALIST_FIELDS.items():
            candidates = [r for r in rows if r.get(field) is not None]
            if not candidates:
                continue
            top = sorted(candidates, key=lambda x: -(x.get(field) or 0))[0]
            horse_name = top.get("horse") or top.get("top_pick_name")
            pos, sp, nr, match_method = ctx["result_lookup_by_horse_id"](rid, top.get("horse_id"), horse_name)
            specialist_rows.append({
                "race_id": rid, "course": res["course"], "off_time": res["off"],
                "specialist": label, "signal_type": kind, "predicted_horse": horse_name,
                "horse_id": top.get("horse_id"), "score": top.get(field), "actual_winner": winner,
                "hit": horse_name == winner, "final_sp": sp,
                "timing_safety": "STRICT_PRE_RACE_PROVEN",
                "source_artifact": "runner_snapshots (morning, immutable)",
            })

    with open(OUT / "race_day_15_specialist_winners.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(specialist_rows[0].keys()))
        w.writeheader()
        w.writerows(specialist_rows)

    print("Done writing v2 tables.")
    return all_rows, conv_rows


if __name__ == "__main__":
    main()
