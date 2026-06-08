# International Baseline Arena — Safe Features Only

**Generated:** 2026-05-23T20:50:25.723009+00:00
**Method:** SAFE_FEATURES_ONLY — confirmed pre-race columns, no fit scores, no SP-derived
**Temporal split:** Train 2015-2022 | Valid 2023 | Test 2024-2025

---

## Why Safe-Only Arena

The first baseline arena produced AUC=0.95 and SR=80%+, which is suspicious for horse racing.
This arena uses ONLY features that are definitively available before the race starts:
pre-race ratings (RPR, OR, TS), static race attributes (draw, distance, weight, going).

Fit scores (course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score)
are EXCLUDED until their time-gating can be confirmed in source code.

---

## Summary Table

| Pack | Test | Fav SR | RPR SR | Best AUC | Best SR | >Fav | Verdict |
|---|---|---|---|---|---|---|---|
| HK_SHA_TIN_V1 | 10,451 | 34.7% | 44.1% | 0.9536 | 81.8% | YES | **SAFE_SHADOW_CANDIDATE** |
| HK_HAPPY_VALLEY_V1 | 5,987 | 26.9% | 40.1% | 0.9630 | 86.6% | YES | **SAFE_SHADOW_CANDIDATE** |
| FR_CHANTILLY_V1 | 8,009 | 29.4% | 58.7% | 0.9103 | 70.1% | YES | **SAFE_SHADOW_CANDIDATE** |
| FR_FLAT_CORE | 23,225 | 29.7% | 59.2% | 0.9071 | 69.7% | YES | **SAFE_SHADOW_CANDIDATE** |
| FR_AUTEUIL_JUMPS_V1 | 4,810 | 27.5% | 62.4% | 0.9054 | 68.7% | YES | **SAFE_SHADOW_CANDIDATE** |

---

## Pack Detail

### HK_SHA_TIN_V1
Safe features (12): `rpr_num, rpr_vs_field, field_size, draw_num, draw_pct, dist_f, going_code, wgt_lbs, age_num, is_aw, or_num, or_vs_field`

Fav SR: 34.7% | RPR SR: 44.1%

- logistic_regression: SR=69.8% AUC=0.9091 Brier=0.0554 | Top: 
- lightgbm: SR=81.8% AUC=0.9536 Brier=0.0396 | Top: rpr_num, rpr_vs_field, or_vs_field

**Safe Verdict: SAFE_SHADOW_CANDIDATE**

### HK_HAPPY_VALLEY_V1
Safe features (11): `rpr_num, rpr_vs_field, field_size, draw_num, draw_pct, dist_f, going_code, wgt_lbs, age_num, or_num, or_vs_field`

Fav SR: 26.9% | RPR SR: 40.1%

- logistic_regression: SR=86.6% AUC=0.9630 Brier=0.0437 | Top: 
- lightgbm: SR=80.4% AUC=0.9558 Brier=0.0443 | Top: or_vs_field, rpr_vs_field, rpr_num

**Safe Verdict: SAFE_SHADOW_CANDIDATE**

### FR_CHANTILLY_V1
Safe features (11): `rpr_num, rpr_vs_field, field_size, draw_num, draw_pct, dist_f, going_code, wgt_lbs, age_num, is_aw, ts_num`

Fav SR: 29.4% | RPR SR: 58.7%

- logistic_regression: SR=64.5% AUC=0.8238 Brier=0.0567 | Top: 
- lightgbm: SR=70.1% AUC=0.9103 Brier=0.0536 | Top: rpr_vs_field, rpr_num, wgt_lbs

**Safe Verdict: SAFE_SHADOW_CANDIDATE**

### FR_FLAT_CORE
Safe features (11): `rpr_num, rpr_vs_field, field_size, draw_num, draw_pct, dist_f, going_code, wgt_lbs, age_num, is_aw, ts_num`

Fav SR: 29.7% | RPR SR: 59.2%

- logistic_regression: SR=64.0% AUC=0.8242 Brier=0.0595 | Top: 
- lightgbm: SR=69.7% AUC=0.9071 Brier=0.0560 | Top: rpr_vs_field, wgt_lbs, rpr_num

**Safe Verdict: SAFE_SHADOW_CANDIDATE**

### FR_AUTEUIL_JUMPS_V1
Safe features (7): `rpr_num, rpr_vs_field, field_size, dist_f, going_code, wgt_lbs, age_num`

Fav SR: 27.5% | RPR SR: 62.4%

- logistic_regression: SR=68.7% AUC=0.8960 Brier=0.0649 | Top: 
- lightgbm: SR=66.2% AUC=0.9054 Brier=0.0641 | Top: rpr_num, rpr_vs_field, wgt_lbs

**Safe Verdict: SAFE_SHADOW_CANDIDATE**


---

## Excluded Feature Categories

- SP/final_market: sp_dec, log_sp, implied_prob, sp_rank, is_fav
- Odds_movement: odds_resilience_score, odds_contraction_score
- RPDC_tags: decoy_support_flag, setup_run_flag, cash_run_flag
- Fit_scores_unconfirmed: course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score
- OR_history_unconfirmed: mark_compression_score, class_num (42% null), curr_or_minus_*
- Position: pos

---

## Verdict Criteria

- **SAFE_SHADOW_CANDIDATE**: AUC ≥ 0.65 and beats favourite — genuine pre-race signal confirmed
- **NEEDS_FEATURE_ENGINEERING**: AUC ≥ 0.58 — some signal, needs more features
- **WEAK_SIGNAL_MORE_FEATURES_NEEDED**: AUC < 0.58 — not sufficient for shadow lane
- **LEAKAGE_CONFIRMED**: Would appear if model still achieves very high AUC with only safe features (unexpected)

---

```
SAFE_ARENA_STATUS: see verdict per pack above
MIGRATION_STATUS: NOT_RUN
WORKER_STATUS: BLOCKED
FIT_SCORES_STATUS: EXCLUDED_PENDING_TIME_GATE_REVIEW
```
