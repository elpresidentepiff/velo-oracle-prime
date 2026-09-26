# Prime Probability Calibration Challenger

- Classification: **ANALYSIS ONLY**
- Model readout: **CALIBRATION_CHALLENGER_BEATS_RAW_BASE_ON_HOLDOUT**
- Late-market readout: **LATE_MARKET_REMAINS_CHAMPION**
- Locked model selection: **g_temperature**
- Locked late-market selection: **late_market**
- Market timing: **late pre-off snapshots only; not morning prices**

## Chronological blocks

| Block | Dates | Range | Races | Complete market |
|---|---:|---|---:|---:|
| train | 32 | 2026-05-21 to 2026-06-30 | 1027 | 219 |
| calibration | 16 | 2026-07-05 to 2026-08-03 | 623 | 623 |
| test | 16 | 2026-08-04 to 2026-09-24 | 595 | 595 |

## Untouched test: model track

| Variant | Races | Top-1 | Log loss | Brier | Flat ROI | ECE |
|---|---:|---:|---:|---:|---:|---:|
| raw_base | 595 | 23.19% | 2.3884 | 0.9029 | -20.00% | 0.0463 |
| base_temperature | 595 | 23.19% | 2.1288 | 0.8536 | -20.00% | 0.0088 |
| g_temperature | 595 | 23.19% | 2.1223 | 0.8522 | -20.00% | 0.0084 |

## Untouched test: complete late-market races

| Variant | Races | Top-1 | Log loss | Brier | Flat ROI | ECE |
|---|---:|---:|---:|---:|---:|---:|
| late_market | 595 | 30.08% | 1.9831 | 0.8144 | -12.60% | 0.0061 |
| base_late_market_blend | 595 | 30.25% | 1.9886 | 0.8167 | -12.44% | 0.0084 |
| g_late_market_blend | 595 | 30.25% | 1.9883 | 0.8165 | -12.44% | 0.0080 |

## Interpretation

Parameters were fitted on the early block, variants were selected on the middle block, and the final block was evaluated only after both were locked. This artifact is evidence, not a promotion or a live-scoring change.
