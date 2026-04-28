# Playbook G V3 Design

- Objective: Design the first Playbook G V3 offline experiment around a ratings + doctrine core while isolating market information to benchmark, calibration, and residual-learning roles.
- Core hypothesis: Ratings + doctrine is the primary signal engine; raw market features crowd doctrine when injected into the core stack, but market can still add value as benchmark, calibration input, or residual target if it is isolated from core feature learning.
- Eligible cohort: `1697 races / 18575 runners`
- Recommendation for V3 execution: `GO_DESIGN_APPROVED_PENDING_REVIEW`

## V3 Arms
- `V3-1` `market_only_baseline`: unchanged benchmark to beat on out-of-time log loss and Brier
- `V3-2` `market_plus_ratings_baseline`: carry forward the strongest market-led baseline from V2 for comparison
- `V3-3` `doctrine_only_baseline`: prove doctrine retains standalone non-zero signal after full activation
- `V3-4` `ratings_plus_doctrine_core`: primary V3 core model candidate
- `V3-5` `ratings_plus_doctrine_with_market_calibration`: test whether market helps only in post-model calibration without crowding core learning
- `V3-6` `ratings_plus_doctrine_residual_over_market`: test additive residual learning over market without feeding raw market into the core feature stack
- `V3-7` `hk_diagnostic`: confirm HK retains the V2 improvement and quantify crowding sensitivity
- `V3-8` `fr_diagnostic`: confirm FR remains positive and stable under the core design
- `V3-9` `year_2025_sensitivity_report`: report 2025 separately as sensitivity-only; do not let it dominate governance because sample is small

## Exact Feature Masks
- Core `ratings + doctrine + structure`: `or_num, rpr_num, ts_num, or_vs_field, rpr_vs_field, runs_since_win, runs_since_place, runs_since_mkt_support, curr_or_minus_last_win_or, curr_or_minus_best_or, mark_compression_score, release_window_score, course_fit_score, going_fit_score, distance_fit_score, quiet_run_score, trainer_timing_score, jockey_switch_intent, odds_resilience_score, odds_contraction_score, decoy_support_flag, setup_run_flag, cash_run_flag, dist_f, going_code, is_aw, class_num, wgt_lbs, field_size, draw_num, draw_pct, age_num`
- Market features excluded from core: `sp_dec, log_sp, implied_prob, sp_rank, is_fav`
- Ratings features: `or_num, rpr_num, ts_num, or_vs_field, rpr_vs_field`
- Doctrine features: `runs_since_win, runs_since_place, runs_since_mkt_support, curr_or_minus_last_win_or, curr_or_minus_best_or, mark_compression_score, release_window_score, course_fit_score, going_fit_score, distance_fit_score, quiet_run_score, trainer_timing_score, jockey_switch_intent, odds_resilience_score, odds_contraction_score, decoy_support_flag, setup_run_flag, cash_run_flag`
- Structure/context features: `dist_f, going_code, is_aw, class_num, wgt_lbs, field_size, draw_num, draw_pct, age_num`

## Hard Gate
- Core log loss target: `<= 1.481028`
- Core Brier target: `<= 0.077519`
- Market-crowding correlation ceiling: `<= 0.58`
- Market top-1 overlap ceiling: `<= 0.45`

## Risks
- 2025 remains a tiny sensitivity slice
- JPN is too small for strong conclusions
- market can still recrowd the model if calibration/residual layers are implemented sloppily
- V3 should preserve the accepted historical authority model and not fall back to raw runner_results joins

## Next Mission
- Review this V3 design, then approve or reject Playbook G V3 offline execution.
