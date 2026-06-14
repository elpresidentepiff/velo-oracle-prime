# DOCS CONSOLIDATION MAP — VÉLØ ORACLE PRIME

**Date:** 2026-06-10 · Nothing archived yet — this is the map the approved sweep will execute.

## The rule going forward
- **Living operational truth** → `docs/current/` only. ONE_TRUTH.md wins all conflicts.
- **Historical proof / completed audits** → `docs/archive/` (after operator approval), one-line tombstone in the archive index.
- **Daily outputs** → `data/reports/` (proofs, cards) or `data/` (artifacts). Never into docs/.
- **No new numbered truth files.** A new doc enters `docs/current/` only if it replaces or consolidates existing truth.

## Current truth docs (KEEP — the spine)
`docs/current/`: ONE_TRUTH · RACE_DAY_RUNBOOK · RACE_DAY_11_EXECUTION_PACKET · LEARNING_ADMISSION_GATE · RACING_API_DECOMMISSION_LIVE_PATH_AUDIT · SUPABASE_REALITY_AUDIT · PERFORMANCE_AND_MONEY_REALITY_AUDIT · PRODUCTION_READINESS_SCORECARD · SIMPLIFICATION_AUDIT · MINIMAL_PRODUCTION_FIX_PLAN · NEXT_10_PRODUCTION_FIXES · VELO_IVY_LEAGUE_PRODUCTION_PLAN · SENIOR_DEV_SIGNOFF_CHECKLIST · DOCS_CONSOLIDATION_MAP · ONE_RACE_DAY_COMMAND_SPEC.
Plus root `THE_ONE_TRUTH.md` (step-by-step manual, referenced by ONE_TRUTH).

Note: the dated audit docs (SUPABASE_REALITY, PERFORMANCE_AND_MONEY, scorecards) are point-in-time evidence — when superseded by a newer audit they move to `docs/archive/` with the rest.

## Merge into ONE_TRUTH, then archive
| Doc | What survives the merge |
|---|---|
| `THE_NEW_TRUTH.md` (root) | Component feature lists, RPD-C tag hierarchy — already absorbed; archive whole file |
| `CURRENT_RUNTIME_TRUTH.md` (root) | File-classification tables; evening path is WRONG (names nonexistent `scrape_results_atr.py`) |
| `docs/live_state/MASTER_STATE.md` | Any state line still true |
| `docs/operations/SCORING_RUNBOOK.md`, `SIGMA_RUNBOOK.md` | Anything RACE_DAY_RUNBOOK lacks |
| `docs/runtime/RACE_DAY_PREP_QUICK_REFERENCE.md`, `RACE_DAY_BUTTON_LAYOUT.md` | Nothing (button deprecated) — archive |

## Duplicate / stale / numbered docs (ARCHIVE after approval)
- `docs/` flat: 133 files — all VELO_* forensics, TIE_V2/V3 designs, PHASE reports, superseded plans → `docs/archive/flat-2026-06/`, keep any file ONE_TRUTH references.
- `docs/stabilization/`: completed-era artifacts; keep ROLLBACK_RUNBOOK + ROLLBACK_MANIFEST accessible (link from ONE_TRUTH), archive the rest.
- `docs/system_audits/`, `docs/audit/`, `docs/agent_handoffs/`, `docs/agent_zero/`, `docs/hackathon-adjacent`: archive wholesale.
- Root strays: `Makefile` (Benter-era), `cron.txt`, `COMMAND.json`, `sigma_tonight.sh`, `sigma_workflow_patch.yml` → archive/delete per SIMPLIFICATION_AUDIT classifications (operator approves deletions).
- `CLAUDE.md`: banner + Racing API corrections applied 2026-06-10; full ~40-line rewrite pointing at docs/current is the follow-up.

## One-off audit docs already classified
See `SIMPLIFICATION_AUDIT.md` for the per-file table (KEEP_CURRENT / ARCHIVE / DELETE_AFTER_APPROVAL / MERGE_INTO_ONE_TRUTH / SHADOW_ONLY / DEPRECATED_REFERENCE / NEEDS_OPERATOR_DECISION).

## Execution order for the approved sweep
1. Operator reviews SIMPLIFICATION_AUDIT + this map and approves.
2. `git mv` archives in one commit per group (root docs / flat docs / stabilization) — reversible.
3. Deletions (cron.txt, COMMAND.json, one-night patch scripts) in a single separate commit, each named in the message.
4. CLAUDE.md rewrite last, after the moves, so its pointers are final.
