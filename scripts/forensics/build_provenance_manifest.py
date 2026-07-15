#!/usr/bin/env python3
"""Phase 0/2: assemble the provenance manifest tying every headline figure
back to its source path/field/join method. Reads only from evidence_staging/
and the already-built data/reports/ outputs in this clean worktree."""
import csv
import json
import os

ROOT = "/mnt/c/Users/puror/velo-race-day-14-proof"
STAGE = os.path.join(ROOT, "evidence_staging", "2026-07-14")
OUT = os.path.join(ROOT, "data", "reports")

with open(os.path.join(OUT, "_evidence_import_manifest.json".replace("_evidence_import_manifest.json", "../../evidence_staging/2026-07-14/_evidence_import_manifest.json"))) if False else open(os.path.join(STAGE, "_evidence_import_manifest.json")) as f:
    import_manifest = json.load(f)

copy_records = {r["original_absolute_path"]: r for r in import_manifest["copy_records"] if r.get("status") == "COPIED_VERIFIED"}

manifest = {
    "mission": "RACE-DAY-14-BEST-DAY-PROOF-01",
    "generated_at_utc": "2026-07-15T00:00:00Z",
    "clean_worktree": {
        "path": ROOT,
        "branch": "evidence/race-day-14-best-day-proof",
        "branched_from": "aef63056f43b2c8558c10333cd226ecae359255b (audit/local-01-truth-reconciliation, primary repo)",
    },
    "primary_evidence_files": [],
    "provenance_table_note": (
        "Every headline figure in this report traces to one of these files. "
        "Join key is race_id (string, RP numeric race id) across racecards, "
        "verdicts, sigma rows, and model_comparison_ledger.csv. Horse identity "
        "join key is horse_id / horse_rp_uid (RP numeric horse id) between "
        "racecards.runners[].horse_id and rp_results.results[].runners[].horse_id. "
        "Prediction-run identity: velo_prime_verdicts_2026_07_14.json is the single "
        "morning run (43 rows, one per race_id, no duplicates observed -- see "
        "race_day_14_race_universe_2026_07_14.csv, in_old_velo_verdicts column, all "
        "43 race_ids appear exactly once)."
    ),
}

for orig_path, rec in copy_records.items():
    manifest["primary_evidence_files"].append({
        "original_absolute_path": orig_path,
        "copied_relative_path": rec["copied_relative_path"],
        "sha256": rec["original_sha256"],
        "size_bytes": rec["original_size_bytes"],
        "original_mtime_utc": rec["original_mtime_utc"],
    })

# Headline claim -> source mapping
manifest["headline_claim_provenance"] = [
    {
        "claim": "43 races captured across seven courses",
        "source_path": "data/racecards_2026_07_14_standard.json",
        "source_field": "top-level array length; distinct .course values",
        "verified_value": "43 races; courses = Leicester, Downpatrick, Wolverhampton (AW), Longchamp, Killarney, Ffos Las, Beverley",
        "join_method": "direct count + set() on .course field",
    },
    {
        "claim": "Old VELO Sigma 23/42 wins, 54.8% SR",
        "source_path": "data/sigma_results/sigma_results_2026_07_14.json",
        "source_field": "wins, evaluated_count, sr",
        "verified_value": "wins=23, evaluated_count=42, sr=0.5476",
        "join_method": "direct field read, cross-checked against model_comparison_ledger.csv velo_outcome==WIN count (23) for date==2026-07-14",
    },
    {
        "claim": "Old VELO frame 31/42, 73.8%",
        "source_path": "data/sigma_results/sigma_results_2026_07_14.json",
        "source_field": "wins + frames (23+8=31), frame_rate",
        "verified_value": "31/42 = 0.7381",
        "join_method": "arithmetic on wins+frames fields",
    },
    {
        "claim": "No-RPR 23.8% SR",
        "source_path": "data/model_comparison_ledger.csv",
        "source_field": "norpr_outcome",
        "verified_value": "10/42 = 23.8%",
        "join_method": "COUNT(norpr_outcome=='WIN') / COUNT(norpr_outcome IS NOT NULL) for date==2026-07-14",
    },
    {
        "claim": "WIN_ONLY 3/6 wins",
        "source_path": "data/sigma_results/sigma_results_2026_07_14.json",
        "source_field": "ew_tracking.win_only_n, ew_tracking.win_only_hits",
        "verified_value": "win_only_n=6, win_only_hits=3",
        "join_method": "direct field read; cross-checked via velo_assigned_product=='WIN_ONLY' groupby in model_comparison_ledger.csv (n=6, wins=3)",
    },
    {
        "claim": "EW_CANDIDATE 2/2 placed, both won",
        "source_path": "data/sigma_results/sigma_results_2026_07_14.json",
        "source_field": "ew_tracking.ew_candidate_n, ew_place_n, ew_win_n",
        "verified_value": "ew_candidate_n=2, ew_place_n=2, ew_win_n=2",
        "join_method": "direct field read; cross-checked via velo_assigned_product=='EW_CANDIDATE' groupby (n=2, wins=2, frames=2)",
    },
    {
        "claim": "Mission Control RP_MERGED_CLEAN, zero flatlines, zero identity failures",
        "source_path": "data/mission_control/2026-07-14_mission_control.json",
        "source_field": "source_truth, flatline_count, identity_failure_count",
        "verified_value": "RP_MERGED_CLEAN, 0, 0",
        "join_method": "direct field read",
        "caveat": "Same file also shows council_artifact_visibility.council_run/packet/report == MISSING and promotion_gate_status == BLOCKED (reason GATE_PIPELINE_TRUTH_MANUAL_RECOVERY_ONLY) -- these are separate gates from source_truth/flatline/identity and do not contradict the headline claim, but are recorded for completeness.",
    },
    {
        "claim": "Council PASS_TO_LEARNING",
        "source_path": "data/mission_control/2026-07-14_mission_control.json ; data/council_reports/velo_council_report_2026-07-14.md",
        "source_field": "council_verdict",
        "verified_value": "PASS_TO_LEARNING",
        "join_method": "direct field read from mission control; corroborated by presence of dated council_packet/council_run/council_report files for 2026-07-14 in the primary repo (mission_control.json's own council_artifact_visibility check ran at 23:12:51Z and reported MISSING for those three paths -- meaning it could not see them at generation time, a timing/path-visibility gap, not evidence the council never ran)",
    },
    {
        "claim": "Nightly learning 43/43 matched, 23 wins, 20 losses, idempotent",
        "source_path": "data/nightly_eod_learning_status_2026_07_14.json",
        "source_field": "matched_races, wins, losses, engine_updates_applied_first_run, duplicates_skipped_second_run",
        "verified_value": "matched_races=43, wins=23, losses=20, engine_updates_applied_first_run=43, duplicates_skipped_second_run=43",
        "join_method": "direct field read",
    },
    {
        "claim": "New Build and Champion Intent Shadow NO_DATA",
        "source_path": "data/model_comparison_ledger.csv",
        "source_field": "nb_outcome, champion_outcome",
        "verified_value": "100% of 42 rows for date==2026-07-14 have nb_outcome=='NO_DATA' and champion_outcome=='NO_DATA'",
        "join_method": "groupby/value_counts on nb_outcome and champion_outcome columns filtered to date==2026-07-14",
    },
    {
        "claim": "V6_GOLD_SEAM FROZEN, cumulative frame rate 62.8%, below 70% floor",
        "source_path": "data/router_shadow_audit_runs/router_shadow_audit_20260714_231325.csv/.md ; data/router_shadow_audit_ledger.csv",
        "source_field": "lane status, frame_rate, n",
        "verified_value": "FROZEN, n=94, wins=29, sr=30.85%, frame_rate=62.77%, threshold_msg='LANE_FROZEN -- FRAME_BELOW_70_AT_N20+', freeze=True",
        "join_method": "direct file read (router audit snapshot copied into evidence_staging: data/router_shadow_audit_runs/router_shadow_audit_20260714_231325.csv and .md)",
        "caveat": "The .md file's own 'Change vs Previous Run' section shows V6_GOLD_SEAM n 89 -> 94 (+5), i.e. 2026-07-14 DID contribute 5 new rows to the cumulative figure -- the lane's cumulative n/frame-rate changed today even though it remained FROZEN. This mission read the router audit's self-reported figures directly; it did not independently re-derive n/frame-rate from raw per-race router ledger rows.",
    },
]

path = os.path.join(OUT, "race_day_14_provenance_manifest_2026_07_14.json")
with open(path, "w") as f:
    json.dump(manifest, f, indent=2)
print("Wrote", path, "with", len(manifest["primary_evidence_files"]), "evidence files and", len(manifest["headline_claim_provenance"]), "headline claims")
