# VÉLØ Oracle Prime — Release Gap List

**Status:** Honest Release Blockers | **Revision:** 2026-04-18.01

This document lists the remaining gaps between current `main` and a defensible production release.

---

## 1. Release-Blockers (Must Fix)
*Fatal gaps that risk corruption of truth or system failure.*

- **Structural Ingestion Sequencing Bug:** Service B scoring may fire before the `runners` table is fully populated with late declarations. Result: top picks may miss better-weighted horses.
- **Stale Build Fingerprint:** The `/api/v1/build-fingerprint` endpoint in `app/main.py` is hardcoded to a legacy commit (`3b78e9d`). Current `HEAD` is `055aa9f`. This prevents definitive verification of the live code version on Railway.
- **API Key Hardening:** Ensure `API_KEY` is set in Railway environment variables for the `velo-oracle` service (verified as a dependency in `app/main.py`).

---

## 2. Verified & Completed (Audit Pass)
*Previously identified risks that have been formally closed.*

- **Supabase Migration Audit:** PROVEN (2026-04-18). Live Supabase production database is 100% synced with all post-20260405 migrations. Required columns for observability, horse state, and G-shadow instrumentation are present.

---

## 2. Degraded-But-Acceptable
*Gaps that can ship but require manual monitoring or "Watch" status.*

- **Phase 4 Test Failures:** 5 "expected" failures in backtest JSON serialization and feature naming. Does not affect live scoring but complicates future development.
- **Sigma Loop Reruns:** Lack of automated backfill for 404 errors (historical Racing API reruns require manual script execution).
- **Display-Only Data:** Several fields in `velo_verdicts` (macro_regime_label, etc.) are decorative and not yet consumed by Playbook G. This creates a "False Confidence Trap" for manual operators.

---

## 3. Post-Release Scope
*Future features that are intentionally excluded from the first release.*

- **Playbook G Live Promotion:** Moving from `shadow` to `live` mode requires 30 days of forensic attribution.
- **LangGraph Orchestration:** Currently unmerged; deferred until structural ensemble v1 stability is proven.
- **Betfair Execution:** The ledger exists, but the live execution bridge to Betfair is currently out of scope.
