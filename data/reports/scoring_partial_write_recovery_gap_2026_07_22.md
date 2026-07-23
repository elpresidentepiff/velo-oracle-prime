# Partial-Write Recovery Gap — Discovery Only (P0-5)

Read-only investigation. No fix implemented in this PR, per SCORING-RUN-ADMISSION-HARDENING-01's own
instruction not to solve this unless the fix is already small and fully proven — it is not.

## Where the pipeline row is opened
`run_prime_today.py:main()`, via the now-hardened `_open_pipeline_run()` (this PR). A `pipeline_runs` row is
inserted with `run_state='running'`, `status=NULL`, before any racecard normalization or scoring begins.

## Every `velo_verdicts` write
`app/services/velo_prime_service.py::persist_race_predictions()`, called once per race inside an un-batched
loop at `run_prime_today.py:2383` (`for race, preds, tier, _reasons in scored:`). Each call is an independent
`sb.table("velo_verdicts").upsert(row, on_conflict="race_id")` — confirmed at
`app/services/velo_prime_service.py:1201`. The loop **continues past individual per-race persist failures**
(tracked only via `persist_ok`/`persist_fail` counters, printed, not raised) — a single bad race does not
abort the run. There is **no transaction or batch boundary** spanning the whole day's races; each race's
write commits independently and immediately.

## Failure points after first write
If the process is killed or crashes partway through the `scored` loop (after some races have already been
upserted), the remaining races for that date are simply never processed in that run. Two distinct recovery
paths exist depending on how the process died:

1. **A Python-level exception** is caught by the top-level `try/except Exception` in
   `if __name__ == "__main__":` (`run_prime_today.py:2904`), which does attempt to close the `pipeline_runs`
   row as `status="FAIL"` — but this close attempt is itself wrapped in a bare `except Exception: pass`, so
   if Supabase is unreachable at that exact moment, the row silently stays `running` forever, and this
   handler only fires for the current process's own recognized exceptions in the first place.
2. **An uncontrolled termination** (SIGKILL, OOM kill, container/VM teardown, host sleep/shutdown mid-run) —
   Python's own exception handling never runs at all, so the `pipeline_runs` row is never closed. **This is
   not hypothetical**: a live read-only query (this census) found **5 rows currently stuck at
   `run_state='running'`, `status=NULL`, dated 2026-04-16 through 2026-06-04** — real, already-existing
   evidence of exactly this failure mode. See `data/reports/stale_pipeline_run_inventory_2026_07_22.md`
   (P0-6, this same mission).

## Does a rerun upsert or insert?
Upsert, `on_conflict="race_id"` — unconditional. A rerun (whether a legitimate retry after failure, or a
future `--authorised-rescore-reason` invocation, or any bypass of the admission gate this PR adds)
overwrites every race's row from scratch with no check of "was this specific race already written by a
completed run, and should this write be allowed to replace it."

## Can a run identify only its own rows?
**No.** Confirmed by inspecting the full `velo_verdicts` row-construction dict in
`persist_race_predictions()`: it contains no `run_id` / `pipeline_run_id` column referencing back to the
`pipeline_runs.id` that produced it. The closest available fields are `commit_sha` (the code version, not
the run instance) and `generated_at` (a timestamp, not a stable identifier). Two different runs of the same
code on the same day would be indistinguishable in `velo_verdicts` except by `generated_at` proximity —
useful for forensic reconstruction (as this whole census has done, using `pipeline_runs` timestamps as a
proxy) but not a real foreign key, and not something application code checks at write time.

## Is rollback possible?
No. Each race's upsert is its own independent request/commit; there is no multi-row transaction wrapping the
day's scoring, so there is nothing to roll back to if a later race in the same run fails or the process dies.

## Recommended minimum future repair (not implemented here)
1. **Run-scoped verdict identity**: add a `pipeline_run_id` column to `velo_verdicts` (nullable, backfill
   not required), populated from the same run_id `_open_pipeline_run()` already produces. This alone would
   let a future query answer "which rows came from which execution" — the missing piece that made this
   whole discovery pass forensic-only rather than a direct query.
2. **Immutable prediction snapshot**: already identified as absent by the earlier
   RUNTIME-ENTRYPOINT-CENSUS-AND-CANONICAL-PATH-01 mission (genuinely greenfield, no local-only
   implementation exists to reconcile first) — this remains the real structural fix, of which
   `pipeline_run_id` above is a minimal down-payment.
3. **Staging-then-promote pattern**: write each run's verdicts to a run-scoped staging area (or a staging
   table keyed by `pipeline_run_id`) and only copy/promote to the canonical `velo_verdicts` rows once the
   entire day's race loop completes with zero `persist_fail`. This would make partial-failure runs leave the
   canonical table untouched rather than partially overwritten — the correct answer to "unsafe" — but it's a
   real schema and write-path change, explicitly out of scope for this PR.
4. Do not claim `PARTIAL_WRITE_RECOVERY_UNSAFE` closed until at least item 1 exists; item 3 fully closes it.
