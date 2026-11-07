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
