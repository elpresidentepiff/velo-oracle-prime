# VELO Shadow Model Artifact Governance — V1

**Status:** ACTIVE  
**Applies to:** All models in `models/shadow/`  
**Effective:** 2026-05-19

---

## 1. Artifact Registry — Current Shadow Models

### VELO_CPU_LOGISTIC_SHADOW_V1 (Active)

| Property | Value |
|---|---|
| Model name | `NO_VP_COMPOSITE_logistic_win` |
| Model type | Logistic Regression |
| Target | `win` (binary) |
| Feature set | `NO_VP_COMPOSITE` |
| Artifact path | `models/shadow/model_arena_v2/NO_VP_COMPOSITE_logistic_win.pkl` |
| Training cutoff | `2026-05-10` (IMMUTABLE per session) |
| Training rows | 1,048 (before 2026-05-10) |
| Validation rows | 262 (2026-05-10 onward, training time) |
| Brier (val) | 0.163400 |
| AUC (val) | 0.6386 |
| SQPE baseline Brier | 0.207244 |

### All V2 Arena Models

| Property | Value |
|---|---|
| Artifact directory | `models/shadow/model_arena_v2/` |
| Pattern | `{FEATURE_SET}_{model}_{target}.pkl` |
| Total files | 90 (6 feature sets × 5 models × 3 targets) |
| Gitignore status | `models/**/*.pkl` — NOT committed to git |
| Training script | `scripts/train_velo_model_arena_v2.py` |

---

## 2. Feature List Hash

**MARKET_ONLY features** (top challenger Brier=0.159857):
```
market_deception_score, place_prob, longshot_prob, release_day_prob
```
SHA-256 of feature list string: computed at training time, logged in arena JSON.

**NO_VP_COMPOSITE features** (shadow champion):
```
sqpe_v17_prob, market_deception_score, improvement_score,
place_prob, longshot_prob, release_day_prob, comment_intel_score,
confidence_level_encoded
```

Full feature sets for all 6 groups are documented in:
`data/reports/velo_model_arena_ablation_v2_latest.json` → `.feature_sets`

---

## 3. Dependency Versions

| Package | Version | Install date |
|---|---|---|
| scikit-learn | per venv | pre-existing |
| xgboost | 3.2.0 | 2026-05-18 |
| catboost | 1.2.10 | 2026-05-18 |
| optuna | 4.8.0 | 2026-05-18 |
| numpy | 2.4.2 (NumpyEncoder required) | pre-existing |

Install log: `docs/engineering/VELO_ML_DEPENDENCY_INSTALL_LOG.md`

---

## 4. Reproducibility Command

To reproduce all 90 V2 arena models from scratch:

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/train_velo_model_arena_v2.py
```

Requirements:
- `data/features/rp_runner_profile_latest.parquet` present
- Training cutoff hardcoded as `VAL_SPLIT_DATE = "2026-05-10"` in the script
- All dependency versions as above

Expected output:
```
Train: 1048 | Val: 262 | Split: 2026-05-10
SQPE baseline Brier (win): 0.207244
...
JSON: data/reports/velo_model_arena_ablation_v2_latest.json
```

If Brier deviates by more than ±0.001 on NO_VP_COMPOSITE logistic: investigate before proceeding.

---

## 5. Dataset Hash

Training data source: `data/features/rp_runner_profile_latest.parquet`  
Row count at V2 training: 1,310 total (1,048 train + 262 val)  
Date range: up to 2026-05-10 (exclusive for training split)

To check dataset integrity before retraining:
```bash
python -c "
import pandas as pd, hashlib, json
df = pd.read_parquet('data/features/rp_runner_profile_latest.parquet')
h = hashlib.md5(df.to_json().encode()).hexdigest()
print(f'rows={len(df)} md5={h}')
"
```

---

## 6. Forward Gate Ledger

| Property | Value |
|---|---|
| Ledger path | `data/reports/shadow_model_forward_gate_ledger.csv` |
| Format | Append-only, one row per daily run |
| Tracking start | 2026-05-18 |
| Gate minimum | n≥300 runners, n≥75 top-decile |
| Current status | GATE_OPEN_ACCUMULATING |
| Script | `scripts/build_shadow_model_forward_gate.py` |

---

## 7. Rollback / Delete Command

To remove all V2 shadow model pkl files:
```bash
rm models/shadow/model_arena_v2/*.pkl
```

To remove and retrain the active shadow challenger only:
```bash
rm models/shadow/model_arena_v2/NO_VP_COMPOSITE_logistic_win.pkl
source venv/bin/activate
PYTHONPATH=. python scripts/train_velo_model_arena_v2.py
```

To roll back V2 arena reports:
```bash
# Reports are versioned by date in JSON. Latest is a symlink-style overwrite.
# No rollback needed — re-run train_velo_model_arena_v2.py to regenerate.
```

---

## 8. No Production Promotion Rule

**PERMANENT — never override:**

```
consumed_live = False
```

No shadow model artifact may enter the live scoring path until ALL of the following are true simultaneously:

1. Forward gate PASSES all 8 gates (see `VELO_CPU_SHADOW_MODEL_PROTOCOL_V1.md`)
2. Operator explicitly approves in writing
3. `consumed_live` flag is set to `True` by operator only
4. A new commit documents the approval with evidence references

The pkl files in `models/shadow/model_arena_v2/` are:
- NOT imported by `scripts/run_prime_today.py`
- NOT imported by `app/main.py` or any Railway service
- NOT imported by `betfair_execution_agent.py` or `betfair_trading_agents.py`
- Read-only for `build_shadow_model_forward_gate.py` (inference only, no scoring side effects)

---

## 9. Gitignore Policy

```gitignore
models/**/*.pkl        # All model binaries — NOT committed
data/*.pkl             # Data-directory pkl files
```

Model weights are local-only. The reproducibility command (Section 4) is the source of truth. Anyone with the training data and the V2 arena script can reproduce all 90 models deterministically.

---

## 10. Governance Review Trigger

Review this document when:
- 2K corpus milestone is reached (retraining required)
- A new model version is promoted to shadow
- Dependency versions change
- A new feature set is added to the arena
- Forward gate reaches PASS status
