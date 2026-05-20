# HFS Implementation Plan Block 001 V1

**Date:** 2026-05-05
**Objective:** Execute the reconstruction of Block 001 according to HFS Repair Spec V3.

## 1. Modification Map (Feature Branch: `feat/hfs-block001-repair`)

| File | Change |
|---|---|
| `alembic/versions/*.py` | Create migration for 19 missing columns (MDS, provenance, etc.). |
| `app/services/velo_prime_service.py` | 1. Wire `V17FeatureExtractor`. 2. Compute real `mpi` and `chaos_bloom`. 3. Separate `pre_race_odds_dec`. |
| `scripts/backfill_historical_feature_store.py` | 1. Update batch control (`batch_id`, `audit_id`). 2. Implement `V17_REPAIR_B3` logic. 3. Add `LEAKAGE_RISK` rejection. |
| `app/core/constants.py` | Add `FEATURE_QUALITY` and `LEAKAGE_STATUS` enums. |

## 2. Required Tests

- **Unit:** `tests/test_hfs_repair_logic.py` (Verify Shannon Entropy and MPI normalization).
- **Integration:** `tests/test_v17_extraction_wired.py` (Verify service correctly calls extractor).
- **Leakage:** `tests/test_odds_temporal_safety.py` (Verify post-race SP rejection in training feed).

## 3. Execution Sequence (Dry-Run First)

1. **Schema Update:** Run `alembic upgrade head` in staging.
2. **Snapshot:** `python scripts/maintenance/snapshot_hfs.py --range B001`.
3. **Dry-Run:** `python3 scripts/backfill_historical_feature_store.py --limit 100 --reconstruction-version V17_REPAIR_B3 --dry-run`.
4. **Validation:** Inspect `data/logs/repair_audit.json` for variance and leakage flags.
5. **Full Write:** Execute in 10,000-row batches with `audit_id` per run.

## 4. Rollback Protection
- **Revert:** `git revert HEAD` + `alembic downgrade -1`.
- **Cleanup:** `DELETE FROM historical_feature_store WHERE reconstruction_version = 'V17_REPAIR_B3'`.

---
**Status:** PENDING APPROVAL. No code will be written until this plan is certified.
