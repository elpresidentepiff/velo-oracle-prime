# International Feature Contract V1

**Date:** 2026-05-23  
**Status:** DESIGN — governs feature engineering for all international packs  
**Classification:** Engineering contract — must be referenced before any model training

---

## Purpose

This document defines which features are mandatory, optional, unavailable, or banned for each international jurisdiction pack. It prevents silent feature leakage and ensures jurisdiction-appropriate models.

---

## HK_SHA_TIN_V1 and HK_HAPPY_VALLEY_V1

### Mandatory Features
| Feature | Source | Notes |
|---|---|---|
| `rpr_vs_field` | Parquet / racecards | Primary rating signal. Corr=0.326 confirmed. |
| `rpr_num` | Parquet / racecards | Absolute RPR value. 97-99% coverage. |
| `or_num` | Parquet / racecards | HK rating 0-140 scale. 97-100% coverage. |
| `or_vs_field` | Computed | Relative HK rating vs field. |
| `field_size` | Parquet | Number of runners. |
| `dist_f` | Parquet | Distance in furlongs (convert from metres). |
| `draw_num` | Parquet | Draw position. Critical at Sha Tin. |
| `class_num` | Parquet | HK Class 1-5. Essential race context. |

### Optional Features (include if coverage > 20%)
| Feature | Coverage | Notes |
|---|---|---|
| `draw_pct` | Good | Draw as % of field — normalised draw signal |
| `age_num` | Good | Horse age |
| `wgt_lbs` | Good | Weight carried |
| `going_code` | Good | Going condition — standard UK scale applies |
| `runs_since_win` | Good | Form cycle |
| `runs_since_place` | Good | Form cycle |
| `mark_compression_score` | 86% | HK OR compression signal |
| `course_fit_score` | Good | Track specialist signal |
| `going_fit_score` | Good | Going preference match |
| `distance_fit_score` | Good | Distance preference match |
| `trainer_timing_score` | Partial | Use HK-specific trainer data only |
| `is_aw` | Low | HK has some polytrack — binary flag |

### New Features to Build (Phase 2)
| Feature | Status | Notes |
|---|---|---|
| `class_trajectory` | NOT IN PARQUET | Compute: delta of class_num over last 4 runs. Build from hk_horse_history. |
| `griffin_flag` | NOT IN PARQUET | Binary: horse in debut HK season. No race history available. |
| `barrier_trial_rpr` | NOT IN PARQUET | For Griffin horses only. From HKJC barrier trial results. |
| `sectional_pace_rank_400m` | NOT IN PARQUET | Pace position at 400m. From HKJC official sectionals. |
| `draw_bias_adjusted` | NOT IN PARQUET | Draw win% for (course, distance, draw) from hk_draw_stats. |
| `benter_market_prior` | NOT IN PARQUET | 1/tote_odds as market probability. From HKJC tote pool. |

### Unavailable Features
| Feature | Reason |
|---|---|
| `ts_num` | **0.0% coverage in HK — DROP entirely** |
| `valeur_rating` | French rating system — does not exist in HK |
| `penetrometer_going` | French going system — does not exist in HK |

### Banned / Leakage Risk
| Feature | Risk | Action |
|---|---|---|
| `sp_dec` | Post-race SP — not available pre-race | EXCLUDE |
| `log_sp` | Derived from SP | EXCLUDE |
| `implied_prob` | Derived from SP | EXCLUDE |
| `sp_rank` | Derived from SP | EXCLUDE |
| `is_fav` | Derived from market odds at race time | EXCLUDE from training features |
| `odds_resilience_score` | Odds movement — potential leakage | EXCLUDE unless confirmed pre-race |
| `odds_contraction_score` | Odds movement | EXCLUDE unless confirmed pre-race |

### UK Features Not Transferable
| Feature | UK Meaning | HK Issue |
|---|---|---|
| `mark_compression_score` | UK OR handicap mark delta | HK uses different rating management — partially usable |
| `trainer_timing_score` | UK trainer seasonal patterns | UK trainer patterns do not transfer to HK licensed trainers |
| `release_window_score` | UK mark compression cycle | Partially applicable to HK handicaps only |

---

## FR_FLAT_CORE (Chantilly, Deauville, Longchamp, Saint-Cloud)

### Mandatory Features
| Feature | Source | Notes |
|---|---|---|
| `rpr_vs_field` | Parquet / racecards | **Primary rating. RPR is the only cross-jurisdiction rating available.** |
| `rpr_num` | Parquet | 90-95% coverage. Primary rating. |
| `field_size` | Parquet | Number of runners. |
| `dist_f` | Parquet | Distance in furlongs. |

### Optional Features
| Feature | Coverage | Notes |
|---|---|---|
| `ts_num` | 51-88% (course-dependent) | TS available at Deauville/Longchamp/Saint-Cloud. Include when coverage >50%. |
| `going_code` | Good | Text going code. Needs penetrometer mapping for accuracy. |
| `age_num` | Good | Horse age |
| `wgt_lbs` | Good | Weight carried |
| `draw_num` | Good | Draw — less deterministic than HK but still informative |
| `class_num` | Variable | FR race classification maps to class_num — verify coverage |
| `runs_since_win` | Good | Form cycle |
| `runs_since_place` | Good | Form cycle |
| `course_fit_score` | Good | Course specialist signal |
| `going_fit_score` | Good | Going preference — enhanced by penetrometer mapping |
| `distance_fit_score` | Good | Distance preference |
| `trainer_timing_score` | Partial | Use FR-specific trainer data only — UK trainer patterns don't transfer |

### New Features to Build (Phase 2)
| Feature | Status | Notes |
|---|---|---|
| `going_penetrometer` | NOT IN PARQUET | Map from PMU API terrain field. Critical for FR going signal. |
| `quintet_plus_flag` | NOT IN PARQUET | Binary: highest-quality race. From PMU programme. |
| `valeur_rating` | NOT IN PARQUET | France Galop rating (20-62 scale). Phase 3 addition. |
| `pmu_morning_odds` | NOT IN PARQUET | Pre-race pool odds. Non-leakage if captured before race. |
| `fr_class_tier` | NOT IN PARQUET | Map race type to tier: G1=1, G2=2, G3=3, Listed=4, Conditions=5, Handicap=6, Claiming=7 |

### Unavailable Features
| Feature | Reason |
|---|---|
| `or_num` | **0.0% coverage in France — DROP entirely** |
| `or_vs_field` | **0.0% coverage in France — DROP entirely** |
| `mark_compression_score` | Requires OR history — inapplicable to French-trained horses |
| `curr_or_minus_best_or` | Requires OR — inapplicable |
| `curr_or_minus_last_win_or` | Requires OR — inapplicable |

### Banned / Leakage Risk
Same as HK: exclude `sp_dec`, `log_sp`, `implied_prob`, `sp_rank`, `is_fav`, `odds_resilience_score`, `odds_contraction_score`

### UK Features Not Transferable
| Feature | Issue |
|---|---|
| `mark_compression_score` | Requires UK OR — 0% in France. Do not use. |
| `release_window_score` | Requires UK OR mark cycle — inapplicable |
| `handicap_plot_score` | UK-specific |
| `trainer_timing_score` | UK trainer seasonal patterns — French trainer patterns differ entirely |

---

## FR_AUTEUIL_JUMPS_V1

### Critical Difference from FR Flat
Auteuil is 97% jump racing (Hurdle 64.9%, Chase 35.0%). Feature importance is different:
- **Jumping ability** is the primary signal — not captured in the current feature set
- **RPR for jumps** correlates at 0.3943 (highest of all venues) — strong signal
- **TS is 0%** — jumps horses get no TS rating

### Mandatory Features
| Feature | Notes |
|---|---|
| `rpr_vs_field` | Primary signal. Strongest cross-venue correlation. |
| `rpr_num` | 71.7% coverage — some gaps for unrated horses |
| `field_size` | |
| `dist_f` | Chase distances differ from flat — important context |

### Banned Features  
Same as FR flat PLUS:
- `ts_num`: 0% coverage — EXCLUDE
- `or_num` / `or_vs_field`: 0% coverage — EXCLUDE

### Known Gap
Jump-specific features not in parquet: jump error rate, jumping fluency, national hunt form. These would significantly improve the Auteuil model. Phase 2 investigation required.

### Verdict
Auteuil has stronger RPR signal than any other venue (0.3943 correlation) but fewer available features. A model trained without jump-specific features may underperform relative to the RPR correlation potential.

---

## Cross-Jurisdiction Rules (All Packs)

```
1. Never transfer UK trainer profiles to FR or HK models
2. Never use UK OR as a feature in France
3. Never use TS in HK or Auteuil (0% coverage)
4. Never use SP-derived features as training features (sp_dec, log_sp, implied_prob, sp_rank)
5. Never pool Sha Tin and Happy Valley evidence in the same gate
6. Never pool FR flat and Auteuil (jumps) in the same model
7. Always apply temporal split — never random split (prevents future leakage)
8. Always validate VP band monotonicity before claiming a model is viable
9. Mark_compression_score in France requires OR — confirm zero or rework before use
10. RPR is the only reliable cross-jurisdiction signal
```
