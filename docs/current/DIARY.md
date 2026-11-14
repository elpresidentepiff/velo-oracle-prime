# DIARY — what happened, who did it, what is open

**Read this first. Append to it last.** Every agent and every session adds one entry at the top of
"Entries" before it stops. No entry means the work is not finished. This is a log, not a truth file:
`docs/current/ONE_TRUTH.md` still wins every conflict.

**Live numbers are not typed here.** Ask the database:

```sql
select * from world_status_summary;                          -- one row: where World stands
select * from world_status_register order by race_date desc; -- day x country coverage / settlement
```

## Entry format

```
### YYYY-MM-DD HH:MM UTC — <agent> — <one-line subject>
Branch / commit:  <branch> @ <sha>  (pushed? deployed?)
Changed:          <files / DB objects, with the migration name for any DDL>
Evidence:         <query, file path or test run that proves it — not "I checked">
Open / broken:    <what is still wrong, with the defect id below>
Next safe action: <one concrete step that needs no re-investigation>
```

## Open defects

| Id | Defect | Evidence | Status |
| --- | --- | --- | --- |
| W-1 | World freeze stored the scorer's 10.0 default as `captured_price`; 120 of 120 frozen races price-blind | `world_model_scorecards`: 1,100 rows, all `captured_price = 10.0`; 9 of 9 priced reruns changed the pick | **Fixed and deployed** (`b77bab5a` on `main`, Railway deploy 2026-11-05 15:08 UTC; price provenance + freeze gate). The 120 frozen rows stay immutable and are reported `PRICE_BLIND`. Confirm the first post-deploy run in `world_pipeline_runs` |
| W-2 | Nothing settled Velo's own World picks (`world_sigma_audits`, `world_learning_events`, `world_pipeline_runs` had 0 rows and no writer) | table counts; `formfav_global_eod.py` grades FormFav only | `src/velo/world_sigma.py` + `scripts/ops/run_world_sigma.py` written, 82 tests pass. **Deployed** with W-1 (same commit) |
| W-3 | The hourly World job is defined only in Railway (`velo-formfav-us-shadow`), not in the repo | no file references `run_formfav_global_shadow.py` | Recorded below. Start command must stay as written |
| W-4 | 33 of 120 frozen top picks tie with rank 2 (rank 1 = list order) | ties query, FR 10/23, US 23/82 | Now flagged per race (`top_tie_size`) and excluded from `skill_sample` |
| W-5 | AU/HK/JP early races are never frozen pre-off (AU 43 of 43 unfrozen, JP 17 of 24 on 2026-11-05) | `world_status_register` | Watch after deploy: hourly runs from 00:00 UTC should cover them |
| U-1 | UK settlement-truth stage (`CANONICAL_TRUTH_V2`) stopped 2026-10-17; its code lives only on unmerged branches | no settled/eligible rows after 10-17; commits `45345db1`, `5787e97f` not in `main` | Recovery cherry-pick on `ops/recovery` |
| U-2 | `SQPE_NO_RPR_SHADOW` has no model output in production; its picks are Main's picks | `sqpe_no_rpr_shadow_prob` NULL on every snapshot row; `models/sqpe_v17_no_rpr_staging/sqpe_v17_no_rpr.pkl` is git-ignored | Operator decision: **ship it** (No-RPR is important). `NORPR-SHIP-01`: model file force-added (6.3 MB, sha256 `65b71b31…`, sklearn 1.8.0 = production pin), all 25 inputs verified present in the live feature vector, the ensemble never reads it (0 references), 6 guard tests. **Proven live 2026-11-07 07:20 run:** 472/472 filled, 25 features, 44 of 46 races vary inside the race. **Corrected 2026-11-07:** 9 races have a tied No-RPR top (`TIED_n_WAY`, arbitrary pick); in the 37 clean races it picks a different horse from Prime in 31 and the same in 6. (An earlier note said 42 of 46: that used a different tie-break and counted tied races.) Disagreement is not skill: judge it on settled results |
| U-3 | Local `main` carries commits not on GitHub: `dcdebf7e` (RP official non-results in Sigma), `fc3b2721` | `git log origin/main..main` | Recovery cherry-pick on `ops/recovery` |
| U-4 | Champion Intent / New Build / Passport have no settled positions; Main has none for 10-25, 10-26, 10-29 | `canonical_model_scorecards.result_position` | Open. Needs U-1 first |
| U-5 | Scoring is started by hand (`trigger_source = manual` every day since 11-02); cloud EOD light run reports PASS with 0 processed | `pipeline_runs`; `velo-prime-scoring` had no `cronSchedule` (the World job has `0 * * * *`; `railway.toml` has it commented out) | **Schedule set 2026-11-07:** `0 7 * * *` on `velo-prime-scoring`, applies from its next deployment. Confirm tomorrow ~07:00 UTC that `pipeline_runs` shows `trigger_source = railway_cron`. The EOD light run is still open |
| U-6 | Rich Context history + Spotlight never reached afternoon races: `resolve_race_off_time_utc` could not parse Racing Post's 12-hour one-digit-hour times (`3.00`), so no cutoff, so no history call | 2026-11-07 packets: 8 races with history, 38 with none; every race with history was 10.xx-12.xx; 56 of 465 runners had history although 310 have prior rows under the same numeric RP id | **Fixed** (`WAKE-VELO-OFFTIME-01`): one-digit hour = pm; 5 regression tests fail on the old code |
| U-7 | The runner snapshot writer sent `rich_context_shadow` / `rich_context_comment_shadow`, columns `runner_prediction_snapshots` lacks, so PostgREST rejected the whole bulk insert (PGRST204) and `_write_supabase` swallowed it as non-fatal. Every scoring run after `8dc9d1e6` would have lost its snapshots, including tomorrow's | Railway log 2026-11-07 11:14Z on the second rescore; no new snapshot rows from either rescore | **Fixed** (`WAKE-VELO-SNAPFIX-01`): fields removed (the same evidence is stored in `rich_context_shadow_packets`); a test pins the table's real columns so a writer that outgrows it fails in CI. Confirm tomorrow's 07:00 run writes snapshots |
| H-1 | Railway service `hermes-agent` (`71327cad`) fails to build on every push to `main` (checked back to 09:08 UTC today, before any of this work) | `list-deployments status=FAILED`; the 2 Nov audit already listed it failed/stopped, "retired-path residue" | Open, not caused by recent work. Disconnect it from `main` or delete it, so a red service stops hiding real failures |
| L-1 | World run ledger showed `rows_inserted = null` instead of 0 when every row was a first-wins duplicate | `world_pipeline_runs` 16:04 UTC run | Fixed with a test (this commit); rows written before the fix keep `null` |
| O-1 | Branch law breached: many long-lived branches, several 20–42 commits ahead of `main` | `git rev-list --count origin/main..<branch>` | **Backed up, nothing deleted.** Laptop-only work is now on origin as tags (secret-pattern scan: 0 hits): `archive/ops-monday-repair-20261012` (20 commits), `archive/ops-formfav-raceday-20261012` (17), `archive/fix-rp-session-alerting-and-venue-allowlist`, `archive/fix-railway-cloud-eod`, `archive/local-main-2026-11-05`. Next: decide per branch, then delete. Inventory: `PLATFORM_CONTROL_REGISTER.md` |
| W-6 | US overnight race-date collision (#189): races keyed by the UTC meetings date while every racecard/prediction/result call is answered by the race's LOCAL date, so for each race off after 00:00 UTC (and early AU) the stored clock belonged to one race and the field to the next racing day's race with the same number. Remington R4 "13 Nov 01:54" showed the 14 Nov field (Stone Cold Lover / Woman's Intuition) | `formfav_races` 2026-11-05..14: 186 races with card vs meeting off 23-24 h apart (US 133, AU 4 at -20 h); 12/13 Nov: 24 + 16 US races, 32 published World picks | **Fixed on branch `fix/us-racecard-integrity-189`, not deployed.** `src/velo/race_identity.py` + local-date keying in worker/adapter, dashboard block, Sigma/EOD quarantine. Needs migration `20261113020000` before the FormFav worker deploy |

## Runtime facts that live nowhere else

- `runner_prediction_snapshots.rank` is **0-based**: rank 0 is Prime's top pick (rank 1 is the second choice). `canonical_model_scorecards.rank` is 1-based. Mixing them up misreports the pick (it happened once on 2026-11-07).
- Hourly World job: Railway project `sincere-empathy`, service `velo-formfav-us-shadow`, cron `0 * * * *`,
  start command `python scripts/ops/run_formfav_global_shadow.py --countries au,ca,fr,hk,jp,us --persist-artifact --persist-scorecard`.
  Settlement now runs inside that same command (`--no-settle` turns it off), so no second service exists.
- Supabase project `ltbsxbvfsxtnharjvqcm` is the VELO project. `UCM Defect` is a different system.
- This worktree's `.git` file holds a Windows path. From WSL use
  `git --git-dir=/mnt/c/Users/puror/velo-oracle-prime/.git/worktrees/velo-oracle-prime-snapshot-fix --work-tree=<worktree>`
  and set `GIT_DIR` / `GIT_WORK_TREE` the same way before `npx gitnexus`.
- Project Python with pytest: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python`.

## Entries

### 2026-11-13 (early) — Claude Code — #189 US racecard integrity: one canonical race identity, wrong-race picks blocked
Why:              Operator: Remington Park R4 (01:54 GMT, US racing date 12 Nov) showed FormFav Stone Cold Lover and World VÉLØ Woman's Intuition; neither ran.
Cause:            `formfav_live_worker` queries meetings by UTC date and keyed each race with that date, but called /form, /predictions, /prices and
                  /results with `date=<that UTC date>` + the race's own timezone, which FormFav answers by LOCAL racing date. Key
                  `formfav:us:2026-11-13:remington_park:r4`: metadata = 12 Nov card (off 13 Nov 01:54Z), form_meta + runners = 13 Nov card (off 14 Nov 01:54Z).
                  The wrong off also moved the price and result polling windows by a day (results for 12 Nov R4 were polled 23 h before the race: `pending`).
Changed:          branch `fix/us-racecard-integrity-189`. New `src/velo/race_identity.py` (local racing date, canonical key, verify_race_identity,
                  verify_selection). Worker keys + queries by local date and refuses to store a card that contradicts the race clock. World adapter does
                  the same and the hourly shadow scans racing dates D-1..D+1 filtered to UTC date D (same race universe as before). Freeze skips
                  unverified races and writes the local race_date + runner number. /api/world-picks and /api/world-day show
                  "RACECARD MISMATCH — NO VERIFIED SELECTION" (fail closed if evidence cannot be read), plus racecard status, non-runners and card
                  timestamp; originals kept under audit_original_picks. World Sigma and FormFav EOD quarantine as `identity_blocked`.
                  Prediction models untouched.
Evidence:         tests/test_race_identity.py (Remington regression, midnight crossing, 13/14 collision, AU, duplicates, scratchings),
                  tests/test_racecard_integrity_pipeline.py; full suite failure set identical before/after (pre-existing env failures only).
Open / broken:    W-6 not deployed. Legacy rows stay contradictory and are blocked by the verifier until the fixed worker rewrites in-window races.
Next safe action: apply migration 20261113020000, deploy dashboard + `velo-formfav-us-shadow` + FormFav worker, then check /api/world-picks for 2026-11-12.

### 2026-11-12 23:00 UTC — Claude Code (Opus 5.5) — Why the UK learning gate is BLOCKED every night, and the fix
Read:             `velo_mission_control` 2026-11-09, 11-11, 11-12: source RP_MERGED_CLEAN, flatline 0, identity 0, Council PASS_TO_LEARNING,
                  and still `learning_gate_status = BLOCKED` with ONE reason: `GATE_PIPELINE_TRUTH_MISSING` (`DAILY_RUN_TRUTH_MISSING`).
Cause:            `update_mission_control._run_truth_status` reads `data/velo_daily_run_truth_<date>.json`. Only the MORNING container writes it
                  (`run_prime_today._emit_daily_truth_packet`); the EOD container starts clean, so it is always MISSING. Same class as
                  WAKE-VELO-GATE-INPUTS-01 (snapshots, observability packet).
Fix:              `rp_cloud_eod._rebuild_daily_run_truth` runs the same watchdog (`velo_daily_run_truth_watchdog.write_report`) before the EOD
                  sequence. It classifies only from Supabase `pipeline_runs` + `velo_verdicts`, so a manual/failed/verdict-less day still blocks.
                  Never fatal. 3 tests added (15 pass). Mission Control, Council, the gate and the learner are not edited.
Expected:         2026-11-12 (railway_cron PASS, 21 verdicts) would read AUTOMATED_RUN_OK -> gate OPEN, learner runs on the shadow state.
Also found:       Rich Context challenger v1 is the market price: `log_sp` coefficient -1.50, every other feature |coef| <= 0.12. It picked the
                  favourite in 124 of 136 races 07-12 Nov. More features (v2) overfit; the fix is more days, not more columns.
Next safe action: after merge + redeploy of `velo-results-sigma`, rerun EOD for 2026-11-12 and read `velo_mission_control.gate_reasons`.

### 2026-11-11 (late morning) — Claude Code (Opus 5.5) — Evening EOD failed every night; fixed, plus automatic catch-up of missed days
Why:              Operator: "Velo works every day... backdate and fill and moving forward everything should be on railway and running auto."
Cause:            run_results_sigma.py reused the morning scoring preflight. Its formfav_factual check is CRITICAL when the newest FormFav form update is
                  over 3 h old; FormFav stops refreshing form once the day's cards are set (~12:46 UTC on 2026-11-10), so the 21:00 UTC EOD died at Step 12
                  every night ("PREFLIGHT FAIL ... formfav_factual"; Railway log 2026-11-10 21:05). 11-08 and 11-10 have no UK sigma; 11-09 only via a
                  manual 05:09 rerun next morning.
Changed:          `2da0a225`: src/preflight.py settlement mode (FormFav not required to grade results; scoring unchanged); run_results_sigma asks for it.
                  scripts/ops/rp_cloud_eod.py: each run first settles any of the last EOD_CATCH_UP_DAYS days (default 14) that had scored UK/IRE races
                  and zero UK sigma rows, oldest first, then today; one failed day does not stop the others; --backfill-only, --date. Tests added (34 pass).
Backfill:         whole-day misses in the last 30 days: 2026-10-18, 10-25, 10-26, 10-29, 11-08, 11-10. A one-off run (`3ba77aa8`, schedule removed from
                  railway.eod.toml AND the service setting, redeployed) never started a container: deployment SUCCESS, zero deploy logs, no pipeline_runs
                  row for an hour. So: schedule restored (service setting + this commit), Railway variable EOD_CATCH_UP_DAYS=30 on velo-results-sigma,
                  and tonight's 21:00 UTC run settles the six days, then 11-11.
Open:             partial days (1-8 races short, likely voids) are not retried; UK learning gate still BLOCKED (11-09: GATE_PIPELINE_TRUTH_MISSING).
Next safe action: after 21:00 UTC tonight read the velo-results-sigma log '"summary"' line and world_day_status for 10-18..11-11; then set
                  EOD_CATCH_UP_DAYS back to 14 (or leave 30: it only ever retries whole-day misses).

### 2026-11-10 (early) — Claude Code (Sonnet 5.5) — EOD encoding crash fixed; Rich Context v2 feature-utilization ablation run, result: negative, not promoted
Branch / commit:  `main` @ `5100dea` (dashboard panel rebase) then two more pushes: the UTF-8/arrow fix, and this entry + the v2 ablation artifact (pushed).
Changed:          (1) `scripts/ops/run_results_sigma.py:958` printed a literal `->MISS` arrow in an f-string; the 2026-11-10 05:09Z run crashed on it
                  (`'charmap' codec can't encode character '→'`) before a same-run retry succeeded. Fixed the literal and added `sys.stdout/stderr.reconfigure(encoding="utf-8",
                  errors="replace")` to `run_results_sigma.py`, `parse_rp_results_capture.py`, `racing_post_account_collector.py`, `rp_cloud_eod.py` so no other non-ASCII
                  character in this codebase's logging can kill a run again. (2) Plan 4 (`WAKE_VELO_RICH_CONTEXT_CHALLENGER_PLAN_V1.md` Phase 5/6): fitted
                  `rich_context_challenger_v2` — identical frozen universe/dates/estimator/grid/calibration as v1, but
                  `src/velo/rich_context_challenger_features_v2.py` reads the rest of `CanonicalHistoryProvider`'s already-computed `canonical_history` fields (distance/going/
                  course-place win-place rates, jockey-pairing and trainer-continuity win rates, jockey/trainer-changed flags, best official rating, average beaten margin,
                  runs_30d/365d) instead of v1's 7-field subset. `scripts/research/fit_rich_context_challenger_v2.py`; artifact at `models/rich_context_challenger_v2/`.
Evidence:         Dry run confirmed identical row counts to v1 (train=2046/217 races, validation=2847/281, holdout=1220/128) — a clean same-universe ablation. Result:
                  holdout log_loss_challenger 0.2831 and brier 0.0826, both *worse* than v1 (0.2713 / 0.0788) and worse than market-only (0.2719) — more features
                  overfit train/validation given only ~2,000 training rows. Also confirmed directly in Supabase: `rich_context_shadow_packets.feature_families` already
                  carries `rp_spotlight_facts`, `formfav_raw_facts`, `formfav_pace_context`, `formfav_class_context`, `formfav_track_bias_context` on every packet since
                  2026-11-07 — those families are not missing capture, they are missing *days* (4 so far; the fit script's own `len(X) < 200` floor is nowhere close).
What it shows:    the "feature-utilization gap" hypothesis from the pathfinder audit does not yet pay off when tested properly — v2 is **not promoted**, `promotion_eligible:
                  false`, live scoring stays on v1 unchanged (`rich_context_challenger_scorer.py` still points at `models/rich_context_challenger_v1/`). Retained for
                  provenance per Phase 6 ("invalid corpora are marked superseded with reason, not rewritten into passing evidence").
Open / broken:    2026-11-08 still has zero settled rows anywhere (unchanged from the prior entry). `rp_spotlight_facts`/`formfav_*` ablations need several more weeks of
                  forward daily accumulation before they clear the same `len(X) >= 200`-per-split floor. `hermes-agent` delete was proposed to the operator and declined/not
                  yet approved in-session.
Next safe action: once 2-3 more weeks of forward packets with settled results exist, rerun this same ablation style against `rp_spotlight_facts`/`formfav_raw_facts` as their
                  own declared family (not blended into v2) before ever touching production.

### 2026-11-09 (midday) — Claude Code (Sonnet 5.5) — Dashboard: Prime vs Challenger panel, and the page now fits a phone
Why:              Carlos asked to see the Rich Context challenger beside Prime ("what is the difference") and for the dashboard to work on a phone.
Changed:          view `public.prime_vs_challenger` (migrations `20261109120000_prime_vs_challenger.sql`, applied as `prime_vs_challenger` then
                  `prime_vs_challenger_not_materialized`; read-only, service_role select only, last 45 days, ~0.5 s for a day); route `GET /api/prime-vs-challenger?date=`
                  in `app/main.py`; pure helper `prime_vs_challenger()` in `app/world_dashboard.py`; panel `pvc-panel` in `app/static/dashboard/index.html`; 4 tests in
                  `tests/test_world_dashboard.py` (all 25 pass). Contract PVC-DASH-01.
Also fixed:       (1) the "Rich Context model" chip read `rich_context_shadow_packets.challenger_probability`, a column that does not exist (scores are in
                  `rich_context_challenger_scores`), so it said NOT FITTED while a model was scoring; it now reads the scores table. (2) The Wake Velo header said
                  "has no model yet and picks nothing"; reworded to say the challenger is shadow only and picks nothing Prime reads. (3) The page had no responsive CSS:
                  the status/date bar was one non-wrapping row 1,123 px wide, so on a phone the date picker sat off-screen. A max-width:600px layer now wraps it.
Evidence:         view vs the hand-computed numbers for 2026-11-07 (46 races): 26 agree, Prime 12 won / 27 placed, challenger 12 / 26, favourite 11 / 26, challenger = favourite
                  in 40. Headless Chromium at 390 px: page scrollWidth 390, no JS errors; screenshots read by eye.
What it shows:    challenger picks the market favourite in 40 of 46 (07 Nov) and 21 of 22 (09 Nov). Where they disagree on 07 Nov (20 settled): Prime's pick won 3, the challenger's 3.
                  One settled day with scores; not evidence of skill. 08 Nov has no packets or scores (scored by hand from local commit `c13dd3a`, not on GitHub).
Open / broken:    08 Nov Rich Context gap (above); the 08 Nov EOD sigma failed twice and no PASS row exists after the 00:17 fix; `app/main.py` has pre-existing
                  `ruff format` differences unrelated to this change.
Next safe action: after the 21:00Z EOD, reload the panel for 09 Nov and read the settled record.

### 2026-11-08 (early) — Claude Code (Sonnet 5.5) — Rich Context challenger v1: fitted, not just evidence-collecting
Why:              Carlos: "rich context has to work... this needs to be wired in." The earlier audit found packets had no model because nobody had fitted one on the
                  two families with real pre-November history (prime_baseline_snapshot, canonical_history) plus market_facts. Spotlight/FormFav have no history before
                  2026-11-06 so they stay declared-but-unfitted; nothing was waiting on new data, only on doing the fit.
Fit:              `scripts/research/fit_rich_context_challenger_v1.py`. Frozen split (declared before any result was read): train 2026-05-26..06-12 (2,046 rows),
                  validation 06-13..06-19 (2,847 rows), untouched holdout 2026-11-04..11-06 (1,220 rows, read exactly once below), forward shadow from 11-07. Logistic
                  regression (L2, lbfgs, seed 2607, class_weight balanced), C selected on validation log loss from the frozen grid (0.1 won), isotonic calibration fit
                  on validation only (>=1000 rows). History came from the existing `CanonicalHistoryProvider` (as-of, leak-proof) via a bulk in-memory repository
                  (one load instead of ~17,000 per-horse HTTP calls). sklearn 1.8 dropped `CalibratedClassifierCV(cv="prefit")`; used `sklearn.frozen.FrozenEstimator`.
Honest result (untouched holdout, never refit on): log loss — Prime alone 0.344, market alone 0.272, challenger 0.271. Brier — Prime 0.093, challenger 0.079. Most of
                  the "lift over Prime" is the challenger also using the market price, calibrated; over the market alone the lift is real but small and consistent in
                  sign across train/validation/holdout (not a dramatic result — reported as such, not oversold).
Wired in:         `src/velo/rich_context_challenger_features.py` (the one feature-vector function training and live scoring both use, so they cannot drift — missing
                  history gets an explicit `_missing` flag and a neutral placeholder, never a favourable guess), `src/velo/rich_context_challenger_scorer.py`
                  (loads the artifact once, scores a packet, ranks a race's packets by probability). `run_prime_today.py` now scores every new packet right after it is
                  built and ranks each race, writing only `challenger_probability`/`challenger_rank`/`challenger_version`/`model_status` onto that packet — never onto
                  `_pred`, so the existing Prime-invariance assertion still covers this. A scoring failure is caught per runner and is non-fatal.
Backfill:         `scripts/ops/backfill_rich_context_challenger_scores.py --date X --execute` scores the ~1,300 packets written on 11-06/11-07 before a model existed,
                  reading each row's already-stored `feature_families` (never re-derived) and updating only those four fields by row id.
Still not done:   promotion needs 500 forward races and a tribunal (Phase 7); this is a shadow score only, picks nothing, changes nothing Prime reads. FormFav/Spotlight
                  ablations wait for their own forward history. Contract WAKE-VELO-CHALLENGER-FIT-01; 11 new tests (one is a live smoke test against the real artifact).
Next safe action: run the backfill for 2026-11-06 and 2026-11-07; from tomorrow's 07:00Z run, check new packets carry a `challenger_probability` and compare its daily
                  top pick against Prime's, building toward the 500-race forward record.

### 2026-11-08 (early) — Claude Code (Sonnet 5.5) — Panel: four lanes now show today's results (read-only fallback)
Changed:          view `wake_velo_model_picks` (migration `wake_velo_model_picks_ingested_results`): where a lane's scorecard row has no result, read it from
                  `racing_horse_runs` by EXACT race_id + horse_id (never by name); the scorecard's own result still wins; new column `result_source`
                  (`scorecard` | `ingested_results`). The panel marks those settled counts with `*` and a footnote. Contract WAKE-VELO-DASH-03; 169 ms.
Effect on 2026-11-07: Champion Intent, New Build A/B and Passport now show settled results (44 / 45 / 45 / 43 of their listed races, all read from the ingested
                  results); every other lane is unchanged (Prime 44 settled, 12 won; all from the scorecard). The scoreboard still counts only clean picks.
Why a fallback:   tomorrow's EOD will write these lanes' results onto the scorecard once the morning inputs are persisted (WAKE-VELO-SETTLE-01); today's inputs were
                  never saved, so the scorecard rows cannot be rebuilt. Nothing is written to `canonical_model_scorecards`.

### 2026-11-08 (early) — Claude Code (Sonnet 5.5) — Why the learning gate has read BLOCKED every night in the cloud, and the two missing inputs
Read:             the 2026-11-07 EOD log: `GATE BLOCKED - learning cannot proceed: COUNCIL_INTEGRITY:WATCH_ONLY: DATA AUDITOR: MISSING_SNAPSHOTS; DATA AUDITOR:
                  SOURCE_UNKNOWN; LEARNING_GATE:BLOCKED`, and Step 12C dying in `run_place_stack_shadow.load_snapshot` (FileNotFoundError).
Cause:            all three read the EOD container's DISK, and the EOD container starts clean.
                  (1) runner snapshots: `data/runner_snapshots_<tag>_*.jsonl` is written by the morning container; the rows are in `runner_prediction_snapshots`
                      (472 for 2026-11-07). The morning orchestrator already restores them (`sync_runner_snapshots_from_supabase.py`) when scoring is skipped;
                      the EOD wrapper never did. Result: Step 12C fails and the Data Auditor labels the day MISSING_SNAPSHOTS.
                  (2) source truth: `update_mission_control` reads it ONLY from `data/velo_run_observability_<tag>_<run>.json`, which `run_prime_today.py` writes
                      to local disk (and by its own contract nowhere else). Never persisted, so every cloud night read UNKNOWN: `GATE_SOURCE_UNKNOWN`.
Fix:              `rp_cloud_eod.py` restores the snapshots (read-only, never fatal, before any capture or scoring); `persist_daily_artifacts.py` also persists the
                  NEWEST observability packet per date (the final run wins, same rule as mission control) under its own filename, and the existing EOD hydrate puts
                  it back. Council, mission control, the gate and the learner are NOT edited. Contract WAKE-VELO-GATE-INPUTS-01; 9 new tests, 5 fail on the old code.
Not made easier: a DEGRADED packet restores as RP_MERGED_DEGRADED and the gate still blocks it (tested); no packet means no row (nothing invented); when the
                  snapshot table has nothing the Auditor still says MISSING_SNAPSHOTS. The nightly learner works on `sentient_state_shadow.json` and guards the live
                  state (`LIVE_STATE_TOUCHED`), so opening the gate cannot change Prime.
Effect:           from tomorrow: the 07:00Z run persists the packet, the 21:00Z EOD restores it and the snapshots. The gate may now OPEN or may stay blocked for a real
                  reason (the packet's label, flatline, missing sigma `uk_sigma_missing`, identity). Whichever it is, it will be the real one. Not run for 2026-11-07
                  (no packet was ever saved for it).
Next safe action: 2026-11-08 after the 21:00Z EOD read `world_day_status` / mission control: `source_truth`, `learning_gate_status`, `council_verdict`, and the
                  EOD log line for Step 12C and Step 20.

### 2026-11-07 (night) — Claude Code (Sonnet 5.5) — Why four shadow lanes never get results, and the fix
Cause:            Champion Intent, New Build A/B and the Passport proxy are rebuilt at EOD (Step 20C) from three files the MORNING container writes
                  (`data/new_build/reports/two_lane_readiness_<tag>.json`, `data/new_build/current_cards/current_card_passport_feed_<tag>.jsonl`,
                  `data/reports/intent_shadow_scorecard_<tag>.csv`). The EOD container (`velo-results-sigma`) starts clean and only restores what is in
                  `velo_report_artifacts`; those three were never persisted (13 artifacts for 2026-11-07, none of them these). The rebuild therefore
                  skipped the four lanes and their morning rows stayed result-less: ~75 rank-1 rows each, 0 results, although ~71 of 75 picks join to
                  `racing_horse_runs`.
Fix:              `persist_daily_artifacts.py` now also persists those three files (the JSON one as ordinary JSON, the CSV and JSONL whole inside the JSON
                  payload under `__text`, read as bytes so CRLF survives; a file over 8 MB is skipped with a warning). `rp_cloud_eod._hydrate_report_artifacts`
                  writes a `__text` payload back byte for byte and still re-serialises ordinary JSON, still skips the verdict backup, still refuses unsafe paths.
                  Contract WAKE-VELO-SETTLE-01. 7 new tests, 5 fail on the old code; the end-to-end test persists in a "morning" root, restores into a clean
                  "evening" root and rebuilds the scorecard with results for all four lanes.
Effect:           takes hold from tomorrow: the 07:00Z run persists the files, the 21:00Z EOD restores them. 2026-11-07's four lanes stay unsettled in
                  `canonical_model_scorecards` (their inputs were never saved); their governed numbers are in the entry above, computed from `racing_horse_runs`.
Not changed:      the scorecard builder, scoring, models, gates and every other EOD step.
Next safe action: 2026-11-08 after the 21:00Z EOD: `select model_name, count(*) filter (where result_position is not null) from canonical_model_scorecards
                  where run_date='2026-11-08' and model_name in ('CHAMPION_INTENT_SHADOW','NEW_BUILD_LANE_A_MODEL','NEW_BUILD_LANE_B_MODEL','PASSPORT_STRENGTH_SCORE_PROXY') group by 1`
                  should be well above 0.

### 2026-11-07 (night) — Claude Code (Sonnet 5.5) — Full wiring check: EOD logs, all-model results, a duplicate 07:00 schedule, red CI
EOD log:          21 of 22 steps PASS. Step 12C (place-stack shadow settlement) exited 1, non-critical. Step 20 finished `FAIL_GATE_BLOCKED` (the learning gate), council
                  `EVIDENCE_INCOMPLETE`. Step 21 skipped by flag. 13 mandatory steps passed. Step 8 Telegram not sent (`--no-notify`).
All models (governed, 2026-11-07 UK): Prime 12 won / 27 framed of 44 settled; Old Velo win identical; MDS 10/42; No-RPR 4/36 clean (8/46 counting tied picks); Old Velo place
                  9/42; longshot 4/42. Champion Intent 4/19, New Build A 4/20, New Build B 6/25, Passport 3/19 clean, settled here directly from `racing_horse_runs`
                  because the EOD never writes results onto those four lanes (their picks join fine: ~71 of 75 match a result). They list more than one pick in
                  22-28 of 47 races.
Duplicate schedule: `velo-rp-capture` (cron `0 7 * * *`, Dockerfile.rpcapture, `rp_cloud_raceday.py`) is the real daily morning job: `races` rows land 07:05-07:13Z on
                  10-28, 10-31, 11-01, 11-02, 11-05, 11-07 and the scoring row opens 07:19-07:31Z. An earlier note here said `velo-prime-scoring` had no scheduler: WRONG.
                  I then gave `velo-prime-scoring` the same `0 7 * * *`, so two services now run the same chain at the same minute against one Racing Post account
                  (session collision, and the loser dies on the pipeline_runs overlap constraint). A change to a later backup time was DENIED by the permission check and
                  is left for the operator. Before the cron existed, every push re-ran the chain on `velo-prime-scoring` (that is where the 00:36 / 01:57 / 02:30Z
                  daily_scoring rows come from).
CI:               the `ci` workflow has been red on main since 2026-11-05 15:19Z (lint, and `cloud-raceday-contract` "Verify Racing API source truth" which asserts
                  the retired API is clean). The only lint error left was mine (`datetime.timezone.utc` in the world-picks route): fixed. `cloud-raceday-contract`
                  is untouched and still fails.
Services:         velo-oracle, velo-formfav-live online; prime-scoring, results-sigma, rp-capture, formfav-uk/us-shadow cron-ready; `hermes-agent` fails every push (old
                  April deployment still online); `velo-daily-ingestion` and `velo-shadow-lab` have no deployment at all.
Open / broken:    07:00 collision (operator decision), `cloud-raceday-contract`, hermes-agent, four lanes without results, `velo_learning_events` stale since 10-27,
                  `velo_vs_formfav` 8 s, UK truth contract on `ops/recovery`, Rich Context unfitted.
Next safe action: operator picks the 07:00 owner before 07:00Z; then 2026-11-08 07:25Z check `trigger_source = railway_cron` and PASS.

### 2026-11-07 (night) — Claude Code (Sonnet 5.5) — EOD run now, at the operator's order; governed UK results in
Ran:              `rp_cloud_eod.py --execute` in the cloud, 20:06:55-20:12:26Z, `[CLOUD-EOD] PASS`: 47 races, 46 scored, 46 results pages, RP login PASS.
Result (governed, from Racing Post): 460 horse runs in 46 races. Prime top pick: 44 with a result, **12 won, 27 in the frame**, the same 12 as the provisional FormFav read.
                  Two top picks have no result position (Kelso 2.00 Wal Buck's, Southwell 6.00 Cavalry Call: outcome UNKNOWN); neither won.
                  No-RPR 4/36, MDS 10/42, Old Velo place 9/42, longshot 4/42 (clean settled races). Champion Intent, New Build A/B and Passport show 0 settled:
                  nothing in the cloud EOD attaches results to those four lanes.
Learning:         `canonical_learning_events` +1,772 (661 with a result), 0 promotion-eligible, all `UNSETTLED`, block reason `PROMOTION_GATED_BY_STANDING_HARD_LAW`.
                  `velo_learning_events` +0 (latest 2026-10-27). World events +39, 0 eligible. Council WATCH_ONLY, learning gate BLOCKED, source_truth UNKNOWN: unchanged.
How it was run:   the cron service only runs on its schedule. Clearing the schedule in Railway did nothing (a redeploy re-runs the old deployment's saved config, and
                  `railway.eod.toml` sets `cronSchedule` itself, which overrides the dashboard). The one-off run came from commenting that line out for one deploy (803ec4f)
                  and restoring it (e276b04, byte-identical to before). The 21:00Z run did not fire tonight (schedule was off until 22:02Z); the EOD had already run.
                  Live config again: cron `0 21 * * *`, last run row 20:11Z. A sleep I used to wait overshot by ~1.5 h; nothing was lost.
Open / broken:    four lanes with no results; `velo_learning_events` stale since 10-27; UK truth contract still only on `ops/recovery`; Rich Context unfitted.
Next safe action: 2026-11-08 07:25Z check `railway_cron` / PASS and snapshots for the 07:00 run; 21:00Z check the nightly EOD fires with the restored schedule.

### 2026-11-07 (late evening) — Claude Code (Sonnet 5.5) — Results check, UK and World, before and after the Rich Context wiring
Read:             UK from FormFav's stored results (16 final, 30 provisional; NOT the Racing Post governed truth), World from `world_velo_picks`. 19:30Z.
UK:               Prime 12/46 winners (26.1%), identical for the 07:20 run and the 11:13 rescore (the top pick is the same in 46/46). Prior five UK days 46/202
                  (22.8%, daily range 11-33%). Other lanes today: MDS 10/45, Old Velo place 9/46, New Build B 6/25, Champion Intent 4/19, No-RPR 4/36,
                  New Build A 4/20, Old Velo longshot 4/46, Passport 3/21 (clean races only for the lanes that tie). Prime picks with history 6/31 vs 6/15 without;
                  with Spotlight 1/8 vs 11/38: tiny samples, and the evidence does not change a pick, so this is not an effect of Rich Context.
World:            AU/JP/FR done; CA 8 and US 56 run until 02:24Z. AU 93 final: 35 won, 53 framed (priced, picks are the favourite). Price-blind: AU 11-06 2/40 final,
                  US 11-05+06 23/168 incl. provisional (13.7% vs ~11% chance). JP has no result source.
Ops:              the 21:00Z `velo-results-sigma` cron was cleared at 19:55Z so a deploy would run the EOD once, at the operator's order. A `redeploy` re-ran the old
                  deployment's saved config and did not run it (no logs, no pipeline_runs row); only a new deployment from a push picks the cleared schedule up.
                  The cron MUST be restored (`0 21 * * *`) after the run. See the next entry for the outcome.
Next safe action: confirm the `velo-results-sigma` run for 2026-11-07 finished PASS, then restore the cron and check it is live.

### 2026-11-07 (night) — Claude Code (Sonnet 5.5) — Wake Velo: end-to-end connection check
Checked:          every link from tomorrow's 07:00 UTC cron to the dashboard, read-only.
Connected:        cron `0 7 * * *` on `velo-prime-scoring` is live; the whole chain ran in the cloud on 2026-11-07 10:52-11:15Z (FormFav gate, RP login PASS,
                  index + race-page capture, parse/score/persist, PASS), no laptop. FormFav gate inputs are fresh: the always-on `velo-formfav-live` worker
                  has already stored form for 2026-11-08 (GB 14 races, IE 8; newest update 18:33Z; the gate needs < 3 h). The snapshot writer matches the
                  live `runner_prediction_snapshots` columns exactly (no drift). Dashboard endpoints: rich-context, world-picks, world-day answer 200 with data.
Fixed:            the service has no TRIGGER_SOURCE variable, so the scheduled run would have been recorded as `manual`. `rp_cloud_raceday.py` now passes
                  `railway_cron` (or `railway_manual` for an authorised rescore) to the score step. Label only. Contract WAKE-VELO-CONNECT-01, 14 tests.
Learned:          since the cron was set, a deploy no longer re-runs the morning chain (it did before: the rescores were run by deploys). Pushes are safe.
                  UK result positions in `canonical_model_scorecards` DO arrive (11-04 43/47, 11-05 43/45, 11-06 34/36 top picks, all equal to
                  `racing_horse_runs`): the `velo-results-sigma` light row showing 0 processed is a legacy counter, not the settlement path.
                  Those rows stay `UNSETTLED` / `official_evaluation_eligible = false`: the truth contract is still only on `ops/recovery`.
Open / broken:    `velo_vs_formfav` takes ~8.7 s (blank UK-vs-FormFav panel). Japan has no result source. UK recovery merge not decided.
Next safe action: 2026-11-08 ~07:25Z: `select trigger_source, status from pipeline_runs where service_name='velo-prime-scoring' and source_date='2026-11-08'`
                  should read `railway_cron` / PASS, and `select count(*) from runner_prediction_snapshots where race_date='2026-11-08'` should be > 0.

### 2026-11-07 (night) — Claude Code (Sonnet 5.5) — World: VELO's own picks ready and visible
Found:            the hourly World job (`velo-formfav-us-shadow`) was already freezing every World race by itself: on 2026-11-07 all 283 races
                  outside GB/IE (AU 110, CA 11, FR 23, JP 36, US 103) were frozen `FIRST_COMPLETE`, pre-off. Each day's races freeze from 00:00 UTC
                  (first row 00:03), so nothing is frozen for the next date until then. (`world_day_status.world_predicted` for 11-08 is FormFav's
                  predictions, not VELO's freeze; an earlier draft of this entry mixed the two.)
                  What was missing was any dashboard surface for VELO's picks: the WORLD DAY panel shows FormFav's picks ("not a VELO selection").
Price state:      only AU (90 of 110) and JP (36 of 36) have a market. CA 0/11, FR 0/23, US 0/103 are `NO_MARKET`, i.e. price-blind.
                  (An earlier count that said "all priced" treated NULL as present; it was wrong and is corrected here.)
Not a skill read: where a market exists the VELO World pick is the shortest price in 123 of 126 races (AU 87/90, JP 36/36). AU's 35 wins from
                  93 final results (37.6%) is therefore what backing favourites gives, not evidence of an edge. The view carries
                  `pick_is_shortest_price` and the panel prints it beside every pick.
Data quality:     ties on the top score: AU 2, FR 12 of 23, US 22 of 103. Three US races carry two rank-1 rows (a runner listed under two name
                  variants, e.g. "Crazy Busted" and "Crazy Busted (Ny)", Belmont R10). Both are flagged (`TIED`, `DUP_RANK`) and kept out of the "clean picks" win count.
Changed:          view `world_velo_picks` (migrations `world_velo_picks`, `world_velo_picks_shortest_price`), `/api/world-picks`, panel "WORLD - VELO PICKS"
                  (TO RUN / OFF / ALL, per-country, TODAY / TOMORROW, refreshes every 5 min), helper `world_picks`. Contract `WORLD-PICKS-01`.
                  Frozen scorecards, the World job, Prime and every model weight untouched. Final and provisional results are counted apart.
Results gap:      Japan has no result source: all 36 JP races are `no_result` (AU 16 and FR 5 more). 95 final, 22 provisional, 57 no_result of 283.
Fixed later:      the view's `pick_is_shortest_price` was true for every price-blind row on earlier days (they store the 10.0 default, and 10.0 equals 10.0):
                  120 of 120 on 2026-11-05. It now counts a verified price only (migration `world_velo_picks_real_prices_only`). The panel already gated on REAL,
                  so the numbers it showed were right; only the raw column was misleading.
Open / broken:    World learning events 0 eligible (identity grade D, price-blind): the World lane still cannot teach anything. US has no market feed.
                  `/api/velo-vs-formfav` returned `available: false` for 2026-11-07 (UK view, not looked at yet).
Next safe action: tomorrow read the panel for 2026-11-07 once the World sigma has run, then split AU/JP wins by "pick = shortest price".

### 2026-11-07 (evening) — Claude Code (Sonnet 5.5) — Did Velo change its mind? New-run suggestions with evidence
Compared:         Prime's 07:20 picks against its 11:13 rescore (Prime's output is stored in each Rich Context packet). **Top pick identical in 46 of 46 races.**
                  Win probability moved on 166 of 465 runners (mean shift 0.002, max 0.13): all 69 runners in the 7 races with a withdrawal (field renormalised) plus
                  97 runners at Doncaster only (7 races, max shift 0.02: a track-level input, not the new evidence). Prices (`sp_dec`) unchanged on every runner.
                  The enrichment did not change Prime's mind, by design: Prime does not read it and Rich Context has no fitted model.
Mistake fixed:    an earlier note called Off The Jury (race 932271) Prime's morning top pick. It was the second choice (snapshot rank is 0-based). See Runtime facts.
Changed:          view `wake_velo_enriched_picks` (migration `wake_velo_enriched_picks`), `/api/rich-context` field `suggestions`, panel section "TODAY'S SUGGESTIONS".
                  Contract `WAKE-VELO-DASH-02`.
Open / broken:    no fitted challenger, so no re-ranked suggestions exist; outcomes show after sigma.
Next safe action: after tonight's results are recorded, open the panel for today and read settled/won/top-3 per model.

### 2026-11-07 (afternoon) — Claude Code (Sonnet 5.5) — Wake Velo: rescore, all-models dashboard panel, daily schedule
Branch / commit:  `main`; dashboard + views follow `0412446`. Operator approved the rescore, the daily schedule and the panel in chat.
Rescore:          `VELO_AUTHORISED_RESCORE_REASON=WAKE-VELO-OFFTIME-FIX-20261107` set on `velo-prime-scoring` (redeploy ran the governed rescore on
                  the off-time fix; prior PASS rows preserved, packets append-only), then blanked again.
                  Result (second `authorised_rescore`, 11:13-11:14 UTC, PASS, 46 races / 465 runners): canonical history 56 -> 310 of 465 runners (12.0% -> 66.7%),
                  Spotlight facts 10 -> 77 (2.2% -> 16.6%), 310 runners eligible for a future fit, 6 races with full history, 4 with none. Packets 465 -> 859
                  (394 new, 71 unchanged). Prime's picks are the 07:20 set: the rescore wrote no new snapshots (that is U-7). The 7 runners absent from the packets are
                  late scratchings (FormFav `scratched = true`), including Off The Jury (race 932271). Correction: Off The Jury was Prime's SECOND choice there; its top pick Talk To The Man is unchanged, so no Prime top pick was withdrawn.
Dashboard:        panel `WAKE VELO · ALL MODELS` (`#rc-panel`, `/api/rich-context`): evidence coverage first batch -> latest, one scoreboard row per
                  model (clean races, same pick as Prime, settled, won, top 3) and a race-by-race grid of every model's top pick.
                  Views (read-only, `security_invoker`, service_role select only): `wake_velo_model_picks`, `rich_context_vs_prime`
                  (migrations `rich_context_vs_prime`, `rich_context_vs_prime_tie_flags`, `wake_velo_model_picks`, `wake_velo_model_picks_rank1_rows`).
                  A pick is a clean read only if not `TIED_*` and the lane wrote one rank-1 row (`tie_status = N/A` is not a tie). Contract `WAKE-VELO-DASH-01`.
Schedule:         `velo-prime-scoring` cronSchedule `0 7 * * *` (was none). See U-5.
Correction:       the earlier "No-RPR differs from Prime in 42 of 46" was wrong (tie-break and tied races). Clean figure is 31 of 37. See U-2.
Open / broken:    Rich Context challenger still unfitted; 7 runners absent from packets are late scratchings, none a Prime top pick; `comments_processed` still 0; `hermes-agent` (H-1).
Next safe action: tonight after the 21:00 UTC sigma, open the panel for today: settled/won/top-3 per model fill in. Judge over weeks, not a day.

### 2026-11-07 — Claude Code (Sonnet 5.5) — Wake Velo: audit of the Rich Context lane, off-time bug fixed
Branch / commit:  `main`, fix commit follows `55a636e7` (other agent's last commit; that agent ran out of credits and was not available).
Verified:          rescore at 10:18 UTC PASS (`authorised_rescore`, 46 races / 465 runners) wrote 465 `rich_context_shadow_packets`, 0 with
                  `challenger_probability`/`challenger_rank` (`AWAITING_FROZEN_MODEL_FIT`). `runner_prediction_snapshots` was NOT rewritten:
                  today's Prime picks are the 07:20 set (472 rows). The lane cannot have changed any selection and was not designed to yet.
Found:            history + Spotlight were available only for races with a two-digit hour (8 of 46 races). Cause U-6. Fixed + tested.
Changed:          `src/velo/rich_context_comment_intelligence.py`, `tests/test_rich_context_comment_intelligence.py`, contract `WAKE-VELO-OFFTIME-01`.
                  Railway `velo-prime-scoring`: `VELO_AUTHORISED_RESCORE_REASON` set to empty (no redeploy) so the guard is back on.
Open / broken:    Rich Context challenger still unfitted (protocol `config/rich_context_challenger_protocol_v1.json` frozen, dates null);
                  7 Prime runners absent from the packets (incl. race 932271 rank 1); `comments_processed` still 0 on the daily run.
Next safe action: after the next scoring run check coverage by race: `select race_id, count(*), count(*) filter (where (family_coverage::jsonb->>'canonical_history')::boolean) from rich_context_shadow_packets where race_date = current_date group by 1`.
                  Expect history on afternoon races now. Then settle tonight's results and compare No-RPR vs Prime.

### 2026-11-05 — Claude Code (Sonnet 5.5) — No-RPR lane shipped; World deployed
Branch / commit:  `main` @ `2597d940` (No-RPR, pushed 16:32 UTC) on top of the other agent's `14df0acb`; World is `b77bab5a`.
                  `ops/recovery` is pushed to origin (UK settlement recovery + Captain fence), **not merged**.
Live check (16:04 UTC run, first after the fix): ledger 6 rows, `last_deployed_commit` filled; US froze 5 priced and deferred 77
                  (`AWAITING_PRICES`), FR 4 frozen / 4 deferred. Settlement graded 22 picks (5 final, 17 provisional): 0 wins, 4 frames,
                  all price-blind morning freezes, far too few to judge. `unresolved_results` fell 120 -> 115.
Not yet confirmed: that every Railway service finished building `2597d940` (only `velo-formfav-live` had when checked); No-RPR output
                  (needs tomorrow's scoring run). Today's AU (43) and JP (17 of 24) races were already off when the job could freeze them.
Changed:          `models/sqpe_v17_no_rpr_staging/sqpe_v17_no_rpr.pkl` (force-added: `.gitignore` blocks `models/**/*.pkl`),
                  `tests/test_no_rpr_shadow_model.py`, contract `NORPR-SHIP-01`.
Evidence:         pkl sha256 identical to the main checkout's copy; `CalibratedClassifierCV`, 25 features, none RPR/OR/TS,
                  predicts under sklearn 1.8.0 / lightgbm 4.6.0 (production pins); `grep no_rpr src/intelligence/velo_prime_ensemble.py` = 0.
Open / broken:    U-1 merge decision (it changes the UK performance panel: only governed rows count, so 2026-10-18 onward looks
                  empty until rebuilt). O-1: ~40 commits sit only on this laptop (`ops/monday-repair-20261012`,
                  `ops/formfav-raceday-20261012`); back up as `archive/*` tags before any deletion. Branch/service inventory:
                  `PLATFORM_CONTROL_REGISTER.md`.
Next safe action: after the next scoring run, prove the lane both exists and varies inside a race:
                  `select race_id, count(*) n, count(sqpe_no_rpr_shadow_prob) filled, count(distinct round(sqpe_no_rpr_shadow_prob::numeric,4)) distinct_probs from runner_prediction_snapshots where created_at > now() - interval '1 day' group by 1 order by distinct_probs limit 10`.
                  `filled = n` and `distinct_probs > 1` is a working lane. `distinct_probs = 1` means the extractor is falling back to defaults (no horse history reached it): then it is still not an independent opinion.

### 2026-11-05 — Platform control audit and dashboard cloud-truth repair

- Verified today's UK/IRE Supabase terminal row: PASS, 45 races, 420 runners.
- Verified ten canonical model families are durable for 2026-11-05.
- Confirmed the live dashboard mixed canonical truth with deploy-time/local paper artifacts.
- Added canonical No-RPR fallback to race cards and routed radical/tri-lane/deep-agent/course-master/RP-gate reports through `velo_report_artifacts`.
- Date-scoped the Truth Cockpit pipeline query and derived New Build status from canonical scorecards.
- Added `PLATFORM_CONTROL_REGISTER.md` as the single GitHub/Railway/Supabase/branch inventory.
- No model weights, learning gates, staking mode or prediction outputs changed.


### 2026-11-05 — Claude Code (Sonnet 5.5) — World audit, settlement writer, price gate, status register
Branch / commit:  `ops/recovery` from `main` @ `cc03a732`. Not pushed. Nothing deployed.
Changed:          `src/velo/world_scorecard_store.py` (price provenance, freeze gate, run ledger, inserted-row counts),
                  `src/velo/world_sigma.py` (new), `scripts/ops/run_world_sigma.py` (new),
                  `scripts/ops/run_formfav_global_shadow.py` (two-pass freeze, ledger, settlement hook),
                  `src/velo/formfav_card_adapter.py` (`error_detail` with country), three test files,
                  contract `ops/task_contracts/WORLD-SETTLE-01.json`, this file.
                  **DDL applied to the live VELO project on operator instruction:** migration `world_status_register`
                  (views `world_status_register`, `world_status_summary`; read-only, no table changed).
Evidence:         `select * from world_status_summary` returns 120 frozen / 120 price-blind / 120 unresolved / 0 eligible.
                  `settle_pick` run on the four real frozen races that already have results: Funabashi R10 final, pick
                  Sun Lycoris finished 4th (miss); three French races provisional. Tests: 82 pass (world sigma, price gate,
                  store, adapter boundary, cache client, global EOD, live-worker backoff, dashboards).
Open / broken:    W-1…W-5, U-1…U-5, O-1 above. The views read "deployed commit: null" until the new code runs.
Next safe action: push `ops/recovery`, merge to `main` (Railway builds from `main`), then confirm with
                  `select * from world_status_summary` that `last_deployed_commit` and `last_settlement_run_at` fill in.

## 2026-11-14 — SIGHT-E3-E4-01: missing history = 0; no price is imputed

- E3: the 18 history/doctrine inputs used Racing-API-era placeholders at scoring time (5.0, 0.33, 0.12 ...). Training used fillna(0) for "no history". Live now uses 0.0 for any absent history input (`LIVE_MISSING_HISTORY_VALUE`, `app/services/sqpe_v17_service.py`).
- E4: a UK runner with no price was priced at 10/1. It now takes the race median of available prices and is flagged `_price_imputed` (`app/services/velo_prime_service.py`). A race with no prices keeps the 10.0 fallback.
- Tests: `tests/test_sight_e3_e4_missing_inputs.py`. Full suite: no new failures versus main (the same pre-existing failures before and after).
- Not in this entry: E5 draw-bias freeze (needs a stored timestamp, schema change). The FormFav price leak is not live for UK because `include_prices=False`.
- Effect: horse-state and TIE tags read these inputs too, so their tags can shift. Re-check on the next scored day.
- Live scoring changed on `main` at 255d5691. Next scheduled run (07:00 UTC) uses it.

## 2026-11-14 — SIGHT-HISTORY-TEST-01: as-of horse-history features, leak-free

- Script: `scripts/research/horse_history_features_test_2025.py`. Features built as-of race date from `raceform` only: prior runs, win and place rates, days since run, runs since last win and place, OR change and best-OR gap, class change, average last three finishes, course, distance and going records.
- Train 2017–2024 (1,228,157 runners), test 2025 (79,054 runners, 8,700 races with SP).
- Results (HistGradientBoosting, not the production GBM):

| Model | AUC | Top pick hit | Level-stake ROI |
|---|---|---|---|
| Leak-free base | 0.648 | 19.3% | −16.0% |
| Base + horse history | 0.698 | 26.2% | −7.6% |
| Favourite (SP) | — | 34.9% | −5.2% |

- Reading: horse history adds about 5 AUC points and roughly 7 hit-rate points. It still does not beat the favourite. Not yet tested: jockey and trainer features (not pulled from `raceform`), and the market-offset blend.
- Not live. Live wiring needs name-keyed history for Jul 2025–now from `racing_horse_runs` and identity matching (about 59% of today's runners match `raceform` by name).

## 2026-11-14 — HISTORY-SHADOW-01: horse-history candidate wired as shadow

- Shared feature code: `app/services/horse_history_features.py` (as-of, prior runs only; used by the test and live). Tests: `tests/test_horse_history_features.py`.
- Live history fetch: `app/services/horse_history_live.py` (read-only Supabase REST: raceform 2017–2025, racing_horse_runs 2026+). Not yet run against live Supabase: no service key in the build container.
- Candidate: `models/horse_history_candidate/` (HistGradientBoosting, 1,317,612 runners 2017–2025, 30 features). `promotion_status: NOT_PROMOTED`. Holdout result (2025, trained 2017–2024): AUC 0.698, top pick 26.2%, ROI −7.6% vs favourite −5.2%. It does not beat the favourite, so it is not live.
- Shadow: `scripts/ops/run_horse_history_shadow.py`, non-critical step 9.1d in `run_full_raceday.py`. Writes `data/horse_history_shadow/<date>.json`. Fail-soft: any error writes FAILED and the day continues. Prime's output is unchanged.
- Open: trainer and jockey history not pulled; market-blend test not run; first live shadow run not yet observed.

## 2026-11-14 — REVIEW-01: self-review of today's wiring

- Found and fixed: the E1 distance fix read `distance_furlongs` from the top level of the race. The builder writes it under `race_info`, so the fix never reached Prime. `src/velo/racecard_loader.py` now reads `race_info` first, then the legacy `distance` string. Test: `tests/test_sqpe_stuck_inputs_fixes.py::test_loader_reads_distance_from_race_info`.
- Added end-to-end test for the history shadow on a current-format racecard with faked history: `tests/test_horse_history_shadow_e2e.py`.
- Still unverified: the Supabase history fetch (no service key in the build container). The 07:00 run on the new code is the first real check.
- Still open: Prime's live model (v17) still includes RPR and Topspeed. Removing them is a model change and needs your decision.

## 2026-11-14 — HISTORY-JT-01: jockey and trainer history added

- Pulled jockey and trainer for all 1,387,120 raceform runners (2017–2025). Counts match the table exactly.
- Shared features now include as-of jockey and trainer rates, trainer-at-course and jockey-at-course rates, and jockey/trainer-change flags. Same-day runs never count. Tests: `tests/test_horse_history_features.py`.
- Result (`scripts/research/horse_history_blend_test_2025.py`, trained 2017–2023, holdout 2025): model AUC 0.7146 (was 0.698); top pick 27.5% (favourite 34.8%); ROI −6.7% (favourite −5.5%). Still does not beat the favourite.
- The blend in that script is not valid: it adds logits without calibration. A fitted blend (logistic on 2024) is the next experiment.
- Candidate retrained with jockey and trainer: `models/horse_history_candidate/` (40 features, 1,317,612 runners, NOT_PROMOTED).
- Live: jockey and trainer are fetched in `app/services/horse_history_live.py` and passed to the shadow. Live name match vs historical names not yet checked.
