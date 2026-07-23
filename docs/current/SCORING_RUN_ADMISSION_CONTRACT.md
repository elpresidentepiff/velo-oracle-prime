# Scoring Run Admission Contract

`scripts/ops/run_prime_today.py::_open_pipeline_run()` is the single admission gate every scoring invocation
passes through — direct manual CLI, the Railway trigger path, and any future orchestrator — regardless of
what wraps or calls it. This document is the operator-facing contract for what it does and does not
guarantee. See `data/reports/bb35c69_pre_pr_tribunal_2026_07_22.md` and
`data/reports/runtime_scheduler_ownership_checkpoint_2026_07_20.md` for the incident history and evidence
this contract is built from.

## Three checks, in order

1. **Supplied `PIPELINE_RUN_ID` validation.** If a parent trigger has already claimed the lock and passes
   its run ID via this environment variable, it is validated (not trusted) before reuse: the row must exist,
   match this exact `service_name` and `source_date`, and be `run_state='running'` with a null `status`. Any
   mismatch hard-aborts — it never falls back to silently creating a different run.
2. **Completed-PASS admission gate.** If `source_date` already has one or more `pipeline_runs` rows with
   `run_state='completed'` and `status='PASS'`, a fresh run is blocked by default and exits non-zero,
   printing every prior run's ID, timestamps, and commit SHA. Production history showed this was routine,
   not exceptional, before this gate existed — 2026-07-14 alone had 4 separate completed PASS scoring runs.
3. **Atomic active-run lock.** A real Postgres partial unique index —
   `idx_pipeline_runs_active_service_date` on `(service_name, source_date) WHERE run_state='running'` —
   blocks true concurrent overlap. This predates this contract and was proven atomic against a real
   temporary Postgres instance, not only a mock (`tests/test_run_prime_today_admission_concurrency.py`).

## The explicit override

`--authorised-rescore-reason INCIDENT_ID` bypasses check 2 only. It requires a non-empty reason/incident ID,
records the prior completed run IDs and the new run's ID in an append-only artifact under
`data/reports/rescore_authorizations/` (one file per authorization, never overwritten), and tags the new
`pipeline_runs` row's `run_type` as `authorised_rescore` instead of `daily_scoring` so it's distinguishable
in any later audit. There is no unauthenticated `--force` equivalent. Default behavior (flag omitted): fail
closed.

## What this contract does NOT cover
- **Partial-write recovery.** A crash mid-scoring (after some races are persisted, before others) is not
  made safe by this contract — see `data/reports/scoring_partial_write_recovery_gap_2026_07_22.md`. Verdict
  rows carry no link back to the `pipeline_runs.id` that wrote them.
- **Stale abandoned `running` rows.** 5 exist in production right now, some months old. This contract does
  not clean them up — see `data/reports/stale_pipeline_run_inventory_2026_07_22.md` for the inventory and a
  specification for a separate future maintenance mission.
- **Anything upstream of scoring** (capture, parsing, RPDC). Only the scoring step itself is admission-gated.
  A wrapper orchestrator invoking this script twice would still duplicate all pre-scoring work even though
  it could not duplicate the scoring/persistence step itself.
