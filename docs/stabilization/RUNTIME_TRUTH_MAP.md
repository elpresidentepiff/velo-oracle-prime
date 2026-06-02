# RUNTIME TRUTH MAP

This document maps the documented vs actual paths for all major execution triggers and scripts, identifying drift and orphans.

| Component | Documented Path | Actual Path | Referenced By | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Scoring Trigger** | `/api/trigger/score-daily` | `scripts/ops/run_prime_today.py` | `app/main.py` | **Match** (Path in `app/main.py` is `scripts/ops/run_prime_today.py`) |
| **Sigma-Light Trigger** | `/api/trigger/sigma` | `scripts/ops/run_results_sigma.py` | `app/main.py` | **Drift** (`app/main.py` points to `scripts/run_results_sigma.py` which does not exist) |
| **Sigma-Full Trigger** | `/api/trigger/sigma-daily` | `archive/dead_scripts/close_sigma_loops.py` | `app/main.py` | **Orphan/Broken** (`app/main.py` points to `scripts/close_sigma_loops.py`, which is dead) |
| **Result Ingestion** | `scripts/ops/ingest_results_to_horse_runs.py` | `scripts/ops/ingest_results_to_horse_runs.py` | Cron/Manual | **Match** |
| **Mission Control** | `scripts/ops/update_mission_control.py` | `scripts/ops/update_mission_control.py` | Cron/Manual | **Match** |
| **Sidecar Feed Writer** | `scripts/ops/new_build_sidecar_feed_writer.py`| `scripts/ops/new_build_sidecar_feed_writer.py` | Manual | **Match** |
| **Dashboard** | `app/main.py` (FastAPI) | `app/main.py` | Railway | **Match** |
