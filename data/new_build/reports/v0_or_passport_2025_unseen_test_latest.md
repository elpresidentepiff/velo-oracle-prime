# V0_OR+Passport — 2025 Unseen Test
Generated: 2026-05-25T22:23:28.720266Z

## Test Set
- Date range: 2025-01-01 → 2025-07-05
- Races: 5,775
- Runners: 57,221
- Passport coverage: 100.0%

## Leakage Checks
- V0: PASS
- V0_OR: PASS
- Passport-only: PASS
- V0_OR+Passport: PASS
- RPR violations: 0

## Results
| Variant | AUC | AUC Δ vs V0_OR | Brier | SR | Frame | Races |
|---|---|---|---|---|---|---|
| V0 | 0.6745 | -0.0043 | 0.0871 | 22.0% | 51.2% | 5,775 |
| V0_OR **← champion** | 0.6788 | +0.0000 | 0.0869 | 22.2% | 51.5% | 5,775 |
| Passport-only | 0.6457 | -0.0331 | 0.0881 | 23.1% | 51.3% | 5,775 |
| V0_OR+Passport **← challenger** | 0.6922 | +0.0134 | 0.0862 | 24.2% | 54.0% | 5,775 |

## Promotion Gates (challenger vs champion)
| Gate | Result |
|---|---|
| auc | PASS |
| brier | PASS |
| sr | PASS |
| frame | PASS |

## Classification: **PASSPORT_CHALLENGER_PROMOTE**

| Class | Meaning |
|---|---|
| PASSPORT_CHALLENGER_PROMOTE | All 4 gates PASS — promote challenger to champion |
| PASSPORT_CHALLENGER_HOLD | 2–3 gates PASS — hold as challenger, gather more evidence |
| PASSPORT_CHALLENGER_RETRAIN_REQUIRED | 0–1 gates PASS — revisit feature set |

## Calibration (V0_OR champion, 2025 test)
| Prob band | n | Predicted | Actual WR | Over/Under |
|---|---|---|---|---|
| 0.00–0.05 | 8,465 | 0.036 | 0.033 | -0.003 |
| 0.05–0.10 | 24,900 | 0.075 | 0.071 | -0.004 |
| 0.10–0.15 | 14,207 | 0.122 | 0.121 | -0.001 |
| 0.15–0.20 | 5,860 | 0.171 | 0.177 | +0.006 |
| 0.20–0.25 | 2,221 | 0.221 | 0.224 | +0.003 |
| 0.25–0.30 | 856 | 0.270 | 0.259 | -0.011 |
| 0.30–0.40 | 561 | 0.339 | 0.348 | +0.009 |
| 0.40–1.01 | 151 | 0.481 | 0.510 | +0.029 |

## Calibration (V0_OR+Passport challenger, 2025 test)
| Prob band | n | Predicted | Actual WR | Over/Under |
|---|---|---|---|---|
| 0.00–0.05 | 10,467 | 0.033 | 0.032 | -0.001 |
| 0.05–0.10 | 23,735 | 0.074 | 0.072 | -0.002 |
| 0.10–0.15 | 13,416 | 0.122 | 0.123 | +0.001 |
| 0.15–0.20 | 5,610 | 0.171 | 0.176 | +0.005 |
| 0.20–0.25 | 2,232 | 0.221 | 0.225 | +0.004 |
| 0.25–0.30 | 874 | 0.272 | 0.301 | +0.029 |
| 0.30–0.40 | 629 | 0.338 | 0.348 | +0.011 |
| 0.40–1.01 | 258 | 0.477 | 0.484 | +0.008 |

## Field-Size Subgroup (V0_OR, 2025 test)
| Group | AUC | SR | Frame | Races |
|---|---|---|---|---|
| 8-11 runners | 0.6541 | 21.2% | 51.0% | 2,467 |
| <=7 runners | 0.6529 | 30.4% | 67.0% | 1,478 |
| 12-15 runners | 0.6473 | 18.1% | 42.1% | 1,477 |
| 16+ runners | 0.6179 | 12.2% | 28.9% | 353 |

## Going Subgroup (V0_OR, 2025 test)
| Group | AUC | SR | Frame | Races |
|---|---|---|---|---|
| Firm | 0.6775 | 22.5% | 51.2% | 4,601 |
| Good | 0.6829 | 20.9% | 52.6% | 1,174 |

## Passport Features Tested
- `pp_career_runs`
- `pp_win_rate`
- `pp_place_rate`
- `pp_days_since_last`
- `pp_layoff`
- `pp_avg_sp_last5`
- `pp_jockey_continuity`
- `pp_course_seen`
- `pp_or_change_3`
- `pp_class_moved_up`
- `pp_class_moved_down`

## Decision
Champion: **V0_OR** (AUC=0.6788, SR=22.2%, Frame=51.5%)
Challenger: **V0_OR+Passport** (AUC=0.6922, SR=24.2%, Frame=54.0%)
Δ AUC: +0.0134  Δ Brier: -0.0007  Δ SR: +1.9%  Δ Frame: +2.6%
Gates passed: 4/4
**PASSPORT_CHALLENGER_PROMOTE**