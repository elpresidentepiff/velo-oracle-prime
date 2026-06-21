# June 19 Mid-Price Deep Dive
Generated: 2026-06-19T22:33:10.454320+00:00

- Races joined: 56
- Wins: 11
- Frames: 33
- Mid-price misses: 17
- Mid-price winners visible top 3: 8
- Mid-price winners visible top 5: 10
- Mid-price winners visible top 8: 17

## Field Bands
| Band | n | Wins | Frames | Mid-price misses |
|---|---:|---:|---:|---:|
| FS_2_5 | 3 | 3 | 3 | 0 |
| FS_6_8 | 20 | 1 | 12 | 6 |
| FS_9_12 | 21 | 5 | 13 | 7 |
| FS_13_PLUS | 12 | 2 | 5 | 4 |

## Top Mid-Price Actions
| Action | n | Wins | Frames | Mid-price misses |
|---|---:|---:|---:|---:|
| MIDPRICE_CLEAN | 11 | 2 | 6 | 3 |
| MIDPRICE_NO_EDGE | 5 | 0 | 3 | 1 |
| MIDPRICE_SPLIT_RACE | 21 | 6 | 11 | 9 |
| MIDPRICE_SUPPRESS_TOP | 19 | 3 | 13 | 4 |

## Rule Pack

- live_status: SHADOW_ONLY
- snapshot_contract: STORE_NO_RPR_NDS_CHAIN_MIDPRICE_FIELDS
- field_band_rule: ANNOTATE_FS_6_8_AS_WIN_LIGHT_FRAME_HEAVY
- small_field_rule: ANNOTATE_FS_2_5_AS_CLEAN_SIGNAL
- training_decision: DO_NOT_RETRAIN_FROM_ONE_DAY; USE_FULL_HISTORICAL_RETRAIN_ALREADY_COMPLETED
