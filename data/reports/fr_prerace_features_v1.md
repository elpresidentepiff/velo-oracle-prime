# FR Pre-Race Features V1

**Generated:** 2026-05-23T22:47:02.785798+00:00
**Rows:** 174,329
**Columns:** 41

---

## Provenance Guarantee

All RPR/TS features use prior-run data only. Same-race RPR/TS are POST_RACE_LEAKAGE_CONFIRMED for FR (winner_max_rate 70-77%). Going, distance, race type are pre-race race attributes. Class_num is 0% in FR — future enrichment required from France Galop or PMU.

---

## Feature Coverage

| Feature | Coverage |
|---|---|
| lagged_rpr_last1 | 72.64% |
| lagged_rpr_last3_avg | 78.16% |
| lagged_rpr_last3_max | 78.16% |
| lagged_ts_last1 | 48.83% |
| lagged_ts_last3_avg | 59.69% |
| prev_finish_pos | 77.40% |
| last3_finish_avg | 79.06% |
| days_since_last_run | 79.71% |
| starts_last_90 | 100.00% |
| prior_course_runs | 100.00% |
| prior_course_win_rate | 61.37% |
| prior_distance_runs | 100.00% |
| prior_distance_win_rate | 65.73% |
| going_is_fast | 100.00% |
| going_is_good | 100.00% |
| going_is_soft | 100.00% |
| is_hurdle | 100.00% |
| is_chase | 100.00% |
| is_flat_code | 100.00% |
| penetrometer_available | 100.00% |
| quintet_plus_available | 100.00% |
| class_proxy_available | 100.00% |
| field_avg_prev_rpr | 95.06% |
| field_std_prev_rpr | 93.98% |
| rpr_rank_lagged | 100.00% |
| race_competitiveness_pre | 95.06% |

---

## Banned Features (Post-Race Leakage Confirmed)

- rpr_num
- ts_num
- or_num
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

## Future Enrichment Gaps (Placeholders)

- **penetrometer**: PMU API (online.turfinfo.api.pmu.fr) — numeric going score. Not in parquet.
- **quintet_plus**: PMU API — Quinté+ race flag. Not in parquet.
- **class_proxy**: France Galop Valeur rating — 0% coverage in current parquet.

---

```
FR_PRERACE_FEATURES_V1_STATUS: BUILT
SAME_RACE_RPR_TS: BANNED (POST_RACE_LEAKAGE_CONFIRMED)
OR: EXCLUDED (0% coverage in FR)
PENETROMETER: PLACEHOLDER (future PMU enrichment)
QUINTET_PLUS: PLACEHOLDER (future PMU enrichment)
OUTPUT: data/features/fr_prerace_features_v1.parquet
```
