# Phase 0 Pre-flight Note - VELO Tech Upgrade

**Date:** 2026-06-05  
**Executor:** Gem Gem Prime

## 1. System Orientation
*   **CURRENT_RUNTIME_TRUTH:** Read and confirmed. System is in PRODUCTION mode for Old VELO scoring but strictly SIM/PAPER for New Build. Hard guards in `execution_bridge.py` prevent live staking.
*   **CLAUDE.md:** Read and confirmed. Following GitNexus doctrine and safety protocols.
*   **GITHUB_TECH_SCOUT:** Read. DuckDB, Evidently, MLflow identified as P0 priorities for infrastructure hardening.

## 2. Dependency Audit
*   `duckdb`: **INSTALLED** (v1.5.3)
*   `tabulate`: **INSTALLED** (v0.10.0)
*   `evidently`: MISSING (Phase 2 target)
*   `mlflow`: MISSING (Phase 3 target)
*   `optuna`: MISSING (Phase 5 target)

## 3. Findings & Observations
*   **Spine Prototype:** I have already built a prototype DuckDB spine (`data/analytics/velo_analytics.db`) which successfully indexes:
    *   **6,168** Horse Passports
    *   **12,468** Paper Predictions
    *   **2,341** Verdicts
    *   **1,101** Innovation Protocol signals
    *   **1,461** Sigma Audits
*   **Evidence of Degradation:**
    *   **Incident A (RPDC Flatline):** Confirmed on 2026-05-24. Every runner had `improvement_score = 0.0872`.
    *   **Incident B (NULL Persistence):** Confirmed in `innovation_protocol`. 376 records missing `assigned_product`.
*   **Integrity:** Verified that `run_prime_today.py` and core scoring paths are free of betting execution imports.

## 4. Immediate Roadmap
1.  **Phase 1 Execution (Next):** Formalize `scripts/ops/query_evidence_duckdb.py` with canned queries and report generation.
2.  **Phase 2 Execution:** Implement Evidently drift reports.
3.  **HarnessGuard Packaging:** Prepare the "Scars" dataset for the AMD Hackathon using findings from Phase 1.

**Status: GREEN. No blockers. Live scoring untouched.**
