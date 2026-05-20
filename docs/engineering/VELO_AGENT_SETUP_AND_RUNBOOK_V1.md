# VÉLØ Agent Setup and Runbook V1

This document provides the foundational operating rules for any agent working on the VÉLØ codebase. Read this before taking any action.

## 1. Task Types & Workflows

1. **Daily Pipeline Operation:** Run standard prediction, ingestion, or sigma scripts.
2. **Code/Feature Updates:** Modifying pipelines, scrapers, or APIs. (Requires dry-run and test validation).
3. **Data Audits:** Investigating feature flatness, missing data, or database state.
4. **Deployments:** Railway-managed CI/CD.

## 2. Read-First Files

Before starting a task, agents **must** read:
- `CLAUDE.md` (Project rules, context, and secrets)
- `VELO_MASTER_LOG.md` (Running history of the system)
- `docs/engineering/VELO_PROCESS_CONTROL.md` (Canonical command list)
- `docs/engineering/VELO_KNOWN_ISSUES_AND_BLOCKERS_V1.md` (Current roadblocks)

## 3. Canonical Commands

Always use Python 3. Activate the virtual environment if possible, or prefix with `PYTHONPATH=.`.

- **Predictions:** `python3 scripts/run_prime_today.py`
- **PDF Ingestion:** `python3 scripts/ingest_racecard_pdfs.py`
- **Results & Sigma:** `python3 scripts/run_results_sigma.py`
- **Dashboard Publish:** `python3 scripts/publish_daily_predictions_to_dashboard.py`

## 4. Source of Truth Map

- **Active Code:** `app/` and `src/` directories.
- **Scripts:** `scripts/` (do not use `archive/dead_scripts/`).
- **Database:** Supabase (Remote). Local DB is deprecated.
- **Predictions / Verdicts:** `velo_verdicts` table.

## 5. Forbidden Actions

- **DO NOT** make scoring changes, model changes, or router changes unless explicitly instructed.
- **DO NOT** commit `.env`, `.claude.json`, or `settings.local.json`.
- **DO NOT** run destructive cleanup or delete files without approval.
- **DO NOT** claim a file or capability is "missing" until you have searched the active repo, archive, docs, data, and scripts.

## 6. Success Criteria & Stop Conditions

- A task is only complete when its canonical script runs cleanly and side-effects are verified (e.g., Supabase write or output JSON).
- **STOP** and ask for help if an environment dependency (like a missing python package) blocks execution.
- **STOP** and report if data required for a model (e.g., `mpi`, `chaos_bloom`) is flat or missing.
