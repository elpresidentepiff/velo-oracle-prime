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

## Do not misstate
- 2,734 ID matches do not equal 2,734 certified races.
- 253 eligible races do not imply 2,597 lost races.
- Available records do not by themselves establish profitable betting edge, statistical significance, or live deployment readiness.
