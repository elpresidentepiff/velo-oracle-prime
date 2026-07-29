# STASH-02 — High-Value Stash Salvage Review — Operator Brief
Generated: 2026-07-04 | REPORT_ONLY | no stash applied/popped/dropped/created | all content extracted read-only via `git show`

---

## Q1. Which stash content is worth saving?

**The `stash@{6}` business/evidence docs and the `stash@{4}` governance doc addition are the clearest saves.** Both are additive (new content on top of files that already exist and are unchanged elsewhere), self-contained, and carry no code risk.

## Q2. Which extracted docs are safe to turn into a docs-only PR?

- **`stash4_VELO_LLM_COUNCIL_V1.md`** (extracted from `stash@{4}`): a full "Daily Run Truth Duty" section (60 diff lines) defining named ownership (DATA AUDITOR, PRIME CHAIR), a required daily truth packet (`data/velo_daily_run_truth_YYYY_MM_DD.{json,md}`), and a hard rule distinguishing five separate truths (deploy/cron/Supabase/local/Telegram). **Confirmed the referenced watchdog script (`scripts/ops/velo_daily_run_truth_watchdog.py`) still exists today** — this section describes a real, currently-live mechanism that simply never got its governance write-up committed. **Safe for a docs-only PR** appending this section to the current `docs/engineering/VELO_LLM_COUNCIL_V1.md`.
- **`VELO_COMPANY_MASTER_PLAN_V1.md`, `VELO_FUNDING_PACK_OUTLINE_V1.md`, `VELO_WHITEPAPER_OUTLINE_V1.md`, `VELO_49_DAY_SIGNAL_DISCOVERY_REPORT_V1.md`, `VELO_SIGNAL_RANKINGS_V1.md`** (extracted from `stash@{6}`): substantial business/strategy and evidence documents (master plan alone is ~20KB / 730 diff lines). These read as complete, real content, not scratch notes. **Recommend a docs-only PR** restoring these under `docs/company/` and `docs/evidence/` — but since these are business-sensitive (funding pack, master plan), flagging for your explicit sign-off on visibility/publication before that PR, not just technical safety.

## Q3. Which code patches require manual review before any PR?

- **`stash5_locked_runtime_patch.diff`** (from `stash@{5}`, self-flagged "review required"): 917 lines across 9 files. The `scripts/run_results_sigma.py` hunk (LOCKED script per project doctrine) adds detection of a horse **entirely absent from the results set** (pre-race withdrawal) as a non-runner-exclusion case — current logic only catches horses that appear in results marked DNF, not horses missing from the result set altogether. This reads as a genuine, sensible bug fix, but it touches the Sigma script's internal counting logic and must go through explicit manual sign-off before any change — this is exactly the kind of change the LOCKED rule exists to gate, not to block forever.
- **`stash8_security_validator_patch.diff`** (from `stash@{8}`): 1015 lines. `app/services/security_validator.py` shows a large restructuring (single hunk spans ~130 lines), plus changes to `app/core/config.py` and significant rework of `persist_race_predictions`/`persist_runner_derived_features` in `app/services/velo_prime_service.py`. This is real, security/persistence-relevant code — needs a security-focused manual diff review, not a mechanical merge.

## Q4. Which patches are too stale/orphaned?

Neither `stash@{5}` nor `stash@{8}` is orphaned by file moves — `app/main.py`, `app/services/security_validator.py`, `app/core/config.py`, `app/services/velo_prime_service.py` all still exist at their original paths. The orphaning problem (files moved during the 2026-05-20 reorg) affects the **other** code files in `stash@{4}` (`cashrun_detector.py`, `velo_morning_cockpit.py`, `sync_verdicts_from_supabase.py` — now under `scripts/audit/`/`scripts/ops/`), which remains genuinely hard to reapply mechanically and is lower priority than the doc salvage.

## Q5. Which stashes remain keep-important?

All five reviewed here (`stash@{4}`, `stash@{5}`, `stash@{6}`, `stash@{8}`, `stash@{10}`) remain `KEEP_IMPORTANT` or `UNKNOWN_NEEDS_MANUAL_REVIEW` — nothing in this pass downgraded any of them. If anything, `stash@{4}`'s doc section and `stash@{6}`'s business docs are now confirmed as concretely recoverable, raising their priority for action.

## Q6. Which stashes can become drop candidates later?

`stash@{10}`'s deletion proposal (5 files, all still present today) remains a pending yes/no decision, not a drop candidate yet — dropping the stash before that decision is made would silently lose the question itself. Nothing in this pass is newly cleared for dropping; the STASH-01 drop candidates (`stash@{2}`, `stash@{7}`, `stash@{9}`) are unaffected by this review.

## Q7. What should be the next PR?

Two candidates, operator's choice of order:
1. **Docs-only PR**: append the "Daily Run Truth Duty" section to `docs/engineering/VELO_LLM_COUNCIL_V1.md` (low risk, describes an already-live mechanism).
2. **Business docs PR**: restore the 5 `docs/company/`/`docs/evidence/` files from `stash@{6}` (low technical risk, but needs your sign-off on content sensitivity before publishing to a repo that's already got public-facing history).

Neither the `run_results_sigma.py` non-runner fix nor the `security_validator.py` rework should become a PR without a dedicated manual review pass first — both are flagged, not yet actioned.

## Q8. What must not be touched?

All 11 stashes remain untouched — no apply, pop, or drop performed. `.env`, `data/browser_profiles/`, `data/racing_post_account_raw/`, `data/current/` were not touched. The extracted files in `data/reports/stash_02_extracted/` are copies for review only — they are not live code and do not replace or modify the current committed versions of anything.

---
## Final Classifications
STASH_02_SALVAGE_REVIEW_COMPLETE
NO_STASH_APPLIED
NO_STASH_POPPED
NO_STASH_DROPPED
NO_STASH_CREATED
NO_FILES_MOVED
NO_FILES_DELETED
NO_SUPABASE_WRITES
NO_TELEGRAM_SEND
NO_COURSE_01_IMPLEMENTATION
NO_VFU_21_LIVE_START
NO_VCP_04_START
NO_MODEL_TRAINING
REPORT_ONLY
