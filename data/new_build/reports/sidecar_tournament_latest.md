# Sidecar Tournament — Challenger V1
Generated: 2026-05-28T19:46:52.283153

Challenger V1 = Core V0_OR + Horse Passport + Intent
Test baseline: AUC 0.6969 | SR 25.02% | Frame 54.98%

## Ablation Results
| variant                                 |   val_AUC |   test_AUC |   test_SR |   test_Frame |   test_AUC_lift |   test_SR_lift | leakage_risk   | verdict          |
|:----------------------------------------|----------:|-----------:|----------:|-------------:|----------------:|---------------:|:---------------|:-----------------|
| A: Challenger V1 (baseline)             |    0.6945 |     0.6969 |    0.2502 |       0.5498 |          0      |         0      | False          | REJECTED_NO_LIFT |
| B: V1 + JTC-D [LEAKAGE_RISK]            |    0.8274 |     0.8418 |    0.4433 |       0.7584 |          0.1449 |         0.1931 | True           | SHADOW_ONLY      |
| C: V1 + Intl Lagged                     |    0.6946 |     0.6967 |    0.2545 |       0.5505 |         -0.0002 |         0.0043 | False          | REJECTED_NO_LIFT |
| D: V1 + JTC-D + Intl Lagged [LEAK_RISK] |    0.8277 |     0.8422 |    0.4438 |       0.7588 |          0.1453 |         0.1936 | True           | SHADOW_ONLY      |
| G: V1 + Market [MARKET_LANE]            |    0.8    |     0.8069 |    0.3603 |       0.6989 |          0.11   |         0.1101 | False          | MARKET_LANE      |
| H: V1 + Intl + Market [MARKET_LANE]     |    0.8001 |     0.8069 |    0.3614 |       0.7001 |          0.11   |         0.1112 | False          | MARKET_LANE      |

## Verdicts
- **Accepted:** none
- **Rejected (no lift):** ['A: Challenger V1 (baseline)', 'C: V1 + Intl Lagged']
- **Shadow only (leakage risk):** ['B: V1 + JTC-D [LEAKAGE_RISK]', 'D: V1 + JTC-D + Intl Lagged [LEAK_RISK]']
- **Market lane:** ['G: V1 + Market [MARKET_LANE]', 'H: V1 + Intl + Market [MARKET_LANE]']

## Sidecar Inventory

### jtcd_trainer_jockey
- `rows`: 178608
- `val_coverage`: 0.997
- `join_keys`: ['trainer', 'jockey']
- `leakage_risk`: NO_DATE_BOUNDARY
- `lane`: SHADOW_ONLY
- `note`: All-time cumulative stats, no cutoff date. Lab experiment only.

### jtcd_trainer_course
- `rows`: 82392
- `val_coverage`: 0.999
- `join_keys`: ['trainer', 'course']
- `leakage_risk`: NO_DATE_BOUNDARY
- `lane`: SHADOW_ONLY
- `note`: All-time cumulative stats, no cutoff date. Lab experiment only.

### jtcd_jockey_course
- `rows`: 75113
- `val_coverage`: 0.999
- `join_keys`: ['jockey', 'course']
- `leakage_risk`: NO_DATE_BOUNDARY
- `lane`: SHADOW_ONLY
- `note`: All-time cumulative stats, no cutoff date. Lab experiment only.

### rpdc
- `lane`: ALREADY_IN_MODEL
- `cols`: ['setup_run_flag', 'cash_run_flag', 'release_window_score', 'quiet_run_score']

### intl_lagged
- `rows`: 1702741
- `val_coverage`: 0.567
- `safe_cols`: ['prev_or_num', 'max_or_num_last3', 'avg_or_num_last3', 'days_since_last_run', 'starts_last_90', 'course_prior_runs', 'course_prior_wr', 'dist_prior_runs', 'dist_prior_wr']
- `rpr_violation`: False
- `null_rates`: {'prev_or_num': 0.451, 'max_or_num_last3': 0.43, 'avg_or_num_last3': 0.43, 'days_since_last_run': 0.115, 'starts_last_90': 0.0, 'course_prior_runs': 0.0, 'course_prior_wr': 0.0, 'dist_prior_runs': 0.0, 'dist_prior_wr': 0.0}
- `lane`: KEEP_MODEL
- `note`: Lagged per-race historical OR/course/dist stats. Temporally safe.

### market
- `cols`: ['sp_dec', 'log_sp', 'implied_prob', 'sp_rank', 'is_fav']
- `val_coverage`: 0.993
- `lane`: MARKET_ONLY
- `note`: Same-race morning odds. Not for morning model.

### rp_context
- `available`: ['comment (raw text)']
- `lane`: ARCHIVE_ONLY
- `note`: No parsed tip/spotlight columns found. Raw comment text only.