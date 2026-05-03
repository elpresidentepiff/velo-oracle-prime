# RACING_API_ANALYSIS_V1 Offline Weight Lab — v2 (Phase 4B)

> **RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK**
> Aggregate lifetime stats with no historical cut-off.
> Do NOT treat as forward-tested evidence.

Run at: `2026-04-30T10:16:43.376645Z`

## A. Files Changed

- `scripts/racing_api_weight_lab.py`

## B. Syntax Checks: PASS

## C. Distance Coverage Fix

| | Before | After |
|---|---|---|
| trainer_distance coverage | 0% | 62.5% |
| jockey_distance coverage | 0% | 61.5% |
| distance_f values resolved | — | 77/77 (100.0%) |

Normalization added: `normalize_distance_f_to_furlongs: ≤40→furlongs, 41-500→÷10, >500→÷220`

## D. Matched-Subset Lift Table

> For each scenario: baseline = all rows with feature present. enriched = top 50% by shadow score.
> Controls for selection bias — tests within-subset discriminative power.

| Scenario | n | base SR | enr SR | SR delta | base ROI | enr ROI | ROI delta |
|---|---|---|---|---|---|---|---|
| A_connection_only | 763 | 0.2267 | 0.2861 | +0.0594 | -0.1201 | -0.0268 | +0.0933 |
| B_course_only | 725 | 0.2083 | 0.2873 | +0.0790 | -0.1834 | -0.0269 | +0.1565 |
| C_distance_only | 917 | 0.2050 | 0.2795 | +0.0745 | -0.2048 | 0.0373 | +0.2421 |
| D_course_distance | 718 | 0.2103 | 0.3092 | +0.0989 | -0.1754 | 0.0827 | +0.2581 |
| E_connection_course | 595 | 0.2303 | 0.3266 | +0.0963 | -0.0892 | 0.1382 | +0.2274 |
| F_connection_distance | 756 | 0.2275 | 0.3254 | +0.0979 | -0.1162 | 0.0903 | +0.2065 |
| G_all_enriched | 592 | 0.2314 | 0.3277 | +0.0963 | -0.0845 | 0.1420 | +0.2265 |

## E. Leakage Status

> **RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK**

## F. Shadow Score Formulas (NOT wired into scoring)

| Score | Formula | Status |
|---|---|---|
| `racing_api_connection_shadow_score` | 0.6 * mean(win_pct signals available) + 0.4 * mean(ae_ratio signals available) | NOT_WIRED |
| `racing_api_course_shadow_score` | 0.6 * mean(win_pct signals available) + 0.4 * mean(ae_ratio signals available) | NOT_WIRED |
| `racing_api_distance_shadow_score` | 0.6 * mean(win_pct signals available) + 0.4 * mean(ae_ratio signals available) | NOT_WIRED |
| `racing_api_enrichment_shadow_score` | 0.6 * mean(all win_pct signals available) + 0.4 * mean(all ae_ratio signals available) | NOT_WIRED |

> Minimum runners/rides per entry: 10

## G. Weight Recommendation

| Analyzer | Current Weight | Verdict |
|---|---|---|
| connections_analyzer | 25% | split_shadow |
| course_distance_analyzer | 20% | split_shadow |

> Do not replace current 25% / 20% weights. Introduce Racing API shadow enrichment score alongside existing analyzer score. Forward-test shadow period required before any weight migration.

## H. Confidence: strong

## I. Governance Confirmation

| Rule | Status |
|---|---|
| live_scoring | NO CHANGE |
| model_probabilities | NO CHANGE |
| sqpe | NO CHANGE |
| playbook_e | STILL PAUSED |
| execution_router | NO CHANGE |
| staking | STILL OFF |
| telegram_betting_alerts | STILL OFF |
| production_feature_wiring | NOT APPLIED |

## Feature Coverage (v2)

| Feature Group | Coverage % |
|---|---|
| jockey_course | 48.1% |
| jockey_distance | 61.5% |
| jockey_trainer | 55.0% |
| trainer_course | 49.0% |
| trainer_distance | 62.5% |
| trainer_jockey | 41.1% |

## Baseline Metrics

| Metric | Value |
|---|---|
| n | 1388 |
| strike_rate | 0.2024 |
| frame_rate | 0.4827 |
| flat_pnl | -563.55 |
| roi | -0.406 |
| brier_score | 0.1583 |
| log_loss | 0.5628 |

## Top Correlations

| Feature | n | Coverage | Correlation |
|---|---|---|---|
| trainer_course_win_pct | 680 | 49.0% | 0.2896 |
| jockey_course_win_pct | 668 | 48.1% | 0.2506 |
| trainer_distance_win_pct | 867 | 62.5% | 0.2415 |
| jockey_trainer_win_pct | 763 | 55.0% | 0.2246 |
| trainer_jockey_win_pct | 571 | 41.1% | 0.2149 |

## Recommendation Case: A

> Shadow signal shows positive within-subset discriminative power. Propose forward-test shadow logging period before any weight change.

## Current Analyzer Weights (unchanged)

| Analyzer | Current Weight |
|---|---|
| connections_analyzer | 25% |
| course_distance_analyzer | 20% |
