# BRANCH SWEEP — 2026-07-29

Operator-ordered sweep following the one-truth consolidation (PR #155). Before this
sweep the repo had ~98 remote branches and ~75 local branches across three eras of the
system. After it: **one branch, `main`, everywhere.** Nothing was made unreachable —
every non-bot branch tip with unmerged commits was anchored to an annotated tag
`archive/2026-07-29/<branch-name>` (32 tags, pushed to origin) before deletion.

## Recovery
```
git log archive/2026-07-29/<branch-name>        # inspect an archived tip
git checkout -b restore/<name> archive/2026-07-29/<branch-name>   # resurrect
```
Bot branches (copilot/*, railway/*, dependabot/*) were deleted without tags — their
PRs preserve the refs on GitHub, and dependabot regenerates on demand.

## Salvaged into main (real fixes that had never landed)
| What | From | Landed as |
|---|---|---|
| Fail-closed pipeline_runs idempotence for `run_full_raceday.py` (+5 tests). The old check matched `velo_verdicts.race_id LIKE '%YYYYMMDD%'` — race_ids are plain numeric so it matched nothing, and it failed OPEN on error. Confirmed mechanism behind the 2026-07-15 double-scoring overwrite. | `fix/canonical-daily-run-p0-gaps` `bb35c69` (local-only, never pushed) | `b7aff7f` |
| NCS/Newcastle alias | `fix/ncs-newcastle-aw-duplicate-row` (PR #154) | verified already fully present in main (`run_results_sigma.py`, `app/main.py:2384`, `build_course_master.py`) — nothing to port; PR closed as landed |

## Notable archived tips (retrievable, deliberately NOT merged)
- **`feature/issue-78-midprice-hunter-module`** (`37f4322`, May 20) — complete Mid-Price
  Hunter Track A shadow module (`src/velo/midprice_hunter.py` + tests + run_prime_today
  wiring). Not merged: the wiring targets a 2-month-stale live scoring path and live
  weights are frozen; issues #78/#80 remain the living tracker. Resurrect from the tag
  if Track A is revived.
- **`evidence/race-day-15-frozen-recount`** (`2b9272d`, PR #151) — 277k-line forensic
  pack whose SCORECARD_GENERATED_NOT_PERSISTED finding drove the 2026-07-16 canonical
  wire-in fix. Evidence preserved at tag; PR closed.
- **`evidence/race-day-14-best-day-proof`** (`313d40c`, PR #150) — same treatment.
- **`ops-worker-shadow-loop-preserve`** (`70aab60`, 99 commits, May 19) — the deliberate
  pre-cleanup preservation branch tracked by issue #72. The tag now serves that purpose.
- **`stabilization/prime-hardening-v1`** (`b6150a7`, 84 commits, Jun 14) — parallel
  hardening line superseded by the governed baseline (PR #91, governance-v1-hardened).
- **`salvage/local-313-july04-07-preserve`** (`add706d`, local-only) — July 04–07
  uncommitted-evidence snapshot, archival by design.
- **`master`** (`864df4f`) — pre-`main` default branch, February era.

## PRs closed (10, each with explanation)
#154 (landed) · #151, #150 (evidence archived) · #127, #125, #119, #112 (superseded by
ONE_TRUTH consolidation) · #90 (superseded by governance-v1 line) · #69, #67 (April-era
Railway architecture, obsolete).

## Deleted without tags (fully merged or bot)
All branches whose tips were already contained in main (71 local incl. every
audit/sigma-2x, fix/champion-*, july04 family, backup/*, safety/*, merge/*), plus 16
copilot/*, 5 railway/*, 7 dependabot/* bot branches, plus one stale Claude agent
worktree branch.

## Safety rule applied
A branch was deleted ONLY if (a) `git rev-list --count origin/main..branch` == 0, or
(b) an `archive/2026-07-29/*` tag anchored its tip, or (c) it was a bot branch with a
PR-preserved ref. Anything else would have been skipped and reported; nothing was.
