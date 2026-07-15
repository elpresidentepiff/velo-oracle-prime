# Race Day 15 — New Build / Champion Intent Scorecard Join Autopsy (Phase 7)

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01. Read-only evidence, re-verified independently inside a clean worktree branched from `aef63056`.

## Question

Multi-Model Sigma reports `n/a` / `NO_DATA` for New Build and Champion Intent on 2026-07-15, despite both lanes producing real local scorecards that day. Why?

## Evidence gathered

| Artifact | Path | Generated at | Races | Runners |
|---|---|---|---|---|
| New Build two-lane readiness | `data/new_build/reports/two_lane_readiness_2026_07_15.json` | 2026-07-15T14:09:30.916443Z | 47 | 394 |
| Champion Intent shadow scorecard | `data/reports/intent_shadow_scorecard_2026_07_15.csv` | (no `generated_at` column; file mtime 14:09Z, same pipeline step as above per `run_full_raceday_cron.log`) | 47 (unique `race_id`) | — |
| Canonical persistence target | Supabase table `canonical_model_scorecards` | — | — | — |

Supabase query (read-only `.select()`), re-run independently this session:

```
canonical_model_scorecards: total rows = 2511
most recent run_date values = ['2026-07-07', '2026-07-07', '2026-07-07']
rows with run_date = '2026-07-15' = 0
model_name distribution (first 2000 rows) = MAIN_VELO_PRIME: 462, CHAMPION_INTENT_SHADOW: 405, NEW_BUILD_LANE_A: 108, NEW_BUILD_LANE_A_MODEL: 25
```

This independently confirms the mission brief's claim: `canonical_model_scorecards` stops dead at 2026-07-07 and has never received a row for 2026-07-15, despite both New Build and Champion Intent producing local scorecards that day (and every day since, judging by the file mtimes on disk).

`canonical_model_scorecards` DOES already carry historical `CHAMPION_INTENT_SHADOW` and `NEW_BUILD_LANE_A` rows for earlier dates (2511 total rows, last dated 2026-07-07), so the persistence path exists and worked at some point in the past — this is a **regression**, not a design gap.

The persistence scripts (`scripts/ops/build_canonical_model_scorecard.py`, `scripts/ops/persist_canonical_model_scorecard.py`) exist in the repository and were not invoked as part of `run_full_raceday.py`'s 19-step sequence on 2026-07-15 (confirmed by grepping the full cron log for the two script names — zero matches for the 2026-07-15 block). Every one of the 19 steps in that day's run passed, but building/persisting the canonical scorecard was simply never one of the 19 steps.

## Classification

**`SCORECARD_GENERATED_NOT_PERSISTED`**

Both New Build and Champion Intent generated real, populated, pre-race-shaped local artifacts on 2026-07-15 (47 races each, non-trivial per-runner probability fields). Neither was ever pushed into `canonical_model_scorecards`, because `run_full_raceday.py`'s step list does not call the canonical-scorecard build/persist scripts at all — it stops at writing the local JSON/CSV files. Multi-Model Sigma joins against `canonical_model_scorecards`, sees zero rows for `run_date = 2026-07-15`, and correctly (from its own point of view) reports `NO_DATA`.

This is distinct from, and should not be confused with, the identity/timing problems also present today:

- **Timing problem (independent, does not explain the `NO_DATA` result but compounds it)**: even if persistence had run, both files were generated at ~14:09 UTC — after the afternoon rescore, and after 23 of the day's 47 races (all of Happy Valley plus the early Catterick/Bath card) had already gone off. Neither file has a run-scoped immutable equivalent to Old VÉLØ's `runner_snapshots_*.jsonl`, so even a working persistence step could not currently produce a `MORNING_RUN_PROVEN` canonical row for these two lanes.
- **ID-scheme drift (independent, secondary risk)**: the afternoon run additionally scored the same 7 Uttoxeter races twice, once under the pre-existing numeric RP race_id (e.g. `922990`) and once under a newly-introduced string scheme (`rp_UTT_20260715_2.48`), with byte-identical off-times. New Build's and Champion Intent's local files use the numeric scheme exclusively today, so this particular drift did not itself break their join — but it is a live landmine: any future day where the string-scheme generator fires first, or where New Build/Champion Intent's own racecard source picks up the string scheme, would silently desync from a Sigma/canonical layer expecting numeric IDs. This is flagged as a contributing identity-mismatch risk (`SCORECARD_IDENTITY_MISMATCH`-in-waiting), not the root cause of today's `NO_DATA`.

## Repair specification (NOT implemented in this evidence mission)

1. Add explicit `build_canonical_model_scorecard.py` + `persist_canonical_model_scorecard.py` invocations as a required step in `run_full_raceday.py`'s sequence, gated on New Build's and Champion Intent's local scorecard steps having passed. Failure to persist must flip the overall run status, not silently no-op.
2. Add a `canonical_model_scorecards` freshness check to the daily health check (`scripts/ops/velo_session_start_check.py` family): alert if `max(run_date)` is more than 1 day behind `CURRENT_DATE`.
3. Give New Build and Champion Intent a run-scoped immutable output filename (mirroring Old VÉLØ's `runner_snapshots_<date>_<date>_<commit>_<unix_ms>.jsonl` pattern) so that a canonical-scorecard build step can point at a frozen, timestamped, hash-stable source instead of the single mutable file that gets overwritten by every subsequent run.
4. Enforce one race_id scheme end-to-end. Either always emit numeric RP ids (recommended — matches the existing 2,511-row canonical history and Sigma's join key), or introduce an explicit id-mapping table and reject any pipeline stage that emits an unmapped scheme.
5. Add a regression test that fails CI if `canonical_model_scorecards.run_date` for `CHAMPION_INTENT_SHADOW` / `NEW_BUILD_LANE_A` falls behind the local scorecard file's date by more than 1 day.
