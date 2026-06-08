# 4-Way Ablation — V0 / V0_OR / Passport-only / V0_OR+Passport
Generated: 2026-05-25T22:18:08.669576Z

## Results
| Variant | Features | AUC | AUC Δ vs V0_OR | SR | Frame | Races |
|---|---|---|---|---|---|---|
| V0 | 17 | 0.6735 | -0.0042 | 21.8% | 50.3% | 11,650 |
| V0_OR **← champion** | 19 | 0.6777 | +0.0000 | 21.9% | 50.8% | 11,650 |
| Passport-only | 11 | 0.6441 | -0.0336 | 21.4% | 50.2% | 11,650 |
| V0_OR+Passport | 30 | 0.6901 | +0.0124 | 22.5% | 52.8% | 11,650 |

## Passport Verdict: **PASSPORT_ADDS_SIGNAL**

V0_OR+Passport vs V0_OR champion:
- AUC delta: +0.0124
- SR delta: +0.6%

## Passport Features Used
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

## Verdicts
| Classification | Meaning |
|---|---|
| PASSPORT_ADDS_SIGNAL | AUC delta > +0.003 vs champion — passport is worth adding |
| PASSPORT_MARGINAL | AUC delta 0–0.003 — small lift, costs feature complexity |
| PASSPORT_NEUTRAL | AUC within ±0.002 — no meaningful change |
| PASSPORT_HURTS | AUC drops > 0.002 — passport adds noise |
| PASSPORT_INSUFFICIENT_COVERAGE | < 5% passport coverage in training set |