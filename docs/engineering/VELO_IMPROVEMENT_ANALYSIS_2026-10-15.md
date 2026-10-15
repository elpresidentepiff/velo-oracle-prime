# How VELO can improve — evidence from the database (2026-10-15)

Everything below is read from Supabase (`velo_verdicts`, `sigma_audits`, `formfav_*`, persisted cards). Samples are small and several cuts were looked at, so treat each as a **lead to test forward**, not a proven edge. Prime scoring is unchanged by this document.

## 1. Was VELO enriched today?
**No.** FormFav's pace, speed-map, class and track-bias features exist for today (40/40 races, 438 runners, quality 0.92) but are shadow-only: Prime does not read them. Coverage of the 6 elite horses today: speed map on 3, pace scenario on 2 of their 6 races, class fit on 5. Barrier-bias statistics were **empty for every runner on every day** (flag said present, sample size 0) because of a key mismatch (`totalStarts` vs `starts`); fixed 2026-10-15 (be618b7) and confirmed on the live API, which returns `advantage, barrierNumber, placeRate, places, totalStarts, winRate, wins` per barrier, plus `expectedWinRate, strongestBarrier, weakestBarrier, conditionStats, distanceStats, recentStats, totalRaces` at race level that the extractor does not use yet. Today's elite horses sit on draws with 34-110 past starts and small edges (advantage 0.00 to +0.06).

## 2. Calibration: VELO's ranking works, its percentages do not
Top-pick win rate by raw `velo_prime_prob` (4,495 settled races, 2026-03-17 → 10-14):

| VP band | n | VELO says | Actual | Gap |
|---|---|---|---|---|
| <15% | 281 | 12.4% | 11.4% | -1.1 |
| 15-25% | 1,088 | 20.3% | 16.5% | -3.9 |
| 25-35% | 1,184 | 29.9% | 21.6% | -8.3 |
| 35-45% | 911 | 39.6% | 26.7% | -13.0 |
| 45-55% | 542 | 49.7% | 32.8% | -16.9 |
| 55%+ | 489 | 65.6% | 37.2% | **-28.4** |

Higher VP does win more often, but VP is not a probability. **Never multiply VP for accumulators or size stakes from it** until it is calibrated.

## 3. Rules at starting price (win-only, £1 level stakes)
| Rule | n | Win % | Return at SP* |
|---|---|---|---|
| All top picks | 4,495 | 23.8 | -14.8% |
| VP30+ (vp ≥ 0.2979) | 2,548 | 29.7 | -9.1% |
| ELITE (Tier A + VP30 + MDS ≥ 0.1693) | 613 | 44.0 | -2.7% |

*Return uses rows that stored a pick price (about half). ELITE by price band:

| Price | n | Win % | Implied by price | Return |
|---|---|---|---|---|
| <2.0 | 118 | 61.9 | 65.9 | -4.5% |
| **2.0-2.5** | 56 | 51.8 | 46.8 | **+11.7%** |
| **2.5-3.0** | 28 | 42.9 | 37.9 | **+12.0%** |
| 3.0-3.5 | 19 | 21.1 | 32.2 | **-35.5%** |
| 3.5-5.0 | 29 | 20.7 | 26.2 | -24.1% |
| 5+ | 18 | 16.7 | 14.5 | +11.1% |

The elite signal looks real (it wins far more than other picks) but it is **already in the price** almost everywhere. The only band that beat the market was 2.0-3.0 (84 bets, thresholds chosen in-sample). Above 3.0 it lost heavily.

## 4. FormFav as a confirmation filter (117 settled GB/IE races, 10-12 → 10-14)
| | Races | VELO pick won | FormFav pick won |
|---|---|---|---|
| Same top pick | 28 | 35.7% | 35.7% |
| Differ, VELO pick in FormFav top 3 | 40 | 35.0% | 32.5% |
| **Differ, VELO pick outside FormFav top 3** | 49 | **16.3%** | 14.3% |

Inside the FormFav top 3: 35.3% (24/68). Outside: 16.3% (8/49). Fisher exact p ≈ 0.035, **before** counting the other cuts examined here. FormFav appears most useful as a veto, not as a feature to add to the score.

## 5. Old VELO three-option card
**No role track record exists.** Every stored card, including past days, still reads `NO_RESULT` and `role_metrics` evaluated = 0; results are never attached. Reconstructed against FormFav results (GB/IE, 10-12 → 10-14, listed morning prices, win-only):

| Role | Picks with result | Wins | Top 3 | Avg price | Win % vs implied | Units |
|---|---|---|---|---|---|---|
| WIN | 104 | 32 | 57 | 6.25 | 30.8% vs 25.3% | +24.7 |
| PLACE | 107 | 21 | 54 | 8.45 | 19.6% vs 18.7% | +10.4 |
| LONGSHOT | 100 | 9 | 39 | 10.26 | 9.0% vs 11.8% | **-23.0** |

Three days only, morning prices (not SP). Direction is informative, magnitude is not.

## 6. Ranked improvements
1. **Attach results to the three-option card at end of day** and persist role metrics. Without it none of the card's roles can be judged. (Small build; unblocks everything below.)
2. **Forward-test FormFav top-3 confirmation as a shadow filter** on VELO's top pick. Pass criterion: ≥ 300 settled races, filtered win rate and return at SP beat unfiltered, holds across course type and price band.
3. **Forward-test an elite price gate (2.0-3.0)**. Pass criterion: ≥ 150 bets, positive return at SP, not carried by a few outliers. Until then do not read the +12% as an edge.
4. **Calibrate VP** (isotonic or Platt on the 4.5k settled rows) so probabilities can drive accumulators and stakes. Ship as a side column first.
5. **LONGSHOT role:** -23 units over 100 picks. Test requiring FormFav win probability ≥ 1.5× the market-implied chance.
6. **Fix enrichment gaps:** (barrier-bias sample bug fixed; next, extract the unused race-level fields `expectedWinRate`, `strongestBarrier`, `weakestBarrier`, `distanceStats`, `conditionStats`, `recentStats`); derive pace from the speed map where the provider gives none (Irish flat, Southwell); persist the cash-run card; capture prices (needs FormFav Premium or Betfair) so closing-line value can be measured.
7. **Per-runner shadow feature rows** with a snapshot time, joined to results, so the chronological ablation in `FORMFAV_UK_ENHANCED_VELO_PLAN_V1.md` can actually run.
