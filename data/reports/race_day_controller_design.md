# Race Day Controller — Technical Design (Phase 11)

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01. Design only — nothing in this document is implemented as part of this evidence mission.

## Why this is needed

2026-07-15 proved that the current system has no single owner of "today's run." Two independently-triggered manual invocations (08:45 and 14:08 UTC) both wrote `status=PASS` to `pipeline_runs` for the same `source_date`, and the second silently overwrote every downstream mutable artifact (`velo_verdicts`, `velo_prime_verdicts_*.json`, `radical_shadow_*.json`, `two_lane_readiness_*.json`, `intent_shadow_scorecard_*.csv`) with no run-scoped key preventing the collision, and no alert firing when it happened. Separately, the two automated scheduling mechanisms that should own this (`score-daily.yml` GitHub Actions, local WSL crontab) were found disabled and unreliable respectively.

## Core principle

One `source_date` has exactly one **sealed** state machine instance. All scoring, persistence, and downstream consumption must go through it. A rerun mints a new, clearly-labeled, non-authoritative run; it can never silently become "the" result for a date that already has a sealed run.

## Required stages

```
DAY_CREATED
  -> SOURCE_CAPTURE_STARTED
  -> SOURCE_CAPTURE_COMPLETE
  -> SOURCE_PARSE_COMPLETE
  -> RACE_UNIVERSE_SEALED
  -> OLD_VELO_COMPLETE
  -> NO_RPR_COMPLETE
  -> NEW_BUILD_COMPLETE
  -> CHAMPION_INTENT_COMPLETE
  -> ALL_SCORECARDS_PERSISTED
  -> DASHBOARD_PUBLISHED
  -> MORNING_RUN_SEALED
  -> RESULTS_CAPTURED
  -> RESULTS_RECONCILED
  -> MULTIMODEL_SIGMA_COMPLETE
  -> COUNCIL_COMPLETE
  -> LEARNING_COMPLETE
  -> DAY_SEALED
```

Each stage record:

| Field | Purpose |
|---|---|
| `expected_input` | Named upstream artifact(s)/stage(s) this stage consumes |
| `source_hash` | SHA-256 of the actual input consumed (not merely the input's identity — the bytes) |
| `output_count` | Row/race/runner count produced |
| `output_hash` | SHA-256 of the actual output artifact written |
| `run_id` | The single run-scoped ID this stage execution belongs to (format: `<source_date>_<commit_short>_<unix_ms>`, matching the pattern Old VÉLØ's `runner_snapshots` already uses) |
| `timestamp` | UTC ISO instant the stage completed |
| `code_identity` | Full git commit SHA + dirty-tree fingerprint (hash of `git status --porcelain` + `git diff` at execution time) |
| `pass_fail` | Terminal status |
| `retry_law` | Whether/how this stage may be retried (idempotent-replay vs. must-mint-new-run) |
| `idempotence_key` | A key that, if reused, guarantees byte-identical output for byte-identical input (used to detect and reject accidental duplicate runs) |

## Hard rules

1. **No stage may progress when its required predecessor is missing or has a different `run_id` than the stages before it.** `RACE_UNIVERSE_SEALED` freezes the race/runner universe (race_ids, off-times, field sizes) for the rest of the day's pipeline; every downstream stage validates its input race_ids are a subset of the sealed universe, and flags — rather than silently absorbs — any additions (this directly targets the Uttoxeter-string-vs-numeric-id duplication bug found on 2026-07-15).
2. **`MORNING_RUN_SEALED` is a one-way gate.** Once a `source_date`'s pipeline reaches `MORNING_RUN_SEALED`, no subsequent write (automated or manual) may overwrite any of that run's persisted artifacts (`velo_verdicts` row keys must include `run_id`, not just `race_id` — this is the single change that would have prevented the entire 2026-07-15 incident by construction, since the afternoon run's upsert-by-`race_id` would then have inserted a second, distinguishable row instead of clobbering the first).
3. **A manual rerun must mint a different `run_id` and is labeled `POST_MORNING_DIAGNOSTIC_RUN` (or `POST_SEAL_RERUN`) in every artifact it writes.** It writes to a parallel, clearly-namespaced location (e.g. `data/reruns/<run_id>/...`), never to the sealed run's canonical path. Dashboards, Sigma, and Council must default to the sealed run and require an explicit flag to view a diagnostic rerun.
4. **Every consumer (Sigma, Council, dashboard, nightly learning) must record which `run_id` it evaluated**, as a first-class column/field, not an implicit assumption. This directly fixes the finding that all 46 Sigma rows for 2026-07-15 have `verdict_id = NULL`, `doctrine_event_id = NULL`, `pick_sp = NULL` — Sigma currently cannot prove which prediction run it evaluated because nothing in its schema carries that reference.
5. **`DASHBOARD_PUBLISHED` must show a run-scoped count, not a live `SELECT count(*) FROM velo_verdicts WHERE ...`.** The dashboard's `verdict_count_today` bug (`app/main.py:2468`, confirmed still present: `race_id=like.*{date}*` filters on a column that never embeds the date) is a symptom of not having a run-scoped source of truth to query in the first place; the Controller's per-stage `output_count` + `output_hash` becomes the dashboard's actual data source.
6. **Single scheduler ownership.** Exactly one mechanism is allowed to advance `DAY_CREATED -> SOURCE_CAPTURE_STARTED` automatically per calendar day (this mission found two independent, uncoordinated mechanisms — a disabled GH Actions workflow and an unreliable local WSL crontab — either of which, if it silently fires late or is triggered manually without the other's knowledge, can create exactly the 2026-07-15 collision). The controller itself, not ad-hoc scripts, owns the "has today already started" check and refuses a second `SOURCE_CAPTURE_STARTED` for the same `source_date` unless explicitly flagged as a diagnostic rerun.

## Storage sketch

A single `race_day_controller_runs` table (new), one row per `(source_date, run_id, stage)`, append-only, with the fields above. `pipeline_runs` (existing) becomes one specific stage's log (`OLD_VELO_COMPLETE`'s underlying scoring call), not the entire picture — which is itself why two independent `pipeline_runs` rows for the same date looked "fine" to every existing check: `pipeline_runs` was never designed to be the single source of daily truth, and nothing else stepped in to be that instead.

## Migration path (not implemented here)

1. Add `run_id` as a first-class column to `velo_verdicts`, `canonical_model_scorecards`, and any other table currently upserting by `race_id`/`source_date` alone.
2. Introduce the `race_day_controller_runs` table and a thin Python state-machine library (`scripts/ops/race_day_controller.py`) that every existing script calls into at stage-start/stage-end instead of writing directly to `pipeline_runs`.
3. Backfill is not required — this is a forward-looking design; historical dates keep their existing (partial) evidence as-is.
4. Retrofit the dashboard's `verdict_count_today` and Sigma's evaluation join to read from the controller's sealed-run pointer instead of the mutable tables.
