# International Rating Dominance Audit

**Generated:** 2026-05-23T21:27:40.787267+00:00

---

## Test Logic

If a rating is **post-race** (awarded based on performance in THIS race):
- The winner earns the highest rating in that race
- Winner max-rating rate: **> 70%**

If a rating is **pre-race** (the rating the horse brought INTO the race):
- Top-rated horse wins at roughly its historical rate (~40-50%)
- Winner max-rating rate: **~40-50% (approximately equal to top-pick SR)**

| Threshold | Verdict |
|---|---|
| Winner max-rating > 70% | POST_RACE_LEAKAGE_SUSPECTED |
| Winner max-rating 55-70% | TIMESTAMP_UNKNOWN |
| Winner max-rating 40-55% | PRE_RACE_SAFE |

---

## Results

| Pack | RPR winner-max | OR winner-max | TS winner-max | Fav SR | Verdict |
|---|---|---|---|---|---|
| HK_SHA_TIN_V1 | 46.37% | 17.77% | N/A | 32.60% | **PRE_RACE_SAFE** |
| HK_HAPPY_VALLEY_V1 | 42.24% | 12.56% | N/A | 28.93% | **PRE_RACE_SAFE** |
| FR_CHANTILLY_V1 | 70.20% | N/A | 76.83% | 29.40% | **POST_RACE_LEAKAGE_SUSPECTED** |
| FR_FLAT_CORE | 70.19% | N/A | 75.31% | 28.95% | **POST_RACE_LEAKAGE_SUSPECTED** |
| FR_AUTEUIL_JUMPS_V1 | 72.56% | N/A | N/A | 31.55% | **POST_RACE_LEAKAGE_SUSPECTED** |

---

## Expected Values

- **Post-race RPR**: winner max rate > 70-80% (RPR is awarded based on winning performance)
- **Pre-race RPR (historical)**: winner max rate ~= RPR-only top-pick SR (~40-50%)
- **Random**: winner max rate = 1 / avg_field_size (~8-10%)

---

```
DOMINANCE_AUDIT_STATUS: see per-pack above
POST_RACE_THRESHOLD: > 0.70
PRE_RACE_EXPECTED: ~0.40-0.50
```
