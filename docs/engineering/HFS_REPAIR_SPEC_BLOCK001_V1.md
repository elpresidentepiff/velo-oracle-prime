# HFS Repair Specification Block 001 V1

**Objective:** Reconstruct HFS Block 001 with 100% wired doctrine signals and zero proxy/default contamination.

## 1. Feature Engineering Fixes

### A. Probability & Entropy (MPI / Chaos)
- **Target:** Populate `mpi` and `chaos_bloom` in `app/services/velo_prime_service.py`.
- **Logic:**
  - `mpi`: Calculate implied probability from `sp_dec`. Normalize across the field.
  - `chaos_bloom`: Calculate Shannon Entropy of the implied probability distribution. Scale to 0-1.

### B. V17 Doctrine Wiring
- **Target:** Remove `DEFAULTS` bypass in `_build_live_features`.
- **Action:**
  - Instantiate `V17FeatureExtractor` within `score_race_velo_prime`.
  - For every runner, call `extractor.extract(horse_id, race_context)`.
  - **Hard Stop:** If extraction fails, the row must be marked `FEATURE_ERROR` and excluded from training feeds, rather than filled with defaults.

### C. Relative Field Stats
- **Target:** Populate `or_vs_field`, `rpr_vs_field`, and `sp_rank`.
- **Action:** Ensure the field-averaging logic in `_build_live_features` is correctly applied and persisted to the HFS columns.

## 2. Infrastructure & Backfill

### A. Batch Control
- **Mandatory:** All repair writes must use `reconstruction_version = 'V17_REPAIR_B1'`.
- **Audit ID:** Assign a unique `audit_id` (UUID) to every execution run.

### B. Rollback Readiness
- **Snapshot:** Before running the repair, export the current `historical_feature_store` state for the target date range to `data/archive/hfs_pre_repair_snapshot.csv`.

## 3. Validation Gates
The repair is only successful if:
1. `mpi` variance > 0 across the field.
2. `chaos_bloom` variance > 0 across the field.
3. `v17_doctrine_features` show variance consistent with historical distributions.
4. Null rate for primary doctrine fields < 1%.

---
**Status:** SPECIFICATION ONLY. Implementation is BLOCKED until approved.
