# runner_master_profile — last-6 patch report
**Generated:** 2026-05-18  
**Governance:** NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE

## Join Summary
| | |
|---|---|
| Rows before | 1,310 |
| Rows after  | 1,310 |
| Rows lost   | **0** |
| Columns before | 112 |
| Columns after  | 112 |
| New columns    | 16 |

## Join Coverage
| | |
|---|---|
| Master unique (horse, date) | 1,310 |
| Spine unique (horse, date)  | 1,542 |
| Overlap                     | 1,310 (100.0%) |
| Rows with last-6 data       | 880 (67.2%) |
| Rows with 0 runs            | 430 (32.8%) |

## Flag Counts
| Flag | Count | % of master |
|---|---|---|
| rating_rebound_flag | 320 | 24.4% |
| silent_improver_flag | 135 | 10.3% |
| exposed_regression_flag | 143 | 10.9% |

## Null Rates by Field
| Field | Null % |
|---|---|
| last6_runs | 0.0% |
| or_slope_6 | 55.8% |
| ts_slope_6 | 43.4% |
| rpr_slope_6 | 40.1% |
| or_drop_from_peak | 53.5% |
| ts_vs_or_gap | 60.5% |
| or_peak_6 | 52.2% |
| ts_peak_recent | 36.3% |
| rpr_peak_recent | 34.0% |
| rating_rebound_flag | 0.0% |
| silent_improver_flag | 0.0% |
| exposed_regression_flag | 0.0% |

## Slope Distributions
| Signal | n | mean | p25 | p75 |
|---|---|---|---|---|
| or_slope_6 | 579 | 0.07 | -1.26 | 1.04 |
| ts_slope_6 | 742 | 1.97 | -3.00 | 5.70 |
| rpr_slope_6 | 785 | 0.76 | -2.30 | 3.40 |

## Raceform Gap Warning
> Aug 2025 – Feb 2026 not covered by raceform_v17_features.parquet.
> For March-May 2026 sigma rows, last-6 arrays reflect pre-Aug 2025 history only.

## Next Steps
1. Run feature audit — measure each last-6 signal alone against won/placed
2. Build `data/training/runner_master_training_dataset_latest.parquet`
3. Train only after audit confirms coverage and no leakage

## Interpretation Guide
| Field | What it means |
|---|---|
| `or_slope_6 < 0` | OR falling — horse being let off by handicapper |
| `or_slope_6 > 0` | OR rising — horse improving, handicapper catching up |
| `ts_slope_6 > 0` | TS improving — horse running better performance figures |
| `or_drop_from_peak > 0` | Current OR below peak — handicap relief |
| `ts_vs_or_gap > 0` | TS above OR — running beyond handicap ceiling |
| `silent_improver_flag` | TS↑ while OR flat/↓ — hidden improver |
| `rating_rebound_flag` | TS V-shape — dip then recovery |
| `exposed_regression_flag` | Both RPR and TS declining |
