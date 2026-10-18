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
| VELO-006 | PR #168's remaining lint failure was `ruff format --check`: two surplus blank lines in `app/main.py`; `app/world_dashboard.py` is already formatted | MEDIUM | Formatting-only repair applied on the research branch; retain CI verification | RESOLVED IN PR #168 |
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

## Snapshot cutover findings — 2026-10-18

| VELO-011 | `runner_prediction_snapshots` ends 2026-06-19: 26,425 rows / 1,360 race-date identities; 74 excess (run_id,race_id,horse_id) records over unique keys | HIGH | Trace persistence cutover and duplicate semantics | OPEN |
| VELO-012 | **Recovery source found:** `velo_verdicts.full_analysis.predictions` contains 2,743 verdict rows / 27,176 runner entries generated on/after 2026-06-20; first item in all has horse_id and velo_prime_prob, but not explicit rank | HIGH | Audit every runner, chronology/real race off, identity, deduplication, complete runner fields and actual official result join; do not treat entries as certified by count alone | INVESTIGATING |
| VELO-013 | The June 20 (`14d7cff`, 481 runners) and June 21 (`821462d`, 166 runners) timing artifacts prove the snapshot stage ran, but no rows reached Supabase. The writer returned its local row count and swallowed the database exception, so the exact initial database error is no longer recoverable from committed evidence. | HIGH | Preserve this as an unresolved observability failure; do not claim a single proven June 20 root cause. | ROOT CAUSE PARTIAL |
| VELO-014 | From `fc297c7`, the writer sent 14 columns absent from the live table (`sqpe_no_rpr_*`, NDS, chain and mid-price fields). Whole-batch insert errors remain warning-only. | CRITICAL (capture) | Production repair requires a separately approved schema/code contract and durable error telemetry; no production or migration change in PR #168. | CONFIRMED DEFECT |
| VELO-015 | Local append-only JSONL capture continued: 188 files, 70,935 rows over 94 dates (20 May–18 Oct), including 38,387 rows after 19 June. Therefore capture continued while the Supabase sink failed. | HIGH | Use the local archive read-only, hash every file and crosswalk with verdict arrays; retain Supabase as independent evidence. | RECOVERY SOURCE VERIFIED |

## Historical crosswalk execution — 2026-10-18

The read-only adapter joined the Supabase snapshot table, 188 local snapshot JSONL files, verdict prediction arrays, canonical scorecards and race truth. It selected one canonical pre-race snapshot run per race when available and used verdict arrays only for remaining races. Verdict array order is stored as `source_ordinal`; it is never invented as model rank.

Source census and immutable SHA256 values:

| Evidence source | Rows / entries | SHA256 |
|---|---:|---|
| `runner_prediction_snapshots` | 26,425 | `03063a04bbd4b499d257b87d2f1c743e9c455ffb65fdc8052fb80ecb0174495d` |
| Local `runner_snapshots_*.jsonl` | 70,935 | `6b7666b270a97d03b4cb85c55bfc7e63838fa1aa8f91a259fd47d3269b6fa557` |
| Local JSONL file-hash manifest (188 files) | 188 | `d029ea7f9167731440797bed848c9a6844f86b0ebe3c2dc1e0291e64674f5aa8` |
| `velo_verdicts` | 6,512 | `1aa1099d0dd5b45e74f283885d2464f0275d20dc04716db68dadc6c4bda7dc99` |
| `velo_verdicts.full_analysis.predictions` | 46,249 | included in verdict hash |
| `canonical_model_scorecards` | 115,375 | `54b15b668f77c950b84cf15e18f842f408f6d5c98244c6b1684c61d8f64c187a` |
| `velo_race_truth` | 6,512 | `a2657fff7ed8bac6a6c1f81483926341fc8fbc9f3f8599eed423686e36f3242b` |

Classification over 48,246 canonical crosswalk rows:

| Race date | Complete verified runners | Incomplete | Duplicate / contradictory identity | Missing pre-race time proof | Missing / unverified official result |
|---|---:|---:|---:|---:|---:|
| 2026-09-29 | 287 | 86 | 0 | 0 | 86 |
| 2026-09-30 | 313 | 37 | 0 | 0 | 37 |
| 2026-10-02 | 300 | 219 | 0 | 39 | 181 |
| 2026-10-05 | 422 | 102 | 0 | 0 | 102 |
| 2026-10-06 | 290 | 42 | 0 | 0 | 42 |
| 2026-10-15 | 231 | 184 | 0 | 0 | 184 |
| **All 94 dates** | **1,843** | **46,403** | **3,406** | **14,597** | **46,365** |

Gap counts overlap and must not be summed. The identity total includes 221 excess local `(run_id,race_id,horse_id)` entries plus 3,185 rows with contradictory date evidence. The official-result total includes one explicit winner contradiction. No non-runner was admitted to the certified replay cohort.

The strict, full-field replay cohort is smaller than the individually verified set: 1,074 runners in 125 races. Every included race has complete starter evidence, exactly one winner, paired `velo_prime_prob` and `sqpe_v17_prob`, and timezone-correct pre-race timestamps. Cohort SHA256: `71ee4dd292049a77d16d1cf7d7d168fe5e340d02b94295609c14257d787adae7`.

The existing Proposer → Evaluator → Reflector chain executed. Velo Prime Brier/log loss were `0.106091` / `0.372467`; SQPE v17 were `0.112116` / `0.442492`. Reflector decision: `REJECT`. Promotion remains `NOT_AUTHORISED`; this run changed no production state.
