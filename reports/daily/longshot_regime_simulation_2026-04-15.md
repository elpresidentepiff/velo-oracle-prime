# Longshot Regime Simulation — 2026-04-15
Window: 2026-03-17 to 2026-04-15
Model: sidecar doctrine simulation only

## Regime
- blocker: `longshot_block_allowed`
- decision tier: `A`
- surface: `AW`
- actual winner SP bucket: `short_<=3.0`

## Current vs Relaxed Proxy
| metric | value |
| --- | --- |
| winner_recovery_count | 6 |
| false_positive_increase | 0 |
| relaxed_regime_win_rate_pct | 66.7 |
| relaxed_regime_place_rate_pct | 33.3 |
| net_a_tier_precision_change_pct_points | 24.7 |
| place_rate_change_pct_points | -0.7 |

## Outcome Split
| outcome | count |
| --- | --- |
| WIN | 6 |
| PLACED | 3 |

## Top Tracks
| track | count |
| --- | --- |
| Southwell (AW) | 3 |
| Kempton (AW) | 2 |
| Dundalk (AW) (IRE) | 2 |
| Wolverhampton (AW) | 1 |
| Lingfield (AW) | 1 |

## Notes
- `winner_recovery_count` is the number of blocker-fired regime rows whose observed outcome was `WIN`.
- `false_positive_increase` is the number of regime rows whose observed outcome was `MISS` and would be re-admitted under the relaxed regime proxy.
- `net_a_tier_precision_change_pct_points` compares the regime proxy win rate against the observed base A-tier win rate over the same window.
- This is a sidecar counterfactual proxy, not a deployed scoring simulation.