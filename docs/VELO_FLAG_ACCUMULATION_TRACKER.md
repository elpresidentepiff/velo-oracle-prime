# VÉLØ Flag Accumulation Tracker

**Status:** ACTIVE ACCUMULATION | **Revision:** 2026-04-18.03

This document tracks the daily arrival of fresh reconciled races bearing the restored doctrine flags and mutation labels. 

---

## 1. Daily Accumulation Census

| Date | Total Reconciled | New Flag-Bearing | New Mutated | Audit Gate Status |
|---|---|---|---|---|
| **2026-04-18** | **784** | **0*** | **0** | **LOCKED** |

*\*Restored flags (cash_run, setup_run, decoy_support) exist in code but have 0 occurrences in the latest 100 reconciled production rows. Accumulation phase active.*

---

## 2. Audit Gaps (The 100-Race Gate)
We do not judge feature effectiveness until the following volume is met:

| Milestone | Target | Current | Status |
|---|---|---|---|
| **Cash-Run Presence** | 100 | 0 | **LOCKED** |
| **Setup-Run Presence** | 100 | 0 | **LOCKED** |
| **Mutation Integrity** | 100 | 0 | **LOCKED** |

---

## 3. Top-Level Integrity State
- **Schema Drift:** **VERIFIED FIXED.**
- **Top-Level Observability:** **VERIFIED FIXED.**
- **Subgroup Effectiveness Audit:** **DAY ZERO / NOT READY.**
- **Retraining:** **HARD HOLD.**

---

## 4. Daily Operational Task
1.  **Rebuild Dataset:** `python scripts/build_training_dataset.py`
2.  **Generate Scoreboard:** `python scripts/analyze_training_dataset.py`
3.  **Update Tracker:** Log new counts and check gate progress.
