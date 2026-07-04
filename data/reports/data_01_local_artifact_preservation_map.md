# DATA-01 — Local Artifact Preservation Map (Full)
Generated: 2026-07-04 | REPORT_ONLY | Branch: `audit/local-01-truth-reconciliation`

## 1. Git/local state

- Current branch: `audit/local-01-truth-reconciliation`, up to date with its remote.
- **Local `main` is stale**: still points at `a8b3e8a`. After PR #92 and #93 merged directly on GitHub, `origin/main` advanced to `1ed8462` — local `main` is now `ahead 6, behind 12` of `origin/main`. This is cosmetic (a simple fast-forward fixes it) but is exactly the kind of "local doesn't reflect GitHub truth" drift the new doctrine exists to prevent. Recommend fast-forwarding local `main` as the very first step of any follow-up.
- **11 stashes** exist across the repo, spanning multiple branches and dates (some from May 2026): `stash@{0}` through `stash@{10}`. None were created or touched in this session except transient stash/pop pairs used to move between branches during REPO-02 work (which were popped back immediately each time — none of those remain). The 11 pre-existing stashes are untouched, unreviewed, and represent exactly the kind of silent local-only state the doctrine flags. Not resolved in this pass — flagged for operator review.
- Branch topology otherwise unchanged from REPO-01/REPO-02 findings: `audit/local-01-truth-reconciliation` still carries the full un-split history including `8753b4f`; `reconcile/vcp-local-truth-clean-v1` and `doctrine/git-supabase-first-v1` are both merged into `main`.

## 2. Local uncommitted tracked files (30)

All 30 are modifications to files whose *baseline* is already committed somewhere in git (either on `main` directly, or on the pushed `audit/local-01-truth-reconciliation` branch via `8753b4f`). None of these are first-appearances — they're daily-refresh deltas. Classification:

- **GITHUB_COMMIT (8 files)**: `data/reports/vcp_01_living_state_operator_brief.md`, `vcp_02_heartbeat_operator_brief.md`, `vcp_03_burn_in_log.json`, `vcp_03_burn_in_log.md`, `vcp_03_operator_brief.md`, `velo_heartbeat_latest.json`, `velo_heartbeat_latest.md` — these are the VCP-01/02/03 daily-refresh outputs; their committed baselines are already on `main` via PR #92, so today's deltas (VCP-03 Day 2, in particular) are a direct, low-risk follow-up commit.
- **DATA_BACKFILL_CANDIDATE (22 files)**: everything else in this list — `data/eod_playbook_g_shadow_critique_20260629.json`, `data/eod_result_study_20260629.{json,md}`, `data/mission_control/latest.json`, `data/new_build/reports/current_card_passport_feed_latest.{json,md}` (3.69MB json — large but text, not binary), `data/new_build/reports/passport_coverage_latest.json`, `data/nightly_eod_learning_status_2026_06_29.json`, `data/playbook_g_nightly_audit_2026_06_29.json`, `data/reports/racecard_cache_gate_latest.{json,md}`, `data/reports/radical_shadow_latest.{json,md}`, `data/reports/vfu_20_field_size_recovery_audit.json`, `vfu_20_field_size_remediation_summary.json`, `vfu_20_field_size_repaired_ledger.jsonl` (7.16MB — the largest single file in this set), `vfu_20_label_reconciliation_after_repair.json`, `vfu_20_operator_brief.json`, `data/router_shadow_audit_latest.md`, `data/sigma_memory/sigma_retrieval_corpus_v1_report.json`, `data/telegram_delivery_truth_2026_06_30.json`, `data/timing_audit/runtime_timing_audit_2026_06_30.json`, `data/velo_daily_run_truth_2026_06_30.md` — all daily-operational-data refreshes, same family as `8753b4f`, recommended for the dedicated data-backfill PR rather than mixed into a code PR.

Note on `data/reports/vfu_20_operator_brief.json`: its committed baseline predates this entire audit chain (commit `ffc37e0`, already on `main` independently of PR #92/#93) — it's a pre-existing, unrelated file that happens to have a same-day local update. Classification unaffected.

## 3. Local untracked files (67)

- **VCP-03 Day 2 artifacts (2)**: `data/reports/vcp03_day2_operator_docket.{json,md}`, `data/reports/vcp03_post_burnin_decision_board.md` → **GITHUB_COMMIT**.
- **New audit-generator code (7) + tests (5)**: `scripts/ops/build_course_00_audit.py`, `build_course_00a_tribunal.py`, `build_j30_forensic_pack.py`, `build_results_01_audit.py`, `build_results_02_audit.py`, `extract_local_draw_stats.py`, `parse_rp_course_profiles.py`, plus `scripts/ops/build_vcp03_day2_docket.py`, and `tests/test_course_00_audit.py`, `test_course_00a_tribunal.py`, `test_j30_forensic_pack.py`, `test_results_01_audit.py`, `test_results_02_audit.py` → **GITHUB_COMMIT**. Same category as the VCP scripts already merged in PR #92.
- **RESULTS-01/02, COURSE-00/00A/00B, J30 forensic report files (~45)**: e.g. `results_01_full_results_truth_audit.{json,md}`, `results_01_operator_brief.md`, `results_02_course_intelligence_audit.{json,md}`, `course_00_course_eyes_completion_pack.{json,md}` (404KB json — largest report here, still text/reviewable), `course_00a_source_provenance_tribunal.{json,md}`, `course_00b_rp_capture_operator_brief.{json,md}`, `course_intelligence_rp_raw.json`, `course_manual_extract.json`, `local_draw_stats_summary.md`, all `j30_*_2026-06-30.{json,md}` files → **GITHUB_COMMIT**. These are exactly what LOCAL-01 already read and summarized; the underlying files themselves were never committed. Per doctrine rule 7, reports/audit evidence belong on GitHub even when sizable, as long as they're text and reviewable — all of these qualify.
- **Council/mission-control/sigma daily snapshots (~10)**: `data/council_packets/council_packet_2026-06-30.json`, `data/council_reports/velo_council_report_2026-06-30.md`, `data/council_runs/council_run_2026-06-30.json`, `data/mission_control/2026-06-30_mission_control.json`, `data/sigma_results/sigma_results_2026_06_30.{json,md}`, `data/radical_shadow_2026_06_30.{json,md}`, `data/router_shadow_audit_runs/router_shadow_audit_20260630_222946.md`, `data/velo_run_observability_2026_06_30_e872189b.json` → **DATA_BACKFILL_CANDIDATE**, same family as the `8753b4f` sweep, just one day newer.
- **Operator card snapshots (2)**: `scripts/data/place_signal_operator_card_2026_06_22.md`, `_24.md` → **DATA_BACKFILL_CANDIDATE**.
- **Root launcher scripts (2)**: `run_login.bat`, `run_login.sh` → **UNKNOWN_OPERATOR_REVIEW**. No secrets (they source `.env` and launch a Firefox-profile login flow correctly), but they sit at repo root rather than in `scripts/`, which is unconventional. Not moved in this pass — flagged for an operator decision on whether they belong in git at all, and if so, where.

## 4. GitHub destination decisions

See `data_01_github_candidates.csv` for the full file-by-file list. Summary: commit VCP-03 Day 2 files + new code/tests directly to a follow-up PR against `main` (same low-risk pattern as PR #92); commit the RESULTS/COURSE/J30 report files either in the same PR or a separate "evidence" PR, operator's call — both are equally safe.

## 5. Supabase destination decisions

No new Supabase-shaped artifacts were discovered in this local sweep beyond what LOCAL-01/REPO-01 already found. The VFU-21 pick_sp ledger remains the only concrete repair candidate, and it's already safely in git (not at risk) — the open question is purely "should we write it to `sigma_audits`," which belongs to SUPA-02, not DATA-01. See `data_01_supabase_candidates.csv`.

## 6. Do-not-lose guarantee (preservation table)

See `data_01_local_artifact_preservation_map.json` for the machine-readable version and the CSVs for the destination-specific breakdowns. Headline: nothing found in this pass is at risk of silent loss that isn't already either (a) safely committed to a pushed branch, or (b) correctly gitignored secret/raw-capture data. The risk is organizational (untracked work sitting around, 11 unreviewed stashes), not data-loss.

## 7. Special-focus items

- **`8753b4f` bulk data sweep**: already pushed to `origin/audit/local-01-truth-reconciliation`. Not at risk of loss. Still not merged to `main` — awaiting the DATA-BACKFILL PR decision per REPO-01/REPO-02.
- **VCP-03 Day 2 burn-in progress**: local-only, uncommitted, genuine governance progress. Recommend committing next.
- **Today's raceday files**: covered under the DATA_BACKFILL_CANDIDATE group above.
- **`vfu_20_*` working-tree files**: modifications to an already-committed, already-on-`main` baseline (commit `ffc37e0`, unrelated to this audit chain). DATA_BACKFILL_CANDIDATE.
- **VFU-21 pick_sp ledger**: already committed and pushed (`7af104e`, on `origin/main`). Not local-only. Repair-write to Supabase remains a SUPA-02 decision.
- **RESULTS-01/02 files**: untracked, GITHUB_COMMIT candidates.
- **COURSE-00/00A/00B files**: untracked, GITHUB_COMMIT candidates.
- **COURSE-00C**: still not built (confirmed absent again — no change since LOCAL-01).
- **J30 forensic files**: untracked, GITHUB_COMMIT candidates.
- **Council reports**: untracked (06-30 snapshot), DATA_BACKFILL_CANDIDATE.
- **`data/current/`**: 12 small files, correctly gitignored, genuine volatile scratch (branch-protection/capture-proof/hardening/task-contract/worktree-safety "latest" pointers plus `velo_living_state.json`). LOCAL_ONLY_SCRATCH by design.
- **`data/racing_post_account_raw/`**: 271MB, correctly gitignored, mostly unusable captures per the earlier COURSE-00B audit (0/106 pages OK). LOCAL_ONLY_SECRET_OR_RAW_CAPTURE.
- **`data/browser_profiles/`**: 761MB, correctly gitignored, Firefox profile/session data for RP login. LOCAL_ONLY_SECRET_OR_RAW_CAPTURE — this is the single largest local-only artifact found in this audit, and it is exactly where it should be (never in git).
- **Raw RP HTML**: covered under `data/racing_post_account_raw/` above.
- **`.env` / credential / cookie / browser-profile files**: `.env`, `.env.example`, `.env.template` found at root plus `workers/ingestion_spine/.env.example`. Only the real `.env` is gitignored and untracked (confirmed); the two `.example`/`.template` files are intentionally tracked templates with no real credentials — correct as-is.
- **Scratch debug files**: the 4 files flagged in REPO-01 (`data/_check_passport_coverage.py`, `data/_check_supabase_jun24.py`, `data/_tmp_fetch.py`, `data/_multimodel_june23_tmp.json`) are present in the working tree because they're already committed (via `8753b4f`, on the pushed audit branch) — not a loss risk, but confirmed `DO_NOT_KEEP` for any future merge to `main`.
