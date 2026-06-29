# 100-DAY RECONCILIATION — SCOPE

**Date:** 2026-06-10 · Universe built from actual artifacts, not calendar assumptions.

| Fact | Value |
|---|---|
| First race day | **2026-03-15** |
| Last race day | **2026-06-10** |
| Race days found | **87** (union of local verdict days and Supabase verdict days) |
| Local verdict backups | 63 days (2026-03-17 → 2026-06-10) |
| Supabase verdict days | 81 days (18 cron-era days have Supabase rows but **no local backup**) |
| Sigma artifacts (recomputable, local) | 19 days (2026-05-21 → 2026-06-09) |
| Supabase `sigma_audits` rows | 2,528 rows bucketed per day (extends sigma evidence before May 21) |
| Results files | 18 canonical (`data/results/`) + 71 legacy (`data/results_*.json`, back to 2026-03-15) |
| Observability packets | 13 days only (2026-05-29 → 2026-06-10) — **source truth is unprovable before May 29** |
| Mission Control files | 23 days (2026-05-15 →) — pre-fix MC defaulted CLEAN, so its labels are advisory only |
| Learning runs (nightly status/Playbook G audits) | 23 days (2026-04-29 → 2026-06-08) |
| `racing_horse_runs` | current through 2026-06-09 (94,915 rows) |

**Builder:** `scripts/ops/build_100_day_truth_ledger.py` (read-only; GET-only Supabase).
**Ledger:** `data/current/velo_100_day_truth_ledger.json` + `data/reports/velo_100_day_truth_ledger.md`.

Key structural facts that shape every downstream judgment:
1. The RPDC persist hijack window (2026-04-21 → 2026-06-10) covers **every** day that has local sigma artifacts. There is no sigma-verified day outside the hijack window.
2. Source truth is only *provable* from 2026-05-29 (first observability packets). Earlier days can never be upgraded to SIGNED_CLEAN retroactively — they are historical outputs.
3. Supabase RPDC tags exist on exactly two days in history: 2026-04-13 and 2026-04-21. From 2026-04-22 the persist boundary silently erased RPDC evidence every day.
