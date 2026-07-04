# July 4 2026 — RPDC Build — Operator Brief
Generated: 2026-07-04 | ONE AUTHORISED SUPABASE WRITE (public.runner_release_candidates, 2026-07-04 only)

---

## 1. Was PR #116 merged?

Yes. Merge commit `d8a57d45e6b8222433a94f6639bf8119ce8f0840`. `origin/main` advanced `a70caa4 → d8a57d4`.

## 2. What did build_rpdc_daily.py write?

Confirmed via source inspection before running: exactly two Supabase calls, both against `runner_release_candidates`, both scoped to the `--date` argument — `_sb_delete(f"/runner_release_candidates?run_date=eq.{date_str}")` followed by `_sb_upsert("/runner_release_candidates", batch, "run_date,race_id,horse_id")`. No calls to `velo_verdicts`, `sigma_audits`, `runner_prediction_snapshots`, Telegram, or model training found anywhere in the script.

## 3. How many RPDC rows/races/runners were built for 2026-07-04?

**453 rows written**, covering **51 races** and **453 distinct horse_ids** (1:1, no duplicates, no null `race_id`/`horse_id`). Tag frequencies: PLACE_FORM=257, CYCLE_RUN_1=214, FRESH_RETURN=92, STABLE_WARM=85, CYCLE_RUN_2=36, COURSE_RETURN=6, CYCLE_RUN_3=2. Cash window (score≥3.0): 34. Trap flagged: 0.

## 4. Did runner_release_candidates touch only 2026-07-04?

Yes — the delete/upsert pair is date-scoped by construction (confirmed via code read before running, not just after). Read-only check post-build confirms exactly 453 rows for `run_date=2026-07-04`.

## First attempt failed — disclosed, not hidden

The first run of `build_rpdc_daily.py --date 2026-07-04` exited **1** with `RPDC_SOURCE_UNAVAILABLE — no source for runners`. It checks (in order) `data/results_2026_07_04.json`, `data/racing_post_account_parsed/*2026-07-04*/racecard_injection.json`, `data/runner_snapshots_2026_07_04_*.jsonl` — none existed in the clean worktree because the injection JSON (a Step 4 output of the earlier live RP scrape) had not been copied over, only the standard cache and passport bank were. Per the mission's own allowance ("any other read-only local lookup file proven required by the successful earlier verdicts-only run"), I copied `data/racing_post_account_parsed/live-full-racepages-2026-07-04/racecard_injection.json` from the dirty repo (sha256 verified matching, recorded in the copy manifest) and re-ran. Second attempt: exit 0, 453 rows written.

---

## Required Classifications
- RPDC_BUILD_AUTHORISED_AND_EXECUTED
- RUNNER_RELEASE_CANDIDATES_WRITE_DATE_SCOPED
- NO_VELO_VERDICTS_WRITE_FROM_RPDC_SCRIPT
- NO_SIGMA_AUDITS_WRITE
- NO_RUNNER_PREDICTION_SNAPSHOT_WRITE
- NO_TELEGRAM_SEND
- NO_MODEL_TRAINING
- REPORT_ONLY
