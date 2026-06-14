# VELO Connection Map

Audit date: 2026-06-07

## Connected Production-Intent Chain

```text
GitHub score-daily workflow / intended Railway cron
  -> scripts/ops/run_prime_today.py
  -> racecard loaders and source-truth gates
  -> app/services/velo_prime_service.py::score_race_velo_prime
  -> local verdict artifact
  -> Supabase verdict persistence
  -> scripts/ops/run_results_sigma.py
  -> Sigma artifact / audit rows
  -> nightly learning sidecars
  -> scripts/ops/update_mission_control.py
  -> Council / promotion decisions
```

The scripts and imports exist. The entire production chain is **not proven** because the
live service is down, cron truth is absent, and the June 7 pipeline run record is absent.

## Proven Call Chains

| Chain | Proof | Status |
|---|---|---|
| `_open_pipeline_run` -> `pipeline_runs.insert` | direct code + passing persistence test after repair | CONNECTED |
| daily run truth -> `build_mission_control` -> learning/promotion gates | direct code + two passing tests after repair | CONNECTED |
| `app.main` -> Railway Nixpacks start command | `railway.toml` + import smoke | DEGRADED |
| GitHub smoke -> production `/health` | workflow run + HTTP 502 | CONNECTED BUT FAILING |
| June 7 verdicts -> Sigma -> learning sidecar | local artifacts | CONNECTED LOCALLY |

## Disconnected / Orphaned Components

| Component | Evidence | Status |
|---|---|---|
| `app/api/router.py` aggregate versioned router | no `app.main` include/reference found | ORPHANED |
| `app/api/v1/predict.py` routes | only reachable through orphaned aggregate router | ORPHANED |
| Feature/monitoring routers requiring `feast` | `app.main` catches missing dependency and continues | SILENTLY BYPASSED |
| GitNexus current architecture graph | metadata points to old commit; refresh failed | UNPROVEN |
| Phase 4 model-file assertions | required files absent in clean checkout | DISCONNECTED FROM REPRODUCIBLE BUILD |
| 1.7M dataset-file assertion | file absent in clean checkout; live DB previously below target | UNPROVEN CLAIM |

## Dead-End / Broken Data Paths

1. **Verdicts -> no pipeline truth:** before repair, `_open_pipeline_run` generated an ID
   but did not insert the database row.
2. **Watchdog -> ignored by Mission Control:** watchdog detected missing pipeline truth,
   but learning and promotion remained open.
3. **Full-suite contract -> removed symbol:** HFS test imports
   `compute_market_intelligence`, which no longer exists.
4. **Health workflow -> unavailable service:** smoke reaches the configured production
   URL and receives HTTP 502.

## Duplicate Sources of Truth

| Truth | Duplicates / conflict |
|---|---|
| Deployment status | runtime docs claim production; live health returns 502 |
| Scheduler ownership | Railway cron documented; GitHub Actions also schedules scoring |
| Daily readiness | Mission Control green conflicted with daily run truth failure |
| Model availability | legacy tests/docs claim models that clean checkout lacks |
| Dataset volume | 1.7M claim conflicts with absent reproducible dataset artifact |

## GitNexus Findings

GitNexus is an audit/development lens only. It does **not** need to be integrated into
the VELO runtime.

- Existing graph: 2,330 files, 43,702 nodes, 60,522 edges, 300 processes.
- Indexed commit: `619f25a4416c8d659a60d5d6db262b626c3f57c7`.
- Audited commit: `14ea7848827679a6687ebb0b70f155d07da85ad2`.
- Refresh attempt failed in the GitNexus CLI.
- Result: graph-derived connectivity for the audited code is **UNPROVEN**.

Direct inspection takes precedence until GitNexus is refreshed.

## Oracle of Odds Relationship

Oracle of Odds is a separate clean challenger, not a Prime runtime dependency:

```text
Prime settled evidence exports
  -> governed migration / training dataset
  -> Oracle of Odds replayable pipeline
  -> shadow evaluation
  -> explicit evidence-gated promotion decision
```

Do not copy Prime's scheduler, deployment configuration, stale tests, or false-green
gates into Oracle of Odds.

