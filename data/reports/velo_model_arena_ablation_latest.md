# VÉLØ MODEL ARENA ABLATION V1

**Run at:** 2026-05-19T05:40:20.814087+00:00  
**Train:** 1048 | **Val:** 262 | **Split:** 2026-05-10  
**SQPE baseline Brier (win):** 0.210688

---

## Win Target

| Feature Set | Model | Brier ↓ | AUC ↑ | ROI | Classification |
|---|---|---|---|---|---|
| FULL_META | logistic | **0.164972** | 0.653294 | -0.0161 | ~ META_CALIBRATOR_PROMISING |
| FULL_META | random_forest | **0.165976** | 0.665776 | -0.0161 | ~ META_CALIBRATOR_PROMISING |
| FULL_META | lightgbm | **0.181064** | 0.613008 | -0.0161 | ~ META_CALIBRATOR_PROMISING |
| NO_VP_COMPOSITE | logistic | **0.16399** | 0.643901 | -0.0161 | ✓ INDEPENDENT_MODEL_PROMISING |
| NO_VP_COMPOSITE | random_forest | **0.164097** | 0.679636 | -0.0161 | ✓ INDEPENDENT_MODEL_PROMISING |
| NO_VP_COMPOSITE | lightgbm | **0.178121** | 0.628789 | -0.0161 | ✓ INDEPENDENT_MODEL_PROMISING |
| NO_VP_NO_MARKET | logistic | **0.176174** | 0.564165 | -0.0161 | ✓ INDEPENDENT_MODEL_PROMISING |
| NO_VP_NO_MARKET | random_forest | **0.182037** | 0.579903 | -0.0161 | ✓ INDEPENDENT_MODEL_PROMISING |
| NO_VP_NO_MARKET | lightgbm | **0.197332** | 0.492987 | -0.0161 | ✓ INDEPENDENT_MODEL_PROMISING |

*SQPE baseline: 0.210688*

---

## Frame Target

| Feature Set | Model | Brier ↓ | AUC ↑ | Classification |
|---|---|---|---|---|
| FULL_META | logistic | **0.212** | 0.724287 | ✗ CURRENT_STACK_BEATS_ALL |
| FULL_META | random_forest | **0.215284** | 0.721891 | ✗ CURRENT_STACK_BEATS_ALL |
| FULL_META | lightgbm | **0.236129** | 0.682854 | ✗ CURRENT_STACK_BEATS_ALL |
| NO_VP_COMPOSITE | logistic | **0.214451** | 0.71409 | ✗ CURRENT_STACK_BEATS_ALL |
| NO_VP_COMPOSITE | random_forest | **0.215299** | 0.730978 | ✗ CURRENT_STACK_BEATS_ALL |
| NO_VP_COMPOSITE | lightgbm | **0.236699** | 0.675403 | ✗ CURRENT_STACK_BEATS_ALL |
| NO_VP_NO_MARKET | logistic | **0.257171** | 0.543303 | ✗ CURRENT_STACK_BEATS_ALL |
| NO_VP_NO_MARKET | random_forest | **0.256635** | 0.544705 | ✗ CURRENT_STACK_BEATS_ALL |
| NO_VP_NO_MARKET | lightgbm | **0.290808** | 0.498627 | ✗ CURRENT_STACK_BEATS_ALL |

---

## Key Verdict

| Metric | Value |
|---|---|
| SQPE baseline Brier | 0.210688 |
| FULL_META best | 0.164972 |
| NO_VP_COMPOSITE best | 0.16399 |
| NO_VP_NO_MARKET best | 0.176174 |
| **Independent signal confirmed** | **YES** |

---

## Governance

```
No production model changes.
No scoring changes.
No SP as predictive feature.
```