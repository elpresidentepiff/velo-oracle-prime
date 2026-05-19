# VÉLØ ML DEPENDENCY APPROVAL REQUEST V1

**Created:** 2026-05-18  
**Status:** PENDING_OPERATOR_APPROVAL  
**Classification:** GOVERNANCE | INSTALL_GATE | NO_AUTO_INSTALL

---

## Context

Stage 1 (CPU Model Arena) ran successfully with LightGBM 4.6.0 + scikit-learn 1.8.0.  
The ablation run confirmed that challengers show **INDEPENDENT_MODEL_PROMISING** signal  
on NO_VP_COMPOSITE (raw sidecars, no velo_prime_prob).

The packages below are needed to complete the arena, run HPO, and track experiments.  
None are installed. None will be installed without explicit operator approval per this doc.

---

## Package 1 — XGBoost

| Field | Value |
|---|---|
| **Package** | `xgboost` |
| **Version target** | `>=2.0.0` |
| **Install command** | `pip install xgboost` |
| **Purpose** | Gradient boosting challenger in model arena — compare vs LightGBM and logistic |
| **Needed now?** | YES — arena is incomplete without it |
| **Risk level** | LOW |
| **Security notes** | No network calls at runtime. Compiled C++ extension, well-audited. |
| **Import scope** | `scripts/train_velo_model_arena.py`, `scripts/train_velo_model_arena_ablation.py` only |
| **Live scoring impact** | NONE — shadow scripts only. Not imported by `run_prime_today.py`. |
| **Rollback** | `pip uninstall xgboost`. No state mutation on install. |

**Operator decision:** `[ ] APPROVED` | `[ ] REJECTED`

---

## Package 2 — CatBoost

| Field | Value |
|---|---|
| **Package** | `catboost` |
| **Version target** | `>=1.2.0` |
| **Install command** | `pip install catboost` |
| **Purpose** | Gradient boosting challenger — native categorical handling, often competitive on tabular data |
| **Needed now?** | YES — arena is incomplete without it |
| **Risk level** | LOW |
| **Security notes** | No network calls at runtime. Compiled extension from Yandex. Pure prediction library. |
| **Import scope** | `scripts/train_velo_model_arena.py`, `scripts/train_velo_model_arena_ablation.py` only |
| **Live scoring impact** | NONE — shadow scripts only |
| **Rollback** | `pip uninstall catboost`. No state mutation on install. |

**Operator decision:** `[ ] APPROVED` | `[ ] REJECTED`

---

## Package 3 — Optuna

| Field | Value |
|---|---|
| **Package** | `optuna` |
| **Version target** | `>=3.0.0` |
| **Install command** | `pip install optuna` |
| **Purpose** | Hyperparameter optimisation (HPO) — Bayesian search over model configs for arena challengers |
| **Needed now?** | NOT IMMEDIATELY — can run arena with default configs first |
| **Recommended sequence** | Approve XGBoost + CatBoost first. Add Optuna when arena has ≥3 model types. |
| **Risk level** | LOW |
| **Security notes** | No network calls required. Has optional database backend (SQLite/PostgreSQL) — will use in-memory mode only unless operator approves persistence. |
| **Import scope** | New script `scripts/run_model_hpo.py` (not yet written). No live imports. |
| **Live scoring impact** | NONE |
| **Rollback** | `pip uninstall optuna`. No state mutation on install. |

**Operator decision:** `[ ] APPROVED` | `[ ] DEFERRED` | `[ ] REJECTED`

---

## Package 4 — MLflow

| Field | Value |
|---|---|
| **Package** | `mlflow` |
| **Version target** | `>=2.12.0` |
| **Install command** | `pip install mlflow` |
| **Purpose** | Experiment tracking — log model runs, metrics, artifacts. Enables run comparison and audit trail. |
| **Needed now?** | NOT IMMEDIATELY — manual JSON logging sufficient at current scale |
| **Recommended sequence** | Approve after arena has ≥6 model × feature_set combinations. |
| **Risk level** | LOW–MEDIUM |
| **Security notes** | MLflow UI runs a local web server on port 5000. Must be isolated to local env — never expose to Railway or production network. No external data transmission in offline mode. |
| **Import scope** | New script `scripts/run_experiment_tracker.py`. No live imports. |
| **Live scoring impact** | NONE |
| **Rollback** | `pip uninstall mlflow`. Local experiment store (`mlruns/`) can be deleted independently. |
| **Storage impact** | Creates `mlruns/` directory locally. Gitignored. |

**Operator decision:** `[ ] APPROVED` | `[ ] DEFERRED` | `[ ] REJECTED`

---

## Package 5 — DSPy (Deferred — Stage 3 SLM)

| Field | Value |
|---|---|
| **Package** | `dspy-ai` or `dspy` |
| **Version target** | `>=2.4.0` |
| **Install command** | `pip install dspy` |
| **Purpose** | Structured LLM pipeline for Phase B of RP Claim Extractor (Stage 3 SLM) |
| **Needed now?** | NO — Phase A (regex) must reach precision ≥ 0.80 first |
| **Prerequisite** | Phase A regex baseline complete + 1,500+ training rows + operator review |
| **Risk level** | MEDIUM |
| **Security notes** | Requires `ANTHROPIC_API_KEY` for Claude integration. API costs apply. All prompts are read-only claim extraction — no write operations via Claude. |
| **Import scope** | `scripts/extract_rp_claims_dspy.py` (not yet written). No live imports. |
| **Live scoring impact** | NONE |
| **Rollback** | `pip uninstall dspy`. No state mutation on install. |

**Operator decision:** `[ ] DEFERRED_PENDING_STAGE3` | `[ ] REJECTED`

---

## Priority Install Order

If all above are approved, recommended install sequence:

```bash
# Priority 1 — completes the model arena immediately
pip install xgboost catboost

# Priority 2 — adds HPO capability after arena baseline established
pip install optuna

# Priority 3 — adds experiment tracking when run count warrants it
pip install mlflow

# Priority 4 — Stage 3 prerequisite only
pip install dspy
```

---

## What Does NOT Need Approval

These are already installed and in use:

| Package | Version | Status |
|---|---|---|
| `lightgbm` | 4.6.0 | INSTALLED — in use |
| `scikit-learn` | 1.8.0 | INSTALLED — in use |
| `numpy` | current | INSTALLED — in use |
| `pandas` | current | INSTALLED — in use |

---

## Governance

```
NO_AUTO_INSTALL               = TRUE
OPERATOR_APPROVAL_REQUIRED    = TRUE (all packages above)
SHADOW_SCRIPTS_ONLY           = TRUE (none enter live scoring path)
NO_LIVE_SCORING_IMPORTS       = TRUE
ROLLBACK_AVAILABLE            = TRUE (pip uninstall, no state mutation)
```

All installed packages are logged in `requirements.txt` after operator approval.

---

**Approval authority:** Operator (purorestrepo1981@gmail.com)  
**No package installs until this doc is reviewed and decisions recorded above.**
