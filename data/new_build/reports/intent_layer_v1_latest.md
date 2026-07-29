# Intent Layer V1 — Ablation vs Champion
Generated: 2026-07-06T11:18:04.921480Z

## Test Set
- 2025 unseen: 2025-01-01 → 2025-07-05
- Races: 5,775 | Runners: 57,221
- Intent feature coverage: 56.5%

## Results
| Variant | AUC | AUC Δ | Brier | SR | Frame | Races |
|---|---|---|---|---|---|---|
| Champion **← champion** | 0.6922 | +0.0000 | 0.0862 | 24.2% | 54.0% | 5,775 |
| Intent-only | 0.6546 | -0.0376 | 0.0878 | 23.6% | 52.6% | 5,775 |
| Champion+Intent **← challenger** | 0.6992 | +0.0070 | 0.0858 | 25.5% | 55.6% | 5,775 |

## Promotion Gates
| Gate | Result |
|---|---|
| auc | PASS |
| brier | PASS |
| sr | PASS |
| frame | PASS |

## Verdict: **INTENT_ADDS_SIGNAL** (4/4 gates)

Δ AUC: +0.0070  Δ Brier: -0.0004  Δ SR: +1.4%  Δ Frame: +1.6%

## Intent Features Used
(15 features, 24.1% of combo model importance)

| Feature | Coverage | Combo Importance % |
|---|---|---|
| `mark_compression_score` | 54.5% | 3.4% |
| `curr_or_minus_last_win_or` | 33.9% | 2.2% |
| `curr_or_minus_best_or` | 54.5% | 1.7% |
| `runs_since_win` | 50.1% | 1.6% |
| `runs_since_place` | 69.7% | 1.9% |
| `runs_since_mkt_support` | 38.2% | 1.5% |
| `odds_resilience_score` | 79.6% | 4.4% |
| `intent_trip_match` | 49.2% | 0.4% |
| `intent_course_win_history` | 100.0% | 1.1% |
| `intent_going_match` | 50.1% | 0.3% |
| `intent_class_drop_vs_best` | 31.3% | 0.9% |
| `intent_run_after_break` | 65.1% | 1.8% |
| `intent_sp_shortening` | 71.7% | 0.7% |
| `intent_wins_last10` | 71.9% | 1.3% |
| `intent_top3_last6` | 79.6% | 0.9% |

## Top 15 Features (Champion+Intent combo)
| Rank | Feature | Importance % |
|---|---|---|
| 1 | `or_vs_field` | 8.5% |
| 2 | `pp_avg_sp_last5` | 7.4% |
| 3 | `official_rating` | 6.9% |
| 4 | `pp_days_since_last` | 6.7% |
| 5 | `wgt_lbs` | 5.5% |
| 6 | `field_size` | 5.0% |
| 7 | `odds_resilience_score` | 4.4% |
| 8 | `pp_career_runs` | 3.8% |
| 9 | `mark_compression_score` | 3.4% |
| 10 | `draw_pct` | 3.4% |
| 11 | `age_num` | 3.3% |
| 12 | `pp_place_rate` | 3.0% |
| 13 | `going_fit_score` | 2.8% |
| 14 | `distance_fit_score` | 2.7% |
| 15 | `quiet_run_score` | 2.6% |