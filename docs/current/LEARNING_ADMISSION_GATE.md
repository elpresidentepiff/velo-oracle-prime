# LEARNING ADMISSION GATE — VÉLØ ORACLE PRIME

**Effective:** 2026-06-10 (operator mandate). The learning runner (`nightly_eod_learning_runner.py`) may execute **only** when this gate evaluates `LEARNING_READY`. No exceptions. No manual bypass without a written operator approval recorded in the day's Mission Control file.

## Statuses

| Status | Meaning |
|---|---|
| `LEARNING_READY` | Every condition below is true AND operator approved admission |
| `LEARNING_BLOCKED_FEATURE_DEGRADED` | Observability packet says `RP_MERGED_DEGRADED` (or any non-CLEAN allowed label) |
| `LEARNING_BLOCKED_SOURCE_UNKNOWN` | No observability packet, malformed packet, or `SOURCE_UNKNOWN_BLOCK` |
| `LEARNING_BLOCKED_PERSISTENCE_UNPROVEN` | `prove_supabase_persistence.py --date D` did not PASS |
| `LEARNING_BLOCKED_RPDC_CORRUPTED` | Persisted RPDC fields disagree with local `rpdc_lookup_status` (hijack symptom) |
| `LEARNING_BLOCKED_OPERATOR_HOLD` | Operator hold for any reason — outranks everything |

## Conditions — ALL must be true for LEARNING_READY

1. Source truth for the date is `RP_MERGED_CLEAN` (from observability packet, via fixed Mission Control).
2. Mission Control `source_truth` matches the observability packet (they now share one source — verify anyway).
3. Feature-health packet exists: `data/velo_run_observability_{date}_*.json` for the scoring run.
4. No live-weighted component appears in `excluded_from_ensemble` on persisted rows (`sqpe_v17`, `improvement_score`, `market_deception_score` all in `active_components`).
5. `improvement_score` is variable and valid across the day's verdicts (not flat, not all-zero).
6. RPDC fields on persisted rows are genuine (`rpdc_primary_tag` matches local backup attach; no `PDF_PLOT` values).
7. `prove_supabase_persistence.py --date D` exits 0 (PASS).
8. Sigma closed successfully: `data/sigma_results/sigma_results_{date}.json` exists with `sigma_status: PASS`, zero identity failures.
9. `ingest_results_to_horse_runs.py` printed `INGEST COMPLETE` with runner counts matching parsed results.
10. No contamination flag: run IDs not in `MC_CONFIG.CONTAMINATED_RUN_IDS`; no flatline gate.
11. Council verdict is `PASS_TO_LEARNING` (not WATCH_ONLY / EVIDENCE_INCOMPLETE / QUARANTINE_DAY).
12. **Operator approves admission** — explicit, per day, never assumed.

## June 11 evaluation (pre-filled where already known)

| # | Condition | Status as of 2026-06-10 |
|---|---|---|
| 1–3 | Source clean + packet | PENDING (UNKNOWN until morning run) |
| 4–5 | Ensemble components live + improvement variable | PENDING |
| 6 | RPDC genuine | Expected PASS — fix `66d23a0` active from June 11 scoring |
| 7 | Persistence proof | PENDING (June 10 currently FAIL on pre-fix rows) |
| 8–9 | Sigma + ingest | PENDING evening |
| 10 | No contamination | PENDING |
| 11 | Council | PENDING |
| 12 | Operator approval | NOT GIVEN |

**Current status for June 11: `LEARNING_BLOCKED_SOURCE_UNKNOWN`** (correct and expected before the day runs).

## Enforcement roadmap
Today this gate is procedural (this document + Mission Control gate reasons). The enforcement fix (NEXT_10 list, queued item): `nightly_eod_learning_runner.py` must refuse to start unless it can read (a) Council `PASS_TO_LEARNING` artifact, (b) Mission Control `learning_gate: OPEN`, and (c) persistence proof PASS for the date — from artifacts, not flags. Until that lands, the operator is the enforcement.
