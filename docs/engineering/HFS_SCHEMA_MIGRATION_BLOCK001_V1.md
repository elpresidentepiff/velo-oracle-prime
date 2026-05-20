# HFS Schema Migration Block 001 V1

**Date:** 2026-05-05
**Revision:** `a1b2c3d4e5f6`
**Status:** CREATED (Implementation Blocked)

## 1. Objective
Expand the `historical_feature_store` table to support the full V17 Doctrine, provenance tracking, and temporal/leakage safety.

## 2. Changes (Additive-Only)

The following columns are added as **NULLABLE** fields. No data is modified during this migration.

### A. Specialist Signal Columns
- `market_deception_score` (FLOAT)
- `improvement_score` (FLOAT)
- `trainer_score` (FLOAT)
- `jockey_score` (FLOAT)
- `course_score` (FLOAT)
- `distance_score` (FLOAT)
- `pace_profile` (TEXT)
- `field_strength` (FLOAT)
- `market_pressure` (FLOAT)

### B. Temporal & Leakage Safety
- `pre_race_odds_dec` (FLOAT)
- `odds_timestamp` (TIMESTAMPTZ)
- `odds_source` (TEXT)
- `prediction_timestamp` (TIMESTAMPTZ)
- `leakage_status` (TEXT) - e.g., 'CLEAN', 'LEAKAGE_RISK'

### C. Provenance & Quality
- `feature_status` (TEXT) - e.g., 'COMPLETE', 'ERROR'
- `feature_quality` (TEXT) - e.g., 'HIGH', 'DEGRADED'
- `feature_provenance` (TEXT) - Originating script/version
- `training_safe` (BOOLEAN) - Primary gate for learning feeds
- `batch_id` (TEXT) - Batch tracking for rollback
- `audit_id` (TEXT) - Execution run ID (UUID/String)

## 3. Indexes
The following indexes are created to optimize reconstruction audits and learning feed extraction:
- `ix_hfs_batch_id`
- `ix_hfs_audit_id`
- `ix_hfs_reconstruction_version`
- `ix_hfs_training_safe`
- `ix_hfs_leakage_status`

## 4. Rollback Safety
- **Additive Nature:** This migration only adds columns and indexes. It does not drop or mutate existing data.
- **Downgrade Logic:** The `downgrade()` function in the Alembic migration removes only these specific columns and indexes.
- **Verification:** `tests/test_hfs_schema_contract.py` provides an automated check for the required schema state.

## 5. Next Phase
Once this migration is applied (after approval), we will proceed to **Phase 2: Canonical Feature Builder Implementation**, where we will wire the logic to populate these columns.
