# HFS Signal Repair Audit V1

**Date:** 2026-05-05

## 1. Executive Summary
The Historical Feature Store (HFS) is currently **not training-safe** for Playbook G. Signals like `mpi` (Market Probability Index) and `chaos_bloom` are flat, null, or relying on proxy defaults.

## 2. Root Cause Analysis
- **Does the data exist?** Yes. There are thousands of entries for jockeys, trainers, courses, and distances.
- **Is the data wired?** No. The feature builder is failing to join this rich profile data into the final doctrine fields.
- **Proxy usage:** Scripts like `audit_hfs_signal_integrity_block001.py` and `global_clean_spine_audit.py` reveal that `mpi` is sourced from `archive_proxy_market_rank_v1` and `chaos_bloom` from `archive_proxy_market_entropy_going_v1`.
- **Pipeline Bypass:** `publish_daily_predictions_to_dashboard.py` explicitly states: `"mpi": "not computed in current pipeline"`.

## 3. Repair Plan
The issue is a broken feature contract, not missing data. To fix this:
1. **Wire the Joins:** Modify the data ingestion and feature building scripts (`build_unified_evidence_corpus.py`, `build_rp_runner_signals.py`) to explicitly join existing `trainer_profiles`, `jockey_profiles`, and `course_profiles` data.
2. **Compute Real Signals:** Calculate `mpi` and `chaos_bloom` using actual standard SPs (since Betfair BSP is not ingested in the Standard plan) rather than falling back to flat proxies.
3. **Backfill:** Re-run the backfill process for Block 001 to replace nulls/proxies with real distributions.
4. **Validation:** Re-run `audit_hfs_signal_integrity_block001.py` and ensure variance > 0 before enabling Playbook G Live.
