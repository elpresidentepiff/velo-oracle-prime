# Stale `pipeline_runs` Inventory — Read-Only (P0-6)

Live, read-only query against production `pipeline_runs`, filtered to `run_state='running'` with no date
filter. No rows mutated, closed, or deleted. 5 rows found, all with `status=NULL` (never closed):

| service_name | source_date | started_at | age (approx, from 2026-07-22) |
|---|---|---|---|
| velo-prime-scoring | 2026-05-13 | 2026-05-13T22:33:32Z | ~2.3 months |
| velo-prime-scoring | 2026-05-31 | 2026-05-31T07:33:34Z | ~1.7 months |
| velo-prime-scoring | 2026-06-04 | 2026-06-04T19:10:48Z | ~1.6 months |
| velo-results-sigma | 2026-04-16 | 2026-04-16T21:21:05Z | ~3.2 months |
| velo-results-sigma | 2026-04-17 | 2026-04-17T21:20:25Z | ~3.2 months |

Split by service: **3 `velo-prime-scoring`, 2 `velo-results-sigma`.**

## Why the existing 24h age-gate didn't close these
`_open_pipeline_run()`'s age-gate only runs when a *new* run for the same `service_name`+`source_date` is
attempted — it closes a stale `running` row it finds in the process of opening a fresh one. If nobody has
retried scoring for 2026-05-13, 2026-05-31, or 2026-06-04 since those dates, the age-gate logic has simply
never been invoked for them, and the rows remain open indefinitely. This is a passive/reactive design, not a
bug in the age-gate logic itself — it does what it's supposed to do when triggered, it's just never
triggered for dates nobody revisits.

## Not addressed in this mission
Per SCORING-RUN-ADMISSION-HARDENING-01's explicit instruction: these rows are **not mutated or closed** as
part of this pass. This is inventory only.

## Specification for a later, separate maintenance mission (not implemented here)
A governed, scheduled "stale-run reaper" that periodically (e.g. daily, or on a dedicated cron) scans for
`run_state='running'` rows older than a fixed threshold (the existing 24h convention is reasonable) across
*all* services, not just the one currently being invoked, and closes them as
`status="FAIL"`/`error_message="closed by scheduled stale-run reaper"` — with the same audit-trail
discipline as this mission's rescore-authorization artifact (append-only log of what was closed and why,
never silently deleted). This is a genuinely separate, small, well-scoped follow-up mission, not part of the
admission-hardening work done here.
