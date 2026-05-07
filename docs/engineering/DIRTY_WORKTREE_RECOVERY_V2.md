# Dirty Worktree Recovery V2

## Overview
This document outlines the recovery of the VÉLØ repository worktree. Previous changes to dashboard, metadata, and PDF ingestion have been reverted to HEAD and saved as external patches to ensure a clean environment for shadow model experiments.

## Recovery Summary
- **Heartbeat Critical**: Only mandatory safety and correctness patches for the permanent shadow heartbeat have been preserved.
- **Quarantined**: HFS repair candidates and dashboard features have been saved to `../velo_recovery_patches/`.
- **Reverted**: Core production files (`app/main.py`, `app/services/velo_prime_service.py`, etc.) have been restored to HEAD.

## Final Commit Scope
Only the following files are authorized for the next safety commit:
1. `app/playbooks/playbook_g_sentient_loopback.py`: `disable_cloud_backup` safety gate.
2. `scripts/run_results_sigma.py`: Non-runner result correctness.
3. `data/dirty_worktree_classification_v2.json`: This audit.
4. `docs/engineering/DIRTY_WORKTREE_RECOVERY_V2.md`: This document.

## Status
- **Repository Health**: **RECOVERED**
- **Experiment Readiness**: **ACTIVE**
- **Safety Gates**: **LOCKED**

---
*Authorized by VÉLØ Command Authority | Containment Division*
