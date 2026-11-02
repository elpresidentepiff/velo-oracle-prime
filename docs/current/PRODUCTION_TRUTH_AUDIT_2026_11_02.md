# Production Truth Audit — 2026-11-02

## Scope

This audit addresses the P0 production-truth discrepancy tracked in issue 179
and the deployment-lineage concerns tracked in issue 170. It is restricted to
post-race identity reporting, deterministic EOD reporting, and read-only
inspection of Railway and Supabase. It does not change pre-race scoring,
models, weights, gates, credentials, execution mode, staking, or production
configuration.

## Verified November 1 race universe

| Evidence source | Verified value |
| --- | ---: |
| Supabase `velo_verdicts` | 36 rows / 36 unique races |
| Top-pick names resolvable from `full_analysis.predictions` | 36 / 36 |
| Supabase verdicts assigned `EW_CANDIDATE` | 5 |
| RP result truth in `racing_horse_runs` | 383 runners / 36 races / 36 winners |
| Local canonical Sigma artifact | 36 evaluated races |
| Supabase `sigma_audits` | 35 rows / 35 races |
| Sigma-only race absent from `sigma_audits` | `931966` |
| `pipeline_runs` for 2026-11-01 | one morning `daily_scoring` PASS; no EOD row |

The local canonical Sigma artifact reports 12 wins, 11 additional frames and
13 misses: a 33.33% win rate and 63.89% win-or-frame rate over 36 races. Its
EW block contains five candidates, four places and no wins.

## Root cause of the reported 38 races and four EW candidates

The source artifacts did **not** contain 38 races. At the time the November 1
EOD brief was written, `model_comparison_ledger.csv` contained 36 unique rows,
and the canonical Sigma artifact contained 36 rows. The generated LLM prose
reported 38 anyway. The same prose listed only four of the five EW candidates,
omitting race `932250`, even though both Sigma and the ledger contained it.

This was an unvalidated generative-reporting failure, not a missing-results or
missing-selection failure. The old EOD brief is not authoritative evidence.

## Root cause of `velo_top_pick = ?`

`run_results_sigma.py` requested `full_analysis` from Supabase but parsed it as
though the field were a runner list. Production stores a dictionary whose
`predictions` member is the runner list. Horse-ID reconciliation still worked,
so the 36 outcome labels were computed against the correct persisted horse IDs,
but the human-readable pick name fell through to `?` when no local backup file
existed. Read-only inspection verified that all 36 names are present and
resolvable in Supabase.

The repair adds a pure name resolver supporting the production dictionary,
serialized dictionary, and legacy list shapes. It always matches
`top_rank_horse_id` first and never invents a name.

## Root cause of missing Sigma detail in the EOD brief

`run_llm_intel_brief.py` read `sigma["results"]`; the canonical artifact writes
per-race records to `sigma["rows"]`. The brief therefore sent no detailed Sigma
rows to the model. The repair reads the canonical key and cross-checks Sigma and
ledger race universes, counts, duplicate IDs, EW membership, and pick-name
coverage before reporting.

EOD truth is now rendered deterministically from the artifacts. The LLM remains
available only for explicitly non-authoritative morning suggestions. A blocked
integrity check returns a non-zero status and prints the exact reasons.

## Railway production lineage

| Service | Observed production state | Evidence |
| --- | --- | --- |
| `velo-oracle` | Active on `main` SHA `9cef83f4` | successful deployment 2026-10-29 |
| `velo-rp-capture` | Current image on SHA `9cef83f4`; 07:00 UTC cron | November 1 logs end with canonical race-day PASS for 36 races |
| `velo-formfav-uk-shadow` | Current image on SHA `9cef83f4`; 08:30 UTC cron | November 1 enriched 36 races / 406 runners, with two identity mismatches |
| `velo-results-sigma` | Legacy SHA `7e8e06e`; configured 21:00 UTC cron | latest listed successful execution/deployment is 2026-04-26; no logs in the last seven days |
| `velo-prime-scoring` | Crashed on SHA `9cef83f4` | October 29 log: RP credentials absent; actual command drifted from manifest |
| `ingestion-spine` | Active on old feature branch SHA `4db2ca31` | build command mutates parser source during build |
| `hermes-agent` | Failed/stopped | retired-path residue |

The critical operational blocker is therefore confirmed: successful morning
scoring does not imply that the cloud EOD/Sigma job ran. The scheduled Sigma
service is not on current `main`, has no recent execution evidence, and writes
no current `pipeline_runs` record. This code repair is not deployed and does
not change that Railway configuration.

## Repair boundary

- Post-race horse-name reporting repaired.
- EOD race counts and EW membership made deterministic and cross-validated.
- No historical artifact was silently rewritten.
- No Supabase record was written or modified.
- No Railway service, cron, variable, command, or deployment was changed.
- No model, weight, pre-race score, gate, credential, Telegram path, or
  execution mode was changed.

## Required classifications

- `POST_RACE_IDENTITY_REPORTING_REPAIRED`
- `LLM_BRIEF_INPUTS_DETERMINISTICALLY_VALIDATED`
- `RAILWAY_CRON_DRIFT_REPORTED`
- `NO_PRE_RACE_SCORING_CHANGE`
- `NO_MODEL_WEIGHT_CHANGE`
- `NO_GATE_BYPASS`
- `NO_SUPABASE_WRITES`
- `NO_TELEGRAM_SEND`
- `NO_MODEL_PROMOTION`
- `NO_PRODUCTION_DEPLOY`

## Next controlled action

After review, merge and deploy the post-race truth repair through the normal CI
path. Separately, repair the Railway EOD service definition so it runs the
current governed `scripts/ops/run_results_sigma.py` sequence from `main`, then
prove one complete date with a `pipeline_runs` EOD record, 100% race-universe
reconciliation, Council, final Mission Control refresh, and learning-gate
outcome. Do not backfill or learn from any date until those gates pass.
