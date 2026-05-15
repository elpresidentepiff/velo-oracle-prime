# VELO Agent Permission Matrix V1

## Purpose
Define what each agent can read, write, and never touch.

| Agent | Responsibility | Allowed Reads | Allowed Writes | Forbidden Paths | DB Reads | DB Writes |
|---|---|---|---|---|---|---|
| Supervisor Agent | decide next safe action | mission control, sentinel, job runs | none | live state, scoring files | `velo_job_runs`, `velo_learning_events` | none |
| Morning Ingestion Agent | build race-day artifacts | RP PDFs, API racecards | `data/racecard_merged/`, RP coverage reports | live state, verdicts, learning states | `races`, `runners`, `courses` | none |
| RacingPostAdapter Agent | normalize RP intelligence | merged racecards, CASHRUN, coverage reports | RP feature artifacts, convergence inputs | live state, verdict overwrite | `races`, `runners` | none |
| Racing API Spine Agent | harvest structured spine data | raw API zone, results, racecards | raw API landing zone, reports | live state, shadow states | `races`, `runners`, `runner_results`, `racing_horses`, `raceform` | none |
| Market Agent | price/deception sidecars | verdicts, market logs, odds snapshots | market sidecars, market snapshots | staking, live state | `velo_verdicts`, `runner_results` | none |
| VELO Scoring Agent | official scoring | racecards, merged RP data, protected live state (read-only) | verdict artifacts, dashboard read models | `shadow_full_train_v1`, live promotion files | `races`, `runners`, `racing_horses` | `velo_verdicts`, `pipeline_runs` |
| Convergence Agent | compare VELO with RP/CASHRUN | verdicts, merged RP, CASHRUN | convergence reports | live state | `velo_verdicts` | none |
| Sigma Agent | results reconciliation | verdicts, results cache | results artifacts, miss forensics | shadow states, live state | `velo_verdicts`, `runner_results` | `sigma_audits` |
| Learning Agent | shadow-only learning | verdicts, results, `shadow_full_train_v2` | `shadow_full_train_v2`, EOD reports | live state, `shadow_full_train_v1` | `sigma_audits`, `velo_learning_events` | `velo_learning_events` |
| Security Sentinel Agent | preflight veto | git state, state files, reports | sentinel preflight artifacts | live state mutation, contaminated shadow | `velo_learning_events`, `learned_patterns`, `velo_job_runs` | none |
| Report Agent | operator intelligence | daily reports, convergence, run truth | mission control outputs, report outputs | live state | `velo_job_runs`, `sigma_audits`, `velo_learning_events` | none |
| Red Team Agent | failure forensics | reports, dry-run artifacts, job history | forensic artifacts only | live state, contaminated shadow writes | `velo_job_runs`, `velo_learning_events`, `sigma_audits` | none |

## Global Forbids
- `data/sentient_state.json`
- `shadow_full_train_v1`
- any `consumed_live=true`
- any live promotion path
- any official prediction overwrite without explicit force approval
