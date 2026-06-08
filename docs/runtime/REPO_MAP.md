# VÉLØ REPO MAP

This document provides a one-page navigation guide to the VÉLØ Oracle Prime repository.

## 1. System Domains

| Domain | Directory | Role | Status |
| :--- | :--- | :--- | :--- |
| **Scoring Engine** | `app/engine/` | Core consensus orchestrator and specialist agents. | **LIVE** |
| **Pipeline Runners** | `app/pipelines/` | Canonical wrappers for daily execution. | **LIVE** |
| **Intelligence** | `src/intelligence/` | Model ensemble logic and weight management. | **LIVE** |
| **Models** | `models/` | Serialized model artifacts (Champion: `sqpe_v17`). | **LIVE** |
| **Data Layer** | `data/` | Feature matrices, snapshots, and prediction logs. | **LIVE** |
| **Audit & Sigma** | `scripts/ops/` | Reconciliation loops and performance analysis. | **LIVE** |
| **Playbook G** | `app/playbooks/` | Sentient loopback and tactical multipliers. | **SHADOW** |
| **Benchmark** | `benchmark/` | Regression protection system (Target: 2k races). | **INACTIVE** |

## 2. Authoritative Documents (Read These First)

1.  **`CLAUDE.md`** — The definitive technical guide for AI agents and developers.
2.  **`CURRENT_RUNTIME_TRUTH.md`** — The source of truth for current production paths.
3.  **`docs/operations/NEW_ENGINEER_BOOTSTRAP.md`** — Quick-start guide for onboarding.
4.  **`docs/operations/SCORING_RUNBOOK.md`** — How to run and verify daily scoring.

## 3. Directory Classification

*   **`app/`**: Production FastAPI application and core engine logic.
*   **`scripts/ops/`**: Production-grade operational scripts (Scoring, Sigma, Ingestion).
*   **`src/`**: Shared libraries, feature engineering, and model logic.
*   **`docs/`**: Structured documentation (Architecture, Operations, Safety).
*   **`data/`**: Runtime storage (Local backups and structured artifacts).
*   **`archive/`**: Retired scripts and superseded documentation.
*   **`research/`**: Experimental notebooks and non-production analysis.

## 4. Boundary Enforcement
*   **LIVE**: Logic that directly influences `velo_prime_prob` and decision tiers.
*   **SHADOW**: Logic that runs in parallel for evidence accumulation (e.g., Sidecars).
*   **PAPER**: Historical analysis or dry-run execution.
*   **ARCHIVE**: Static history; never imported by live paths.
