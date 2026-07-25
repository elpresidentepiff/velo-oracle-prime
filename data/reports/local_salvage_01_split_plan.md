# LOCAL-SALVAGE-01 — Split Plan
Generated: 2026-07-07 | REPORT_ONLY — this is a plan, nothing below has been executed as a PR.

Source: `data/reports/local_salvage_01_classification.csv` (321 files).

## Bucket 1 — JULY07-RACEDAY-EVIDENCE-LOCK (16 files)
Today's raceday cycle: `racecards_2026_07_07_*`, `industry_selections_20260707.json`,
`radical_shadow_2026_07_07.*`, `tri_lane_stress_test_2026_07_07_v1.*`,
`intent_shadow_audit_2026_07_07.json` / `intent_shadow_scorecard_2026_07_07_summary.md`,
`old_velo_rp_newspaper_file_gate_2026_07_07.*`, `sidecar_stack_operator_card_2026_07_07.*`,
`velo_daily_run_truth_2026_07_07.md`, `timing_audit/runtime_timing_audit_2026_07_07.json`,
`telegram_delivery_truth_2026_07_07.json`, `velo_run_observability_2026_07_07_85ad5214.json`.
**Not yet mergeable to main as final evidence** — today's Sigma/results have not run.
Recommended action: hold on the preservation branch until results/Sigma close out tonight,
then bundle as one dated PR alongside the 07-07 Sigma output.

## Bucket 2 — VCP03-PROGRESS-LOCK (7 files)
`vcp_03_burn_in_log.{json,md}`, `vcp_03_operator_brief.md`, `vcp03_day2_operator_docket.{json,md}`,
`vcp03_post_burnin_decision_board.md`, plus the `vcp_01`/`vcp_02` operator-brief files carried in the
same diff. This is Day-2+ burn-in progress (per LOCAL-01 Q4: Day 2 = PASS, promotion_learning=ELIGIBLE,
1 carried contradiction). Recommended action: separate small PR once burn-in reaches a stable
checkpoint (operator already flagged 8 more days needed before VCP-04).

## Bucket 3 — LOCAL-ONLY-REPORTS-ARCHIVE (61 files, `UNIQUE_REPORT_OR_AUDIT`)
July 4-6 operator briefs, council packets/reports/runs, sigma results (06-30, 07-04, 07-05),
nightly EOD learning artifacts, course intelligence audits (COURSE-00/00A/00B), RESULTS-01/02,
SUPA-02, DATA-01, STASH-01/02, J30 forensic pack, canonical scorecard/learning-events runtime
summaries for 07-05/07-06. This is the real audit trail — none of it exists on origin/main under
these paths even though some topics (e.g. canonical scorecard) were independently re-built and
merged there via a different route. Recommended action: single dated-range PR
(`data(archive): local operational reports July 04-06`), reviewed as data-only, no code.

## Bucket 4 — DO-NOT-MERGE-SCRATCH-QUARANTINE (0 files this pass)
No files in the current 321-path diff matched the known scratch pattern (the `data/_check_*`,
`data/_tmp_*` files flagged in REPO-01 were part of the older `8753b4f` bulk commit, not this
working-tree diff). Bucket kept for structural consistency with the REPO-01 precedent; empty now.

## Bucket 5 — ALREADY-MERGED-DROP-LIST (150 files, `ALREADY_MERGED_MAIN_EQUIVALENT`)
Byte-identical to what's already on `origin/main` (mostly code: `run_prime_today.py`,
`racecard_loader.py`, `new_build_dashboard_server.py` config-adjacent files, `THE_ONE_TRUTH.md`,
`app/services/velo_prime_service.py`, `app/static/dashboard/index.html`, plus a large share of the
"modified" dated report files that turned out identical). **Recommended action: drop — do not
commit or PR these.** They only show as dirty because this branch's commit history diverged from
origin/main; the content itself already matches upstream. Safe to discard once the branch is
brought current from origin/main (a separate, explicit rebase/merge decision — not part of this
mission).

## Not yet bucketed — NEEDS_OPERATOR_REVIEW (58 files)
Two sub-groups:
1. **Code/tests not on origin/main** (14 files: `build_course_00_audit.py`, `build_course_00a_tribunal.py`,
   `build_intent_shadow_scorecard.py`, `build_j30_forensic_pack.py`, `build_results_01_audit.py`,
   `build_results_02_audit.py`, `extract_local_draw_stats.py`, `parse_rp_course_profiles.py`,
   `new_build_dashboard_server.py`, and their matching test files) — these need a code review pass,
   not a data-archive drop. They likely belong with Bucket 3's topics but as code, so recommend a
   dedicated small PR per feature area rather than folding into the data-archive PR.
2. **Diverged-from-main tracked files** (`docs/current/ONE_TRUTH.md` differs from origin/main's
   version — expected, since origin/main's ONE_TRUTH has moved on through PRs #131-#141 that this
   branch never pulled) and a handful of untracked files with no origin/main equivalent and no
   pattern match (`docs/current/VELO_MODEL_SOURCE_MAP.md`, `run_login.bat`, `run_login.sh`,
   `scripts/data/place_signal_operator_card_2026_06_22.md`, `scripts/data/place_signal_operator_card_2026_06_24.md`).
   Recommend operator eyeball each before any PR — full list in
   `data/reports/local_salvage_01_classification_summary.md`.

## Bucket 6 — DIRTY_RUNTIME_CACHE_DO_NOT_COMMIT (29 files)
Rolling `*_latest.json`/`*_latest.md` pointer files (mission_control/latest.json,
sidecar_stack_latest.json, tri_lane_agent_review_latest.*, radical_shadow_latest.*, etc.) plus
`data/sentient_state_shadow.json` and `data/sigma_audits_dump.json`. These are overwritten on every
run and carry no unique historical value beyond their dated counterparts already captured in
Bucket 1/3. Recommended action: never commit; regenerate on demand.

## Recommended PR order
1. Bucket 5 drop (no PR — just don't stage these; confirm via re-diff after any future rebase)
2. Bucket 3 (`LOCAL-ONLY-REPORTS-ARCHIVE`) — lowest risk, pure historical data
3. Bucket 2 (`VCP03-PROGRESS-LOCK`) — small, self-contained
4. NEEDS_OPERATOR_REVIEW code files — after explicit review, likely folded into feature-specific PRs
5. Bucket 1 (`JULY07-RACEDAY-EVIDENCE-LOCK`) — hold until tonight's results/Sigma complete, then one PR

## Classification
`PR_SPLIT_PLAN_CREATED`
