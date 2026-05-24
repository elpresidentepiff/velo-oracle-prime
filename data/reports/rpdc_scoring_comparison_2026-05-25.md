# RPDC Scoring Comparison — 2026-05-25

**Generated:** 2026-05-24T18:06:04.618279+00:00  
**Data source:** snapshot:runner_snapshots_2026_05_24_2026_05_24_932096b7_1779620153700.jsonl  

**NOTE:** Using 2026-05-24 as proxy — 2026-05-25 card not yet available  

---

## Formula Status: `FEATURE_DEGRADED`

> improvement_score = 0.0872 (constant) → excluded by zero-variance kill switch. Active components: ['market_deception_score', 'sqpe_v17'].

## Path A vs Path B

| Metric | Path A (current) | Path B (RPDC bridge) |
|---|---|---|
| improvement_score constant | True | True |
| Zero-variance kill switch fires | True | True |
| Active components | ['market_deception_score', 'sqpe_v17'] | ['market_deception_score', 'sqpe_v17'] |
| Scoring changed | — | NO — read-only annotation |
| Tier distribution | {'A': 9, 'B': 135, 'X': 74, 'C': 23} | (identical) |

## RPDC Annotation Coverage (Path B adds)

| Metric | Value |
|---|---|
| Runners matched to RPDC memory | 151 (62.7%) |
| Runners with RPDC tags | 104 |
| Cash window runners | 34 |

## Comparison Result

| Metric | Result |
|---|---|
| Scoring identical | True |
| Tier changes | 0 |
| A-tier changes | 0 |
| Top horse changes | 0 |
| Probability deltas | NONE — RPDC Option B is read-only annotation, no scoring formula change |

## May 25 Classification

**`FEATURE_DEGRADED`**

> improvement_score excluded (constant). RPDC local memory provides annotation context only. Improvement variance requires pipeline change to inject racecard features (or_vs_field, rpr_vs_field, age_num).

```
AUDIT_DATE:          2026-05-25
IS_PROXY:            True
FORMULA_STATUS:      FEATURE_DEGRADED
SCORING_IDENTICAL:   True
IMPROVEMENT_CONST:   True
KILL_SWITCH:         True
SUPABASE_WRITES:     NONE
SCORING_CHANGE:      NONE
MODEL_CHANGE:        NONE
```