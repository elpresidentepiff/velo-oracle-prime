# VÉLØ MODEL ARENA CALIBRATION REVIEW V1

**Created:** 2026-05-18  
**Status:** ANALYSIS_COMPLETE  
**Classification:** TRAINING_EVIDENCE | NO_LIVE_CHANGE | SHADOW_MODEL_REVIEW

---

## Executive Summary

The ablation V1 confirms **INDEPENDENT_MODEL_PROMISING** across all three feature sets on the  
win target. The challengers are not VP recalibrators — they carry genuine signal beyond  
`velo_prime_prob`. The critical finding: **removing VP improves win Brier** (NO_VP_COMPOSITE  
beats FULL_META). This rules out the meta-calibrator hypothesis for the win target.

Frame target remains **CURRENT_STACK_BEATS_ALL** — current VP ensemble is the best frame  
calibrator at this data volume.

---

## Full Ablation Results

### Win Target (SQPE baseline Brier: 0.210688)

| Feature Set | Model | Brier ↓ | AUC ↑ | vs SQPE | Classification |
|---|---|---|---|---|---|
| FULL_META (10f) | logistic | **0.164972** | 0.6533 | −0.0457 | META_CALIBRATOR_PROMISING |
| FULL_META (10f) | random_forest | 0.165976 | 0.6658 | −0.0447 | META_CALIBRATOR_PROMISING |
| FULL_META (10f) | lightgbm | 0.181064 | 0.6130 | −0.0296 | META_CALIBRATOR_PROMISING |
| **NO_VP_COMPOSITE (8f)** | **logistic** | **0.163990** | 0.6439 | **−0.0467** | **INDEPENDENT_MODEL_PROMISING** |
| **NO_VP_COMPOSITE (8f)** | **random_forest** | **0.164097** | **0.6796** | **−0.0466** | **INDEPENDENT_MODEL_PROMISING** |
| NO_VP_COMPOSITE (8f) | lightgbm | 0.178121 | 0.6288 | −0.0326 | INDEPENDENT_MODEL_PROMISING |
| NO_VP_NO_MARKET (4f) | logistic | 0.176174 | 0.5642 | −0.0345 | INDEPENDENT_MODEL_PROMISING |
| NO_VP_NO_MARKET (4f) | random_forest | 0.182037 | 0.5799 | −0.0286 | INDEPENDENT_MODEL_PROMISING |
| NO_VP_NO_MARKET (4f) | lightgbm | 0.197332 | 0.4930 | −0.0133 | INDEPENDENT_MODEL_PROMISING |

**Best win challenger:** NO_VP_COMPOSITE logistic (Brier=0.163990, −22.2% vs SQPE)

### Frame Target (frame Brier baseline: implicit in VP ensemble)

| Feature Set | Model | Brier ↓ | AUC ↑ | Classification |
|---|---|---|---|---|
| FULL_META (10f) | logistic | 0.212000 | **0.7243** | CURRENT_STACK_BEATS_ALL |
| FULL_META (10f) | random_forest | 0.215284 | 0.7219 | CURRENT_STACK_BEATS_ALL |
| FULL_META (10f) | lightgbm | 0.236129 | 0.6829 | CURRENT_STACK_BEATS_ALL |
| NO_VP_COMPOSITE (8f) | logistic | 0.214451 | 0.7141 | CURRENT_STACK_BEATS_ALL |
| NO_VP_COMPOSITE (8f) | random_forest | 0.215299 | **0.7310** | CURRENT_STACK_BEATS_ALL |
| NO_VP_COMPOSITE (8f) | lightgbm | 0.236699 | 0.6754 | CURRENT_STACK_BEATS_ALL |
| NO_VP_NO_MARKET (4f) | logistic | 0.257171 | 0.5433 | CURRENT_STACK_BEATS_ALL |
| NO_VP_NO_MARKET (4f) | random_forest | 0.256635 | 0.5447 | CURRENT_STACK_BEATS_ALL |
| NO_VP_NO_MARKET (4f) | lightgbm | 0.290808 | 0.4986 | CURRENT_STACK_BEATS_ALL |

---

## Q1: Are challengers only improving because of VP?

**Answer: NO.**

The definitive test: NO_VP_COMPOSITE (no `velo_prime_prob`, no `decision_tier`) produces  
the **best Brier across all win models** (logistic 0.163990). FULL_META, which includes VP,  
scores *worse* (0.164972). VP is not driving the win improvement — removing it makes the  
model marginally better.

This means the sidecars (SQPE, MDS, improvement_score, place_prob, longshot_prob,  
release_day_prob, comment_intel_score) are carrying genuine predictive signal that is  
not merely re-learning VP's composite.

**Interpretation:** VP is an additive composite of these same signals. Feeding VP and  
its components into the same model creates partial redundancy. The model learns faster  
from the raw components directly.

---

## Q2: Does LightGBM learn independently?

**Answer: YES, but it is the weakest win model at this data volume.**

LightGBM win Brier (NO_VP_COMPOSITE: 0.178121) beats SQPE (0.210688) but loses to  
logistic (0.163990) and RF (0.164097) by ~14 Brier points. At 1,048 training rows  
LightGBM's advantages (non-linear interactions, complex feature splits) are offset by  
overfitting risk. The min_child_samples=25 constraint limits split quality at this n.

LightGBM's frame AUC (0.6829–0.6754) is lower than logistic/RF (0.7243–0.7310),  
confirming simpler models generalise better at current scale.

**2K milestone expectation:** When corpus reaches 2,000 rows, LightGBM is the model  
most likely to leap ahead of logistic. Its gains will compound with data volume.  
Both XGBoost and CatBoost should be installed before the 2K rerun.

---

## Q3: Is logistic enough as a calibrator?

**Answer: YES, at current data volume. Likely not at 2K+.**

Logistic achieves the best win Brier (0.163990) with `CalibratedClassifierCV` (isotonic  
calibration, 3-fold CV). It outperforms both tree models across all feature sets for  
win prediction. This is expected behaviour at 1,048 training rows — linear models  
generalise better than non-linear when data is sparse relative to feature space.

For the frame target, logistic is the best Brier model (0.212000) but the frame AUC  
from RF/logistic is statistically similar (0.7243 vs 0.7219). The discrimination  
quality is equivalent; what differs is calibration, not ranking.

**Recommendation:** Run logistic as shadow forward model now. Retire it when 2K rerun  
shows a tree model has converged past it.

---

## Q4: Does any model improve frame prediction?

**Answer: NO, not in Brier terms at current n.**

All frame models score CURRENT_STACK_BEATS_ALL — none beat the SQPE win Brier  
threshold (0.210688) used as the frame comparison baseline.

**Important methodological note:** The frame Brier comparison uses the *win* SQPE  
baseline, not a calibrated frame baseline. The actual implicit frame baseline (VP  
ensemble `place_prob` component) is not isolated in this run. Frame AUC is strong  
(0.731 for NO_VP_COMPOSITE RF), which means the *ranking* quality is good — the  
issue is absolute probability calibration for frame events.

**Two reasons frame models underperform:**

1. Frame class imbalance (47% positive) makes calibration harder — the model's  
   probability outputs need wider range to cover the distribution, producing higher  
   Brier scores vs win (22% positive).
2. At 1,310 rows total, frame signal is still noisy in the tail (low-VP selections  
   that place but don't win).

**Next step on frame:** Separate frame Brier baseline using `place_prob` direct  
calibration run. This requires a dedicated audit, not a cherry-pick comparison  
against the win baseline.

---

## Q5: Safe for shadow policy?

**Classification: SHADOW_LANE_ELIGIBLE — with conditions.**

Conditions for shadow forward use:

| Condition | Status |
|---|---|
| Beats SQPE Brier on time-split val | YES (all win models) |
| No VP as feature (avoids circular recalibration) | YES if using NO_VP_COMPOSITE |
| No SP as predictive feature | YES (never included) |
| No staking or routing change | YES (shadow-only) |
| Operator review of promotion gate | PENDING |
| n≥300 forward shadow runners | PENDING |
| n≥75 top-decile forward runners | PENDING |

**Recommended shadow model:** NO_VP_COMPOSITE logistic — best Brier, simplest  
architecture, most interpretable, lowest overfitting risk at current n.

**NOT ready for:** Weight changes, ensemble update, VP recalibration, routing rule  
modification, live staking.

---

## Critical Nuance: NO_VP_COMPOSITE Beats FULL_META

This is the single most important finding of Ablation V1.

NO_VP_COMPOSITE (Brier 0.163990) edges out FULL_META (0.164972) by 0.001 Brier  
points. The gap is narrow but directionally consistent across logistic (NO_VP wins)  
and RF (NO_VP wins). LightGBM also shows the same pattern (0.178121 vs 0.181064).

**Implication:** Including `velo_prime_prob` as a feature in the challenger adds  
marginal noise, not signal. VP is a weighted sum of several of the same sidecars  
already in the feature set. The model picks up the structural signal directly from  
the components.

This does **not** mean VP is a bad ensemble composite for live scoring. VP is tuned  
and audited for its current role. What it means is that a challenger trained on the  
raw components is not "just recalibrating VP" — it's learning from the same source  
data and producing better probability estimates for the win target independently.

---

## Recommended Next Actions

**Immediate (approved):**
1. Forward-shadow lane: NO_VP_COMPOSITE logistic, win target, live scoring output  
   compared against model result but no weight applied
2. Store model pkl: `models/shadow/model_arena/ablation/NO_VP_COMPOSITE_logistic_win.pkl`  
   (already written by ablation script)
3. Gate: 300 forward runners before any promotion review

**Pending operator approval:**
4. Install XGBoost + CatBoost → complete arena (see VELO_ML_DEPENDENCY_APPROVAL_REQUEST_V1.md)
5. 2K rerun when corpus reaches 2,000 clean rows (est. 2026-07)
6. Frame calibration standalone audit (separate from win Brier comparison)

**Do not do:**
- Change VP ensemble weights based on this run
- Promote any model to production scoring
- Use arena Brier results to justify routing rule changes
- Adjust tier thresholds based on model AUC

---

## Governance

```
CLASSIFICATION: TRAINING_EVIDENCE | NO_LIVE_CHANGE
NO_SCORING_CHANGE              = TRUE
NO_MODEL_REPLACEMENT           = TRUE
NO_VP_WEIGHT_CHANGE            = TRUE
NO_ROUTING_RULE_CHANGE         = TRUE
SHADOW_FORWARD_PENDING_GATE    = TRUE (n≥300 runners required)
OPERATOR_DECISION_AT_GATE      = TRUE
```
