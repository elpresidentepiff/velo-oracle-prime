# Challenger V1 Promotion Review
Generated: 2026-05-28T19:31:24.248799

## Verdict: `PROMOTE_CHALLENGER_V1`

| Metric | Core V0_OR | Challenger F | Lift |
|---|---|---|---|
| Test AUC   | 0.6769 | 0.6969 | +0.0200 |
| Test SR    | 0.2232 | 0.2502 | +0.0270 |
| Test Frame | 0.5113 | 0.5498 | — |
| Val AUC    | 0.6768 | 0.6945 | — |

## Task 1 — Full Ablation Table
| variant            |   val_AUC |   val_SR |   val_Frame |   test_AUC |   test_SR |   test_Frame |   test_AUC_lift |   test_SR_lift |
|:-------------------|----------:|---------:|------------:|-----------:|----------:|-------------:|----------------:|---------------:|
| A: Core V0_OR      |    0.6768 |   0.2173 |      0.5069 |     0.6769 |    0.2232 |       0.5113 |          0      |         0      |
| B: Passport-only   |    0.6442 |   0.2124 |      0.5017 |     0.6448 |    0.2274 |       0.5117 |         -0.0321 |         0.0042 |
| C: Intent-only     |    0.6329 |   0.2051 |      0.4928 |     0.643  |    0.2244 |       0.5049 |         -0.0339 |         0.0012 |
| D: Core + Passport |    0.6895 |   0.2298 |      0.5283 |     0.6903 |    0.2419 |       0.5385 |          0.0134 |         0.0187 |
| E: Core + Intent   |    0.6864 |   0.2256 |      0.5228 |     0.6906 |    0.2397 |       0.5385 |          0.0137 |         0.0165 |
| F: All Combined    |    0.6945 |   0.2363 |      0.5383 |     0.6969 |    0.2502 |       0.5498 |          0.02   |         0.027  |

## Task 2 — Intent Null Audit
| feature                   |   null_train_% |   null_val_% |   null_test_% | null_class   | zero_fill_valid   | fix_required   |
|:--------------------------|---------------:|-------------:|--------------:|:-------------|:------------------|:---------------|
| mark_compression_score    |              0 |            0 |             0 | conditional  | True              | no             |
| curr_or_minus_last_win_or |              0 |            0 |             0 | conditional  | True              | no             |
| curr_or_minus_best_or     |              0 |            0 |             0 | conditional  | True              | no             |
| runs_since_win            |              0 |            0 |             0 | conditional  | True              | no             |
| runs_since_place          |              0 |            0 |             0 | conditional  | True              | no             |
| runs_since_mkt_support    |              0 |            0 |             0 | conditional  | True              | no             |
| odds_resilience_score     |              0 |            0 |             0 | conditional  | True              | no             |
| intent_trip_match         |              0 |            0 |             0 | conditional  | True              | no             |
| intent_course_win_history |              0 |            0 |             0 | computable   | True              | no             |
| intent_going_match        |              0 |            0 |             0 | conditional  | True              | no             |
| intent_class_drop_vs_best |              0 |            0 |             0 | conditional  | True              | no             |
| intent_run_after_break    |              0 |            0 |             0 | conditional  | True              | no             |
| intent_sp_shortening      |              0 |            0 |             0 | conditional  | True              | no             |
| intent_wins_last10        |              0 |            0 |             0 | conditional  | True              | no             |
| intent_top3_last6         |              0 |            0 |             0 | conditional  | True              | no             |

**High-null intent features (>60% null in val):** []

### Passport Null Summary
|                      |   null_train_% |   null_val_% |   null_test_% |
|:---------------------|---------------:|-------------:|--------------:|
| pp_career_runs       |              0 |            0 |             0 |
| pp_win_rate          |              0 |            0 |             0 |
| pp_place_rate        |              0 |            0 |             0 |
| pp_days_since_last   |              0 |            0 |             0 |
| pp_layoff            |              0 |            0 |             0 |
| pp_avg_sp_last5      |              0 |            0 |             0 |
| pp_jockey_continuity |              0 |            0 |             0 |
| pp_course_seen       |              0 |            0 |             0 |
| pp_or_change_3       |              0 |            0 |             0 |
| pp_class_moved_up    |              0 |            0 |             0 |
| pp_class_moved_down  |              0 |            0 |             0 |

## Task 3 — Feature Contribution (Challenger F)
Layer importance: **core=48.3%  passport=26.2%  intent=25.5%**

### Top 20 Features
| feature                   | layer    |   importance_pct |
|:--------------------------|:---------|-----------------:|
| or_vs_field               | core     |             8.62 |
| pp_avg_sp_last5           | passport |             8.11 |
| official_rating           | core     |             7.19 |
| pp_days_since_last        | passport |             6.55 |
| wgt_lbs                   | core     |             5.71 |
| field_size                | core     |             5.43 |
| odds_resilience_score     | intent   |             4.36 |
| pp_career_runs            | passport |             4.22 |
| pp_place_rate             | passport |             3.49 |
| mark_compression_score    | intent   |             3.38 |
| age_num                   | core     |             3.12 |
| going_fit_score           | core     |             2.99 |
| quiet_run_score           | core     |             2.95 |
| curr_or_minus_last_win_or | intent   |             2.8  |
| runs_since_place          | intent   |             2.58 |
| draw_pct                  | core     |             2.54 |
| intent_run_after_break    | intent   |             2.31 |
| trainer_timing_score      | core     |             2.08 |
| distance_fit_score        | core     |             2.04 |
| pp_or_change_3            | passport |             1.86 |

## Task 4 — Segment Stability (Core vs Full, Test Set)

### year
| Segment | n | Core SR | Full SR | SR Lift | Core Frame | Full Frame |
|---|---|---|---|---|---|---|
| 2025 | 57221 | 0.2232 | 0.2502 | 0.027 | 0.5113 | 0.5498 |

### aw_vs_turf
| Segment | n | Core SR | Full SR | SR Lift | Core Frame | Full Frame |
|---|---|---|---|---|---|---|
| 0 | 37484 | 0.2192 | 0.2425 | 0.0233 | 0.5003 | 0.5393 |
| 1 | 19737 | 0.2303 | 0.2638 | 0.0335 | 0.5309 | 0.5682 |

### dist_band
| Segment | n | Core SR | Full SR | SR Lift | Core Frame | Full Frame |
|---|---|---|---|---|---|---|
| 11-14f | 9405 | 0.2188 | 0.2692 | 0.0504 | 0.5292 | 0.5746 |
| 7-8f | 20057 | 0.2227 | 0.2442 | 0.0215 | 0.5192 | 0.5545 |
| 9-10f | 18231 | 0.2287 | 0.2522 | 0.0235 | 0.4865 | 0.5331 |
| sprint(<6f) | 7366 | 0.195 | 0.225 | 0.03 | 0.505 | 0.5363 |
| staying(14f+) | 2162 | 0.296 | 0.288 | -0.008 | 0.576 | 0.576 |

### field_band
| Segment | n | Core SR | Full SR | SR Lift | Core Frame | Full Frame |
|---|---|---|---|---|---|---|
| big(15+) | 14600 | 0.1411 | 0.1811 | 0.04 | 0.3526 | 0.3884 |
| large(11-14) | 21936 | 0.2029 | 0.2322 | 0.0293 | 0.4494 | 0.5003 |
| medium(6-10) | 18721 | 0.247 | 0.2715 | 0.0245 | 0.5717 | 0.6084 |
| small(<6) | 1964 | 0.3613 | 0.3636 | 0.0023 | 0.7995 | 0.7972 |

### or_band
| Segment | n | Core SR | Full SR | SR Lift | Core Frame | Full Frame |
|---|---|---|---|---|---|---|
| low(<70) | 20114 | 0.1813 | 0.2035 | 0.0222 | 0.4063 | 0.4282 |
| mid(70-89) | 10870 | 0.1947 | 0.2065 | 0.0118 | 0.3927 | 0.4126 |
| unrated | 22435 | 0.2196 | 0.2367 | 0.0171 | 0.4647 | 0.4977 |
| upper(90+) | 3802 | 0.2366 | 0.2507 | 0.0141 | 0.4239 | 0.4408 |

## Governance
- `rpr_violation`: False
- `sp_violation`: False
- `new_build_only`: True
- `old_live_velo_impact`: False

## Verdict Rationale
- Test AUC lift is positive and material
- Intent nulls are conditional (meaningful absence, zero-fill valid)
- Segment stability shows consistent lift across key dimensions
- Operator approval required before production deployment