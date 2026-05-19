# MAY 18 LEARNING ELIGIBILITY AUDIT

**Date:** 2026-05-18  
**Run at:** 2026-05-19T00:07:54.876515+00:00  
**Classification:** MAY18_SYNTHETIC_ID_NORMALISATION_DRIFT_FIXED | SIGMA_RECONCILIATION_RECOVERED | MODEL_RESULT_AT_BASELINE | LEARNING_NOT_AUTO_APPROVED

---

## Coverage Summary

| Metric | Count |
|---|---|
| Official predictions | 34 |
| Sigma evaluated (DB) | 28 |
| Learning eligible | **28** |
| Excluded — Tier X | 4 |
| Excluded — True NR/DNF | 2 |
| Excluded — No result | 0 |
| Excluded — Identity residual | 0 |
| Sigma coverage % | 82.4% |
| Eligible % of total | 82.4% |

---

## Identity Failure Recovery

| | Count |
|---|---|
| Identity failures BEFORE fix (commit 1dc8d5b) | 24 |
| Identity failures AFTER fix (commit dc33a5e) | 0 |
| Residual identity failures | **0** |

---

## Prior Consumption State

| Metric | Value |
|---|---|
| velo_learning_events in DB | 0 |
| consumed_shadow=True | 0 |
| consumed_live=True | 0 |
| Previously consumed | No |

---

## Gate Assessment

| Gate | Status |
|---|---|
| consumed_live=False | PASS |
| consumed_shadow=False | PASS |
| Identity failures = 0 | PASS |
| Eligible = sigma rows | PASS |
| All gates clear | **PASS** |

---

## Recommendation

**HOLD_PENDING_OPERATOR_APPROVAL**

All 28 eligible rows are clean (no prior consumption, 0 identity failures). May 18 may enter shadow training only after explicit operator approval. Classification: BASELINE_MODEL_RESULT.

---

## Eligible Race IDs

```
  2026-05-18_CRL_230
  2026-05-18_CRL_300
  2026-05-18_CRL_330
  2026-05-18_CRL_435
  2026-05-18_CRL_510
  2026-05-18_Lingfield_220
  2026-05-18_Lingfield_422
  2026-05-18_Lingfield_457
  2026-05-18_ROS_450
  2026-05-18_ROS_550
  2026-05-18_ROS_620
  2026-05-18_ROS_720
  2026-05-18_ROS_750
  2026-05-18_ROS_820
  2026-05-18_Redcar_240
  2026-05-18_Redcar_310
  2026-05-18_Redcar_340
  2026-05-18_Redcar_410
  2026-05-18_Redcar_443
  2026-05-18_Windsor_540
  2026-05-18_Windsor_710
  2026-05-18_Windsor_740
  2026-05-18_Windsor_810
  2026-05-18_Wolverhampton_600
  2026-05-18_Wolverhampton_730
  2026-05-18_Wolverhampton_800
  2026-05-18_Wolverhampton_830
  2026-05-18_Wolverhampton_900
```

## Excluded Race IDs

**Tier X (4):**
```
  2026-05-18_CRL_400
  2026-05-18_Lingfield_350
  2026-05-18_Windsor_610
  2026-05-18_Windsor_640
```

**True NR/DNF (2):**
```
  2026-05-18_Lingfield_250
  2026-05-18_ROS_650
```

**No result (0):**
```
```

**Identity residual (0):**
```
```

---

## Hard Rules — Confirmed

```
consumed_shadow      = False
consumed_live        = False
no_scoring_change    = True
no_model_change      = True
no_router_change     = True
no_staking_change    = True
target_state         = shadow_full_train_v2
```

Do not consume until Presidente approves.