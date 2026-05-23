# International Baseline Arena V1

**Generated:** 2026-05-23T19:45:56.090607+00:00
**Method:** Temporal split — Train 2015-2022, Valid 2023, Test 2024-2025
**Status:** OFFLINE ONLY — no DB, no scoring, no live state

---

## Summary Table

| Pack | Total | Test | Fav SR | RPR SR | Best Model SR | Best AUC | >Fav | >RPR | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| HK_SHA_TIN_V1 | 50,976 | 10,451 | 34.7% | 44.1% | 81.5% | 0.9541 | YES | YES | **VIABLE_SHADOW_CANDIDATE** |
| HK_HAPPY_VALLEY_V1 | 30,557 | 5,987 | 26.9% | 40.1% | 84.3% | 0.9591 | YES | YES | **VIABLE_SHADOW_CANDIDATE** |
| FR_CHANTILLY_V1 | 47,568 | 8,009 | 29.4% | 58.7% | 64.5% | 0.9072 | YES | YES | **VIABLE_SHADOW_CANDIDATE** |
| FR_FLAT_CORE | 142,352 | 23,225 | 29.7% | 59.2% | 68.6% | 0.9076 | YES | YES | **VIABLE_SHADOW_CANDIDATE** |
| FR_AUTEUIL_JUMPS_V1 | 31,977 | 4,810 | 27.5% | 62.4% | 67.3% | 0.9051 | YES | YES | **VIABLE_SHADOW_CANDIDATE** |

---

## Pack Detail


### HK_SHA_TIN_V1
Train: 36,975 | Valid: 3,550 | Test: 10,451  
Features: 20 | Leakage: CLEAN  
Favourite SR: 34.7% | Best-RPR SR: 44.1%

- logistic_regression: SR=78.4% AUC=0.9225 Brier=0.0453 Cal=0.055 | Beats Fav=True | Top features: 
- random_forest: SR=61.5% AUC=0.9177 Brier=0.0534 Cal=0.1537 | Beats Fav=True | Top features: rpr_vs_field, rpr_num, or_vs_field
- lightgbm: SR=81.5% AUC=0.9541 Brier=0.0395 Cal=0.043 | Beats Fav=True | Top features: rpr_num, rpr_vs_field, or_num

**Verdict: VIABLE_SHADOW_CANDIDATE**

### HK_HAPPY_VALLEY_V1
Train: 22,103 | Valid: 2,467 | Test: 5,987  
Features: 19 | Leakage: CLEAN  
Favourite SR: 26.9% | Best-RPR SR: 40.1%

- logistic_regression: SR=84.3% AUC=0.9591 Brier=0.0444 Cal=0.0737 | Beats Fav=True | Top features: 
- random_forest: SR=60.7% AUC=0.9261 Brier=0.0586 Cal=0.1968 | Beats Fav=True | Top features: rpr_vs_field, rpr_num, or_num
- lightgbm: SR=80.6% AUC=0.9548 Brier=0.0441 Cal=0.0367 | Beats Fav=True | Top features: rpr_num, rpr_vs_field, or_vs_field

**Verdict: VIABLE_SHADOW_CANDIDATE**

### FR_CHANTILLY_V1
Train: 34,519 | Valid: 5,040 | Test: 8,009  
Features: 17 | Leakage: CLEAN  
Favourite SR: 29.4% | Best-RPR SR: 58.7%

- logistic_regression: SR=63.0% AUC=0.8237 Brier=0.0568 Cal=0.0256 | Beats Fav=True | Top features: 
- random_forest: SR=64.3% AUC=0.8746 Brier=0.0582 Cal=0.1556 | Beats Fav=True | Top features: rpr_vs_field, rpr_num, ts_num
- lightgbm: SR=64.5% AUC=0.9072 Brier=0.0546 Cal=0.0392 | Beats Fav=True | Top features: rpr_vs_field, rpr_num, wgt_lbs

**Verdict: VIABLE_SHADOW_CANDIDATE**

### FR_FLAT_CORE
Train: 104,863 | Valid: 14,264 | Test: 23,225  
Features: 17 | Leakage: CLEAN  
Favourite SR: 29.7% | Best-RPR SR: 59.2%

- logistic_regression: SR=63.8% AUC=0.8237 Brier=0.0595 Cal=0.0246 | Beats Fav=True | Top features: 
- random_forest: SR=66.3% AUC=0.8691 Brier=0.0608 Cal=0.1561 | Beats Fav=True | Top features: rpr_vs_field, rpr_num, ts_num
- lightgbm: SR=68.6% AUC=0.9076 Brier=0.0560 Cal=0.0248 | Beats Fav=True | Top features: rpr_vs_field, wgt_lbs, rpr_num

**Verdict: VIABLE_SHADOW_CANDIDATE**

### FR_AUTEUIL_JUMPS_V1
Train: 24,137 | Valid: 3,030 | Test: 4,810  
Features: 13 | Leakage: CLEAN  
Favourite SR: 27.5% | Best-RPR SR: 62.4%

- logistic_regression: SR=67.3% AUC=0.8981 Brier=0.0648 Cal=0.093 | Beats Fav=True | Top features: 
- random_forest: SR=60.2% AUC=0.8779 Brier=0.0682 Cal=0.1506 | Beats Fav=True | Top features: rpr_vs_field, rpr_num, field_size
- lightgbm: SR=64.2% AUC=0.9051 Brier=0.0643 Cal=0.1544 | Beats Fav=True | Top features: rpr_vs_field, rpr_num, field_size

**Verdict: VIABLE_SHADOW_CANDIDATE**


---

## Methodology

**Feature sets:** Non-leakage fundamental features only. No SP/odds-derived features.
OR excluded from FR packs (0% coverage). TS excluded from HK and Auteuil (0% coverage).

**Verdict criteria:**
- VIABLE_SHADOW_CANDIDATE: AUC ≥ 0.65 and beats favourite baseline
- NEEDS_FEATURE_ENGINEERING: AUC ≥ 0.58 (promising signal, needs local features)
- DATA_GAP: insufficient data or features

**Governance:**
```
No Supabase writes.
No production pipeline changes.
No scoring changes.
Research only.
```
