# ROLLBACK MANIFEST

If the stabilization and hardening phases cause regressions, follow these rollback layers.

## Layer 1: Code Rollback
1. Delete the `stabilization/prime-hardening-v1` branch.
2. Checkout the `main` branch (or previous known-good commit).

## Layer 2: Configuration Rollback
Ensure the following variables (if changed) are restored in Railway and local `.env`:
*   `VELO_ENABLE_CANONICAL_PIPELINE_WRAPPERS=0`
*   `VELO_STRICT_SCRIPT_PATH_VALIDATION=0`
*   `VELO_STRICT_RECONCILIATION_MODE=0`
*   `VELO_STRICT_SAFETY_IMPORT_GUARD=0`
*   `VELO_EXECUTION_MODE` (Remove strict enforcement if it blocks)
*   `VELO_G_SHADOW_MODE` (Remove strict enforcement if it blocks)

## Layer 3: File Restoration
If a partial rollback is needed, restore the following files from `docs/stabilization/snapshots/`:
*   `app/main.py`
*   `scripts/ops/run_prime_today.py`
*   `scripts/ops/run_results_sigma.py`
*   `scripts/ops/ingest_results_to_horse_runs.py`
*   `src/intelligence/velo_prime_ensemble.py`
*   `src/velo/execution_bridge.py`
*   `CURRENT_RUNTIME_TRUTH.md`

## Layer 4: Post-Rollback Smoke Checks
1. Verify `/health` endpoint returns 200.
2. Verify `python scripts/ops/run_prime_today.py --dry-run` completes without error.
3. Verify `python scripts/ops/run_results_sigma.py --dry-run` (if flag exists) completes.
