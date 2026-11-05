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
| U-2 | `SQPE_NO_RPR_SHADOW` has no model output in production; its picks are Main's picks | `sqpe_no_rpr_shadow_prob` NULL on every snapshot row; `models/sqpe_v17_no_rpr_staging/sqpe_v17_no_rpr.pkl` is git-ignored | Operator decision: **ship it** (No-RPR is important). `NORPR-SHIP-01`: model file force-added (6.3 MB, sha256 `65b71b31…`, sklearn 1.8.0 = production pin), all 25 inputs verified present in the live feature vector, the ensemble never reads it (0 references), 6 guard tests. Check `sqpe_no_rpr_shadow_prob` is non-NULL in `runner_prediction_snapshots` after the next scoring run, and that its picks now differ from Main's |
| U-3 | Local `main` carries commits not on GitHub: `dcdebf7e` (RP official non-results in Sigma), `fc3b2721` | `git log origin/main..main` | Recovery cherry-pick on `ops/recovery` |
| U-4 | Champion Intent / New Build / Passport have no settled positions; Main has none for 10-25, 10-26, 10-29 | `canonical_model_scorecards.result_position` | Open. Needs U-1 first |
| U-5 | Scoring is started by hand (`trigger_source = manual` every day since 11-02); cloud EOD light run reports PASS with 0 processed | `pipeline_runs` | Open |
| H-1 | Railway service `hermes-agent` (`71327cad`) fails to build on every push to `main` (checked back to 09:08 UTC today, before any of this work) | `list-deployments status=FAILED`; the 2 Nov audit already listed it failed/stopped, "retired-path residue" | Open, not caused by recent work. Disconnect it from `main` or delete it, so a red service stops hiding real failures |
| L-1 | World run ledger showed `rows_inserted = null` instead of 0 when every row was a first-wins duplicate | `world_pipeline_runs` 16:04 UTC run | Fixed with a test (this commit); rows written before the fix keep `null` |
| O-1 | Branch law breached: many long-lived branches, several 20–42 commits ahead of `main` | `git rev-list --count origin/main..<branch>` | **Backed up, nothing deleted.** Laptop-only work is now on origin as tags (secret-pattern scan: 0 hits): `archive/ops-monday-repair-20261012` (20 commits), `archive/ops-formfav-raceday-20261012` (17), `archive/fix-rp-session-alerting-and-venue-allowlist`, `archive/fix-railway-cloud-eod`, `archive/local-main-2026-11-05`. Next: decide per branch, then delete. Inventory: `PLATFORM_CONTROL_REGISTER.md` |

## Runtime facts that live nowhere else

- Hourly World job: Railway project `sincere-empathy`, service `velo-formfav-us-shadow`, cron `0 * * * *`,
  start command `python scripts/ops/run_formfav_global_shadow.py --countries au,ca,fr,hk,jp,us --persist-artifact --persist-scorecard`.
  Settlement now runs inside that same command (`--no-settle` turns it off), so no second service exists.
- Supabase project `ltbsxbvfsxtnharjvqcm` is the VELO project. `UCM Defect` is a different system.
- This worktree's `.git` file holds a Windows path. From WSL use
  `git --git-dir=/mnt/c/Users/puror/velo-oracle-prime/.git/worktrees/velo-oracle-prime-snapshot-fix --work-tree=<worktree>`
  and set `GIT_DIR` / `GIT_WORK_TREE` the same way before `npx gitnexus`.
- Project Python with pytest: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python`.

## Entries

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
