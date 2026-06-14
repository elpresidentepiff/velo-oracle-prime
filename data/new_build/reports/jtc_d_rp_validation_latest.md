# JTC-D Rolling Rebuild — Sidecar Validation Report
Generated: 2026-05-30

## Summary
| Item | Value |
|---|---|
| Data source | core_v0_historical_dataset.parquet (2015-2025) |
| Rolling window | 365 days (2024-07-05 to 2025-07-05) |
| Window rows | 118,087 |
| Bayesian prior | prior_n=20, global_sr=0.10 |
| New files | data/features/jtc_d_rp/ |
| Status | SHADOW_ONLY — leakage-free |

## Table Summary
| Table | Rows | Max Signal | Mean Signal |
|---|---|---|---|
| trainer_jockey | 23,629 | 0.3184 | 0.0133 |
| trainer_course | 17,378 | 0.2529 | 0.0175 |
| trainer_dist | 10,819 | 0.2452 | 0.0217 |
| jockey_course | 12,907 | 0.3084 | 0.0203 |
| jockey_dist | 8,115 | 0.2258 | 0.0239 |

## Leakage Analysis (CRITICAL FINDING)
| Model | AUC | Delta vs Base | Status |
|---|---|---|---|
| Challenger V1 base | 0.6958 | — | CHAMPION |
| V1 + OLD JTC-D (all-time cumulative) | 0.8370 | +0.1412 | LEAKAGE CONFIRMED |
| V1 + NEW JTC-D (365d rolling) | 0.7597 | +0.0639 | REAL SIGNAL |

### Interpretation
- Old JTC-D was inflated by all-time cumulative stats including future wins
- Leakage accounted for 0.0773 AUC — 55% of the apparent lift was fake
- New rolling JTC-D still adds genuine +0.0639 AUC over Challenger V1
- This is a strong real sidecar signal after leakage correction

## Coverage (held-out test set)
| Signal | OLD Coverage | NEW Coverage |
|---|---|---|
| tj_jtc_signal | 99.6% | 100.0% |
| tc_jtc_signal | 99.8% | 100.0% |
| td_jtc_signal | 96.3% | 100.0% |
| jc_jtc_signal | 99.9% | 100.0% |
| jd_jtc_signal | 96.3% | 100.0% |

## Top Signals (NEW 365d window)

### Top Trainer x Jockey
| Trainer | Jockey | Wins | Runs | SR | Signal |
|---|---|---|---|---|---|
| A P OBrien | Ryan Moore | 94 | 260 | 36.1% | 0.3184 |
| Charlie Appleby | William Buick | 77 | 231 | 33.3% | 0.2896 |
| F-H Graffard | Mickael Barzalona | 57 | 186 | 30.7% | 0.2586 |

### Top Jockey x Course
| Jockey | Course | Wins | Runs | SR | Signal |
|---|---|---|---|---|---|
| Ryan Moore | Curragh (IRE) | 38 | 85 | 44.7% | 0.3084 |
| Zac Purton | Sha Tin (HK) | 100 | 377 | 26.5% | 0.2440 |

## Next Steps
1. Run official sidecar tournament with NEW JTC-D paths for SR/Frame metrics
2. If SR/Frame passes threshold, consider Challenger V2 with JTC-D
3. CONSTRAINT: JTC-D must win solo before stacking with other sidecars

## Files Written
- `data/features/jtc_d_rp/trainer_jockey_profile.parquet`
- `data/features/jtc_d_rp/trainer_course_profile.parquet`
- `data/features/jtc_d_rp/trainer_dist_profile.parquet`
- `data/features/jtc_d_rp/jockey_course_profile.parquet`
- `data/features/jtc_d_rp/jockey_dist_profile.parquet`
- `data/new_build/reports/jtc_d_rp_build_latest.json`
- `data/new_build/reports/jtc_d_rolling_validation_latest.json`
- `scripts/ops/build_jtc_d_rolling.py`
- `scripts/ops/validate_jtc_d_rolling.py`
