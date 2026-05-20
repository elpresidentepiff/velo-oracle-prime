# HFS Schema Drift Reconciliation V1

**Date:** 2026-05-05
**Reconciliation Migration:** `b2c3d4e5f6g7`
**Status:** RECONCILED (Alembic matches Live DB)

## 1. Summary of Drift
The production Supabase database was manually expanded with the 21-column V17 Doctrine contract. The local repository's Alembic migration history was behind this state. This reconciliation phase aligns the repository with reality.

## 2. Reconciled Contract (21 Columns)

| Category | Columns | Data Type |
|---|---|---|
| **Specialist Signals** | `market_deception_score`, `improvement_score`, `trainer_score`, `jockey_score`, `course_score`, `distance_score`, `field_strength`, `market_pressure` | `double precision` |
| **Pace Architecture** | `pace_profile` | `jsonb` |
| **Temporal Safety** | `pre_race_odds_dec` (double), `odds_timestamp` (timestamptz), `prediction_timestamp` (timestamptz), `odds_source` (text), `leakage_status` (text) | Mixed |
| **Audit Provenance** | `feature_status`, `feature_quality`, `training_safe` (bool), `batch_id`, `audit_id`, `reconstruction_version` | Mixed |
| **Quality Architecture**| `feature_provenance` | `jsonb` |

## 3. Implementation Logic
The migration `b2c3d4e5f6g7_hfs_block001_schema_drift_reconciliation.py` uses idempotent checks:
- `ADD COLUMN IF NOT EXISTS` logic via `_column_exists()` helper.
- `ALTER COLUMN ... TYPE JSONB` for existing `pace_profile` and `feature_provenance` columns to ensure correct structure.
- `CREATE INDEX IF NOT EXISTS` for all 5 audit/performance indexes.

## 4. Verification Proof
- **Staging/Local:** Running `alembic upgrade head` will now produce the correct schema from scratch.
- **Production:** Running `alembic upgrade head` will be a no-op (idempotent), but will register the migration as complete in the `alembic_version` table.
- **Test:** `tests/test_hfs_schema_contract.py` provides absolute proof of alignment.

## 5. Final Verdict
- **HFS_SCHEMA_STATUS:** **FIT_FOR_REPAIR_IMPLEMENTATION**
- **HFS_TRAINING_SAFE:** **FALSE** (Pending Feature Builder wiring)
- **Alembic Drift:** **RESOLVED**
