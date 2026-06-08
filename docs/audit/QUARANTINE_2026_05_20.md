# QUARANTINE — 2026-05-20

## Classification

| Field | Value |
|---|---|
| Date | 2026-05-20 |
| run_id (primary) | 32cc27f9 |
| run_id (secondary) | 847964a6 |
| Source | RP_MERGED pre-a33c5bd |
| Fix commit | a33c5bd84aa600a98bd9e1bfdc381750f20f23a4 |
| Classification | SCORING_FLATLINE_CONTAMINATED |
| training_eligible | false |
| promotion_eligible | false |
| learning_eligible | false |
| forensic_value | true |
| Data deleted | false |

## Contamination Evidence

| Metric | Value |
|---|---|
| Total races scored | 33 |
| Fully uniform races | 6 |
| Majority-tied races | included in fully_uniform count |
| Runners per snapshot | 269 |
| Total snapshot rows (3 files) | 807 |
| Sigma SR on this day | 6.2% |
| Baseline SR | 20% |

## Fully Uniform Races

All runners in these races received identical VP scores — the model scored blind:

| Race ID | Uniform VP |
|---|---|
| rp_AYR_20260520_1.42 | 0.2500 |
| rp_AYR_20260520_2.42 | 0.0833 |
| rp_AYR_20260520_3.42 | 0.0833 |
| rp_AYR_20260520_4.42 | 0.1111 |
| rp_AYR_20260520_5.15 | 0.1250 |
| rp_GOW_20260520_7.20 | 0.2500 |

## Affected Snapshot Files

All files below are contaminated by pre-fix RP_MERGED hydration failure.
Do not use for training, promotion evidence, or Gate V2 qualification.

```
data/runner_snapshots_2026_05_20_2026_05_20_32cc27f9_1779275128551.jsonl
data/runner_snapshots_2026_05_20_2026_05_20_32cc27f9_1779275802075.jsonl
data/runner_snapshots_2026_05_20_2026_05_20_847964a6_1779359676175.jsonl
```

## Root Cause

Pre-a33c5bd scoring pipeline failed to hydrate forecast odds into canonical runner
odds before RP_MERGED source is used. When Racing API returns 401, the fallback to
RP_MERGED fired without populating per-runner odds, causing all runners to receive
identical score inputs. SQPE scored identically for all runners in 6 races.

Fix applied in commit a33c5bd: forecast odds hydrated into canonical runner odds
prior to RP_MERGED path; flatline diagnostics added; TS/pdf_intel wired earlier.

## Gate V1 Contamination

CPU Shadow Gate V1 triggered at n=538 runners on 2026-05-20.
Gate V1 is GATE_V1_AUDIT_ONLY — contaminated by pre-fix rows.
See: `data/reports/cpu_shadow_gate_v2_latest.json` for clean Gate V2 state.

## Preservation

All contaminated files are kept for forensic regression use.
- They verify that the flatline fix eliminated uniform scoring
- They serve as calibration anchors if new model pathologies emerge
- They must never be included in any training corpus, learning consume, or promotion evidence

## Operating Rules (permanent)

```
DO_NOT_TRAIN on any snapshot from 2026-05-20
DO_NOT_USE_FOR_PROMOTION — sigma SR=6.2%, not representative
DO_NOT_USE_FOR_GATE_V2_QUALIFICATION
KEEP_FOR_FORENSIC_REGRESSION — do not delete
```

## Sigma Audit Status

Sigma was run on 2026-05-20 results. The sigma_audits rows written on this date
are valid truth records (actual race outcomes) and are NOT quarantined.
Only the prediction-side snapshots and verdict quality are contaminated.
Raw result truth is always preserved in sigma_audits regardless of scoring quality.
