# REPO-01 — GitHub Main Reconciliation Plan (Full)
Generated: 2026-07-03 | REPORT_ONLY | main untouched

## Scope compared
`origin/main` (018d618) .. `audit/local-01-truth-reconciliation` (b0c354f)
7 commits, 555 files changed, 470,571 insertions(+), 56,982 deletions(-)

## Per-commit breakdown

| Commit | Subject | Files changed | Category |
|---|---|---|---|
| ede88e6 | fix(dashboard): NB top3 missing for all races on governed-card API | 2 | Code fix — safe |
| 8753b4f | chore(data): raceday 2026-06-29 sigma + learning + June 30 prep | 474 | Bulk data backfill — needs split |
| e5b259b | fix(A-3)+chore(VCP-00): going_code regression fix + truth lock + docs archive sweep | 55 | Mostly doc renames — safe |
| ff86674 | feat(VCP-01): VÉLØ Living State Packet | 4 | VCP code/report — safe |
| 5f83fec | feat(VCP-02): VÉLØ Heartbeat V1 | 6 | VCP code/report — safe |
| a8b3e8a | feat(VCP-03): Ten-Day Coherence Burn-In — Day 1 PASS | 6 | VCP code/report — safe |
| b0c354f | audit(local): LOCAL-01 truth reconciliation report | 9 | Audit reports — safe, is the point of this exercise |

**The 8753b4f commit alone is 85% of the changed files.** It bundles ~3 weeks (2026-06-09 to 2026-06-29) of previously-uncommitted daily operational artifacts: `data/reports/` (105 files), `data/sigma_results/` (29), `data/learning_inputs/` (20), `data/sigma_memory/` (15), `data/mission_control/` (15), `data/council_runs/reports/packets` (43 combined), `data/timing_audit/` (9), `data/new_build/reports/` (9), `data/race_shape/` (8), `data/router_shadow_audit_runs/` (4), dated racecard snapshots, and 4 model `feature_importance.csv` updates. It also contains 4 scratch/debug scripts that were accidentally committed inside `data/` instead of `scripts/`.

## Dangerous-file check (Q4)

- **Temp/scratch scripts found:** `data/_check_passport_coverage.py`, `data/_check_supabase_jun24.py`, `data/_multimodel_june23_tmp.json`, `data/_tmp_fetch.py`. All hardcode the absolute path `C:\Users\puror\velo-oracle-prime`, not portable, no lasting purpose beyond one-off debugging on 2026-06-23/24. They correctly read Supabase credentials via `os.getenv(...)` — **no secrets are hardcoded** — but they are junk in the wrong directory. Classification: `DO_NOT_MERGE` / `DELETE_CANDIDATE`.
- **Secrets scan:** full diff scanned for `api_key`, `secret`, `password`, `token`, `service_role`, `BEGIN PRIVATE`, `sk-ant`, `sk-proj`, `AKIA`. Zero literal credential values found. All matches are either safe `os.getenv()` references or incidental substring matches inside racecard/comment text (e.g. a horse-form comment containing "akian" as a substring). One historical doc line (now archived) references "rotate Racing API password" as an old audit action item — text, not a live secret.
- **Large binary/generated outputs:** none — all changed files are text (JSON/JSONL/MD/CSV/PY). No videos, images, model binaries, or browser-profile data in this diff.
- **Stale reports:** the 34 `R100` renames move genuinely stale root docs (`CURRENT_RUNTIME_TRUTH.md`, `THE_NEW_TRUTH.md`, and 32 `docs/current/*` files) into `docs/archive/` — this is the fix, not a problem.

## VCP / governance / dashboard safety confirmation (Q5-7)

- `scripts/ops/build_velo_living_state.py`, `build_velo_heartbeat.py`, `build_vcp03_burn_in_log.py` — each REPORT_ONLY, no Supabase/Telegram writes detected, already run successfully for 2 consecutive days locally. **Safe to merge.**
- Governance/docs cleanup (`CLAUDE.md`, `README.md`, `docs/current/ONE_TRUTH.md`, 34 renames) — pure documentation accuracy and reorganization, zero runtime behavior change. **Safe to merge.**
- Dashboard fix (`app/main.py`, `publish_daily_predictions_to_dashboard.py`) — 9-line diff, already running locally since 2026-06-29 without reported regression. **Safe to merge.**

## Raceday-data commit decision (Q8)

Recommend **splitting**, not merging as-is:
1. Remove the 4 scratch files permanently (never merge, candidates for local deletion once operator confirms no other reference).
2. Re-commit the remaining ~470 files as their own dedicated, clearly-labeled data-backfill commit/PR, separate from code changes, so review and `git blame` stay meaningful.
3. Model `feature_importance.csv` files (4) can ride with either PR — low risk, operator's call.

## LOCAL-01 report commit decision (Q9)

**Merge.** Its entire purpose is external visibility; leaving it stranded on a branch that might later be deleted defeats that purpose.

## Merge plan (Q10)

**Option C selected: build a clean branch from `origin/main` with only the safe, reviewed set.**

Proposed clean-branch contents (not yet created — this is a plan):
- `e5b259b` non-rename files: `CLAUDE.md`, `README.md`, `docs/current/ONE_TRUTH.md`, `scripts/ops/new_build_two_lane_score.py`, `tests/test_new_build_paper_scorer.py`
- 34 `R100` doc renames from `e5b259b`
- `ff86674`, `5f83fec`, `a8b3e8a` in full (VCP-01/02/03 code, reports, task contracts, tests)
- `ede88e6` in full (dashboard fix)
- `b0c354f` in full (LOCAL-01 reports)

Total for the clean PR: **82 files**, all individually reviewed as safe in this pass, versus 555 in the raw branch diff.

The `8753b4f` raceday-data backfill (474 files minus 4 scratch files = 470 files) becomes a **separate operator decision**, tracked but not bundled.

## What was NOT done in this pass
No clean branch was created. No cherry-pick was performed. No PR was opened. No merge to `main` occurred. `main` remains at `a8b3e8a` locally / `018d618` on `origin/main`. This document is the plan; execution requires a follow-up authorization.
