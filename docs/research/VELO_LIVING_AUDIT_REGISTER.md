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

## Multi-model and captured-price replay — 2026-10-18

The adapter now inventories probability and price evidence without converting scores or categorical actions into probabilities. Of 48,246 crosswalk rows, 47,841 contain `sqpe_v17_prob`, 27,649 contain `sqpe_no_rpr_shadow_prob`, and 28,490 contain a positive `sp_dec` value in the prediction record. The price is accepted only when the containing prediction record is strictly pre-race; its field name and source hash are retained.

Both SQPE variants are complete on the existing 1,074-runner / 125-race frozen cohort (cohort SHA256 `71ee4dd292049a77d16d1cf7d7d168fe5e340d02b94295609c14257d787adae7`). The extended artifact SHA256 is `5fcc1d3b7ba114ad6e609ed7db1ed1880a24378b7bac94045ea18b2ce6966427`.

| Model | Brier | Log loss | 10-bin ECE | Brier delta vs Prime | Race-level 95% CI | Reflector |
|---|---:|---:|---:|---:|---:|---|
| Velo Prime | 0.106091 | 0.372467 | 0.060752 | — | — | baseline |
| SQPE v17 | 0.112116 | 0.442492 | 0.090516 | +0.006025 | [+0.002192, +0.016230] | REJECT |
| SQPE no-RPR shadow | 0.100426 | 0.349853 | 0.011329 | -0.005665 | [-0.017201, +0.002980] | REVIEW_REQUIRED |

The no-RPR shadow improves the point estimates, but its race-level Brier interval crosses zero. `REVIEW_REQUIRED` is therefore an invitation to independent chronological validation, not promotion evidence.

For a descriptive value check, each model selected one highest-probability runner per race for a flat one-unit stake at the `sp_dec` value captured in the pre-race record. Prime returned 101.66 units from 125 stakes (ROI -18.672%); SQPE v17 returned 104.91 (-16.072%); SQPE no-RPR returned 106.33 (-14.936%). The no-RPR paired ROI delta versus Prime was +3.736 percentage points, with a race-level 95% interval of [-63.020%, +70.492%]. All three lost money. The adapter does not claim that `sp_dec` was independently timestamped by the market provider or obtainable at execution; those provenance questions remain open, so these returns are descriptive only.

Requested challenger gaps remain explicit:

- MDS Heavy, Calibrated G and Passport Strength have no crosswalked runner-level win-probability artifact.
- New Build lanes A/B live in separate historical artifacts and are not yet joined to this cohort.
- Mid-Price Hunter is captured as an action/category, not a runner win probability; it must be evaluated under its declared selection policy rather than coerced into Brier/log-loss input.

No production state, live model weight, database record, promotion status or betting system changed.

## Evo² policy replay and certification triage — 2026-10-18

| ID | Finding | Severity | Evidence / next action | Status |
|---|---|---|---|---|
| VELO-016 | New Build historical `two_lane_readiness` artifacts expose **ranked top-three only** and frequently horse names but not canonical horse IDs. Individual reports have a shared generated_at and some race cards precede that timestamp. | HIGH | Added `src/intelligence/challenger_policy_replay.py` strict offline top-pick audit; require unambiguous runner-name match, rank-one identity, and report timestamp strictly before race off. Reject post-off and ambiguous rows; NEVER compute full-field Brier from top-three. Complete historical evaluation awaits local readiness files on the replay machine. | IMPLEMENTED RESEARCH GATE; EMPIRICAL COHORT PENDING |
| VELO-017 | Mid-Price Hunter is an existing action policy with `MIDPRICE_CLEAN`, `MIDPRICE_SUPPRESS_TOP`, `MIDPRICE_NO_EDGE`, and `MIDPRICE_SPLIT_RACE`. Historical actions are not win probabilities. | HIGH | Added action-only conditional-outcome replay with pre-race timestamp, canonical Prime top-pick match, declared rule version and strict shadow-only flags. Non-clean abstention is a **hypothetical counterfactual**, not a deployed execution rule. | IMPLEMENTED RESEARCH GATE; EMPIRICAL COHORT PENDING |
| VELO-018 | `canonical_model_scorecards` records 78,683 ineligible rows marked `GOVERNED_REBUILD_REQUIRED`, spanning 2,330 distinct run_date/race_id combinations. These rows have **zero** complete-source flags and **zero** result-source hashes. | CRITICAL (evidence) | Recover official provider results through governed source rebuild and verified provenance, not eligibility flag edits. Read-only `scripts/research/evo2_official_eligibility_triage.sql` added. | SOURCE RECOVERY REQUIRED |
| VELO-019 | 15,890 scorecard rows marked `RESULT_SOURCE_INCOMPLETE`, across 235 race/date identities. 10,749 have source hashes but **zero** are marked result-source complete. | HIGH | Audit hashed-but-incomplete official result evidence separately; hashes prove byte identity, not completeness or trustworthy official status. | RECONCILIATION REQUIRED |

New optional flags in `historical_crosswalk_cli.py`:
- `--new-build-readiness-dir PATH` reads existing `two_lane_readiness_*.json` files (never writes to them).
- `--midprice-ledger-csv PATH` reads the historical Mid-Price Hunter action ledger.
- Both emit fail-closed provenance-tagged `evo2_policy_replays` into the existing report and do not change the certified 1,074-runner probability cohort or authorise promotion.
- A separate PR-only GitHub workflow `evo2-offline.yml` checks this research code and executes dedicated offline tests rather than relying on ingestion-only CI.

**Status:** The user-provided frozen 125-race replay remains the only executed certified probability comparison. New Build/Mid-Price results must remain unclaimed until the local archive and readiness/ledger artifacts are evaluated together. No production edits, provider calls, database writes, stake placement or promotion were performed.

## 2026-10-18 production runtime and replay completeness sweep

| ID | Finding | Severity | Next action | Status |
|---|---|---|---|---|
| VELO-020 | Railway `velo-prime-scoring` cron `0 9 * * *` **FAILED** on 2026-10-18 at 09:02:16 UTC; `velo-results-sigma` cron `0 21 * * *` **FAILED** on 2026-10-17 at 21:00:42 UTC. UK FormFav cron succeeded on Oct 18. | CRITICAL (operations) | Issue #172: recover original cron exceptions and run IDs. Latest successful *deployment* is not proof scheduled execution succeeds. No production repair without approval. | CONFIRMED CRON FAILURES |
| VELO-021 | Sigma active deployed commit is `7e8e06e` from Apr 26, with command `scripts/run_results_sigma.py`; **that old path exists at its deployed commit**, but not on current `main`. Runtime logs returned no current cron exception. A previous path-mismatch causality hypothesis is NOT established. | HIGH | Trace actual old code execution, data providers, failed cron outputs and migration path to current `scripts/ops/run_results_sigma.py`. | DRIFT CONFIRMED; ROOT CAUSE UNKNOWN |
| VELO-022 | Prime scoring's Railway deployment commit `9425564c` (Oct 15) runs `scripts/ops/run_cloud_raceday.py`, which fetches Racing API Standard. `docs/current/ONE_TRUTH.md` (Jul 29) explicitly prohibits live Racing API and requires RP HTML live. | CRITICAL (source governance) | Obtain operator source-policy resolution; compare live code/output provenance and observer packet; do not silently switch provider. | POLICY CONTRADICTION CONFIRMED |
| VELO-023 | `pipeline_runs` has a manual completed `PASS` for Oct 18 (21 races/239 runners, generated Oct 17 23:41–23:42 UTC). Its 21 verdict race IDs match 21 of the 28 Oct 18 scorecard races; 7 scorecard races have no matching verdict in this manual run. | HIGH | Reconcile universe and timestamps; do not equate a PASS on 21 with complete 28-race day coverage. Scorecard rows may reflect later/different source subsets. | COVERAGE GAP CONFIRMED |
| VELO-024 | `ingestion-spine` Railway deployment is online on Apr 16 SHA `4db2ca3`, configured source branch `feature/v10-launch` absent from current 14 GitHub branches; its build command rewrites `workers/ingestion_spine/parsers/__init__.py` at build time. `velo-shadow-lab` is offline and its configured `shadow-lab` branch is absent too. | HIGH (reproducibility) | Pin exact immutable source and review build-time source mutation and legacy service intent before any deployment. Retired Hermes excluded as active defect. | SOURCE/BUILD DRIFT CONFIRMED |
| VELO-025 | Current replay `frozen_holdout` / `frozen_model_holdout` validates *observed crosswalk starters* and exactly one winner but does not explicitly verify the starter set equals an independent official full-field participant manifest/count. Chronological holdout date alone also does not prove model weights were trained strictly before it. | HIGH (evaluation validity) | Require independent official starter-set proof, stable model SHA/train cutoff, no data leakage, race-date stratification and external official source certification before upgrading replay to independently verified. Existing 125-race result remains internally gated research evidence. | REVIEW GAP CONFIRMED |
| VELO-026 | Railway project has zero configured project webhooks; other alert channels unverified. The project has cron failures while GitHub branch checks all pass. | HIGH (observability) | Audit notification/alert ownership and failure reporting without inventing recipient or claiming no other notifications. | ALERT PATH UNVERIFIED |

Additional verified observations:
- `velo_learning_events`: 5,133 recorded, 4,449 consumed_shadow and 0 consumed_live. This does NOT establish that no other production learning path exists.
- `velo_race_truth`: 6,512 records, 4,592 with winner IDs/reconciled dates (not independently official-certified).
- `model_versions`: one row with latest trained_at 2025-12-03, inconsistent with artifacts described in `ONE_TRUTH`; registry cannot be treated as authoritative.
- Research commit `19640df3` has SUCCESS for ordinary CI, Evo2 offline tests, GX and safety. Eleven offline policy/CLI tests passed. No live deployment/promotion.
- `hermes-agent` is explicitly retired by owner; its online state/warnings are NOT counted as an operational incident. Any resource cleanup requires separate approval.
- The Rugby/April Docker-era logs showing a null-byte syntax error in early October are historical logs; not evidence of the precise Oct 18 cron failure.

All findings read-only. Issue #172 holds the production reliability investigation; master backlog #171 tracks remaining work.
