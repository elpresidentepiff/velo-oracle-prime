# International Lagged Rating Features

**Generated:** 2026-05-23T21:45:39.628571+00:00
**Rows:** 1,702,741
**Columns:** 32

---

## Method

For each horse sorted by date, lagged features use only races 0..N-1. Current-race RPR/OR/TS excluded. Static race attributes passed through.

Lagged features use ONLY previous-run data. For race N of a horse:
- `prev_rpr_num` = the rpr_num value from the horse's most recent prior race
- `max_rpr_num_last3` = max rpr_num over the 3 runs before this race
- `avg_rpr_num_last3` = avg rpr_num over the 3 runs before this race
- Same for `or_num` and `ts_num`
- `course_prior_wr` = win rate at this course in ALL prior runs (strict lag)
- `dist_prior_wr` = win rate at this distance band in ALL prior runs (strict lag)

**The current race's rpr_num, or_num, ts_num are NOT used.**

---

## Feature Coverage

| Feature | Coverage |
|---|---|
| prev_rpr_num | 81.20% |
| max_rpr_num_last3 | 86.65% |
| avg_rpr_num_last3 | 86.65% |
| prev_or_num | 54.93% |
| max_or_num_last3 | 56.97% |
| avg_or_num_last3 | 56.97% |
| prev_ts_num | 61.13% |
| max_ts_num_last3 | 72.07% |
| avg_ts_num_last3 | 72.07% |
| days_since_last_run | 88.55% |
| starts_last_90 | 73.52% |
| course_prior_runs | 46.34% |
| course_prior_wr | 15.16% |
| dist_prior_runs | 78.08% |
| dist_prior_wr | 38.44% |

---

```
LAGGED_FEATURES_STATUS: BUILT
CURRENT_RACE_RATINGS: EXCLUDED
OUTPUT: data/features/international_lagged_rating_features.parquet
```
