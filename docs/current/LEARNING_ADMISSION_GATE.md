# LEARNING ADMISSION GATE — VÉLØ ORACLE PRIME

**Effective:** 2026-11-03. The learning runner (`nightly_eod_learning_runner.py`) may execute **only** when this gate evaluates `LEARNING_READY`. Integrity failures are never bypassed. Performance weakness and missing optional context are evidence for shadow learning, not integrity failures.

## Statuses

| Status | Meaning |
|---|---|
| `LEARNING_READY` | Every integrity condition below is true |
| `LEARNING_READY_DEGRADED_CONTEXT` | Integrity is intact; one or more optional, non-live-weighted context lanes are missing |
| `LEARNING_BLOCKED_SOURCE_UNKNOWN` | No observability packet, malformed packet, or `SOURCE_UNKNOWN_BLOCK` |
| `LEARNING_BLOCKED_PERSISTENCE_UNPROVEN` | `prove_supabase_persistence.py --date D` did not PASS |
| `LEARNING_BLOCKED_RPDC_CORRUPTED` | Persisted RPDC fields disagree with local `rpdc_lookup_status` (hijack symptom) |
| `LEARNING_BLOCKED_OPERATOR_HOLD` | Operator hold for any reason — outranks everything |

## Conditions — ALL must be true for LEARNING_READY

1. Source truth is a permitted RP label and its capture timestamp is pre-race. `RP_MERGED_DEGRADED` is admissible only when the degradation is optional context and all live-weighted inputs remain valid.
2. Mission Control `source_truth` matches the observability packet (they now share one source — verify anyway).
3. Feature-health packet exists: `data/velo_run_observability_{date}_*.json` for the scoring run.
4. No live-weighted component appears in `excluded_from_ensemble` on persisted rows (`sqpe_v17`, `improvement_score`, `market_deception_score` all in `active_components`).
5. `improvement_score` is variable and valid across the day's verdicts (not flat, not all-zero).
6. RPDC fields on persisted rows are genuine (`rpdc_primary_tag` matches local backup attach; no `PDF_PLOT` values).
7. `prove_supabase_persistence.py --date D` exits 0 (PASS).
8. Sigma closed successfully: `data/sigma_results/sigma_results_{date}.json` exists with `sigma_status: PASS`, zero identity failures.
9. `ingest_results_to_horse_runs.py` printed `INGEST COMPLETE` with runner counts matching parsed results.
10. No contamination flag: run IDs not in `MC_CONFIG.CONTAMINATED_RUN_IDS`; no flatline gate.
11. Council verdict is `PASS_TO_LEARNING`, or `WATCH_ONLY` whose reasons are exclusively performance-based. `EVIDENCE_INCOMPLETE`, `QUARANTINE_DAY`, and integrity-based `WATCH_ONLY` block admission.
12. The runner records the admission decision and reasons in Mission Control. No manual approval is required for a normal, gate-passing scheduled run; no operator can override an integrity failure.

## State separation

Daily run availability, result/outcome integrity, shadow-learning admission, and model promotion are separate states. A dashboard or optional sidecar failure may degrade visibility without invalidating Prime. A poor strike rate may produce `WATCH_ONLY` while still remaining valid shadow-learning evidence. Promotion remains separately gated and is never implied by learning admission.
