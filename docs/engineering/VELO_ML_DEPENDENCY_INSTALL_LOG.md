# VÉLØ ML DEPENDENCY INSTALL LOG

**Created:** 2026-05-18  
**Status:** COMPLETE — installed 2026-05-18  
**Classification:** GOVERNANCE | CONTROLLED_INSTALL | AUDIT_TRAIL

---

## Operator Approval (from session 2026-05-18)

```
APPROVED: Optuna, CatBoost, XGBoost
HOLD:     MLflow (local-only plan required first)
SCOPE:    Existing project venv only — no Railway, no production
```

**Priority order:**
1. Optuna (improves every model search)
2. CatBoost (categorical structure benefit)
3. XGBoost (standard arena challenger)

---

## Pre-Install State

**Environment:** `venv/` in `/mnt/c/Users/puror/velo-oracle-prime`  
**Python:** 3.12  
**Pre-install package count:** 166

**Relevant pre-install versions:**

| Package | Version |
|---|---|
| lightgbm | 4.6.0 |
| scikit-learn | 1.8.0 |
| numpy | 2.4.2 |
| pandas | 2.3.3 |
| optuna | NOT INSTALLED |
| catboost | NOT INSTALLED |
| xgboost | NOT INSTALLED |

---

## Install Command

```bash
source venv/bin/activate && pip install optuna catboost xgboost
```

---

## Post-Install State

<!-- Populated after install completes -->

| Package | Version | Status |
|---|---|---|
| optuna | 4.8.0 | INSTALLED |
| catboost | 1.2.10 | INSTALLED |
| xgboost | 3.2.0 | INSTALLED |
| lightgbm | 4.6.0 | PRE-EXISTING |
| scikit-learn | 1.8.0 | PRE-EXISTING |

---

## Rollback Plan

```bash
source venv/bin/activate
pip uninstall optuna catboost xgboost -y
```

No state mutation from install. No files written to production paths.  
Rollback is instant and clean.

---

## Scope Restrictions (permanent)

```
INSTALL_SCOPE             = venv/ only
RAILWAY_DEPLOY            = NOT TRIGGERED (these packages not in requirements.txt yet)
LIVE_SCORING_IMPORTS      = FORBIDDEN (scripts/run_prime_today.py must not import these)
PRODUCTION_USE            = FORBIDDEN until arena V2 gate passed + operator decision
MLFLOW                    = HOLD (local-only plan required)
```

---

## Governance

```
OPERATOR_APPROVED          = TRUE (2026-05-18 session)
AUDIT_TRAIL                = THIS DOCUMENT
NO_AUTO_PROMOTE            = TRUE
NO_REQUIREMENTS_UPDATE     = TRUE (until operator explicitly approves)
```
