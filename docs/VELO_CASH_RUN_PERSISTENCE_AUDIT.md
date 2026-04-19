# VÉLØ Cash-Run Persistence Audit

**Revision:** 2026-04-18.01 | **Status:** PROVEN & FIXED

This document traces the lifecycle of the `cash_run_flag` to explain its absence from historical Sigma audits and documents the surgical fix.

---

## 1. Where It Is Born
**File:** `app/services/v17_feature_extractor.py`
The flag is correctly computed during the `_build_live_features` step. It analyzes trainer form, dry spells, and handicap mark compression to determine if a run is a heavily targeted "cash run." The result (`1.0` or `0.0`) is added to the `features` dictionary.

## 2. Where It Survives
**File:** `app/services/velo_prime_service.py`
The `features` dictionary successfully survives into `_feats_by_horse`, a temporary mapping used to feed the Horse State Engine later in the pipeline.

## 3. Where It Dies (The Silent Drop)
**File:** `app/services/velo_prime_service.py` (Inside `score_race_velo_prime`)
The `VeloPrimeEnsemble` evaluates the features and returns a `Prediction` object. The pipeline then iterates through these predictions to build the final `results` array (which eventually becomes the `full_analysis` JSON blob in Supabase). 

**The Gap:** Only specific, hardcoded fields from the prediction (like `velo_prime_prob`, `improvement_score`, etc.) were mapped into the final `row` dictionary. The raw doctrine flags inside `_feats_by_horse` (like `cash_run_flag`, `setup_run_flag`, and `decoy_support_flag`) were merged into a temporary `_merged` dictionary to feed the Horse State Engine, but **were never assigned to `row`**. Thus, they were discarded from memory before the database persistence step.

## 4. The Exact Fix
The flag persistence was surgically restored in `app/services/velo_prime_service.py`.

```python
for row in results:
    _live_feats = _feats_by_horse.get(row.get("horse", ""), {})
    
    # ── CASH RUN & DOCTRINE PERSISTENCE ────────────────────────────────
    row["cash_run_flag"] = bool(_live_feats.get("cash_run_flag", 0.0) == 1.0)
    row["setup_run_flag"] = bool(_live_feats.get("setup_run_flag", 0.0) == 1.0)
    row["decoy_support_flag"] = bool(_live_feats.get("decoy_support_flag", 0.0) == 1.0)
    # ───────────────────────────────────────────────────────────────────
```

Future runs will now successfully persist the `cash_run_flag` to the `full_analysis` blob in `velo_verdicts`, allowing the Sigma Loop and training plane to accurately audit cash-run strike rates.
