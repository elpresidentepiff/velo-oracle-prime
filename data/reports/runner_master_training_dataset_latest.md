# runner_master_training_dataset — build report
**Generated:** 2026-05-18  
**Source:** runner_master_profile_latest.parquet  
**Governance:** NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE

## Shape
| | |
|---|---|
| Rows | 1,310 |
| ID columns | 8 |
| Feature columns | 53 |
| Target columns | 5 |
| Leakage check | PASSED |

## Target Distribution
| Target | Count | % |
|---|---|---|
| won | 274 | 20.9% |
| placed | 669 | 51.1% |
| flat-stake ROI | — | -17.0% |

## Feature Coverage (priority signals)
| Feature | Non-null | % |
|---|---|---|
| VP | 1310 | 100.0% |
| SQPE v17 | 1175 | 89.7% |
| MDS | 1308 | 99.8% |
| Improvement | 1308 | 99.8% |
| OR (current) | 1034 | 78.9% |
| TS (current) | 1128 | 86.1% |
| RPR (current) | 1202 | 91.8% |
| TJ partnership | 733 | 56.0% |
| Trainer course | 827 | 63.1% |
| Jockey course | 698 | 53.3% |
| TS slope (last6) | 742 | 56.6% |
| OR slope (last6) | 579 | 44.2% |
| OR drop from peak | 609 | 46.5% |
| TS vs OR gap | 517 | 39.5% |

## Derived Features
| Feature | Rule |
|---|---|
| `tier_numeric` | A=4, B=3, C=2, D=1, X=0 |
| `tj_high_flag` | trainer_jockey_sr >= D8 (0.0847) |
| `dist_band_f` | dist_band → midpoint furlongs |
| `is_flat` / `is_jumps` / `is_handicap` | race_type one-hot |
| `is_class4_lower` | class_num >= 4 |
| `profit_loss_1pt` | (sp - 1) if won else -1 |

## SP Note
> `sp_decimal` is the realised Starting Price (post-race market).  
> Used as market proxy for pre-race assessment.  
> It appears in both the feature block (market proxy) and target block (actual_sp).  
> Do not use as a feature in models where SP leakage is a concern.

## Raceform Gap Warning
> last-6 features use pre-Aug 2025 raceform history.  
> For March-May 2026 sigma rows, last-6 arrays exclude Aug 2025–Feb 2026 runs.

## Next Steps
1. **Step 4 — Feature audit**: measure each signal alone vs won/placed before modelling
2. **Step 5 — Train**: rolling date split only (no random split)
3. Models: logistic regression (baseline) + LightGBM
4. Never train on rows where result is unknown (result_matched=False)
