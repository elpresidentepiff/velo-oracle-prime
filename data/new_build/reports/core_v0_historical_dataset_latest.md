# Core V0 Historical Dataset
Generated: 2026-05-25T21:38:08.816554Z

## Dataset Size
- **Total rows**: 1,162,031
- **Total races**: 116,111
- **Total horses**: 148,741
- **Date range**: 2015-01-01 → 2025-07-05

## Splits
| Split | Rows | Races |
|---|---|---|
| Train (2015-2023) | 987,511 | 98,686 |
| Val (2024) | 117,299 | 11,650 |
| Test (2025) | 57,221 | 5,775 |

## Leakage Audit
- RPR in features: **False** (must be False)
- SP in features: **False** (must be False for morning model)
- Result: **PASS**

## Target Distribution
- Win rate overall: 10.0%
- Win rate train: 10.0%

## Features Kept
**18 features:**

- `type`
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

## Dropped (>30% null): ['class_num', 'or_num', 'curr_or_minus_last_win_or', 'curr_or_minus_best_or', 'mark_compression_score', 'runs_since_win', 'runs_since_place', 'course_fit_score']