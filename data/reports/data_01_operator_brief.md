# DATA-01 — Local Artifact Preservation Map — Operator Brief
Generated: 2026-07-04 | REPORT_ONLY | no files moved, deleted, committed, or pushed | no Supabase writes

---

## Q1. What is still local-only?

**97 changed paths** on the laptop right now (30 modified tracked files + 67 untracked files), none of them committed. Broken down:
- **8 files** = real VCP-03 Day 2 / governance progress (`vcp_03_burn_in_log.json/.md`, `vcp_03_operator_brief.md`, `vcp_01/02_*_operator_brief.md`, `velo_heartbeat_latest.*`, `vcp03_day2_operator_docket.*`, `vcp03_post_burnin_decision_board.md`, `scripts/ops/build_vcp03_day2_docket.py`) — this is genuine unpushed governance work, same category as what PR #92 just merged.
- **7 new audit-generator scripts + 5 new tests** (`build_course_00_audit.py`, `build_course_00a_tribunal.py`, `build_j30_forensic_pack.py`, `build_results_01_audit.py`, `build_results_02_audit.py`, `extract_local_draw_stats.py`, `parse_rp_course_profiles.py` + their tests) — real code, currently nowhere but the laptop.
- **~45 report files** from RESULTS-01/02, COURSE-00/00A/00B, J30 forensic, local draw stats — the evidence LOCAL-01 already read and summarized, but the underlying files themselves were never committed.
- **~25 files** of daily operational data (council packets/reports/runs for 06-30, mission_control 06-30, sigma_results 06-30, timing_audit, telegram_delivery_truth, router_shadow_audit, velo_daily_run_truth, velo_run_observability, eod_*/nightly_eod_*/playbook_g_* for 06-29, radical_shadow, new_build passport feed, vfu_20 ledger updates) — same family as the `8753b4f` bulk sweep from REPO-01, just newer dates.
- **2 root launcher scripts** (`run_login.bat`, `run_login.sh`) — small, no secrets, unconventional location.
- Plus 11 accumulated `git stash` entries across multiple branches, some dating back to May — themselves a form of silent local-only state the new doctrine is meant to end.

## Q2. What would be lost if the laptop died today?

**Less than it looks.** Cross-checked against GitHub:
- `main`, the `audit/local-01-truth-reconciliation` branch (which includes the full `8753b4f` bulk sweep), the `reconcile/vcp-local-truth-clean-v1` branch, and the `doctrine/git-supabase-first-v1` branch are **all pushed to origin**. Nothing in git history — including the "dangerous" 474-file bulk commit — is at risk of disappearing with the laptop.
- The VFU-21 pick_sp ledger (`data/reports/vfu_21_pick_sp_backfill_ledger.jsonl`) is **already committed and pushed** (commit `7af104e`, on `origin/main`) — it is not local-only, contrary to how it's sometimes been described. It's a Supabase *write* candidate, not a git-loss risk.
- What **would** genuinely be lost: the 97 uncommitted/untracked changes above, and the 11 stashed diffs (some of which may be stale/abandoned work nobody would notice missing, others of which may be real).
- What is **correctly** local-only and would be lost, but *should* be: `data/browser_profiles/` (761MB of Firefox session/cookie data for RP login — correctly gitignored, this is exactly the kind of thing that should never be in git and losing it just means re-logging-in), `.env` (credentials, correctly gitignored), `data/current/` (12 small current-state scratch files, correctly gitignored), `data/racing_post_account_raw/` (271MB raw captures, correctly gitignored, mostly 404/blocked pages per the earlier COURSE-00B audit).

## Q3. What should go to GitHub?

The VCP-03 Day 2 progress, the 7 new audit scripts + 5 tests, and the ~45 RESULTS/COURSE/J30 report files. These are exactly the class of artifact the new doctrine calls `GITHUB_COMMIT` — code and reviewable evidence, small enough to review, no secrets. See `data_01_github_candidates.csv`.

## Q4. What should go to Supabase?

Nothing new was found this pass beyond what LOCAL-01/REPO-01 already identified: the VFU-21 pick_sp ledger remains the strongest repair candidate (already in git, not yet written to the `sigma_audits` table). No new Supabase-shaped artifact was discovered in this local sweep. See `data_01_supabase_candidates.csv` — it's short and mostly points back to SUPA-02's existing scope.

## Q5. What should become a data-backfill PR?

The ~25 files of daily operational data (council/mission_control/sigma_results/timing_audit/telegram_delivery_truth/router_shadow_audit/eod_*/playbook_g_*/vfu_20 updates for 06-29/06-30) — same family as `8753b4f`, same recommendation: bundle as its own dedicated, clearly-labeled PR, not mixed with code. See `data_01_data_backfill_candidates.csv`.

## Q6. What must stay local because secret/raw capture?

`.env`, `data/browser_profiles/` (761MB, Firefox session data), `data/racing_post_account_raw/` (271MB raw HTML captures), `data/current/` (12 files, intentionally volatile scratch). All four are already correctly `.gitignore`'d — confirmed via `git check-ignore`. No action needed; this is the doctrine working as intended.

## Q7. What is junk?

The 4 scratch files already flagged in REPO-01 (`data/_check_passport_coverage.py`, `data/_check_supabase_jun24.py`, `data/_tmp_fetch.py`, `data/_multimodel_june23_tmp.json`) are **already committed** — on the pushed `audit/local-01-truth-reconciliation` branch, inside `8753b4f`. They are not a data-loss risk (git history preserves them), but they remain hygiene junk that should never reach `main`. No new junk files were found in this pass. See `data_01_do_not_keep_candidates.csv`.

## Q8. What is the safest next migration step?

In this order:
1. **Fast-forward local `main`** to match `origin/main` (local `main` ref is currently stale at `a8b3e8a`, now 12 commits behind `origin/main` after the PR #92/#93 merges — trivial `git switch main && git pull --ff-only`, zero risk, but worth doing before anything else so "local main" stops lying about where main actually is).
2. **Commit the VCP-03 Day 2 progress** + the 7 audit scripts/5 tests to a new small PR against `main` — this is the same low-risk pattern as PR #92, just the next slice.
3. **Commit the ~45 RESULTS/COURSE/J30 report files** as a second PR (or bundled with #2 if the operator prefers one PR) — evidence, not code, but same low risk.
4. **Build the DATA-BACKFILL PR** for the ~25-file operational-data family, separately, clearly labeled, reviewed before merge.
5. **Run SUPA-02** (report-only) once the above is settled, so the Supabase repair plan is written against a GitHub state that's actually current.
6. Leave the 11 stashes and the gitignored secret/raw-capture directories alone — they need operator attention but are not urgent and not part of this migration.

## Q9. What must not be touched?

`.env`, `data/browser_profiles/`, `data/racing_post_account_raw/`, `data/current/` — all correctly local-only by design. The 8 stashes not authored this session (dated back to May, on branches unrelated to current work) — don't drop or pop them without knowing what they hold; they need a dedicated review, not a side effect of this mission. Supabase itself — no writes performed or recommended in this pass.

---
## Final Classifications
DATA_01_LOCAL_ARTIFACT_PRESERVATION_MAP_COMPLETE
NO_FILES_MOVED
NO_FILES_DELETED
NO_COMMITS_AFTER_DOCTRINE_MERGE
NO_SUPABASE_WRITES
NO_TELEGRAM_SEND
NO_COURSE_01_IMPLEMENTATION
NO_VFU_21_LIVE_START
NO_VCP_04_START
NO_MODEL_TRAINING
LOCAL_ONLY_ARTIFACTS_DECLARED
GITHUB_CANDIDATES_DECLARED
SUPABASE_CANDIDATES_DECLARED
DATA_BACKFILL_CANDIDATES_DECLARED
DO_NOT_KEEP_CANDIDATES_DECLARED
REPORT_ONLY
