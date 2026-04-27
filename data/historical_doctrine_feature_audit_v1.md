# Historical Doctrine Feature Activation Audit V1

## Scope
- Eligible races: `1697`
- Eligible runners: `18575`

## A. 37-Vector Schema
- `00` `sp_dec` (market)
- `01` `log_sp` (market)
- `02` `implied_prob` (market)
- `03` `dist_f` (structure)
- `04` `going_code` (structure)
- `05` `is_aw` (structure)
- `06` `class_num` (structure)
- `07` `wgt_lbs` (structure)
- `08` `or_num` (rating)
- `09` `rpr_num` (rating)
- `10` `ts_num` (rating)
- `11` `or_vs_field` (rating)
- `12` `rpr_vs_field` (rating)
- `13` `field_size` (structure)
- `14` `draw_num` (structure)
- `15` `draw_pct` (structure)
- `16` `age_num` (structure)
- `17` `sp_rank` (market)
- `18` `is_fav` (market)
- `19` `runs_since_win` (doctrine)
- `20` `runs_since_place` (doctrine)
- `21` `runs_since_mkt_support` (doctrine)
- `22` `curr_or_minus_last_win_or` (doctrine)
- `23` `curr_or_minus_best_or` (doctrine)
- `24` `mark_compression_score` (doctrine)
- `25` `release_window_score` (doctrine)
- `26` `course_fit_score` (doctrine)
- `27` `going_fit_score` (doctrine)
- `28` `distance_fit_score` (doctrine)
- `29` `quiet_run_score` (doctrine)
- `30` `trainer_timing_score` (doctrine)
- `31` `jockey_switch_intent` (doctrine)
- `32` `odds_resilience_score` (doctrine)
- `33` `odds_contraction_score` (doctrine)
- `34` `decoy_support_flag` (doctrine)
- `35` `setup_run_flag` (doctrine)
- `36` `cash_run_flag` (doctrine)

## B/C. Activation Status
- Active / non-constant features (`18`): `sp_dec, log_sp, implied_prob, going_code, is_aw, class_num, wgt_lbs, or_num, rpr_num, ts_num, or_vs_field, rpr_vs_field, field_size, draw_num, draw_pct, age_num, sp_rank, is_fav`
- Constant / defaulted features (`18`): `runs_since_win, runs_since_place, runs_since_mkt_support, curr_or_minus_last_win_or, curr_or_minus_best_or, mark_compression_score, release_window_score, course_fit_score, going_fit_score, distance_fit_score, quiet_run_score, trainer_timing_score, jockey_switch_intent, odds_resilience_score, odds_contraction_score, decoy_support_flag, setup_run_flag, cash_run_flag`

## Core Finding
- Historical HFS reconstruction still calls `_build_live_features(r_norm, nrace, [], [])`.
- `_build_live_features` then fills doctrine slots from `DEFAULTS` when nothing was precomputed.
- Result: the entire doctrine layer is dead/defaulted in the scoped historical training cohort.

## Separate Structural Issue
- Constant non-default features: `dist_f`
- `dist_f` is pinned at `16.0` because the historical HFS path feeds numeric `distance_f` into a parser that expects string labels like `1m2f` and falls back to `16.0`.

## D/E/F. Feature Groups
- Market: `sp_dec, log_sp, implied_prob, sp_rank, is_fav`
- Rating: `or_num, rpr_num, ts_num, or_vs_field, rpr_vs_field`
- Doctrine: `runs_since_win, runs_since_place, runs_since_mkt_support, curr_or_minus_last_win_or, curr_or_minus_best_or, mark_compression_score, release_window_score, course_fit_score, going_fit_score, distance_fit_score, quiet_run_score, trainer_timing_score, jockey_switch_intent, odds_resilience_score, odds_contraction_score, decoy_support_flag, setup_run_flag, cash_run_flag`

## G/H/I. Sourceability
- Live-only / not historical-safe as-is: `plot_conviction, or_compression_score, postdata_score, ts_master, or_delta_to_best_win, intent_signals, trainer_recent_form, comment_intel_score, horse_state, tie_gate_signals`
- Historical-feasible: `cash_run_flag, chaos_bloom, class_regime_pressure, course_fit_score, course_jurisdiction_regime, curr_or_minus_best_or, curr_or_minus_last_win_or, decoy_support_flag, distance_fit_score, draw_position_pressure, field_entropy, field_size_chaos, going_fit_score, going_regime_pressure, jockey_switch_intent, mark_compression_score, market_pressure_rank, mpi, odds_contraction_score, odds_resilience_score, or_rpr_vs_field_pressure, prior_only_horse_history, quiet_run_score, release_window_score, runs_since_mkt_support, runs_since_place, runs_since_win, setup_run_flag, trainer_timing_score, weight_vs_field_pressure`
- Historical-infeasible without other upstream systems: `comment_intel_score, horse_state, intent_signals, or_compression_score, or_delta_to_best_win, plot_conviction, postdata_score, tie_gate_signals, trainer_recent_form, ts_master`

## J/K/L. Why The Doctrine Layer Is Dead
- `runs_since_win` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `horse_id, prior race_date, prior finishing positions`; raceform sufficiency = `True`
- `runs_since_place` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `horse_id, prior race_date, prior finishing positions`; raceform sufficiency = `True`
- `runs_since_mkt_support` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `horse_id, prior race_date, prior SP history`; raceform sufficiency = `True`
- `curr_or_minus_last_win_or` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `current OR, horse_id, prior winning OR`; raceform sufficiency = `True`
- `curr_or_minus_best_or` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `current OR, horse_id, prior OR history`; raceform sufficiency = `True`
- `mark_compression_score` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `current OR, horse_id, prior OR history`; raceform sufficiency = `True`
- `release_window_score` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `runs_since_win, mark_compression_score`; raceform sufficiency = `True`
- `course_fit_score` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `current course, horse_id, prior course matches, prior win/place outcomes`; raceform sufficiency = `True`
- `going_fit_score` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `current going, horse_id, prior going matches, prior win/place outcomes`; raceform sufficiency = `True`
- `distance_fit_score` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `current distance, horse_id, prior distance matches, prior win/place outcomes`; raceform sufficiency = `True`
- `quiet_run_score` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `horse_id, last prior race beaten margin`; raceform sufficiency = `True`
- `trainer_timing_score` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `current trainer, trainer prior wins, trainer prior starts, current race_date`; raceform sufficiency = `True`
- `jockey_switch_intent` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `current jockey, horse_id, last prior jockey`; raceform sufficiency = `True`
- `odds_resilience_score` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `horse_id, last 2-3 prior SP values`; raceform sufficiency = `True`
- `odds_contraction_score` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `current SP, horse_id, last prior SP`; raceform sufficiency = `True`
- `decoy_support_flag` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `current is_fav, trainer_timing_score`; raceform sufficiency = `True`
- `setup_run_flag` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `horse_id, last prior beaten margin`; raceform sufficiency = `True`
- `cash_run_flag` defaults via `backfill_historical_feature_store.py:509` and `velo_prime_service.py:189`; needs `trainer_timing_score, runs_since_win, mark_compression_score`; raceform sufficiency = `True`

## M. Leakage Risk
- `market_pressure_rank`: status=`activate_now` risk=`low` inputs=`sp_dec, implied_prob, sp_rank, field_size, within-race rank/normalization`
- `field_entropy`: status=`activate_now` risk=`low` inputs=`field implied probability distribution, field_size, going, jurisdiction`
- `draw_position_pressure`: status=`activate_now` risk=`low` inputs=`draw, field_size, course, jurisdiction`
- `weight_vs_field_pressure`: status=`activate_now` risk=`low` inputs=`weight_lbs, field weight distribution, race class, distance`
- `or_rpr_vs_field_pressure`: status=`activate_now` risk=`low` inputs=`official_rating, rpr, ts, field rating distribution`
- `class_regime_pressure`: status=`activate_now` risk=`low` inputs=`current class, field class context, jurisdiction, race type`
- `going_regime_pressure`: status=`activate_now` risk=`low` inputs=`going, jurisdiction, course, field distribution`
- `course_jurisdiction_regime`: status=`activate_now` risk=`low` inputs=`course, jurisdiction, distance, race type`
- `field_size_chaos`: status=`activate_now` risk=`low` inputs=`field_size, market entropy, going uncertainty`
- `horse_prior_history`: status=`requires_prior_history_engine` risk=`medium` inputs=`horse_id, prior race_date, prior positions, prior SP, prior OR/RPR/TS, prior course/going/distance, prior jockey, prior trainer, prior beaten margin`

## N. Outcome Exclusion Proof
- Forbidden fields: `winner_flag, is_winner, placed_flag, finish_position, position, pos, comment, result_comment, future_race_result, post_race_ranking, sqpe_v17_prob, velo_prime_prob, g_base_prob, place_prob, g_shadow_flags, g_shadow_horse_id, g_shadow_mode, g_shadow_multiplier, verdict_flags`
- Contract intersection with forbidden fields: `[]`
- Rule: Prior-race outcomes are allowed only when source race_date < current race_date; current-race outcomes are forbidden.

## O/P. Contract And Plan
- Recommended option: `D`
- Recommendation: Build prior-only horse history engine before Playbook G V2.
- Expand historical context rehydration to carry current-row jockey, trainer, SP, beaten margin, class_raw, and distance metadata from raceform.
- Build a prior-only history engine keyed by horse_id and race_date, excluding current-day/current-race rows conservatively.
- Compute the 18 doctrine features from prior-only history instead of DEFAULTS, preserving the existing 37-vector order.
- Add manifest-scoped HFS reconstruction smoke test on a small accepted block and rerun this audit to prove doctrine dimensions are no longer constant.
- Only after doctrine activation passes should Playbook G V2 ablation dry-run proceed.
