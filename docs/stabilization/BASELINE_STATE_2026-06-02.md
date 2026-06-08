# PRE-HARDENING HISTORICAL BASELINE: 2026-06-02

**STATUS: ARCHIVED BASELINE**
*This document captures the system state BEFORE the stabilization and hardening work began.*

## Environment & Run Details (Pre-Snapshot)
*   **Active Branch:** `stabilization/prime-hardening-v1` (Initial)
*   **Target Date Configured:** 2026-06-02
*   **Execution Mode (`VELO_EXECUTION_MODE`):** Not globally enforced (assumed PAPER/ARCHIVE based on script runs)
*   **G Shadow Mode (`VELO_G_SHADOW_MODE`):** assumed offline/shadow
*   **Betfair Mode (`BETFAIR_MODE`):** Not globally enforced
*   **Active Ensemble Profile:** `core_v0_or_passport` (Challenger V1) and `sqpe_v17`
*   **Known Trigger Endpoints:** FastAPI currently serving `/api/governed-card` and `/api/old-velo-verdicts`.

## Canonical Scripts in Use
*   **Old Velo Scoring:** `scripts/ops/run_prime_today.py`
*   **New Build Scoring:** `scripts/ops/new_build_two_lane_score.py` & `scripts/ops/new_build_paper_score_today.py`
*   **Sigma Reconciliation:** `scripts/ops/run_results_sigma.py`
*   **RPDC/Newspaper:** `scripts/ops/build_rpdc_daily.py`

## Health Endpoint Expected Output
Currently lacks strict structural health checks; returns basic API status.

## Last Known Key Runtime Docs
*   `CURRENT_RUNTIME_TRUTH.md`
*   `README.md`
