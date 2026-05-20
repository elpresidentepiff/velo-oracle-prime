# Dirty Worktree Containment V1

## Overview
This document classifies uncommitted modifications to core VÉLØ files to ensure repository containment and prevent experiment contamination. A full backup patch has been created at `data/dirty_worktree_backup_before_classification.patch`.

## File Classification

### 1. Heartbeat Critical / Shadow Loop Safety (KEEP)
These files contain mandatory instrumentation for the permanent shadow heartbeat and dashboard reliability.
- **`app/playbooks/playbook_g_sentient_loopback.py`**: Critical safety gate (`disable_cloud_backup`).
- **`scripts/run_results_sigma.py`**: Essential correctness fix (non-runner detection).
- **`app/main.py`**: Panel C dashboard support and authoritative Supabase fallback.
- **`app/services/velo_prime_service.py`**: Dashboard metadata reliability (race table upsert).
- **`app/static/dashboard/index.html`**: Panel C UI components.

### 2. HFS Repair Candidate (HOLD)
This file contains the core HFS repair refactor. It is functionally complete but requires a verified dry-run before commitment.
- **`scripts/backfill_historical_feature_store.py`**: Massive refactor to pure functions + safety gates.

### 3. Unauthorized / Unrelated (REVERT)
These changes are legitimate bug fixes but are unrelated to the current shadow-loop/intelligence mission.
- **`scripts/ingest_racecard_pdfs.py`**: PDF parsing bounds check.

## Safety Verdict
- **Experiments**: **BLOCKED** until dirty worktree is resolved.
- **HFS Dry-Run**: **BLOCKED** until backfill changes are committed or quarantined.
- **Supabase Writes**: **BLOCKED** (Except for authorized race metadata).

## Recommended Recovery Plan
1.  **Revert**: `git restore scripts/ingest_racecard_pdfs.py`.
2.  **Commit**: Stage and commit the Heartbeat Critical and Shadow Loop Safety files.
3.  **Hold**: Keep `scripts/backfill_historical_feature_store.py` staged separately for dry-run validation.

---
*Authorized by VÉLØ Command Authority | Containment Division*
