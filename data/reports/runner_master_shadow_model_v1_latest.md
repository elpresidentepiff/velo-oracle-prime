# Runner Master Shadow Model V1
**Generated:** 2026-05-18  
**Governance:** NO_SCORING_CHANGE | NO_MODEL_PROMOTION | NO_ROUTER_CHANGE | NO_STAKING_CHANGE | NO_LIVE_STATE_MUTATION  
**Status:** SHADOW_QUARANTINE — not wired to scoring, router, or staking

---

## Mission
> Can VP + TJ_TOP20 + current_or + last-six scalar trends beat VP alone without using SP?

**Answer: YES — VP + TJ_TOP20 + current_or + last-six scalar trends beat VP alone**

---

## Rolling Date Split
| | |
|---|---|
| Cutoff | 2026-05-04 |
| Train | 805 rows (20.00% WR) |
| Test  | 505 rows (22.38% WR) |
| Train dates | 2026-03-17 → 2026-05-03 |
| Test dates  | 2026-05-04 → 2026-05-17 |

---

## TJ Threshold (Training Set P80)
| | |
|---|---|
| Threshold | 0.1847 |
| TJ_HIGH in train | 99/805 (12.3%) |
| TJ_HIGH in test  | 49/505 (9.7%) |

---

## Model Comparison

| Model | AUC | Top-decile WR | Top-decile lift | Top-decile ROI | Strip ROI | Verdict |
|---|---|---|---|---|---|---|
| VP Baseline | 0.6675 | 43.14% | +0.2076 | +0.0467 | -0.0673 | BASELINE |
| Model A (LogReg) | 0.7006 | 45.10% | +0.2272 | -0.0988 | -0.0496 | **AUC_ONLY** |
| Model B (LightGBM) | 0.6213 | 47.06% | +0.2468 | -0.1780 | -0.0499 | **FAIL** |
| Model C (Ensemble) | 0.6768 | 52.94% | +0.3056 | +0.1186 | -0.0496 | **PASS_QUARANTINE** |

---

## Feature Importance (LightGBM — gain)

| Feature | Gain |
|---|---|
| velo_prime_prob | 1656.66 |
| ofr_api | 1051.32 |
| trainer_jockey_sr | 884.85 |
| rpr_slope_6 | 596.93 |
| ts_slope_6 | 560.42 |
| or_slope_6 | 478.49 |
| ts_vs_or_gap | 206.27 |
| mds_high_flag | 102.35 |
| or_drop_from_peak | 82.19 |
| field_size | 43.24 |
| _tj_high_today20 | 21.87 |
| class_num | 12.93 |
| is_flat | 0.00 |
| is_jumps | 0.00 |
| dist_band_f | 0.00 |

## Logistic Regression Coefficients

| Feature | Coefficient |
|---|---|
| velo_prime_prob | +0.4363 |
| _tj_high_today20 | +0.2872 |
| ofr_api | +0.2579 |
| or_drop_from_peak | -0.1673 |
| mds_high_flag | +0.1412 |
| ts_vs_or_gap | +0.0991 |
| ts_slope_6 | -0.0704 |
| or_slope_6 | +0.0610 |
| rpr_slope_6 | -0.0517 |
| trainer_jockey_sr | -0.0423 |
| class_num | -0.0318 |
| field_size | -0.0077 |
| is_flat | +0.0000 |
| is_jumps | +0.0000 |
| dist_band_f | +0.0000 |

---

## Calibration (Best Model)

| Bin | Mean prob | Actual WR | n |
|---|---|---|---|
| 1 | 0.173 | 0.120 | 142 |
| 2 | 0.289 | 0.216 | 236 |
| 3 | 0.473 | 0.267 | 90 |
| 4 | 0.661 | 0.480 | 25 |
| 5 | 0.869 | 0.750 | 12 |

Brier score: 0.1699

---

## SP-Band Diagnostics (test set, top-20% by model score)
_Diagnostic only — SP is post-race, not a feature_

| SP Band | n | WR | ROI all | n top20% | ROI top20% |
|---|---|---|---|---|---|
| EW_SP_under_3 | 124 | 47.58% | -0.1411 | 25 | -0.0072 |
| SP_3_to_6 | 140 | 21.43% | -0.0959 | 28 | -0.2232 |
| SP_6_to_10 | 88 | 17.05% | +0.3523 | 18 | -0.5833 |
| SP_10_plus | 153 | 5.88% | -0.1634 | 31 | +2.0968 |

---

## Return Concentration (Best Model)
Gini: 3.0751  
Top-decile % of total P&L: -0.2428

---

## Hard Governance
```
Model is in SHADOW_QUARANTINE.
Not wired to: scoring pipeline, router, Telegram, staking, paper ledger.
Promotion requires: evidence review, operator decision.
NO_SCORING_CHANGE | NO_MODEL_PROMOTION | NO_ROUTER_CHANGE
NO_STAKING_CHANGE | NO_LIVE_STATE_MUTATION
```
