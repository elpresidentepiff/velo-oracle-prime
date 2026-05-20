# VÉLØ Active Pipeline Consolidation Spec V1

**Date:** 2026-05-05
**Objective:** Eliminate fragmentation and define the single canonical path for all scoring, backfilling, and learning.

## 1. Current Pipeline Classification

- **`run_prime_today.py`**: **ACTIVE**. The primary entry point for daily scoring.
- **`velo_prime_service.py`**: **ACTIVE**. The core logic for ensemble scoring.
- **`prediction_chain.py`**: **CANDIDATE_FOR_CONSOLIDATION**. It contains modern async patterns but is currently bypassed by the main production scripts. It should be merged into the canonical path or formally retired.
- **`backfill_historical_feature_store.py`**: **ACTIVE**. Used for reconstruction but currently uses a broken/bypassed feature contract.

## 2. The Canonical Path (Spine)

Every prediction and HFS entry must flow through this sequence:

1. **Ingestion**: `Racing API` (Standard) -> `racing_api_normalizer.py`
2. **Feature Extraction**:
   - `V16BaseFeatures` (implied odds, dist, going, etc.)
   - `V17DoctrineFeatures` (Live extraction via `V17FeatureExtractor`)
   - **Fix:** Remove `DEFAULTS` bypass in `velo_prime_service.py`.
3. **Market Intelligence**:
   - Compute `mpi` (runner-level)
   - Compute `chaos_bloom` (race-level)
   - **Requirement:** Timestamp-safe odds ONLY.
4. **Scoring**: `VeloPrimeEnsemble` (all models)
5. **Persistence**:
   - `predictions` table (Live)
   - `historical_feature_store` (Reconstruction/Training)
6. **Reconciliation**: `scripts/run_results_sigma.py`
7. **EOD Audit**: (New Control Layer) -> Strike rate, Brier score, Calibration.
8. **Shadow Learning**: `Playbook G` (Only from EOD-validated events).

## 3. Schema Migration Plan (Doctrine Columns)

To support the full doctrine, the `historical_feature_store` must be migrated.

**Migration: `add_missing_doctrine_columns`**
- `ALTER TABLE historical_feature_store ADD COLUMN market_deception_score FLOAT;`
- `ALTER TABLE historical_feature_store ADD COLUMN improvement_score FLOAT;`
- `ALTER TABLE historical_feature_store ADD COLUMN trainer_score FLOAT;`
- `ALTER TABLE historical_feature_store ADD COLUMN jockey_score FLOAT;`
- `ALTER TABLE historical_feature_store ADD COLUMN course_score FLOAT;`
- `ALTER TABLE historical_feature_store ADD COLUMN distance_score FLOAT;`
- `ALTER TABLE historical_feature_store ADD COLUMN pace_profile TEXT;`
- `ALTER TABLE historical_feature_store ADD COLUMN field_strength FLOAT;`
- `ALTER TABLE historical_feature_store ADD COLUMN market_pressure FLOAT;`
- `ALTER TABLE historical_feature_store ADD COLUMN pre_race_odds_dec FLOAT;`
- `ALTER TABLE historical_feature_store ADD COLUMN odds_timestamp TIMESTAMPTZ;`
- `ALTER TABLE historical_feature_store ADD COLUMN odds_source TEXT;`

## 4. Immediate Stop Conditions
- **Bypass Detection**: If a script uses `DEFAULTS` instead of `V17FeatureExtractor` for a training row, it must abort.
- **Leakage Detection**: If `sp_dec` is used as a model input for a pre-race prediction, it must abort.

---
**Status:** PROPOSED ARCHITECTURE. Implementation is BLOCKED until approved.
