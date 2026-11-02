# Railway Cloud EOD Recovery — RAILWAY-EOD-182

## Outcome contract

The existing VÉLØ end-of-day sequence can run in Railway without the operator's
laptop only when all of the following are true:

1. `velo-results-sigma` deploys the current production `main` SHA with
   `/railway.eod.toml` and cron `0 21 * * *`.
2. `scripts/ops/rp_cloud_eod.py` reconstructs the exact scored race universe from
   Supabase morning `races` and `velo_verdicts` rows.
3. Every scored race retains an identity-matching Racing Post racecard URL that can
   be transformed to its Racing Post result URL. Missing or mismatched identities
   stop the run.
4. The existing signed-in cloud RP credentials/profile capture the result HTML and
   the existing parser produces the dated results artifact.
5. The existing EOD orchestrator completes Sigma, multi-model Sigma, results
   ingestion, Mission Control, Council, final Mission Control refresh, learning
   gates, canonical persistence, and date-scoped artifact persistence.
6. The dated EOD report has every mandatory step `ok=true`, and Supabase contains a
   `pipeline_runs` row for `velo-results-sigma` with `PASS/completed`.

Railway's morning and evening cron containers do not share a filesystem. Supabase is
therefore the durable handoff. The wrapper hydrates existing morning report artifacts
from `velo_report_artifacts`; multi-model Sigma uses exact rank-1 rows from
`canonical_model_scorecards` only when its local morning files are absent. The live
scoring implementation and weights are unchanged.

## Deployment verification

Do not mark recovery complete from a successful GitHub check or Railway build alone.
Verify the service config file, deployed commit SHA, cron, date-specific logs, EOD
report postconditions, and durable pipeline run. If any mandatory gate fails, stop and
report the exact failure. Do not substitute another source, shrink the race set, or
bypass a gate.

## Final classifications

- RAILWAY_CLOUD_EOD_RECOVERY_IMPLEMENTED
- RACING_POST_HTML_REMAINS_AUTHORITATIVE
- EXISTING_EOD_GATES_ENFORCED
- NO_PRE_RACE_SCORING_CHANGE
- NO_LIVE_SCORING_CHANGE
- NO_MODEL_WEIGHT_CHANGE
- NO_GATE_BYPASS
- NO_SUPABASE_WRITES_DURING_BUILD
- NO_SUPABASE_WRITES
- NO_TELEGRAM_SEND
- NO_MODEL_PROMOTION
- NO_LIVE_BETTING

`NO_SUPABASE_WRITES` classifies this implementation and validation task. The authorized
production EOD operation continues to perform the repository's existing canonical
persistence steps; this repair adds no new scoring or model-state write path.
