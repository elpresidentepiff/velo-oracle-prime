# Historical Tier-A Replay — leakage-honest

Generated 2026-06-10T22:33:21.177067+00:00 · READ-ONLY

**EXACT_REPLAY: BLOCKED_LEAKAGE** — IN_SAMPLE: sqpe_v17 metadata source=raceform_clean.parquet, train_rows=1,447,607 (~85% of this file); MARKET_INPUT: model features include sp_dec/log_sp/implied_prob/sp_rank/is_fav — final SP is a model input; edge-vs-SP is circular

## Decade baselines (flat 1pt at SP)

| Proxy | n | SR | avg SP | P&L | ROI |
|---|---|---|---|---|---|
| P0_all_runners | 1,692,214 | 10.2% | 24.54 | -435,400.9 | -25.73% |
| P1_favourite | 183,388 | 32.9% | 3.19 | -17,006.2 | -9.27% |
| P2_favourite_with_ratings_edge | 78,428 | 37.4% | 3.19 | 3,750.2 | 4.78% |

## P2 (fav + ratings edge) by year
| Year | n | SR | ROI |
|---|---|---|---|
| 2015 | 7,201 | 37.7% | 8.11% |
| 2016 | 7,367 | 38.0% | 9.4% |
| 2017 | 8,048 | 37.5% | 5.54% |
| 2018 | 8,104 | 38.1% | 7.72% |
| 2019 | 7,825 | 37.9% | 5.11% |
| 2020 | 5,165 | 36.5% | 3.59% |
| 2021 | 7,916 | 36.9% | 3.4% |
| 2022 | 7,730 | 37.8% | 2.15% |
| 2023 | 7,401 | 36.1% | 1.03% |
| 2024 | 7,777 | 36.6% | 2.94% |
| 2025 | 3,894 | 38.2% | 1.97% |

**Stability:** positive years 11/11 · best 2016 · worst 2023

**Conclusion:** The decade replay CANNOT validate Tier A with the current model (leakage). It CAN and does establish the baselines Tier A must beat, by year/class/surface/odds-band. The walk-forward harness is the path to real validation.