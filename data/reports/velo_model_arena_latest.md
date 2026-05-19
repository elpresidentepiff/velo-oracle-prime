# VÉLØ MODEL ARENA — LATEST RUN

**Run at:** 2026-05-19T00:29:33.404369+00:00  
**Training rows:** 1048  
**Validation rows:** 262  
**Val split date:** 2026-05-10

---

## Dependencies

- `lightgbm`: INSTALLED 4.6.0
- `xgboost`: MISSING — install not automatic, operator approval required
- `catboost`: MISSING — install not automatic, operator approval required
- `optuna`: MISSING — install not automatic, operator approval required
- `mlflow`: MISSING — install not automatic, operator approval required

---

## Results by Target

### Target: win

| Model | Brier ↓ | Log Loss ↓ | AUC ↑ | ROI (full) |
|---|---|---|---|---|
| logistic_baseline | 0.164972 | 0.510646 | 0.653294 | nan |
| random_forest | 0.165976 | 0.509709 | 0.665776 | nan |
| lightgbm | 0.183007 | 0.599927 | 0.621608 | nan |
| xgboost | None | None | None | n/a |
| catboost | None | None | None | n/a |

### Target: frame

| Model | Brier ↓ | Log Loss ↓ | AUC ↑ | ROI (full) |
|---|---|---|---|---|
| logistic_baseline | 0.212 | 0.619323 | 0.724287 | n/a |
| random_forest | 0.215284 | 0.630586 | 0.721891 | n/a |
| lightgbm | 0.239972 | 0.711912 | 0.677302 | n/a |
| xgboost | None | None | None | n/a |
| catboost | None | None | None | n/a |

## Classifications

| Model/Target | Classification |
|---|---|
| logistic_baseline_win | **SHADOW_MODEL_PROMISING** |
| random_forest_win | **SHADOW_MODEL_PROMISING** |
| lightgbm_win | **SHADOW_MODEL_PROMISING** |
| logistic_baseline_frame | **CURRENT_STACK_BEATS_ALL** |
| random_forest_frame | **CURRENT_STACK_BEATS_ALL** |
| lightgbm_frame | **CURRENT_STACK_BEATS_ALL** |

---

## Hard Rules

```
No production model changes.
No scoring changes.
No SP as predictive feature.
Classification only — must beat SQPE Brier before any promotion.
```