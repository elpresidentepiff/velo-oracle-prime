# HK Pre-Race Features V1

**Generated:** 2026-05-23T22:45:02.818979+00:00
**Rows:** 81,533
**Columns:** 45

---

## Provenance Guarantee

All features use prior-run data only. Same-race RPR/OR/TS are banned. Draw stats are computed from races strictly before current race date. Class trajectory uses previous run's class, not current race class as a rating.

---

## Feature Coverage

| Feature | Coverage |
|---|---|
| prev_rpr_num | 92.41% |
| last3_rpr_avg | 93.39% |
| prev_or_num | 92.15% |
| last3_or_avg | 92.70% |
| prev_finish_pos | 93.52% |
| last3_finish_avg | 93.59% |
| days_since_last_run | 93.60% |
| starts_last_90 | 100.00% |
| course_prior_runs | 100.00% |
| course_prior_wr | 88.94% |
| distance_prior_runs | 100.00% |
| distance_prior_wr | 86.63% |
| prev_class_num | 89.29% |
| class_move_direction | 87.79% |
| class_drop_flag | 89.29% |
| class_rise_flag | 89.29% |
| prior_class_win_rate | 83.84% |
| prior_class_place_rate | 83.84% |
| draw_inside_flag | 100.00% |
| draw_outside_flag | 100.00% |
| draw_win_rate_lagged | 99.58% |
| draw_place_rate_lagged | 99.58% |
| field_avg_prev_rpr | 99.48% |
| field_std_prev_rpr | 99.30% |
| field_avg_prev_or | 98.70% |
| rpr_rank_lagged | 100.00% |
| or_rank_lagged | 100.00% |
| rating_consensus_lagged | 100.00% |
| race_competitiveness_pre | 98.70% |

---

## Banned Features (Same-Race / Post-Race)

- rpr_num
- or_num
- ts_num
- rpr_vs_field
- or_vs_field
- sp_dec
- implied_prob
- log_sp
- sp_rank
- pos
- is_fav
- odds_contraction_score
- odds_resilience_score
- decoy_support_flag
- setup_run_flag
- cash_run_flag
- jockey_switch_intent

---

```
HK_PRERACE_FEATURES_V1_STATUS: BUILT
SAME_RACE_RPR_OR_TS: BANNED
DRAW_STATS: LAGGED_BY_DATE
CLASS_TRAJECTORY: LAGGED_BY_RUN
OUTPUT: data/features/hk_prerace_features_v1.parquet
```
