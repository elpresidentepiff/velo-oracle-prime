# International Arena Sanity Tests

**Generated:** 2026-05-23T20:52:43.792693+00:00

---

## Summary

| Pack | Date Split | Group Split | Shuffle (real/shuffled AUC) | Sanity Verdict |
|---|---|---|---|---|
| HK_SHA_TIN_V1 | CLEAN | CLEAN | real=0.9504 shuf=0.4738 | **SANITY_PASSED** |
| HK_HAPPY_VALLEY_V1 | CLEAN | CLEAN | real=0.9522 shuf=0.5096 | **SANITY_PASSED** |
| FR_CHANTILLY_V1 | CLEAN | CLEAN | real=0.8984 shuf=0.6051 | **MARGINAL_INVESTIGATE** |

---

## Test Descriptions

1. **Date split**: Confirms temporal split — train ≤ 2022, valid 2023, test > 2023
2. **Group split**: Confirms no race_id appears in both train and test
3. **Shuffle test**: Shuffles target labels within races. If model AUC collapses to ~0.50, features are genuine pre-race signals. If AUC stays high, leakage exists.
4. **Ablation**: Tests different feature subsets to identify where the signal comes from

---

## Ablation Results

### HK_SHA_TIN_V1 — Ablation Results
Favourite SR baseline: 34.7%

| Feature Set | AUC | Top-Pick SR | N Races | Features |
|---|---|---|---|---|
| RPR_ONLY | 0.8750 | 44.0% | 832 | rpr_vs_field |
| RPR_AND_OR | 0.9509 | 82.5% | 832 | rpr_vs_field, rpr_num, or_vs_field, or_num |
| RATINGS_ONLY | 0.9509 | 82.5% | 832 | rpr_num, rpr_vs_field, or_num, or_vs_field |
| SAFE_PRE_RACE_ONLY | 0.9443 | 80.0% | 832 | rpr_vs_field, rpr_num, or_vs_field, field_size, draw_num, age_num, dist_f, going_code, wgt_lbs, is_aw, draw_pct |
| NO_FIT_SCORES | 0.9443 | 80.0% | 832 | rpr_vs_field, rpr_num, or_vs_field, field_size, draw_num, age_num, dist_f, going_code, wgt_lbs, is_aw, draw_pct |
| FIT_SCORES_ONLY | 0.6604 | 22.0% | 832 | course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score |

### HK_HAPPY_VALLEY_V1 — Ablation Results
Favourite SR baseline: 26.9%

| Feature Set | AUC | Top-Pick SR | N Races | Features |
|---|---|---|---|---|
| RPR_ONLY | 0.8577 | 39.0% | 521 | rpr_vs_field |
| RPR_AND_OR | 0.9524 | 82.3% | 521 | rpr_vs_field, rpr_num, or_vs_field, or_num |
| RATINGS_ONLY | 0.9524 | 82.3% | 521 | rpr_num, rpr_vs_field, or_num, or_vs_field |
| SAFE_PRE_RACE_ONLY | 0.9437 | 78.9% | 521 | rpr_vs_field, rpr_num, or_vs_field, field_size, draw_num, age_num, dist_f, going_code, wgt_lbs, draw_pct |
| NO_FIT_SCORES | 0.9437 | 78.9% | 521 | rpr_vs_field, rpr_num, or_vs_field, field_size, draw_num, age_num, dist_f, going_code, wgt_lbs, draw_pct |
| FIT_SCORES_ONLY | 0.6207 | 15.4% | 521 | course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score |

### FR_CHANTILLY_V1 — Ablation Results
Favourite SR baseline: 29.4%

| Feature Set | AUC | Top-Pick SR | N Races | Features |
|---|---|---|---|---|
| RPR_ONLY | 0.8628 | 56.8% | 676 | rpr_vs_field |
| RPR_AND_OR | 0.8805 | 58.7% | 676 | rpr_vs_field, rpr_num |
| RATINGS_ONLY | 0.8942 | 62.6% | 676 | rpr_num, rpr_vs_field, ts_num |
| SAFE_PRE_RACE_ONLY | 0.8975 | 63.6% | 676 | rpr_vs_field, rpr_num, field_size, draw_num, age_num, dist_f, going_code, wgt_lbs, is_aw, draw_pct |
| NO_FIT_SCORES | 0.8975 | 63.6% | 676 | rpr_vs_field, rpr_num, field_size, draw_num, age_num, dist_f, going_code, wgt_lbs, is_aw, draw_pct |
| FIT_SCORES_ONLY | 0.5933 | 14.5% | 676 | course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score |


---

## Interpretation

- **SANITY_PASSED**: Shuffle test collapsed AUC. Features are genuine. Investigate why AUC is so high in safe arena.
- **LEAKAGE_CONFIRMED**: AUC barely dropped after shuffle. One or more features encode the outcome.
- **MARGINAL_INVESTIGATE**: Partial AUC collapse. Some signal may be leaking.

---

```
SANITY_STATUS: see above per pack
MIGRATION_STATUS: NOT_RUN
WORKER_STATUS: BLOCKED
```
