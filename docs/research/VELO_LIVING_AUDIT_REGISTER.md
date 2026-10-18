# VÉLØ — Living Architecture & Defect Register

Owner: VÉLØ engineering. Updated: 2026-10-18. Scope: evidence-led findings only.
Reference: issues #167, #169; draft PR #168. This register lives on the experimental branch pending review.

## Operating rule
Every discovered issue receives an ID, observed source, date, impact, confidence, verification steps and resolution status. Do not assume configuration evidence proves runtime behavior. Open or link a GitHub issue for actionable production faults. NEVER silently flip eligibility flags or change deployments.

| ID | Evidence / finding | Severity | Next action | Status |
|---|---|---|---|---|
| VELO-001 | Supabase `velo_learning_events` has 5,133 total entries, 4,449 consumed_shadow, 0 consumed_live; not proof of no live learning via other paths | HIGH | Trace shadow consumers, production model hashes and all promotion paths; confirm actual learning integration | OPEN |
| VELO-002 | Supabase `model_versions` contains one active row; latest `trained_at` 2025-12-03, not an authoritative inventory of current artifacts | HIGH | Correlate Git SHA, training outputs, inference models and deployed image builds | OPEN |
| VELO-003 | Oct 17-18 canonical scorecards: 5,969 rows, 0 `official_evaluation_eligible`, `result_source_complete=false`, 17 Oct RESULT_SOURCE_INCOMPLETE | CRITICAL (evaluation) | Trace result contracts, independent race coverage and verification before interpreting model performance | OPEN |
| VELO-004 | Oct 17: 60 shadow result_confirmed learning events; no `model_versions` training timestamp in past 48 h | MEDIUM | Determine whether persisted state changed and whether any production code consumed it | OPEN |
| VELO-005 | README points to root-level Sigma scripts; canonical scripts are `scripts/ops/run_results_sigma.py` and `app/pipelines/sigma_runner.py`, CPU gate at `scripts/build_cpu_shadow_gate_v2.py` | LOW | Update documentation in dedicated PR after canonical code-path verification | OPEN |
| VELO-006 | GitHub PR #168 CI lint failed on `app/main.py:1803` Ruff B023; other initial test and safety jobs succeeded | MEDIUM | Separate pre-existing closure issue from challenger lab; verify base branch and fix through scoped PR | OPEN |
| VELO-007 | Railway production project `sincere-empathy` has `ingestion-spine` source branch `feature/v10-launch` (last reported SUCCESS 2026-04-16) while `velo-prime-scoring` and `velo-oracle` use `main` (SUCCESS 2026-10-15) | HIGH | Trace deployed commit, service health, configs and ingestion ownership; no redeploy until verified | OPEN |
| VELO-008 | Railway `velo-results-sigma` source branch is null in returned config (last SUCCESS 2026-04-26), while `velo-shadow-lab` uses `shadow-lab` and reports no latest deployment | HIGH | Determine effective deployed SHA, source and whether loops run; inspect schedules/logs | OPEN |
| VELO-009 | Railway `hermes-agent` deployment showed FAILED 2026-10-15, but owner confirms service is RETIRED / NOT IN USE | INFORMATIONAL | Exclude from operational alerts and Evo² work; consider decommission separately only with explicit approval | RETIRED — NOT AN ACTIVE DEFECT |
| VELO-010 | Railway `focused-dream` `web` service sources older `velo-oracle/main`, latest deployment FAILED 2026-05-25 | MEDIUM | Confirm whether legacy, active or obsolete; avoid deleting until dependencies mapped | OPEN |

## Known Railway service lineage (configuration, NOT live code verification)
- Railway project: `sincere-empathy` / environment `production`
- `velo-oracle-prime`: repo `elpresidentepiff/velo-oracle-prime`, `main`, last SUCCESS 2026-07-25
- `velo-formfav-live`, `velo-oracle`, `velo-formfav-us-shadow`, `velo-formfav-uk-shadow`, `velo-prime-scoring`: same repo `main`, last SUCCESS 2026-10-15
- `ingestion-spine`: repo `velo-oracle-prime`, `feature/v10-launch`, last SUCCESS 2026-04-16
- `velo-results-sigma`: repo `velo-oracle-prime`, branch unspecified, last SUCCESS 2026-04-26
- `velo-shadow-lab`: repo URL `velo-oracle-prime`, `shadow-lab`, latest deployment not returned
- `hermes-agent`: RETIRED / NOT IN USE per owner confirmation; exclude from active outage/health analysis
- Railway `focused-dream/web`: old repo `velo-oracle/main`, latest FAILED 2026-05-25

## Next audit checkpoint
Verify every live service's actual deployment commit, process command, schedules, recent logs and canonical data targets. For Evo², map frozen prediction snapshots and the production scoring code path; only then connect Proposer/Reflector to verified holdouts.

## Owner correction — 2026-10-18
Hermes is retired and must not be represented as an active fault. One truth: canonical VÉLØ repository is `elpresidentepiff/velo-oracle-prime`; `main` is intended canonical source, subject to verification of deployed SHAs/service roles. Evo² stays research-only until evidence-gated. Do not route new work to old VÉLØ repositories, feature branches, or Hermes. No production configuration has been changed.
