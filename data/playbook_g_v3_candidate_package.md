# Playbook G V3 Offline Candidate Package

## Status
- candidate: `ratings + doctrine + structure core + temperature scaling`
- status: `offline_research_candidate_only`
- `not_for_deployment = true`
- raw market features are excluded from the core learner
- calibration method: `temperature_scaling_without_market`

## Model Shape
- Core learner uses:
  - ratings features
  - doctrine features
  - structure/context features
- Core learner excludes raw market features:
  - `sp_dec`
  - `log_sp`
  - `implied_prob`
  - `sp_rank`
  - `is_fav`
- Market is allowed only as:
  - benchmark
  - post-model diagnostic

## Feature Mask
- Ratings:
  - `or_num`, `rpr_num`, `ts_num`, `or_vs_field`, `rpr_vs_field`
- Doctrine:
  - `runs_since_win`, `runs_since_place`, `runs_since_mkt_support`
  - `curr_or_minus_last_win_or`, `curr_or_minus_best_or`
  - `mark_compression_score`, `release_window_score`
  - `course_fit_score`, `going_fit_score`, `distance_fit_score`
  - `quiet_run_score`, `trainer_timing_score`, `jockey_switch_intent`
  - `odds_resilience_score`, `odds_contraction_score`
  - `decoy_support_flag`, `setup_run_flag`, `cash_run_flag`
- Structure/context:
  - `dist_f`, `going_code`, `is_aw`, `class_num`, `wgt_lbs`
  - `field_size`, `draw_num`, `draw_pct`, `age_num`

## Forbidden Inputs
- `winner_flag`, `placed_flag`, `finish_position`, `position`
- result comments
- future race results
- post-race ranking
- `sqpe_v17_prob`, `velo_prime_prob`, `g_base_prob`, `place_prob`
- `g_shadow_*`, `sentient_*`, `verdict_flags`
- any prior model output
- any outcome-derived field

## Training Cohort
- accepted historical training authority:
  - `race_results distinct accepted events`
  - `races.runners_count`
  - `accepted historical_feature_store rows`
- known caveat:
  - direct `runner_results` join has legacy horse-id drift and is not the authority for this cohort
- cohort filters:
  - `training_eligible = pending_global_training_gate`
  - `data_owner_confirmed = true`
  - `source = historical_raceform`
  - `event_identity_contract = race_id_course_race_date`
  - `signal_contract_version = HISTORICAL_SIGNAL_PROXY_V1`
  - `historical_doctrine_contract = HISTORICAL_DOCTRINE_FEATURES_V1`
  - `doctrine_source = prior_only_raceform_history`
  - `macro-year mismatch = 0`
  - vector length `37`
- cohort size:
  - races: `1697`
  - runners: `18575`

## Split Definition
- train: `2017-2020` -> `1060` races / `11757` runners
- validation: `2021-2022` -> `523` races / `5804` runners
- test: `2023-2025` -> `114` races / `1014` runners
- split rule: strict out-of-time, no random shuffle across years

## Final Metrics
- Candidate test:
  - log loss: `1.271421`
  - Brier: `0.067636`
  - ECE: `0.034484`
  - top-1: `54.39%`
  - top-3: `86.84%`
- Comparisons:
  - market-only test log loss / Brier: `1.725229 / 0.085483`
  - market + ratings test log loss / Brier: `1.481647 / 0.076613`
  - uncalibrated V3 core log loss / Brier / ECE: `1.434518 / 0.073330 / 0.042030`

## Market Isolation Proof
- market features excluded from core: `true`
- market probability correlation: `0.4842`
- top-1 market overlap: `0.3684`
- gates:
  - correlation must be `<= 0.58`
  - top-1 overlap must be `<= 0.45`
- result: `pass`

## Calibration Proof
- method: `temperature_scaling_without_market`
- ECE improvement vs uncalibrated V3 core: `+0.007546`
- log loss delta vs uncalibrated V3 core: `-0.163097`
- Brier delta vs uncalibrated V3 core: `-0.005694`
- result: `pass`

## HK / FR / 2025 Caveats
- `HK`: positive vs market
  - candidate log loss: `1.384536`
  - market log loss: `2.004304`
  - races: `29`
- `FR`: positive vs market
  - candidate log loss: `1.221795`
  - market log loss: `1.629290`
  - races: `84`
- `JPN`: informational only
  - races: `1`
- `2025`: sensitivity only
  - log loss: `1.335394`
  - top-1: `38.46%`
  - top-3: `80.77%`
  - races: `26`

## Governance And Safety
- leakage audit: `pass`
- outcome-field exclusion: `pass`
- prior model output exclusion: `pass`
- `training_eligible` unchanged: `true`
- HFS mutation: `false`
- DB writes: `false`
- Playbook E: `blocked`
- deployment: `blocked`

## Known Blockers
- The candidate is not approved for production promotion.
- The full V3 suite failed because market-assisted variants re-crowded the signal.
- The calibrated candidate still needs a calibrated-candidate-specific stability audit with uncertainty intervals.
- `2025` remains too small for governance beyond sensitivity reporting.
- Calibration is improved, but governance review is still required before any shadow or production path.

## Production Promotion Requirements
- checkpoint and preserve this candidate package
- run calibrated-candidate stability audit against market and market+ratings
- prove calibration remains stable without market recrowding in `HK` and `FR`
- keep `2025` isolated until the sample is materially larger
- define and approve a shadow-only governance gate before any deployment discussion
- do not change `training_eligible` or activate Playbook E as part of this package
