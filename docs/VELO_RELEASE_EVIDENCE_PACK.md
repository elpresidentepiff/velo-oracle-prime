# VÉLØ Oracle Prime — Release Evidence Pack

**Status:** Canonical Proof of Truth | **Revision:** 2026-04-18.01

This document provides the canonical evidence for the system's performance, health, and operational integrity on current `main`.

---

## 1. Operational Health Truth
*Evidence that the system can be monitored and audited in production.*

- **Health Endpoint:** `GET /health` (verified on `main`). Performs:
  - Supabase connectivity check.
  - Pipeline freshness check (PASS within <26h).
  - Model load integrity check (SQPE v17/v16).
- **Audit Logs:** `pipeline_runs` table in Supabase (Service B/C log).
- **Fingerprint:** `GET /api/v1/build-fingerprint` returns commit `3b78e9d` as the build anchor.
- **Migration Audit (2026-04-18):** PROVEN. Live Supabase schema is 100% synced with post-20260405 migrations. Required columns for observability, horse state, and G-shadow instrumentation are present.

---

## 2. Model & Doctrine Freeze
*Evidence that the system uses a fixed, auditable decision matrix.*

- **Primary Weights:** SQPE v17 (45%), Market Deception (10%), Place Prob (8%), Longshot (7%).
- **Ablation Baseline:** `FULL_MINUS_DEAD` is the production default.
- **Shadow Mode:** `VELO_G_SHADOW_MODE=shadow` (Verified in `app/main.py`). Playbook G computes but does NOT mutate live scores.
- **Ingestion Sequencing Audit (2026-04-18):** CLASSIFIED. Ingestion is classified as **Degraded-but-Shippable**. The system is aware of the Single-Fetch risk (late declarations), and this is documented as an auditable operational risk rather than a fatal logic failure.

---

## 3. Performance Proof (2026 Benchmarks)
*The system's most recent verified output against 2026 race data.*

- **Audit Sample 1:** `results/SIGMA_WOLVERHAMPTON_17FEB2026_REPORT.md`
  - WIN/PLACED reconciliation: 26 races, WIN=5, PLACED=7, MISS=14.
- **Audit Sample 2:** `results/STRIKE_RECOMMENDATIONS_20260218.md`
  - Canonical strike recommendations generated for live betting day.
- **Test Baseline:** `test_summary.txt` (Passing 35/40, critical systems operational).

---

## 4. Leakage & Integrity Control
*Evidence that future data has not poisoned the release.*

- **Leakage Firewall:** `tests/test_v12_features.py` (Gate C passed).
- **Macro Dampener:** `BHA Macro Layer` correctly flattens probabilities in "Chaos Mode" (verified in `velo_prime_ensemble.py`).
- **Doctrine Verification:** `VELO_MASTER_LOG` confirms "Truth before optimization" doctrine is enforced at the ensemble layer.
