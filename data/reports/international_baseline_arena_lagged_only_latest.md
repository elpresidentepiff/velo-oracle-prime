# International Baseline Arena — Lagged Features Only

**Generated:** 2026-05-23T21:57:18.753379+00:00
**Method:** LAGGED_ONLY — current-race RPR/OR/TS entirely excluded
**Temporal split:** Train 2015-2022 | Valid 2023 | Test 2024-2025

---

## Why Lagged-Only Arena

The safe arena produced AUC=0.90-0.96 with current-race ratings (rpr_num, or_num, etc.).
The co-founder's question: are those ratings available BEFORE the race?

This arena bans all current-race rating fields entirely. It uses only:
- Previous run's ratings (prev_rpr_num, prev_or_num, prev_ts_num)
- Rolling stats over last 3 runs (max, avg)
- Static race attributes (draw, distance, weight, going)
- Historical course/distance win rates (computed with strict lag)

**If this arena achieves strong AUC/SR: the signal exists in pre-race-verifiable data.**
**If AUC collapses dramatically: the current-race ratings were doing the work (and need timestamp verification).**

---

## Summary Table

| Pack | Test | Fav SR | Prev-RPR SR | Best AUC | Best SR | >Fav | Verdict |
|---|---|---|---|---|---|---|---|
| HK_SHA_TIN_V1 | 9,766 | 34.2% | 17.5% | 0.7005 | 22.9% | NO | **NEEDS_FEATURE_ENGINEERING** |
| HK_HAPPY_VALLEY_V1 | 5,832 | 26.7% | 15.7% | 0.6619 | 20.3% | NO | **NEEDS_FEATURE_ENGINEERING** |
| FR_CHANTILLY_V1 | 6,875 | 29.2% | 20.0% | 0.6449 | 17.8% | NO | **NEEDS_FEATURE_ENGINEERING** |
| FR_FLAT_CORE | 19,661 | 29.2% | 18.6% | 0.6457 | 18.5% | NO | **NEEDS_FEATURE_ENGINEERING** |
| FR_AUTEUIL_JUMPS_V1 | 3,927 | 29.6% | 18.5% | 0.6399 | 21.2% | NO | **NEEDS_FEATURE_ENGINEERING** |

---

## Pack Detail

### HK_SHA_TIN_V1
Lagged features (19): `prev_rpr_num, max_rpr_num_last3, avg_rpr_num_last3, prev_or_num, max_or_num_last3, avg_or_num_last3, days_since_last_run, course_prior_runs, course_prior_wr, dist_prior_runs, dist_prior_wr, draw_num, draw_pct, field_size, dist_f, going_code, wgt_lbs, age_num, is_aw`

Fav SR: 34.2% | Prev-RPR SR: 17.5%

- logistic_regression: SR=21.8% AUC=0.6708 Brier=0.0719 | Top: 
- lightgbm: SR=22.9% AUC=0.7005 Brier=0.0708 | Top: prev_rpr_num, avg_rpr_num_last3, avg_or_num_last3

**Lagged Verdict: NEEDS_FEATURE_ENGINEERING**

### HK_HAPPY_VALLEY_V1
Lagged features (18): `prev_rpr_num, max_rpr_num_last3, avg_rpr_num_last3, prev_or_num, max_or_num_last3, avg_or_num_last3, days_since_last_run, course_prior_runs, course_prior_wr, dist_prior_runs, dist_prior_wr, draw_num, draw_pct, field_size, dist_f, going_code, wgt_lbs, age_num`

Fav SR: 26.7% | Prev-RPR SR: 15.7%

- logistic_regression: SR=19.0% AUC=0.6575 Brier=0.0781 | Top: 
- lightgbm: SR=20.3% AUC=0.6619 Brier=0.0782 | Top: prev_rpr_num, avg_or_num_last3, avg_rpr_num_last3

**Lagged Verdict: NEEDS_FEATURE_ENGINEERING**

### FR_CHANTILLY_V1
Lagged features (16): `prev_rpr_num, max_rpr_num_last3, avg_rpr_num_last3, prev_ts_num, max_ts_num_last3, avg_ts_num_last3, days_since_last_run, starts_last_90, draw_num, draw_pct, field_size, dist_f, going_code, wgt_lbs, age_num, is_aw`

Fav SR: 29.2% | Prev-RPR SR: 20.0%

- logistic_regression: SR=17.5% AUC=0.6449 Brier=0.0758 | Top: 
- lightgbm: SR=17.8% AUC=0.6435 Brier=0.0759 | Top: wgt_lbs, days_since_last_run, avg_rpr_num_last3

**Lagged Verdict: NEEDS_FEATURE_ENGINEERING**

### FR_FLAT_CORE
Lagged features (16): `prev_rpr_num, max_rpr_num_last3, avg_rpr_num_last3, prev_ts_num, max_ts_num_last3, avg_ts_num_last3, days_since_last_run, starts_last_90, draw_num, draw_pct, field_size, dist_f, going_code, wgt_lbs, age_num, is_aw`

Fav SR: 29.2% | Prev-RPR SR: 18.6%

- logistic_regression: SR=18.3% AUC=0.6382 Brier=0.0779 | Top: 
- lightgbm: SR=18.5% AUC=0.6457 Brier=0.0777 | Top: days_since_last_run, wgt_lbs, prev_rpr_num

**Lagged Verdict: NEEDS_FEATURE_ENGINEERING**

### FR_AUTEUIL_JUMPS_V1
Lagged features (9): `prev_rpr_num, max_rpr_num_last3, avg_rpr_num_last3, days_since_last_run, field_size, dist_f, going_code, wgt_lbs, age_num`

Fav SR: 29.6% | Prev-RPR SR: 18.5%

- logistic_regression: SR=21.2% AUC=0.6399 Brier=0.0855 | Top: 
- lightgbm: SR=18.9% AUC=0.6214 Brier=0.0859 | Top: field_size, avg_rpr_num_last3, days_since_last_run

**Lagged Verdict: NEEDS_FEATURE_ENGINEERING**


---

## Interpretation

- **SAFE_SHADOW_CANDIDATE**: Lagged features achieve AUC ≥ 0.65 and beat favourite.
  Current-race ratings not required. Production use viable with lagged pipeline.
- **NEEDS_FEATURE_ENGINEERING**: Some signal, but needs additional pre-race features.
- **TIMESTAMP_UNPROVEN_HOLD**: AUC too weak with lagged-only — investigate whether
  current-race ratings are truly pre-race before allowing their use.

---

```
LAGGED_ARENA_STATUS: see verdict per pack
CURRENT_RACE_RATINGS: BANNED_FROM_THIS_ARENA
MIGRATION_STATUS: NOT_RUN
WORKER_STATUS: BLOCKED
```
