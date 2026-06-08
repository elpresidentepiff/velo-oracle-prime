# International Pre-Race Feature Safety Audit

**Generated:** 2026-05-23T22:53:27.578077+00:00

---

## Verdict Summary

| Verdict | Count |
|---|---|
| DROP | 2 |
| FUTURE_ENRICHMENT | 3 |
| PRE_RACE_SAFE | 49 |
| REVIEW_REQUIRED | 1 |

---

## Feature Detail

| Pack | Feature | Null Rate | Winner-Max | Verdict |
|---|---|---|---|---|
| HK | prev_rpr_num | 7.6% | 18.28% | PRE_RACE_SAFE |
| HK | last3_rpr_avg | 6.6% | 15.28% | PRE_RACE_SAFE |
| HK | prev_or_num | 7.8% | 10.24% | PRE_RACE_SAFE |
| HK | last3_or_avg | 7.3% | 7.91% | PRE_RACE_SAFE |
| HK | prev_finish_pos | 6.5% | 4.16% | PRE_RACE_SAFE |
| HK | last3_finish_avg | 6.4% | 2.46% | PRE_RACE_SAFE |
| HK | days_since_last_run | 6.4% | 10.65% | PRE_RACE_SAFE |
| HK | starts_last_90 | 0.0% | 20.27% | PRE_RACE_SAFE |
| HK | course_prior_runs | 0.0% | 9.21% | PRE_RACE_SAFE |
| HK | course_prior_wr | 11.1% | 21.71% | PRE_RACE_SAFE |
| HK | distance_prior_runs | 0.0% | 9.67% | PRE_RACE_SAFE |
| HK | distance_prior_wr | 13.4% | 20.88% | PRE_RACE_SAFE |
| HK | prev_class_num | 10.7% | 70.64% | **DROP** |
| HK | class_move_direction | 12.2% | 54.18% | PRE_RACE_SAFE |
| HK | class_drop_flag | 10.7% | 60.44% | **REVIEW_REQUIRED** |
| HK | class_rise_flag | 10.7% | 75.58% | **DROP** |
| HK | prior_class_win_rate | 16.2% | 18.16% | PRE_RACE_SAFE |
| HK | prior_class_place_rate | 16.2% | 21.73% | PRE_RACE_SAFE |
| HK | draw_inside_flag | 0.0% | 33.98% | PRE_RACE_SAFE |
| HK | draw_outside_flag | 0.0% | 28.66% | PRE_RACE_SAFE |
| HK | draw_win_rate_lagged | 0.4% | 35.27% | PRE_RACE_SAFE |
| HK | draw_place_rate_lagged | 0.4% | 35.01% | PRE_RACE_SAFE |
| HK | field_avg_prev_rpr | 0.5% | N/A | PRE_RACE_SAFE |
| HK | field_std_prev_rpr | 0.7% | N/A | PRE_RACE_SAFE |
| HK | field_avg_prev_or | 1.3% | N/A | PRE_RACE_SAFE |
| HK | rpr_rank_lagged | 0.0% | 7.39% | PRE_RACE_SAFE |
| HK | or_rank_lagged | 0.0% | 13.74% | PRE_RACE_SAFE |
| HK | rating_consensus_lagged | 0.0% | 15.10% | PRE_RACE_SAFE |
| HK | race_competitiveness_pre | 1.3% | N/A | PRE_RACE_SAFE |
| FR | lagged_rpr_last1 | 27.4% | 25.98% | PRE_RACE_SAFE |
| FR | lagged_rpr_last3_avg | 21.8% | 23.05% | PRE_RACE_SAFE |
| FR | lagged_rpr_last3_max | 21.8% | 23.24% | PRE_RACE_SAFE |
| FR | lagged_ts_last1 | 51.2% | 23.37% | PRE_RACE_SAFE |
| FR | lagged_ts_last3_avg | 40.3% | 19.58% | PRE_RACE_SAFE |
| FR | prev_finish_pos | 22.6% | 9.29% | PRE_RACE_SAFE |
| FR | last3_finish_avg | 20.9% | 7.92% | PRE_RACE_SAFE |
| FR | days_since_last_run | 20.3% | 11.78% | PRE_RACE_SAFE |
| FR | starts_last_90 | 0.0% | 27.54% | PRE_RACE_SAFE |
| FR | prior_course_runs | 0.0% | 24.11% | PRE_RACE_SAFE |
| FR | prior_course_win_rate | 38.6% | 37.47% | PRE_RACE_SAFE |
| FR | prior_distance_runs | 0.0% | 22.96% | PRE_RACE_SAFE |
| FR | prior_distance_win_rate | 34.3% | 35.04% | PRE_RACE_SAFE |
| FR | going_is_fast | 0.0% | N/A | PRE_RACE_SAFE |
| FR | going_is_good | 0.0% | N/A | PRE_RACE_SAFE |
| FR | going_is_soft | 0.0% | N/A | PRE_RACE_SAFE |
| FR | is_hurdle | 0.0% | N/A | PRE_RACE_SAFE |
| FR | is_chase | 0.0% | N/A | PRE_RACE_SAFE |
| FR | is_flat_code | 0.0% | N/A | PRE_RACE_SAFE |
| FR | penetrometer_available | 0.0% | N/A | FUTURE_ENRICHMENT |
| FR | quintet_plus_available | 0.0% | N/A | FUTURE_ENRICHMENT |
| FR | class_proxy_available | 0.0% | N/A | FUTURE_ENRICHMENT |
| FR | field_avg_prev_rpr | 4.9% | N/A | PRE_RACE_SAFE |
| FR | field_std_prev_rpr | 6.0% | N/A | PRE_RACE_SAFE |
| FR | rpr_rank_lagged | 0.0% | 25.87% | PRE_RACE_SAFE |
| FR | race_competitiveness_pre | 4.9% | N/A | PRE_RACE_SAFE |

---

## Dominance Test

Winner-max rate thresholds (same as rating provenance audit):
- > 70%: DROP (leakage suspected)
- 55–70%: REVIEW_REQUIRED
- < 55%: PRE_RACE_SAFE

---

```
SAFETY_AUDIT_STATUS: COMPLETE
LEAKAGE_THRESHOLD: 0.70
REVIEW_THRESHOLD: 0.55
```
