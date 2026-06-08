# Improvement Restored Scoring Comparison — 2026-05-24

**Generated:** 2026-05-24T21:25:37.092290+00:00  
**Runner source:** snapshot:runner_snapshots_2026_05_24_2026_05_24_932096b7_1779620153700.jsonl  


**NOTE:** Path C uses cross-date racecard proxy (racecards_2026_05_17_standard.json). OFR/RPR/age are from a different day — demonstrative only.  

---

## May25 Gate: `PARTIAL_FORMULA_RPDC`

> RPDC injection restores improvement_score variance. Racecard OFR/RPR/age still needed for full restore.

## Path Comparison

| Path | Description | Kill switch | Score range | VP delta max | Tier changes |
|---|---|---|---|---|---|
| A (current) | DEFAULTS only | FIRES | 0.0000 | — | — |
| B (RPDC) | + curr_or_minus_last_win_or | OK | 0.0161 | 0.0006 | 0 |
| C (racecard+RPDC) | + or/rpr/age (proxy) | OK | 0.0443 | 0.0006 | 0 |

## RPDC Coverage

| Metric | Value |
|---|---|
| Runners | 241 |
| RPDC matched | 151 (62.7%) |
| Racecard matched | 2 (0.8%) |

## Path Verdicts

| Path | Verdict |
|---|---|
| A | KILL_SWITCH_FIRES — current state |
| B | PARTIAL_RESTORE_ONLY — variance present, kill switch defeated |
| C | PARTIAL_RESTORE_ONLY — variance present, kill switch defeated |

```
AUDIT_DATE:          2026-05-24
IMPROVEMENT_WEIGHT:  0.12
PATH_A_KILL_SWITCH:  True
PATH_B_KILL_SWITCH:  False
PATH_C_KILL_SWITCH:  False
PATH_B_RANGE:        0.0161
PATH_C_RANGE:        0.0443
TIER_CHANGES_B:      0
TIER_CHANGES_C:      0
MAY25_GATE:          PARTIAL_FORMULA_RPDC
SUPABASE_MUTATED:    False
SCORING_CHANGED:     False
FORMULA_CHANGED:     False
MODEL_CHANGED:       False
```