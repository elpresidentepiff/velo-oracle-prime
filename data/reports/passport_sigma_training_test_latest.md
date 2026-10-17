# Passport + Sigma Training Test
Generated: 2026-10-17T02:26:50.232651+00:00

## Sigma Selector
- Status: PASS
- Rows: 3049
- Test races: 760
- Baseline AUC: 0.5890443213296399
- Selector AUC: 0.7725761772853186
- Baseline top-1: 0.25
- Selector top-1: 0.25
- Staging model: /mnt/c/Users/puror/velo-oracle-prime/models/sigma_selector_staging/sigma_selector.pkl

### Acceptance Bands
| Ranker | Accept top % | n | SR | ROI/pt | P&L | Avg SP |
|---|---:|---:|---:|---:|---:|---:|
| baseline_model_probability | 10 | 76 | 0.3947 | -0.2120 | -16.1100 | 4.0858 |
| baseline_model_probability | 20 | 152 | 0.3487 | -0.2597 | -39.4800 | 4.1292 |
| baseline_model_probability | 30 | 228 | 0.3114 | -0.3130 | -71.3600 | 4.5136 |
| baseline_model_probability | 50 | 380 | 0.2974 | -0.2413 | -91.7100 | 5.4996 |
| sigma_selector | 10 | 76 | 0.6711 | 0.0138 | 1.0500 | 1.5333 |
| sigma_selector | 20 | 152 | 0.5526 | -0.0409 | -6.2200 | 1.8051 |
| sigma_selector | 30 | 228 | 0.4825 | -0.0557 | -12.6900 | 2.1082 |
| sigma_selector | 50 | 380 | 0.4026 | -0.0251 | -9.5500 | 2.7317 |

## Passport vs RP Files
- Status: PASS
- Train rows: 631099
- Test rows: 30492
- Test races: 3691

| Model | Features | AUC | LogLoss | Top-1 | MRR |
|---|---:|---:|---:|---:|---:|
| RP_SAFE_FILES_ONLY | 25 | 0.6983 | 0.3414 | 0.2652 | 0.4807 |
| RP_CORE_NO_RPR_NO_MARKET | 17 | 0.6870 | 0.3450 | 0.2482 | 0.4651 |
| RP_DOCTRINE_NO_RATINGS_NO_MARKET | 23 | 0.6916 | 0.3438 | 0.2604 | 0.4770 |
| PASSPORT_ONLY | 11 | 0.6362 | 0.3560 | 0.2471 | 0.4620 |
| RP_CORE_PLUS_PASSPORT | 28 | 0.6989 | 0.3413 | 0.2609 | 0.4798 |
| RP_DOCTRINE_PLUS_PASSPORT | 34 | 0.7018 | 0.3406 | 0.2690 | 0.4848 |

- Best by top-1: RP_DOCTRINE_PLUS_PASSPORT
- Passport-only gap vs RP core top-1: -0.0011
- Passport-only gap vs RP core AUC: -0.0508
- RP core + passport top-1 lift vs RP core: 0.0127
- RP core + passport AUC lift vs RP core: 0.0119
- Doctrine + passport top-1 lift vs doctrine: 0.0086
- Doctrine + passport AUC lift vs doctrine: 0.0102
- Banned RPR/market features used: []

### Top Feature Importance
#### RP_SAFE_FILES_ONLY
- field_size: 0.016286
- runs_since_place: 0.008397
- or_vs_field: 0.007074
- or_num: 0.005005
- class_num: 0.004633
- quiet_run_score: 0.004482
- age_num: 0.001211
- wgt_lbs: 0.001069
#### RP_CORE_NO_RPR_NO_MARKET
- field_size: 0.018672
- or_vs_field: 0.007378
- quiet_run_score: 0.006404
- distance_fit_score: 0.002309
- going_fit_score: 0.00209
- age_num: 0.001318
- wgt_lbs: 0.001
- trainer_timing_score: 0.000751
#### RP_DOCTRINE_NO_RATINGS_NO_MARKET
- field_size: 0.015532
- runs_since_place: 0.008266
- quiet_run_score: 0.004809
- class_num: 0.003969
- wgt_lbs: 0.002927
- age_num: 0.001282
- trainer_timing_score: 0.000996
- mark_compression_score: 0.000972
#### PASSPORT_ONLY
- pp_avg_sp_last5: 0.009123
- pp_place_rate: 0.004764
- pp_days_since_last: 0.003906
- pp_class_moved_up: 0.001283
- pp_career_runs: 0.001124
- pp_class_moved_down: 0.000725
- pp_win_rate: 0.000709
- pp_jockey_continuity: 0.000632
#### RP_CORE_PLUS_PASSPORT
- field_size: 0.017355
- or_vs_field: 0.005564
- quiet_run_score: 0.00541
- pp_avg_sp_last5: 0.005182
- pp_days_since_last: 0.002118
- pp_place_rate: 0.001303
- pp_class_moved_up: 0.000738
- going_fit_score: 0.000621
#### RP_DOCTRINE_PLUS_PASSPORT
- field_size: 0.014318
- pp_avg_sp_last5: 0.006719
- runs_since_place: 0.005988
- quiet_run_score: 0.003537
- class_num: 0.002148
- pp_days_since_last: 0.001847
- wgt_lbs: 0.000915
- pp_class_moved_up: 0.000613

## Verdict
PASSPORT_HELPFUL_SHADOW_ONLY | SIGMA_SELECTOR_HAS_SIGNAL
