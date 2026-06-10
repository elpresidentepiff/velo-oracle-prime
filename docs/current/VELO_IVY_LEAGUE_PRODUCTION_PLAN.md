# VÉLØ IVY LEAGUE PRODUCTION PLAN

**Date:** 2026-06-10 · Master plan. Supersedes scattered roadmaps for production-engineering scope. Model/feature research roadmaps live elsewhere and are unchanged.

## 1. Current state (proven 2026-06-10)
Scoring core is strong: 34/34 races scored and persisted with full lineage (commit SHA, ensemble components per row). Learning gates are genuinely multi-layered. But: every run is manual (`MANUAL_RECOVERY_ONLY`), cron unproven, Telegram disabled, the day scored DEGRADED without a pre-check, Mission Control can mislabel degraded days CLEAN, RPDC persistence has been silently severed since April 21, the paper ledger can't close results (ID chain), pytest can't run, CI tests a legacy worker, and three contradictory truth docs sit at root.

## 2. Target state
One command runs a race day. Every stage emits a proof artifact. Degraded is loud and pre-scoring. Mission Control never lies. Supabase rows are self-describing (source health on-row). Tests run locally and in CI on every push. One truth spine in `docs/current/`. Everything else archived.

## 3. The one live path
```
RP HTML capture → parse → validate_rp_injection (GATE) → merged build + PDF-intel coverage check
→ build_rpdc_daily → run_prime_today (--source rp) → Supabase velo_verdicts + local backup + observability
→ [evening] results capture → parse → sigma → horse_runs ingest → corpus → Mission Control → Council
→ learning runner (only on PASS_TO_LEARNING) → bridge/router shadow audits
```
Formula: `SQPE_IMPROVEMENT_MDS_V1` — VP = (0.45·sqpe_v17 + 0.12·improvement + 0.10·MDS)/0.67. UNCHANGED.

## 4. The one race-day command target
`python scripts/ops/run_race_day.py --date D --phase morning|evening [--dry-run]` (Fix #9) — a thin orchestrator that subprocesses the existing One Truth scripts, threads `FINAL_CAPTURE_LABEL` automatically, stops on first failure, prints next command. No scoring logic inside it, ever.

## 5. The one truth doc structure
```
docs/current/ONE_TRUTH.md            ← state truth (what is live/shadow/blocked)
docs/current/RACE_DAY_RUNBOOK.md     ← lifecycle
THE_ONE_TRUTH.md (root)              ← step-by-step command detail (referenced)
docs/current/*_AUDIT.md              ← dated evidence audits
everything else                      ← docs/archive/ after approval
```

## 6. Supabase truth requirements
- June-10-style persistence proof after every run (Fix #3).
- `source_truth` + `feature_degraded` columns on `velo_verdicts` (migration, approval).
- RPDC columns carry RPDC data again (Fix #2, approval).
- Ledger/innovation rows use real RP IDs end-to-end so results close.
- `market_snapshots`/`results` either get a writer or are dropped from docs.

## 7. Mission Control truth requirements
- Source truth read from observability artifact; `UNKNOWN` when missing; never CLEAN by default (Fix #1).
- Observability packet is a required MC input (Fix #4).
- MC gate reasons must include RPDC attach coverage and persistence proof status.

## 8. Race Day 11 rehearsal result
Read-only rehearsal performed 2026-06-10: session check RUNS; June 10 injection gate PASS (34/34/381 consistency across injection→verdicts→RPDC); `--dry-run` mode confirmed to disable persistence+Telegram. Full dry-run scheduled for the morning of June 11 per RACE_DAY_11_REHEARSAL_PLAN.md.

## 9. Testing requirements
pytest ≥8.2 pinned; 3 drifted modules repaired; harness-enforcement tests green; new unit tests for MC source truth, RPDC persist mapping, degraded banner; golden-path smoke test runnable offline.

## 10. CI requirements
`ci.yml` runs `tests/` on every push/PR to this branch and main; ingestion_spine job kept only if that worker stays live (operator decision); failing CI blocks merge.

## 11. Archive/delete strategy
Per SIMPLIFICATION_AUDIT.md classifications. Order: commit current work → archive MERGE'd truth docs → archive dated one-off scripts → delete only DELETE_AFTER_APPROVAL items, each individually approved. Nothing deleted before its content is merged or proven dead.

## 12. Docs consolidation strategy
`docs/current/` is canonical. Root keeps only README, THE_ONE_TRUTH (step manual), LICENSE, MANDATE. CLAUDE.md rewritten to ~40 lines pointing at docs/current. Every archived doc gets a one-line tombstone in the archive index.

## 13. Operator approval gates
| Decision | Needed for |
|---|---|
| RPDC persist fix (#2) | changes Supabase write payload |
| `source_truth` migration | schema change |
| Ledger ID-chain repair | rewrites how bridge rows are keyed |
| Telegram re-enable | outward-facing |
| Cron: fix Railway vs manual-first | operations posture |
| Archive/delete batch | irreversible-ish |

## 14. Weekly roadmap
- **Week of Jun 10:** Fixes #1, #3, #5, #6 (no-approval set) + June 11 rehearsal. Operator decisions taken on #2 and migration.
- **Week of Jun 17:** #2 (if approved), #7, #8 — tests + CI green. Ledger ID-chain repair design.
- **Week of Jun 24:** #9 orchestrator in dry-run for 3 days, then primary. #10 docs sweep.
- **Week of Jul 1:** 5 consecutive clean orchestrated days → sign-off review against SENIOR_DEV_SIGNOFF_CHECKLIST.md.

## 15. Definition of production-ready
Five consecutive race days where: one command ran each phase · zero hand-copied labels · source health CLEAN or loudly degraded BEFORE scoring · persistence proof green · Mission Control matched observability · evening chain completed through Step 20 or stated `DAY INCOMPLETE` with the exact blocker · CI green throughout.
