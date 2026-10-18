# Evo² — historical truth recovery and existing evolution stack (2026-10-18)

## Read-only findings
- `canonical_model_scorecards`: 115,375 rows, 2,850 distinct (run_date,race_id) combinations across 69 dates. 253 combinations currently officially eligible.
- `velo_race_truth`: 6,512 rows / distinct race_id; 2,734 of the 2,850 scorecard race keys match this table **by race_id only**. 116 unmatched by this join. Matching IDs are NOT certification; dates, source hashes, terminal status, winner lists, non-runners and provenance still require validation.
- `race_results`: 3,227 distinct race_id rows, but zero direct race_id matches to these scorecards; investigate identifier namespace rather than declaring absent data.
- Read-only SELECT operations performed; no mutations, promotions or deployed changes.

## Existing governance — DO NOT REBUILD OR BYPASS
- `docs/engineering/VELO_AGENT_HARNESS_V1.md`: **DESIGN ONLY**, sentinel / mission-control / council governance contract.
- `docs/engineering/VELO_LLM_COUNCIL_INTEGRATION_WITH_HARNESS_V1.md`: Council audits harness return and rejects shadow-only promotions; status DEFINED.
- `src/velo/council/`: implementation directory; runtime wiring not yet verified.
- `scripts/ops/nightly_eod_learning_runner.py`: Playbook G shadow EOD entry point; execution and schedules require verification.
- `src/learning/auto_retrain.py`, `scripts/ops/run_multimodel_sigma.py`, `scripts/build_cpu_shadow_gate_v2.py`: existing learning/replay gate components; their presence alone is not proof of daily execution.
- `docs/engineering/VELO_LLM_COUNCIL_V1.md`, `docs/engineering/VELO_OPERATIONAL_HARNESS_PROTOCOL_V1.md` and `docs/engineering/VELO_LEARNING_LOOP_STATUS_V1.md` must be traced before inventing new orchestration.
- Evo² PR #168 remains an offline research branch; do not install or deploy a separate evolution stack now.

## Next recovery path
1. Make a **read-only** per-date census joining scorecards to `velo_race_truth`, verifying race date, identity namespace and official outcome source.
2. For 2,734 overlapping race identities, classify COMPLETE, PARTIAL, CONTRADICTORY, or UNVERIFIED—never bulk set eligibility based on ID matches.
3. Trace 116 unmatched scorecard race IDs through `races`, `racecards`, `velo_verdicts`, ingestion snapshots and local archived capture files; preserve exact IDs and provenance.
4. Trace `race_results` identifier namespace and date coverage independently.
5. Build a backtest across **all verified dates and models** with frozen pre-off predictions and matched runner populations; compare Brier, log loss, top-pick accuracy, calibration and race/day variance where valid.
6. Evo² Proposer outputs research hypotheses; existing Harness/Sentinel enforces scope; Evaluator tests frozen holdouts; LLM Council examines reproducible evidence; Reflector recommends REJECT or REVIEW_REQUIRED. No agent self-approval or silent live learning.
7. Record immutable snapshots and hashes, and audit rejected cases separately. Promotion remains blocked until independent validation and operator authorization.

## Implemented recovery path (PR #168)

- `src/intelligence/historical_runner_crosswalk.py` is the pure read-only crosswalk. It reuses `identity_resolver`, `prediction_run_selector`, and the existing challenger `Observation` contract.
- `src/intelligence/historical_crosswalk_cli.py` reads an immutable four-table export or performs allowlisted GET-only PostgREST reads. `--snapshot-jsonl-dir` adds the local append-only archive. There are no POST/PATCH/DELETE methods.
- Every original row used by a crosswalk record has a canonical SHA256. Each local JSONL file also receives its own raw-byte hash and a file-manifest hash.
- Snapshot runs are selected with the existing timezone-aware canonical run selector. Post-race runs, ambiguous runs, duplicate runner identities and unmapped timestamps fail closed.
- Verdict predictions have no explicit historical rank. The adapter preserves their array position as `source_ordinal` and leaves `rank=null`.
- Scorecard eligibility, result-source completeness/hash and `velo_race_truth.actual_winner_id` must agree. Missing or contradictory evidence is never filled.
- Frozen replay uses identical paired runner cohorts, chronological date bounds and exactly one verified winner per complete race. It invokes the existing Proposer, Evaluator and Reflector; it has no promotion authority.

### Capture cutoff conclusion

The cutoff is a Supabase sink cutoff, not a scoring-capture cutoff. Local JSONL evidence continues through 18 October.

1. Last Supabase snapshot rows: 19 June, commit `3667d39`.
2. The 20 June run at `14d7cff` recorded a 481-runner snapshot stage in 0.7497 seconds; the 21 June run at `821462d` recorded 166 runners in 0.3759 seconds. Both revisions' 37 written fields match the live table. The committed pipeline evidence does not retain the warning text, so the exact database exception is unproved.
3. The store reports the number written locally and catches every Supabase exception as non-fatal. Pipeline PASS and observability `persistence_status=OK` measured verdict persistence, not snapshot persistence.
4. At `fc297c7`, 14 new fields were added to each snapshot insert without corresponding live columns. That mismatch deterministically rejects later whole-batch inserts. The current writer still contains those fields and still swallows the error.
5. Local JSONL files are the primary alternative capture: 70,935 rows in 188 files, with 38,387 rows after 19 June. Verdict arrays independently cover the post-cutoff period.

### Runtime governance truth

- Harness and Sentinel are working Python implementations under `src/velo/harness/`; this change also has an enforced read-only task contract.
- The Council implementation under `src/velo/council/` is deterministic rule logic. Despite the historical name “LLM Council,” it contains no LLM calls.
- `nightly_eod_learning_runner.py` has Council integration, but repository presence and historical artifacts do not prove every scheduled run executed. `ONE_TRUTH.md` records prior missing Council runs and a period where the runner did not read the actual Council output.
- The replay therefore treats governance artifacts as evidence to validate, not as automatic certification or promotion authority.

## Do not misstate
- 2,734 ID matches do not equal 2,734 certified races.
- 253 eligible races do not imply 2,597 lost races.
- Available records do not by themselves establish profitable betting edge, statistical significance, or live deployment readiness.
