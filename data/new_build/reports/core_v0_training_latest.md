# Core V0 Training Report
Generated: 2026-05-25T21:49:20.404017Z

## Safety
- RPR violation: **False** (must be False)
- SP in features: **False** (must be False for morning model)
- Leakage check: **PASS**
- `velo_scoring_allowed`: **False**

## Model
- Type: LightGBM
- Features: 17

## Validation Metrics
| Metric | Core V0 | OR-Rank Baseline | Lift |
|---|---|---|---|
| AUC | 0.6735 | — | — |
| Brier | 0.0861 | — | — |
| SR (top-1 win rate) | 21.8% | 14.9% | +6.9% |
| Frame rate (top-3 contains winner) | 50.3% | 40.1% | +10.2% |
| Races evaluated | 11,650 | | |

## Features
- `dist_f`
- `going_code`
- `is_aw`
- `field_size`
- `draw_num`
- `draw_pct`
- `age_num`
- `wgt_lbs`
- `or_vs_field`
- `release_window_score`
- `going_fit_score`
- `distance_fit_score`
- `quiet_run_score`
- `trainer_timing_score`
- `jockey_switch_intent`
- `setup_run_flag`
- `cash_run_flag`