#!/usr/bin/env python3
"""
P0-16 clean-checkout verification.

Proves every headline number in race_day_14_best_day_proof_2026_07_14.md
can be independently reproduced from ONLY the committed evidence bundle at
data/evidence/race_day_14_2026_07_14/ -- no read from evidence_staging/
(uncommitted, local-only) and no read from the primary repo.

Run from a fresh clone/checkout of this branch:
    PYTHONPATH=. python3 scripts/forensics/verify_evidence_bundle.py

Exits non-zero if any assertion fails.
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUNDLE = os.path.join(ROOT, "data", "evidence", "race_day_14_2026_07_14")

failures = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


# ---------------------------------------------------------------------------
# Load bundle files (verbatim copies + extracts) -- ONLY from data/evidence/
# ---------------------------------------------------------------------------
with open(os.path.join(BUNDLE, "data/sigma_results/sigma_results_2026_07_14.json")) as f:
    sigma = json.load(f)

with open(os.path.join(BUNDLE, "data/racecards_2026_07_14_race_level_extract.csv")) as f:
    racecard_rows = list(csv.DictReader(f))

with open(os.path.join(BUNDLE, "data/model_comparison_ledger_2026_07_14_slice.csv")) as f:
    ledger_slice = list(csv.DictReader(f))

with open(os.path.join(BUNDLE, "data/mission_control/2026-07-14_mission_control.json")) as f:
    mission_control = json.load(f)

with open(os.path.join(BUNDLE, "data/nightly_eod_learning_status_2026_07_14.json")) as f:
    nightly = json.load(f)

with open(os.path.join(BUNDLE, "data/router_shadow_audit_runs/router_shadow_audit_20260714_231325.csv")) as f:
    router_rows = list(csv.DictReader(f))

with open(os.path.join(BUNDLE, "data/new_build/reports/two_lane_readiness_2026_07_14.json")) as f:
    nb_readiness = json.load(f)

# ---------------------------------------------------------------------------
# Reproduce headline claims
# ---------------------------------------------------------------------------
print("=== 43-race universe, 7 courses ===")
check("43 races in racecard extract", len(racecard_rows) == 43, f"got {len(racecard_rows)}")
courses = sorted({r["course"] for r in racecard_rows})
check("7 distinct courses", len(courses) == 7, f"got {courses}")

print("\n=== Sigma: 23/42 wins, 8 frames, 11 misses ===")
check("wins == 23", sigma["wins"] == 23)
check("evaluated_count == 42", sigma["evaluated_count"] == 42)
check("frames == 8", sigma["frames"] == 8)
check("misses == 11", sigma["misses"] == 11)
check("true_non_runners == 1", sigma["true_non_runners"] == 1)
sr = round(sigma["wins"] / sigma["evaluated_count"] * 100, 1)
check("recomputed SR == 54.8%", sr == 54.8, f"got {sr}")
frame_rate = round((sigma["wins"] + sigma["frames"]) / sigma["evaluated_count"] * 100, 1)
check("recomputed frame rate == 73.8%", frame_rate == 73.8, f"got {frame_rate}")

print("\n=== race 923388 explicitly voided from Sigma ===")
sigma_race_ids = {row["race_id"] for row in sigma["rows"]}
check("923388 absent from sigma rows", "923388" not in sigma_race_ids)
check("923388 present in racecard extract (i.e. it was on the card)",
      any(r["race_id"] == "923388" for r in racecard_rows))

print("\n=== WIN_ONLY 3/6, EW_CANDIDATE 2/2 placed+won ===")
ew = sigma["ew_tracking"]
check("WIN_ONLY 6 picks, 3 wins", ew["win_only_n"] == 6 and ew["win_only_hits"] == 3)
check("EW_CANDIDATE 2 picks, 2 placed, 2 won",
      ew["ew_candidate_n"] == 2 and ew["ew_place_n"] == 2 and ew["ew_win_n"] == 2)

print("\n=== Old VELO 23/42, No-RPR 10/42 (recomputed from ledger slice) ===")
velo_wins = sum(1 for r in ledger_slice if r["velo_outcome"] == "WIN")
norpr_wins = sum(1 for r in ledger_slice if r["norpr_outcome"] == "WIN")
check("42 rows in ledger slice", len(ledger_slice) == 42, f"got {len(ledger_slice)}")
check("Old VELO wins == 23 (recomputed)", velo_wins == 23, f"got {velo_wins}")
check("No-RPR wins == 10 (recomputed)", norpr_wins == 10, f"got {norpr_wins}")
nb_no_data = all(r["nb_outcome"] == "NO_DATA" for r in ledger_slice)
champ_no_data = all(r["champion_outcome"] == "NO_DATA" for r in ledger_slice)
check("New Build NO_DATA for all 42 rows", nb_no_data)
check("Champion Intent NO_DATA for all 42 rows", champ_no_data)

print("\n=== Mission Control: RP_MERGED_CLEAN, zero flatlines/identity failures ===")
check("source_truth == RP_MERGED_CLEAN", mission_control["source_truth"] == "RP_MERGED_CLEAN")
check("flatline_count == 0", mission_control["flatline_count"] == 0)
check("identity_failure_count == 0", mission_control["identity_failure_count"] == 0)
check("council_verdict == PASS_TO_LEARNING", mission_control["council_verdict"] == "PASS_TO_LEARNING")

print("\n=== Nightly learning: 43/43 matched, 23 wins, 20 losses, idempotent ===")
check("matched_races == 43", nightly["matched_races"] == 43)
check("wins == 23", nightly["wins"] == 23)
check("losses == 20", nightly["losses"] == 20)
check("first-run applied == 43", nightly["engine_updates_applied_first_run"] == 43)
check("duplicate-run applied == 0 (idempotent)", nightly["engine_updates_applied_duplicate_run"] == 0)
check("live_sentient_state_touched == false", nightly["live_sentient_state_touched"] is False)

print("\n=== nightly's extra race vs Sigma == the 923388 non-runner case ===")
denominator_gap = nightly["matched_races"] - sigma["evaluated_count"]
check("nightly matched_races - sigma evaluated_count == 1", denominator_gap == 1)
loss_reconciliation = sigma["frames"] + sigma["misses"] + sigma["true_non_runners"]
check("sigma frames+misses+true_non_runners == nightly losses (20)",
      loss_reconciliation == nightly["losses"], f"got {loss_reconciliation}")

print("\n=== V6_GOLD_SEAM FROZEN, frame rate 62.8%, below 70% floor ===")
v6 = next(r for r in router_rows if r["label"] == "V6_GOLD_SEAM")
check("V6_GOLD_SEAM lane_state == LANE_FROZEN", v6["lane_state"] == "LANE_FROZEN")
check("V6_GOLD_SEAM freeze == True", v6["freeze"] == "True")
check("V6_GOLD_SEAM frame rate ~62.8%", abs(float(v6["fr"]) - 62.77) < 0.1, f"got {v6['fr']}")
check("V6_GOLD_SEAM n == 94", v6["n"] == "94")

print("\n=== New Build readiness (not a scorecard) ===")
check("New Build races_scored == 43", nb_readiness["races_scored"] == 43)
check("New Build runners_scored == 368", nb_readiness["runners_scored"] == 368)
check("New Build overall_status == READY (feature layer only)", nb_readiness["overall_status"] == "READY")

# ---------------------------------------------------------------------------
print(f"\n{'='*60}")
if failures:
    print(f"FAIL: {len(failures)} assertion(s) failed: {failures}")
    sys.exit(1)
else:
    print("PASS: all headline claims reproduced from the committed evidence bundle alone.")
    sys.exit(0)
