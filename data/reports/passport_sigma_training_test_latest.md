# Passport + Sigma Training Test
Generated: 2026-06-19T23:09:26.636478+00:00

## Sigma Selector
- Status: PASS
- Rows: 1105
- Test races: 274
- Baseline AUC: 0.5872034747744738
- Selector AUC: 0.7657200133645172
- Baseline top-1: 0.2664
- Selector top-1: 0.2664
- Staging model: C:\Users\puror\velo-oracle-prime\models\sigma_selector_staging\sigma_selector.pkl

### Acceptance Bands
| Ranker | Accept top % | n | SR | ROI/pt | P&L | Avg SP |
|---|---:|---:|---:|---:|---:|---:|
| baseline_model_probability | 10 | 27 | 0.5185 | 0.1333 | 3.6000 | 3.1163 |
| baseline_model_probability | 20 | 55 | 0.4182 | -0.0945 | -5.2000 | 3.4196 |
| baseline_model_probability | 30 | 83 | 0.3494 | -0.1299 | -10.7800 | 4.2594 |
| baseline_model_probability | 50 | 139 | 0.3022 | -0.1091 | -15.1700 | 5.4325 |
| sigma_selector | 10 | 27 | 0.7037 | 0.1270 | 3.4300 | 1.6278 |
| sigma_selector | 20 | 55 | 0.6364 | 0.1589 | 8.7400 | 1.8765 |
| sigma_selector | 30 | 83 | 0.5301 | 0.0600 | 4.9800 | 2.1666 |
| sigma_selector | 50 | 139 | 0.4173 | -0.0004 | -0.0600 | 2.7676 |

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
| PASSPORT_ONLY | 11 | 0.6362 | 0.3560 | 0.2471 | 0.4623 |
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
