# Playbook G Dry-Run Gate v1

Generated: `2026-04-27T11:46:24.519622+00:00`

No training was executed. This is a training-readiness gate only.

## Scope
- Eligible race events: `1697`
- Eligible runner rows: `18575`
- Training scope: `training_eligible = pending_global_training_gate`, `source = historical_raceform`, `signal_contract_version = HISTORICAL_SIGNAL_PROXY_V1`, `event_identity_contract = race_id_course_race_date`, `macro_year_used = race year`, `vector length = 37`

## Data Shape
- Year breakdown (races): `{"2017": 294, "2018": 280, "2019": 292, "2020": 194, "2021": 321, "2022": 202, "2023": 47, "2024": 41, "2025": 26}`
- Jurisdiction breakdown (races): `{"FR": 649, "HK": 1029, "JPN": 19}`
- Course breakdown (top): `{"Chantilly (FR)": 525, "Compiegne (FR)": 124, "Happy Valley (HK)": 443, "Kokura (JPN)": 11, "Sapporo (JPN)": 8, "Sha Tin (HK)": 586}`
- Runners per race: `avg=10.946, min=3, max=18`
- Winner label distribution: `positives=1697, negatives=16878, positive_rate=0.091359`

## Feature Readiness
- Vector dimension check: `{"37": 18575}`
- Vector NaN / inf: `nan=0, inf=0`
- Leakage exclusion: `pass`
- Outcome exclusion: `pass`

## Market Benchmarks
- The candidate must beat these out-of-time market references on the first dry-run.
- Test market baseline: `log_loss=1.725229, brier=0.085483, top1=0.359649, top3=0.692982`

## Proposed Split
- Train: `{"jurisdiction_breakdown": {"FR": 424, "HK": 624, "JPN": 12}, "race_count": 1060, "runner_count": 11757, "years": [2017, 2018, 2019, 2020]}`
- Validation: `{"jurisdiction_breakdown": {"FR": 141, "HK": 376, "JPN": 6}, "race_count": 523, "runner_count": 5804, "years": [2021, 2022]}`
- Test: `{"jurisdiction_breakdown": {"FR": 84, "HK": 29, "JPN": 1}, "race_count": 114, "runner_count": 1014, "years": [2023, 2024, 2025]}`
- Secondary recommendation: Run an anchored rolling-origin backtest by year in addition to the primary holdout because the late years are sparse and FR-heavy.

## Baselines
- `market_implied_probability_baseline`: normalize implied probability within race.
- `sp_rank_baseline`: reciprocal SP-rank weights within race.
- `simple_logistic_baseline`: market-only logistic control on `[sp_dec, log_sp, implied_prob, sp_rank, is_fav]`.
- `playbook_g_candidate_model`: calibrated GBM plus isotonic calibration on the 37-vector only.

## Pass / Fail
- Pass only if the candidate beats the market-implied baseline and the market-only logistic control on out-of-time probability metrics.
- HK and FR must each be non-negative versus market on log loss; JPN is informational only.
- Any use of prior model outputs, Playbook shadow state, verdict metadata, or outcome labels in the training matrix is an automatic stop.

## Risks
- The eligible training cohort is 1,697 race events and 18,575 runners, not the full ~1,939 clean historical races. The excluded remainder is outside the strict pending_global_training_gate OASIS scope and should stay excluded from the first dry-run.
- The 2025 slice is clean but small (26 races / 244 runners) and uses explicit proxy macro context 2025_PROXY_V1. It should be included in the out-of-time test, but any 2025-specific conclusions must be treated as low-sample sensitivity checks.
- The late test period is FR-heavy and JPN-light. Jurisdiction gating should focus on HK and FR; JPN should be monitored but not used as a blocker.
- historical_feature_store rows contain prior model outputs and sentient metadata outside the 37-vector. Those keys are safe only if they remain excluded from the first training matrix.
- No training should touch training_eligible, historical_feature_store, or live verdict systems during the dry-run.

## Recommendation
- `GO_OFFLINE_DRY_RUN_ONLY`
- The accepted OASIS cohort is large enough, fully audited, macro-year-correct, provenance-complete, and leakage-safe when restricted to the 37-vector. The next step should be a strictly offline Playbook G dry-run whose only purpose is to measure whether the candidate beats market probability on out-of-time data.
- Not approved in this step: `live deployment`, `Playbook E activation`, `production model promotion`, `mutation of historical_feature_store`, `training_eligible state changes`
