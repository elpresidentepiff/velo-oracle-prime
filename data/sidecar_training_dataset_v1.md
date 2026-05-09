# VÉLØ Sidecar Training Dataset v1
Generated: 2026-05-08 20:53

## Summary
Total rows: 11542
Winners: 1233 (10.7%)
Win baseline: 10.68%

## Time-Aware Split
| Split | Rows | % |
|---|---|---|
| train | 6654 | 57.7% |
| validation | 2724 | 23.6% |
| test | 2164 | 18.7% |

## Racing API Coverage
| Field | Coverage |
|---|---|
| trainer_course_win_pct (from full_analysis) | 1143/11542 (9.9%) |
| trainer_dist_win_pct (from full_analysis) | 475/11542 (4.1%) |
| jockey_course_win_pct (from Supabase) | 11326/11542 (98.1%) |
| jockey_dist_win_pct (from Supabase) | 11325/11542 (98.1%) |
| trainer_jockey_win_pct | 8343/11542 (72.3%) |
| jockey_trainer_win_pct | 11517/11542 (99.8%) |
| rpdc_score | 9264/11542 (80.3%) |
| sigma_outcome | 828/11542 (7.2%) |

## Ensemble Score Coverage
| Field | Coverage |
|---|---|
| velo_prime_prob | 11542/11542 (100.0%) |
| sqpe_v17_prob | 11542/11542 (100.0%) |
| improvement_score | 11374/11542 (98.5%) |
| market_deception_score | 11374/11542 (98.5%) |
| place_prob | 11374/11542 (98.5%) |

## Notes
- Jockey course lookups require course_id — races table stores course name only.
  Run `scripts/refresh_racing_api_stat_cache.py --full-refresh` to build local SQLite
  cache for faster lookups once course_id mapping is established.
- Trainer stats extracted directly from velo_verdicts.full_analysis (already embedded).
- Jockey stats fetched from Supabase Racing API tables (jockey_id × dist_f match).
- dist_f matching uses 'Xf' string format — verify against Racing API table values.
- DO NOT use this dataset for live VP weight changes without evidence gate passage.
- TIER: DATA_AVAILABLE → CALIBRATION_TEST only. No live scoring effect.