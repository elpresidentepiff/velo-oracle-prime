# LOCAL-01 — Local Truth Reconciliation Audit (Full)
Generated: 2026-07-03 | Repo: /mnt/c/Users/puror/velo-oracle-prime | REPORT_ONLY

Four repo copies exist on this machine: `/home/purorpurorestrepo1981/velo-oracle-prime` (HEAD d573e94, 2026-04-05, stale), its WSL mirror, `~/.openclaw/workspace/repos/velo-oracle-prime` (HEAD 5967c74, 2026-03-23, stale), and `/mnt/c/Users/puror/velo-oracle-prime` (HEAD a8b3e8a, 2026-06-29, **active — this is the one audited**).

## A. Git / Branch Truth
- Current branch: `main`. Local HEAD = local `main` = `a8b3e8a`.
- `origin/main` = `018d618`.
- Ahead: 6 commits (ede88e6..a8b3e8a). Behind: 0.
- 29 modified tracked files, ~140 untracked files/dirs in working tree (raceday data, RESULTS/COURSE/J30 report families, council packets, new scripts).
- VCP commits e5b259b, ff86674, 5f83fec, a8b3e8a are all local, all on local `main`, none pushed. No separate VCP branch — built directly on main.
- Numerous stale/divergent branches exist locally (`merge/operator-integrity-core-2026-05-04` behind 350, `release/operator-integrity-approved` behind 350, an `worktree-agent-a4cfb9a6` worktree 156 behind `feature/v10-launch`). These predate and are unrelated to the current VCP/RESULTS/COURSE work.
- GitHub main (018d618) is stale relative to local not just in commits but in doc hygiene: local already archived `CURRENT_RUNTIME_TRUTH.md` out of root (part of e5b259b), GitHub's checkout still shows it at root because GitHub hasn't received that commit.

## B. VCP Local Truth
All three VCP core scripts and their operator briefs exist, are tracked, and are committed (see `local_01_missing_from_github_table.csv`). `data/current/velo_living_state.json` exists but is intentionally `.gitignore`'d (current-state scratch file, not history). VCP-03 burn-in is genuinely at 2/10 PASS days (2026-06-30, 2026-07-01), with Day 2 showing `promotion_learning: ELIGIBLE` and 1 recorded contradiction (C-01, carried from VCP-01, not suppressed). `next_safe_action` in the VCP-02 brief still literally reads `VCP-01-REVIEW` — this is stale boilerplate left over from the VCP-01 template and should be corrected in a later doc pass, but it is not evidence of a broken pipeline.

Filenames in the mission brief using `vcp03_*` (no underscore after "vcp") do not exist; the real convention is `vcp_03_*`. This is a naming mismatch in the audit brief, not a missing artifact.

## C. RESULTS / COURSE Local Truth
Every RESULTS-01, RESULTS-02, COURSE-00, COURSE-00A, and COURSE-00B file listed in the mission brief **exists on disk**, all generated 2026-06-30, all **untracked** (never `git add`ed, not gitignored — just not yet committed). COURSE-00C (planned CDP-based capture) does not exist — none of its 3 files were created; RP course-profile capture via plain HTTP is fully blocked (0 of 106 captured HTML pages usable: 53 x 404, 53 x login-required).

## D. RESULTS-01 vs Supabase
RESULTS-01 used a local sigma dump through 2026-06-23 (2,977 rows, 102 dates); Supabase's `sigma_audits` had grown to 3,167 rows by the external audit date — the gap is time, not a data-quality bug. Notably, Supabase's `pick_sp known: 1,212` is **exactly** the same absolute count as RESULTS-01's local `pick_sp_present: 1212/2977` — strong evidence Supabase has received zero new pick_sp values since this local snapshot, even as row count grew. RESULTS-01 should be rerun against a fresher sigma dump before being treated as canonical, or Supabase should be treated as canonical for row counts while RESULTS-01 remains canonical for its tier/course/exotics breakdowns (those aren't independently in Supabase).

## E. VFU-21 Local Truth
Ran 2026-06-17 (12 days before the VCP gate structure existed), self-terminated with `blocked_from_live_use: true`. Classification: **HISTORICAL_ARTIFACT / REPORT_ONLY_PREWORK**, not a gate violation — the VCP-01 brief's "VFU-21 gate: CLOSED" language is forward-looking (about continuing to VFU-22), not retroactive. Local ledger (3,052 rows), summary JSON and MD all exist and match GitHub exactly (VFU-21 v2 is already pushed at commit 7af104e).

## F. Supabase/Local Linkage
No local file found that maps `sigma_audits` rows to `velo_verdicts` IDs beyond what's already in Supabase (363/3,167 linked) — this needs a dedicated SUPA-02 pass. The VFU-21 pick_sp ledger is the strongest concrete repair candidate found (86.3% local coverage vs 38.27% in Supabase), but carries a negative EW ROI on the recovered data (-12.5%), so repairing *coverage* and trusting the recovered *price* for staking are separate operator decisions. `local_draw_stats_by_course.csv` (14 courses/49 races, VERIFIED_LOCAL) is not present in Supabase's `course_profiles` table (which has surface/country for 70 courses but zero handedness).

## G. Course Eyes Local Truth
COURSE-00C not built. RP course-profile capture is blocked at the HTTP layer (login-required/404), confirmed by COURSE-00B's own capture stats. `extract_local_draw_stats.py` output (49 races / 14 courses, VERIFIED_LOCAL) is confirmed on disk and matches the operator's prior recollection. Southwell is correctly annotated as Tapeta in `course_00a_verified_course_registry.csv`, but its source status is `SECONDARY_PUBLIC_SOURCE`, not `VERIFIED_LOCAL` — the registry filename overstates its own verification level. Most course facts (handedness, pace bias, draw bias except Chester/York/a few others) remain `HYPOTHESIS_*`.

## H. Local Data Inventory
`data/` = 3.7G total. `data/reports` = 88M / 790 files. `data/racing_post_account_raw` = 271M / 1,877 files (mostly unusable captures per COURSE-00B). `data/racecard_merged` = 55M / 356 files. `models/` = 114M. `data/current/` and `data/racing_post_account_raw/` are the two directories intentionally excluded via `.gitignore`; everything else untracked in `data/reports` is untracked by omission, not by policy, and is a real gap versus GitHub.

## I. Runtime Entrypoints
See `local_01_runtime_entrypoints_table.csv`. Core live path: `run_prime_today.py` (scoring, writes `pipeline_runs`) -> Telegram senders (`send_final_tg_report.py` et al.) -> `run_results_sigma.py` (evening reconciliation) -> `publish_daily_predictions_to_dashboard.py` (writes `velo_verdicts`). VCP triple and RESULTS/COURSE/VFU audits are all REPORT_ONLY. Several fields marked `unknown` where this pass could not fully confirm Supabase/Telegram touch without deeper script reads — flagged rather than guessed.

## J. Supabase Write Paths
Only 10 scripts actually import a Supabase client (`create_client`/`from supabase`); of those, 4 perform real writes: `run_prime_today.py` (`pipeline_runs` insert/update — the live scoring entrypoint), `build_rp_runner_signals.py` (`rp_runner_signals` upsert), `force_close_runs.py` (`pipeline_runs` update — dangerous if run by mistake), `publish_daily_predictions_to_dashboard.py` (`velo_verdicts` insert). A broad grep for `.insert(`/`.update(`/`.rpc(` alone was noisy (matched Python dict/list methods unrelated to Supabase) and was discarded in favor of the `.table(...)` pattern, which reliably identifies real Supabase calls.

## K. File Classification
See `local_01_file_classification_table.csv`. Core organs (`run_prime_today.py`, `run_results_sigma.py`, `racecard_loader.py`, `source_truth_enforcer.py`, `build_rpdc_daily.py`) = VITAL. VCP scripts = INTEGRAL. RESULTS/COURSE/VFU-21 audit scripts and their reports = USEFUL_SHADOW / REPORT_ONLY. `data/current/` and `data/racing_post_account_raw/` = ARCHIVE (correctly gitignored). Telegram senders and `force_close_runs.py` = DANGEROUS_DO_NOT_RUN outside the governed daily loop. Old integration branches (350 commits behind) and one stale worktree = STALE/UNKNOWN_NEEDS_REVIEW.

---
See `local_01_operator_brief.md` for the direct Q&A answer sheet and final classifications.
