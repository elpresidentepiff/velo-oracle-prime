# Improvement Feature Assembler — 2026-05-25

**Generated:** 2026-05-24T18:34:17.735322+00:00  
**Runner source:** snapshot:runner_snapshots_2026_05_24_2026_05_24_932096b7_1779620153700.jsonl  
**Racecard source:** racecard_proxy:racecards_2026_05_17_standard.json  

> **WARNING — Path C uses cross-date racecard proxy.** OFR/RPR/age values are from a different scoring day. This demonstrates what variance WOULD look like with real racecard data, not actual May25 values.

---

## Verdict: `PARTIAL_RESTORE_POSSIBLE_LOW_COVERAGE`

> Path C kills switch does not fire but racecard match rate is 0.8% (low).

## Path Comparison

| Path | Description | Features restored | Kill switch | Score range | Mean |
|---|---|---|---|---|---|
| A (current) | DEFAULTS only | 0 | FIRES | 0.0 | 0.0872 |
| B (RPDC) | + curr_or_minus_last_win_or | 1 | OK | 0.0161 | 0.0872 |
| C+RPDC (racecard) | + or_vs_field, rpr_vs_field, age_num | 4 | OK | 0.0443 | 0.0871 |

## Coverage

| Source | Matched | Rate |
|---|---|---|
| RPDC memory (JSONL) | 151 | 62.7% |
| Standard racecard (OFR/RPR/age) | 2 | 0.8% |

## Feature at-default rates (100% = all runners at neutral default)

| Feature | Default | Path A | Path B | Path C+RPDC |
|---|---|---|---|---|
| `mark_compression_score` | 0.0 | 100.0% | 100.0% | 100.0% |
| `curr_or_minus_best_or` | 0.0 | 100.0% | 100.0% | 100.0% |
| `curr_or_minus_last_win_or` | 0.0 | 100.0% | 95.0% | 95.0% |
| `release_window_score` | 0.0 | 100.0% | 100.0% | 100.0% |
| `runs_since_win` | 5.0 | 100.0% | 100.0% | 100.0% |
| `runs_since_place` | 2.0 | 100.0% | 100.0% | 100.0% |
| `trainer_timing_score` | 0.12 | 100.0% | 100.0% | 100.0% |
| `distance_fit_score` | 0.33 | 100.0% | 100.0% | 100.0% |
| `course_fit_score` | 0.33 | 100.0% | 100.0% | 100.0% |
| `or_vs_field` | 0.0 | 100.0% | 100.0% | 99.6% |
| `rpr_vs_field` | 0.0 | 100.0% | 100.0% | 99.6% |
| `age_num` | 0.0 | 100.0% | 100.0% | 99.6% |

```
AUDIT_DATE:          2026-05-25
RACECARD_PROXY:      True
RPDC_MATCH_RATE:     62.7%
RACECARD_MATCH_RATE: 0.8%
PATH_A_KILL_SWITCH:  True
PATH_B_KILL_SWITCH:  False
PATH_C_KILL_SWITCH:  False
VERDICT:             PARTIAL_RESTORE_POSSIBLE_LOW_COVERAGE
SUPABASE_WRITES:     NONE
SCORING_CHANGE:      NONE
```