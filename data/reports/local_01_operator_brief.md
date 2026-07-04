# LOCAL-01 — Local Truth Reconciliation Audit — Operator Brief
Generated: 2026-07-03 (report-only, no writes)
Repo: /mnt/c/Users/puror/velo-oracle-prime
HEAD: a8b3e8a (branch: main)

REPORT_ONLY. No code changed. No files deleted/moved. No commit. No push.

---

## Q1. Is GitHub main behind local?

**Yes.** `origin/main` = `018d618` (fix(capture): Firefox profile support + venue URL coverage + Step 8 doc update).
Local `main` = `a8b3e8a`, **6 commits ahead**:

```
a8b3e8a feat(VCP-03): Ten-Day Coherence Burn-In — Day 1 PASS
5f83fec feat(VCP-02): VÉLØ Heartbeat V1 — first voice of coherence
ff86674 feat(VCP-01): VÉLØ Living State Packet — velo_living_state_v1
e5b259b fix(A-3)+chore(VCP-00): going_code regression fix + truth lock + docs archive sweep
8753b4f chore(data): raceday 2026-06-29 sigma + learning + June 30 prep
ede88e6 fix(dashboard): NB top3 missing for all races on governed-card API
```

Zero commits behind (`git log HEAD..origin/main` is empty) — local has *only* pulled forward, never diverged backward. Local docs are also cleaner than GitHub's: `CURRENT_RUNTIME_TRUTH.md` is already archived out of root locally (part of the e5b259b "docs archive sweep"), which explains why ChatGPT's GitHub audit still saw it stale at root — that's GitHub's copy, not local's.

## Q2. Which commits are local-only?

The 6 listed above (`ede88e6`..`a8b3e8a`). None are pushed. This is the entire VCP-00/01/02/03 body of work plus the A-3 going_code fix and a raceday data commit.

## Q3. Are VCP-00/01/02/03 actually local?

**Yes, all real, committed to local main, not pushed.** Confirmed via file existence + git log:
- VCP-00: going_code fix + docs archive (commit `e5b259b`)
- VCP-01: `scripts/ops/build_velo_living_state.py`, `data/reports/vcp_01_living_state_operator_brief.md` — tracked, committed
- VCP-02: `scripts/ops/build_velo_heartbeat.py`, `data/reports/vcp_02_heartbeat_operator_brief.md`, `data/reports/velo_heartbeat_latest.{md,json}` — tracked, committed
- VCP-03: `scripts/ops/build_vcp03_burn_in_log.py`, `data/reports/vcp_03_burn_in_log.{json,md}`, `data/reports/vcp_03_operator_brief.md` — tracked, committed (though these three files show as *modified* in working tree because Day 2 was logged after the commit — see Q4)

Files named in the mission brief that do **not** exist under those exact names: `data/reports/vcp03_day1_operator_brief.md`, `vcp03_day2_operator_brief.md`, `vcp03_burn_in_log.jsonl`, `ops/task_contracts/VCP-03.json`. The real files use a different naming convention (`vcp_03_*` with underscore, not `vcp03_*`) — this is a naming-guess mismatch in the mission brief, not a missing artifact. `data/reports/vcp03_day2_operator_docket.md/json` (untracked) is the closest analog for a "day 2" artifact and exists.

## Q4. Is VCP-03 truly 2/10 PASS locally?

**Yes, confirmed from `vcp_03_burn_in_log.json`:**
- Day 1 (2026-06-30): PASS, promotion_learning=GATED, contradictions=0
- Day 2 (2026-07-01): PASS, promotion_learning=ELIGIBLE, contradictions=1 (C-01: Mission Control reports RP_MERGED_CLEAN but learning gate is BLOCKED — carried from VCP-01, not suppressed)
- 8 days remaining before the 10-day burn-in completes and VCP-04 may be considered.
- These Day-2 updates are why `vcp_03_*` files show as locally modified against the committed Day-1 snapshot — **uncommitted burn-in progress, not a discrepancy.**

## Q5. Is VFU-21 actually already run?

**Yes — ran 2026-06-17, twelve days before the VCP gate structure (VCP-00 through VCP-03) was built on 2026-06-29.** Two versions exist in git history: `e89095f` (59.2% SP coverage) then `7af104e` v2 (86.3% coverage, 2633/3052 rows, EW ROI -12.5%). Both are on `origin/main` already (pushed). The local ledger/summary files match GitHub's numbers exactly.

## Q6. Did VFU-21 violate gate or is it report-only historical?

**Classification: HISTORICAL_ARTIFACT / REPORT_ONLY_PREWORK. No gate violation.**
Reasoning: VFU-21 completed and self-terminated (`blocked_from_live_use: true`, "STOP — operator review required before VFU-22") on 2026-06-17. The VCP gate that says "VFU-21 gate: CLOSED — awaiting operator review before VFU-21" was written on 2026-06-29/30 as **forward-looking language about a future/continued VFU-21 (or VFU-22 follow-on)**, not a retroactive rule that VFU-21's original run broke. VFU-21 never touched live scoring, Supabase, or Telegram — it read local result archives and wrote local report files only. No contradiction to hide, but worth having the operator confirm the VCP-01 brief's "VFU-21 gate: CLOSED" phrasing isn't misread as "VFU-21 never ran."

## Q7. Which local artifacts explain the 2,977 vs 3,167 gap?

RESULTS-01 (`results_01_full_results_truth_audit.json`, generated 2026-07-01T00:05Z) used a local sigma dump capped at **2026-06-23** (102 unique dates, 2,977 rows). Supabase's `sigma_audits` table has grown to 3,167 rows by the time of the external audit — the extra 190 rows are sigma results from **2026-06-24 through ~2026-07-01/02** that were written to Supabase after RESULTS-01 ran. RESULTS-01 itself shows a `verdict_races: 3173` figure inside its own JSON (close to Supabase's 3,167), meaning the underlying verdict corpus was already larger than the sigma dump it filtered against — RESULTS-01 is a snapshot of a moving target, not a wrong query.

Mid-price-won gap (803 local vs 857 Supabase) is proportional to the same ~6% row growth — no anomaly.

## Q8. Which local files can repair Sigma-verdict linkage?

None found in this pass that resolve it. `verdict_races: 3173` and `pick_sp_present: 1212` are both counted from the local sigma dump/ledger, not from a `sigma.verdict_id` join. There is no local file discovered that carries an explicit `sigma_audits.id -> velo_verdicts.id` map beyond what the ingestion scripts already write at runtime. **Flag for a dedicated follow-up (SUPA-02), not resolvable from LOCAL-01 alone.**

## Q9. Which local files can repair pick_sp/field_size/race_type coverage?

**`data/reports/vfu_21_pick_sp_backfill_ledger.jsonl` (3,052 rows) is the strongest candidate** — it already recovered pick_sp for 1,778 rows beyond what was "already had SP" (903 from results JSON + 2 from sigma WIN), reaching 86.3% coverage locally, well above Supabase's 38.27% (1,212/3,167). This ledger was never pushed to Supabase (VFU-21 is REPORT_ONLY by design) — **it is the single biggest concrete repair candidate found in this audit.** It needs an explicit operator decision before any write, since VFU-21's own EW P&L on the recovered data is negative (ROI -12.5%), so "repairing coverage" and "trusting the recovered price for staking" are two different decisions.

No local file discovered yet for `field_size`/`race_type` coverage repair specifically — RESULTS-02 and COURSE-00 audits work with courses/going, not per-race field_size/race_type backfill. Flag as open gap.

## Q10. Which local course intelligence exists as VERIFIED_LOCAL?

Only `data/reports/local_draw_stats_by_course.csv` (14 courses, 49 races) carries the `VERIFIED_LOCAL` tag, and it is derived from local result data, not RP scraping. Everything in `course_00a_verified_course_registry.csv` (17 courses) is tagged `SECONDARY_PUBLIC_SOURCE` or `HYPOTHESIS_*` — **not VERIFIED_LOCAL**, despite the filename. Southwell's surface is correctly noted as Tapeta there, but the source status is `SECONDARY_PUBLIC_SOURCE`, not verified.

COURSE-00B's actual RP capture attempt (2026-07-01) recovered **zero** usable pages: 106 HTML files captured, but 0 OK, 53 x 404, 53 x login-required/blocked. `parse_rp_course_profiles.py` exists and ran, but the underlying capture is fully blocked. COURSE-00C (the planned CDP/browser-driven capture) was never built — none of its 3 expected files exist.

## Q11. What is the next safe mission after LOCAL-01?

Per the mission's own stop condition and the state found here: **REPO-01 (repo/branch reconciliation plan: what gets pushed from the 6 local-only commits + ~140 untracked report/script files) + SUPA-02 (Sigma-verdict linkage repair plan, incorporating the VFU-21 pick_sp ledger as a repair candidate)**. Do not start COURSE-01, VFU-21-live, or VCP-04 until the operator has reviewed this brief.

## Q12. What should not be touched?

- `data/current/` and `data/racing_post_account_raw/` — intentionally `.gitignore`'d (confirmed via `git check-ignore`), large/volatile, not meant for git.
- Any Supabase table — no write path was exercised in this audit.
- The VFU-21 ledger — it is a repair *candidate*, not yet operator-approved for use.
- The 6 unpushed local commits — do not push without operator review of the VCP-03 burn-in state (only 2/10 days PASS).

---

## Final Classifications
LOCAL_01_TRUTH_RECONCILIATION_COMPLETE
LOCAL_GIT_STATE_AUDITED
UNPUSHED_COMMITS_IDENTIFIED
LOCAL_VCP_STATE_AUDITED
LOCAL_RESULTS_REPORTS_AUDITED
LOCAL_COURSE_REPORTS_AUDITED
LOCAL_VFU21_STATE_AUDITED
LOCAL_SUPABASE_REPAIR_CANDIDATES_IDENTIFIED
LOCAL_RUNTIME_ENTRYPOINTS_MAPPED
LOCAL_SUPABASE_WRITE_PATHS_MAPPED
LOCAL_FILE_CLASSIFICATION_WRITTEN
GITHUB_LOCAL_DRIFT_REPORTED
SUPABASE_LOCAL_DRIFT_REPORTED
CONTRADICTIONS_RECORDED_NOT_SUPPRESSED
MEMORY_CAPTURE_OPEN
FAILURE_LEARNING_OPEN
PROMOTION_LEARNING_GATED
NO_COURSE_01_IMPLEMENTATION
NO_VFU_21_LIVE_START
NO_VCP_04_START
NO_MODEL_TRAINING
NO_LIVE_SCORING_CHANGE
NO_SUPABASE_WRITES
NO_TELEGRAM_SEND
CANONICAL_HORSE_PASSPORT_NOT_MUTATED
REPORT_ONLY

---
STOP — operator reviews this brief before REPO-01 or SUPA-02 begins. No commit, no push, no delete, no move performed.
