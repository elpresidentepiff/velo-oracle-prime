# Prime Market-Blind Ranker Challenger

- Classification: **ANALYSIS ONLY**
- Locked calibration selection: **pairwise_core_c0.1**
- Holdout readout: **PARTIAL_RANKING_LIFT_NOT_PROMOTABLE**
- Prices, favourite flags, runner identity, and result fields were excluded from features.
- No fitted model object was persisted or installed.

## Untouched holdout

| Variant | Top-1 | Top-3 | Log loss | Brier | MRR | Pairwise | ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| stored_g | 23.19% | 52.77% | 2.1223 | 0.8522 | 0.4363 | 64.80% | -20.00% |
| pairwise_core_c0.01 | 25.38% | 55.46% | 2.1329 | 0.8511 | 0.4557 | 66.05% | -25.90% |
| pairwise_core_c0.1 **← selected** | 25.38% | 54.96% | 2.1317 | 0.8503 | 0.4562 | 66.03% | -26.15% |
| pairwise_core_c1 | 25.04% | 54.96% | 2.1319 | 0.8503 | 0.4545 | 65.98% | -27.18% |
| pairwise_core_c10 | 25.04% | 54.96% | 2.1319 | 0.8503 | 0.4545 | 65.96% | -27.18% |
| pairwise_expanded_c0.01 | 23.87% | 50.92% | 2.1328 | 0.8512 | 0.4357 | 64.41% | -26.55% |
| pairwise_expanded_c0.1 | 24.03% | 50.59% | 2.1309 | 0.8499 | 0.4347 | 64.31% | -27.39% |
| pairwise_expanded_c1 | 23.87% | 50.76% | 2.1311 | 0.8499 | 0.4339 | 64.27% | -27.90% |
| pairwise_expanded_c10 | 23.87% | 50.76% | 2.1312 | 0.8499 | 0.4339 | 64.27% | -27.90% |

## Interpretation

The early block alone fitted all coefficients and probability scaling. The middle block locked the candidate and hyperparameters. The final block was then evaluated once. This is a supervised ranking experiment, not a production model, promotion, or RL policy.
