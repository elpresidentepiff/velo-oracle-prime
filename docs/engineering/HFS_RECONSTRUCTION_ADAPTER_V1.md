# HFS Reconstruction Adapter V1

## Overview
The HFS Reconstruction Adapter is a specialized hardened layer within the historical backfill process. It ensures that all historical feature data is computed using verified pure functions and subjected to strict temporal safety gates before being committed to the Historical Feature Store.

## Core Mandates
1.  **Isolated Calculation**: Features like MPI (Manipulation Probability Index) and Chaos Bloom are computed using deterministic pure functions (`app/services/hfs_pure_features.py`).
2.  **Temporal Safety**: Prevents "future leakage" by strictly checking odds timestamps against race execution/reconciliation timestamps.
3.  **Leakage Blocking**: If a pre-race odds timestamp is missing (e.g., using final SP price without proof of pre-race availability), the row is marked `training_safe = false` and `leakage_status = LEAKAGE_RISK`.
4.  **Provenance**: Every row contains a `_meta` block in its `feature_json` tracking the reconstruction version, batch ID, and audit ID.
5.  **Schema Compliance**: Produces rows that strictly match the 21-column HFS schema.

## Integration Point
The adapter is integrated into `scripts/backfill_historical_feature_store.py` within the `build_rows_for_race` function. This ensures that the live scoring service (`app/services/velo_prime_service.py`) remains entirely untouched and operational.

## Usage (Dry-Run Only)
```bash
PYTHONPATH=. python3 scripts/backfill_historical_feature_store.py --dry-run --limit-races 10
```

## Validation
- `tests/test_hfs_reconstruction_adapter.py` verifies:
    - Schema compliance (column count/order).
    - MPI/Chaos Bloom calculation and consistency.
    - Leakage detection for SP-only data.
    - Provenance metadata integrity.
