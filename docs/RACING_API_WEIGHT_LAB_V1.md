# RACING_API_ANALYSIS_V1 Offline Weight Lab

> **RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK**
> The Racing API analysis tables contain aggregate lifetime stats with no historical cut-off.
> Results may overstate live-ready lift. Do NOT treat as forward-tested evidence.

Run at: `2026-04-30T10:05:26.974939Z`

## A. Files Created

- `scripts/racing_api_weight_lab.py`
- `supabase/migrations/racing_api_analysis_v1.sql`
- `docs/RACING_API_ANALYSIS_V1_LOAD_REPORT.md`
- `docs/RACING_API_WEIGHT_LAB_V1.md`

## C–D. Sample & Date Range

- Sample size: **1388**
- Date range: `2026-03-17` → `2026-04-29`

## E. Feature Coverage

| Feature Group | Coverage % |
|---|---|
| trainer_course | 49.0% |
| jockey_course | 48.1% |
| jockey_trainer | 55.0% |
| trainer_jockey | 33.9% |

## F. Baseline Metrics

| Metric | Value |
|---|---|
| n | 1388 |
| strike_rate | 0.2024 |
| frame_rate | 0.4827 |
| flat_pnl | -563.55 |
| roi | -0.406 |
| brier_score | 0.1583 |
| log_loss | 0.5628 |

## G–H. Scenario Lift Table

| Scenario | n | SR lift | Frame lift | ROI lift |
|---|---|---|---|---|
| D_with_connection_features | 763 | +0.0243 | +0.0180 | +0.2859 |
| E_with_course_distance_features | 725 | +0.0059 | +0.0111 | +0.2226 |
| F_all_racing_api_features | 0 | -0.2024 | -0.4827 | +0.4060 |

## Top Positive Features

| Feature | n | Coverage % | Correlation |
|---|---|---|---|
| trainer_course_win_pct | 680 | 49.0% | 0.2896 |
| jockey_course_win_pct | 668 | 48.1% | 0.2506 |
| trainer_jockey_win_pct | 470 | 33.9% | 0.2503 |
| jockey_trainer_win_pct | 763 | 55.0% | 0.2246 |
| jockey_course_ae | 668 | 48.1% | 0.1598 |

## Top Negative Features

| Feature | n | Coverage % | Correlation |
|---|---|---|---|

## I. Leakage Risk

> **RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK**

## J–K. Recommendation

**Case: A**

> Racing API features show positive ROI and strike-rate lift. Propose new shadow weights — do not activate in production yet.

Confidence: **strong**

## L. Governance Confirmation

| Rule | Status |
|---|---|
| Live scoring unchanged | NO CHANGE |
| Model probabilities unchanged | NO CHANGE |
| SQPE unchanged | NO CHANGE |
| Playbook E | STILL PAUSED |
| Execution Router | NO CHANGE |
| Staking | STILL OFF |
| Telegram betting alerts | STILL OFF |
| Production feature wiring | NOT APPLIED |

## Current Analyzer Weights (unchanged)

| Analyzer | Current Weight |
|---|---|
| connections_analyzer | 25% |
| course_distance_analyzer | 20% |
