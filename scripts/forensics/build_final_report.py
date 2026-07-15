#!/usr/bin/env python3
"""Assemble the final race_day_14_best_day_proof_2026_07_14.json from all
intermediate outputs already written to data/reports/ by
build_race_day_14_report.py and build_provenance_manifest.py."""
import json
import os

ROOT = "/mnt/c/Users/puror/velo-race-day-14-proof"
OUT = os.path.join(ROOT, "data", "reports")


def j(name):
    with open(os.path.join(OUT, name)) as f:
        return json.load(f)


phase5 = j("_phase5_old_velo_vs_no_rpr.json")
phase6 = j("_phase6_best_day_stats.json")
product = j("_old_velo_product_breakdown.json")
provenance = j("race_day_14_provenance_manifest_2026_07_14.json")
uncommitted = json.load(open(os.path.join(ROOT, "provenance", "UNCOMMITTED_RUNTIME_CODE_PROVENANCE.json")))

final_verdict = "BEST_VERIFIED_RECENT_DAY"

report = {
    "mission": "RACE-DAY-14-BEST-DAY-PROOF-01",
    "date": "2026-07-14",
    "generated_at_utc": "2026-07-15T00:00:00Z",
    "classification_phase1_race_universe": "RACE_UNIVERSE_RECONCILED",
    "phase1_summary": {
        "morning_racecard_races": 43,
        "old_velo_verdicts": 43,
        "raw_html_racecard_files": 45,
        "raw_html_racecard_files_explanation": "45 = 43 race pages + 2 course/index pages (captured incidentally during the browse/capture session, not counted as races).",
        "manifest_captures_recorded": 3,
        "manifest_bug_explanation": "See race_day_14_manifest_gap_autopsy_2026_07_14.md -- proven code-path bug in racing_post_account_collector.py's batch capture() manifest write: all_captures is filtered to the CURRENT invocation's --url-list, so a later invocation with a smaller URL list (the 3 Longchamp URLs) silently overwrote/truncated the manifest, even though all 45 HTML files remained on disk from earlier invocation(s).",
        "reconstructed_43_urls_method": "Operator extracted canonical URLs directly via regex on <link rel=\"canonical\"> in each of the 45 raw HTML files, converted /racecards/ -> /results/, producing 43 unique result URLs (2 index-page URLs correctly excluded as non-race pages).",
        "sigma_race_count": 42,
        "sigma_42_explanation": "1 of the 43 races (923388, Wolverhampton (AW) 19:55) had Old VELO's specific top pick (Wonderful Wendy) declared a non-runner (NR) before the off. The race itself ran (11 of 12 declared runners raced, won by Luan @ SP 2.62), but Sigma's evaluation logic correctly excludes races where the PREDICTED horse never ran from its win/frame/miss denominator -- this is the sigma.true_non_runners=1 case, not a data loss.",
        "nightly_learning_race_count": 43,
        "nightly_43_explanation": "nightly_eod_learning_runner.py's OUTCOME_ONLY_EOD_REPLAY logic is a binary WIN/LOSS classifier with no separate non-runner/void bucket and no PLACE/frame bucket. It counts all 43 predicted races and buckets everything that isn't a WIN as a LOSS -- so its 20 losses = Sigma's 8 PLACED (frames) + Sigma's 11 true MISS rows + the 1 true-non-runner race (923388), which nightly counts as a loss rather than excluding or voiding it.",
        "race_present_in_nightly_but_not_sigma": {
            "race_id": "923388",
            "course": "Wolverhampton (AW)",
            "off": "19:55",
            "old_velo_top_pick": "Wonderful Wendy",
            "pick_status": "NON_RUNNER (declared NR before the off)",
            "race_outcome": "Race ran; won by Luan @ SP 2.62",
            "sigma_treatment": "Excluded from evaluated_count (true_non_runners=1)",
            "nightly_treatment": "Counted as one of the 20 'losses' -- classification inconsistency between Sigma's 3-bucket (WIN/PLACED/MISS, non-runner excluded) taxonomy and nightly's 2-bucket (WIN/LOSS, non-runner not excluded) taxonomy. Not a data error in either artifact individually, but the two systems are not directly comparable on this one race without adjustment.",
        },
        "duplicated_excluded_unscored_abandoned_void_or_identity_unresolved_races": "None found. All 43 race_ids appear exactly once across racecards, verdicts, and the ledger; the one true non-runner (923388) is a single-horse-level non-runner within a race that otherwise ran and was fully scored/results-parsed, not a void/abandoned race.",
    },
    "phase2_result_and_timing_truth": {
        "provenance_table": "See race_day_14_provenance_manifest_2026_07_14.json (headline_claim_provenance array) for the full source-path/field/join-method table.",
        "no_post_result_rescoring": "PARTIALLY_PROVEN -- file mtimes show data/velo_prime_verdicts_2026_07_14.json (14:07:48Z) generated before data/results/rp_results_2026_07_14.json (23:11:21Z) and before data/sigma_results/sigma_results_2026_07_14.json (23:11:54Z), a >9 hour gap consistent with morning-scoring-then-evening-results. However, this mission could not confirm per-race prediction timestamps against exact per-race off-times for the earliest race on the card (Leicester 923082, off 13:54) because the verdict JSON schema does not carry a per-race generation timestamp and this mission does not have independently confirmed timezone semantics (local BST vs UTC) for the 'off_time'/'off' fields recorded across artifacts. See 'what remains unproven' in the markdown dashboard.",
        "no_cross_date_result_contamination": "PROVEN for the races checked -- rp_results_2026_07_14.json race_time_raw values are all 2026-07-14T*, and every race_id in the reconciliation table maps 1:1 to a single date across all source files (no race_id collisions with adjacent dates observed in the sampled joins).",
        "no_duplicate_prediction_run_pooling": "PROVEN -- velo_prime_verdicts_2026_07_14.json contains exactly 43 rows, one per unique race_id, no duplicates (see race_day_14_race_universe_2026_07_14.csv).",
        "no_omitted_race_silently_improving_denominator": "PROVEN -- Sigma's denominator (42) is smaller than the full card (43) with a specifically identified, artifact-proven reason (true non-runner), not a silent omission; both directions were checked (nothing in verdicts/racecards is silently absent from Sigma without explanation).",
    },
    "phase3_four_model_summary_csv": "race_day_14_four_model_summary_2026_07_14.csv",
    "phase3_lane_classifications": {
        "old_velo_live": "FULL_PRE_RACE_SCORECARD",
        "no_rpr_shadow": "FULL_PRE_RACE_SCORECARD",
        "new_build": "NO_PRE_RACE_SCORECARD",
        "champion_intent_shadow": "NO_PRE_RACE_SCORECARD",
    },
    "phase4_old_velo_product_breakdown": product,
    "phase4_win_only_verification": {"claimed": "3/6", "verified_n": 6, "verified_wins": 3, "match": True},
    "phase4_ew_candidate_verification": {"claimed": "2/2 placed, 2/2 won", "verified_n": 2, "verified_placed": 2, "verified_wins": 2, "match": True},
    "phase5_old_velo_vs_no_rpr": phase5,
    "phase5_causation_note": (
        "Old VELO's 23 wins vs No-RPR's 10 wins (13-win gap, 31.0pp SR gap) cannot be attributed to RPR "
        "information alone from this evidence. The 'No-RPR' shadow lane differs from Old VELO not just in "
        "RPR exclusion but in its entire probability pathway (sqpe_no_rpr_shadow_prob is a distinct model "
        "output, not simply Old VELO with one feature zeroed) -- both lanes share the same underlying SQPE/"
        "improvement/MDS ensemble structure but No-RPR's variant likely differs in calibration, not just in "
        "the presence/absence of RPR. Attributing the full 31pp gap to 'RPR access' specifically, rather than "
        "to broader differences in the two model configurations, is NOT proven by this evidence -- it is "
        "plausible but the causal claim is UNPROVEN and should not be stated as fact."
    ),
    "phase6_best_day_verdict": final_verdict,
    "phase6_stats": phase6,
    "phase6_jul13_comparison_note": "data/model_comparison_ledger.csv contains NO rows for 2026-07-13 at all -- the ledger has a gap for that date (consistent with prior session memory noting missing sigma dates). A direct 07-13 vs 07-14 comparison could not be performed from this artifact; this is recorded as a gap, not silently skipped.",
    "phase7_confidence_flood_and_leakage": {
        "vp_by_outcome": {
            "WIN_avg_vp": 0.5041, "WIN_n": 23,
            "PLACED_avg_vp": 0.4130, "PLACED_n": 8,
            "MISS_avg_vp": 0.4051, "MISS_n": 11,
        },
        "discrimination_gap": "WIN average VP (0.504) exceeds MISS average VP (0.405) by ~10 points -- real discrimination between winners and losers exists, this is NOT a flat/uninformative probability distribution.",
        "expected_wins_from_summed_probabilities": 19.36,
        "actual_wins": 23,
        "calibration_read": "Actual wins (23) exceed the sum of predicted win probabilities (19.36) -- the model was, in aggregate, mildly UNDERconfident on 2026-07-14, not overconfident. This is the opposite direction from an overfitting/leakage concern.",
        "high_confidence_threshold_flood_check": "36 of 42 races (85.7%) cleared the >=0.30 'high confidence' bar used for the WIN_ONLY/EW_CANDIDATE bucket sizing in Sigma's own high_conf_n figure. This threshold captures nearly the whole card, which is a genuine MILD flood pattern at that specific 0.30 cut -- it is a low bar, not a selective one -- even though the WIN vs MISS averages above show real underlying discrimination. Recorded as a caveat, not disqualifying.",
        "brier_log_loss": "NOT COMPUTED -- would require the full per-runner probability distribution (all runners per race, not just the top pick), which is not present in the copied evidence files (sigma_results rows carry only the top-pick's velo_prime_prob per race, not a full-field distribution). Recorded as a gap.",
        "no_leakage_into_pre_race_scorecard": "PARTIALLY_PROVEN -- see phase2 timing note above; file-mtime ordering is consistent with no leakage but per-race timestamp proof is incomplete for the earliest race on the card.",
    },
    "phase8_learning_containment": {
        "43_of_43_matched_verified": True,
        "23_wins_20_losses_verified": True,
        "denominator_difference_from_sigma_explained": "See phase1_summary.nightly_43_explanation and race_present_in_nightly_but_not_sigma above.",
        "first_run_state": {"engine_updates_applied_first_run": 43, "learning_mode": "OUTCOME_ONLY_EOD_REPLAY"},
        "second_run_idempotence": {"engine_updates_applied_duplicate_run": 0, "duplicates_skipped_second_run": 43},
        "live_sentient_state_touched": False,
        "shadow_state_touched": True,
        "supabase_writes_attempted_by_nightly_runner": False,
        "scorer_weights_changed": "NOT CHANGED -- this mission did not modify any scoring code and the nightly status file's own fields (live_sentient_state_touched=false, hfs_features_used=false) corroborate no live-weight mutation occurred as part of the 2026-07-14 nightly run.",
        "model_files_changed": "NOT CHANGED -- no model .pkl files were touched by this mission; the primary repo's dirty model.pkl (data/new_build/models/core_v0_or_passport_intent/model.pkl) predates this mission and was not created or modified by the 2026-07-14 nightly learning run (New Build had NO_DATA for 07-14, see Phase 9).",
        "no_promotion_occurred": True,
        "no_hfs_mutation": True,
        "no_sealed_july_12_learningeventv2_2_packet_consumed": "NOT INDEPENDENTLY VERIFIED THIS MISSION -- no evidence of it being consumed was found in the 2026-07-14 nightly status file (which only reports its own day's 43 events), but this mission did not specifically search for or hash-verify the July 12 sealed packet's untouched state. Recorded as a gap.",
        "no_learning_loop_01b_work_performed": "PROVEN by omission -- no LEARNING-LOOP-01B artifacts, branches, or file paths were found or created anywhere in this mission's evidence trail.",
    },
    "phase9_router_and_missing_lanes": {
        "v6_gold_seam": {
            "cumulative_n": 94, "wins": 29, "frame_rate_pct": 62.77, "sr_pct": 30.85,
            "required_frame_floor_pct": 70, "state": "LANE_FROZEN",
            "freeze_reason": "FRAME_BELOW_70_AT_N20+",
            "changed_by_2026_07_14": "YES -- n went from 89 to 94 (+5 rows contributed by 07-14), ROI 9.8%->11.4%, P&L GBP8.75->GBP10.75. The lane remained FROZEN before and after; 07-14 data updated the cumulative figures but did not change the freeze state.",
            "no_unfreeze_or_promotion_proof": "freeze=True is explicitly recorded in both the .csv and .md snapshot generated 2026-07-14 23:13 UTC (the same run that also updated the cumulative n); no separate unfreeze event exists in the evidence.",
        },
        "new_build_gap": "See race_day_14_new_build_NO_DATA_2026_07_14.md -- readiness/feature layer (Lane A Core+Passport) completed and gated READY, but no per-race scored prediction card exists for 07-14. The specific missing step could not be pinpointed with certainty from artifacts alone (no shell history for the missing invocation).",
        "champion_intent_gap": "See race_day_14_champion_intent_NO_DATA_2026_07_14.md -- no execution trace at all for 07-14; consistent with prior session memory noting the Champion Intent Layer V1 rerun was still pending going into this period.",
    },
    "phase10_manifest_autopsy": "See race_day_14_manifest_gap_autopsy_2026_07_14.md for the full root-cause analysis, cross-date mismatch table, and repair/regression-test recommendations (not implemented in this mission).",
    "uncommitted_runtime_code_provenance": uncommitted["governance_conclusion"],
    "final_verdict_reasoning": (
        "2026-07-14 ranks #1 by strike rate and #1 by raw win count among all 37 valid ledger days recorded in "
        "data/model_comparison_ledger.csv (#1 among the 32 days with >=20 races, #1 among the 28 days with >=30 "
        "races on the same strike-rate measure), and #1 by theoretical SP ROI among the ONLY 2 ledger dates "
        "(2026-07-10 and 2026-07-14) that carry usable winner_sp data -- all other ledger dates are missing SP "
        "data entirely and were NOT compared on ROI. The Wilson 95% CI for 23/42 is [39.9%, 68.8%], entirely above "
        "the ~17.1% EXPLICITLY ASSUMED null baseline strike rate (carried over from prior session memory, NOT "
        "independently reconstructed from 2026-07-13 in this mission -- the ledger has zero rows for that date). "
        "The one-sided exact binomial P(X>=23 | n=42, p=0.171) is approximately 3.45e-08 -- precise, extremely "
        "small, but explicitly NOT zero -- a statistically extreme result, not noise. All ledger dates prior to "
        "2026-07-14 were read from the ledger's own recorded aggregates and were NOT independently "
        "re-forensically verified in this mission (timing_proof_status=NOT_RE_VERIFIED_THIS_MISSION on every "
        "such row) -- this is ledger-derived context, not a full 37-day forensic re-audit. However, the verdict "
        "is NOT BEST_VERIFIED_DAY_EVER because: (1) committed HEAD "
        "is PROVEN (not merely suspected) to not equal the code that produced the day's racecard artifact -- "
        "src/velo/racecard_loader.py's uncommitted GB/IRE region-tagging fix was demonstrably active, meaning full "
        "code-level reproducibility from git history alone is not currently possible; (2) the day's result "
        "completeness depended on a manual, undocumented, non-repeatable operator workaround (regex URL "
        "reconstruction) because the canonical Step 10A pipeline was fed a truncated manifest -- had this not been "
        "caught, Mission Control would have wrongly reported RP_MERGED_CLEAN on a 3-race sample; (3) frame-rate "
        "rank (5th) is not #1, so the day is not uniformly dominant across every metric; (4) the July 13 "
        "comparison the mission was asked to make could not be performed at all -- the ledger has no rows for "
        "that date. Given all of this, BEST_VERIFIED_RECENT_DAY is the strongest supportable classification: "
        "genuinely exceptional and statistically well-clear of noise, but short of an unconditional 'best day ever' "
        "claim given the proven code-provenance and process-completeness caveats."
    ),
}

path = os.path.join(OUT, "race_day_14_best_day_proof_2026_07_14.json")
with open(path, "w") as f:
    json.dump(report, f, indent=2)
print("Wrote", path)
