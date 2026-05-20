# HFS Truth Audit Block 001 V1

**Date:** 2026-05-05
**Verdict:** **HFS_BLOCK001_TRAINING_SAFE = FALSE**

## 1. Executive Summary
The Historical Feature Store (HFS) is in a state of **Intelligence Collapse**. While the core database contains rich profile data (horses, jockeys, trainers), the "Doctrine" signals required for Playbook G and specialist models are either NULL, DEFAULT, or PROXY-based. Most critically, the V17 feature extractor is bypass-defaulted to constant values (e.g., 0.0, 0.33) during backfills.

## 2. Signal-by-Signal Truth Map

| Signal | Status | Root Cause | Evidence |
|---|---|---|---|
| `mpi` | **BROKEN/NULL** | Not computed in `velo_prime_service`. | `publish_daily_predictions_to_dashboard.py:75` |
| `chaos_bloom` | **BROKEN/NULL** | Not computed in `velo_prime_service`. | `publish_daily_predictions_to_dashboard.py:76` |
| `v17_doctrine` | **DEFAULT/FLAT** | `V17FeatureExtractor` is defined but NOT CALLED by the backfill engine. | `app/services/velo_prime_service.py:175` |
| `rpr_vs_field` | **NULL** | Missing join/computation in backfill path. | Data Audit (500-row sample) |
| `sp_rank` | **NULL** | Missing join/computation in backfill path. | Data Audit (500-row sample) |
| `narrative_*` | **NULL** | Not implemented in pipeline. | Dashboard bypass list |

## 3. Root Cause Evidence
- **Bypass Logic:** `app/services/velo_prime_service.py` uses `DEFAULTS` from `v17_feature_extractor` instead of executing the extraction. This results in every horse in the historical dataset having identical "intelligence" features.
- **Data Dark Batches:** Recent HFS entries (Batch `EXCLUDED_DATA_DARK`) show `scoring_status: missing_prediction`. This indicates that when the backfill script cannot find a pre-existing prediction, it saves a shell row with NULL/DEFAULT doctrine signals.
- **Fragmentation:** A newer `prediction_chain.py` exists that *appears* to be wired, but it is NOT used by the canonical `run_prime_today.py` or the `backfill_historical_feature_store.py` script.

## 4. Signal Variance Report (Block 001)
- **Total Rows Audited:** 500
- **Null Rate (Doctrine Fields):** 100% (excluding mpi/chaos which show sparse proxy data in older rows).
- **Variance (V17 Features):** 0.0 (Constant defaults).

## 5. Conclusion
Playbook G is currently learning from a field of constants. Promoting it to live stakes is **strictly forbidden** until the HFS is reconstructed with real doctrine signals.
