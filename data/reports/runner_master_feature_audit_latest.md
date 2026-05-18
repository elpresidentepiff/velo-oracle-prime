# runner_master_profile — Feature Audit V1
**Generated:** 2026-05-18  
**Governance:** NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE

## Baseline
| | |
|---|---|
| Rows | 1,310 |
| Winners | 274 (20.92%) |
| Flat-stake ROI (all sigma) | -17.25% |

---

## SP Leakage Governance

```
sp_decimal = realised Starting Price (post-race settlement)
RISK: HIGH
DO NOT USE SP AS A PREDICTIVE FEATURE IN ANY PRODUCTION/SHADOW MODEL

SP is approved for:
  ROI calculation (target field)
  SP-band stratification (grouping rows for analysis)
  target: actual_sp

If pre-race odds are needed as a feature, use:
  odds_at_prediction / live_price_pre_off / forecast_price
  (none currently in dataset — must be ingested separately)
```

SP vs won: Spearman rho = -0.3927 (p = 0.0000)
> Negative rho confirms SP encodes market expectation (lower SP = more likely to win).
> This makes SP a leakage proxy — the model would learn to re-rank by market rather than by VELO signal.

---

## TJ Threshold Audit

| | GLOBAL_D8 | TODAY_TOP20 |
|---|---|---|
| Threshold | 0.0847 | 0.1847 |
| n_high | 615 | 148 |
| % of covered | 84% | 20% |
| Win rate | 23.4% | 39.9% |
| ROI | -17.9% | 4.3% |
| Lift vs low | +3.9pp | +21.4pp |
| Strip-top ROI | -24.5% | -3.8% |

**Diagnosis: THRESHOLD_TOO_LOW**

---

## Numeric Signals

| Signal | n | Cov% | Winner mean | Loser mean | Spearman ρ | Top-decile lift | Top-decile ROI |
|---|---|---|---|---|---|---|---|
| VELO Prime Prob | 1310 | 100% | 0.321 | 0.246 | +0.2181 *| +22.6pp | -18.1% |
| TJ Partnership SR | 733 | 56% | 0.160 | 0.132 | +0.1864 *| +14.2pp | -13.4% |
| TS Slope (last-6) | 742 | 57% | 2.758 | 1.804 | +0.0417 | +4.5pp | -13.8% |
| OR Slope (last-6) | 579 | 44% | 0.778 | -0.059 | +0.0661 | -0.0pp | -31.5% |
| RPR Slope (last-6) | 785 | 60% | 1.023 | 0.700 | +0.0212 | -1.0pp | -58.6% |
| OR Drop from Peak | 609 | 46% | 2.495 | 3.984 | -0.1215 *| -6.9pp | -70.6% |
| TS vs OR Gap | 517 | 40% | -33.011 | -30.408 | -0.0421 | -1.6pp | -52.1% |
| Current OR | 1034 | 79% | 91.897 | 80.010 | +0.1835 *| +13.0pp | -28.3% |
| Current TS | 1128 | 86% | 86.594 | 82.924 | +0.0369 | +0.8pp | -40.4% |
| Current RPR | 1202 | 92% | 102.417 | 97.846 | +0.0807 *| +3.2pp | -30.6% |

## Flag Signals

| Signal | n (true) | Flag % | WR on | WR off | Lift | ROI on | ROI off | Verdict |
|---|---|---|---|---|---|---|---|---|
| Silent Improver | 135 | 10.3% | 14.8% | 21.6% | -6.8pp | -15.6% | -17.4% | **NEGATIVE_SIGNAL** |
| Rating Rebound | 320 | 24.4% | 15.9% | 22.5% | -6.6pp | -11.7% | -19.1% | **NEGATIVE_SIGNAL** |
| Exposed Regression | 143 | 10.9% | 18.2% | 21.2% | -3.1pp | -13.7% | -17.7% | **NEGATIVE_SIGNAL** |
| MDS High | 41 | 3.1% | 65.8% | 19.5% | +46.4pp | -11.8% | -17.4% | **WEAK_POSITIVE** |
| TJ HIGH (global D8) | 615 | 46.9% | 23.4% | 18.7% | +4.7pp | -17.9% | -16.6% | **WEAK_POSITIVE** |

## Compound Signals

| Compound | n | WR | Lift vs base | ROI | Strip-top ROI |
|---|---|---|---|---|---|
| VP≥0.30 + TJ_HIGH | 211 | 35.1% | +16.9pp | -13.5% | -17.4% |
| VP≥0.30 + silent_improver | 29 | 24.1% | +3.3pp | -38.3% | -51.5% |
| VP≥0.30 + rating_rebound | 70 | 25.7% | +5.1pp | -4.1% | -20.1% |
| VP≥0.30 + ts_slope>2 | 86 | 29.1% | +8.7pp | 1.0% | -11.9% |
| VP≥0.30 + or_drop>3 | 48 | 22.9% | +2.1pp | -33.7% | -44.0% |
| VP≥0.40 + TJ_HIGH | 79 | 51.9% | +33.0pp | -1.7% | -10.7% |
| VP≥0.30 only (no TJ) | 188 | 33.5% | +14.7pp | 18.6% | 1.1% |
| exposed_regression + VP<0.20 | 104 | 11.5% | -10.2pp | -20.7% | -38.4% |

## VP Band Truth (this dataset)

| VP Band | n | Win rate | ROI |
|---|---|---|---|
| VP<0.20 | 463 | 13.4% | -25.0% |
| VP 0.20-0.30 | 448 | 16.7% | -26.1% |
| VP 0.30-0.40 | 249 | 27.7% | -2.3% |
| VP>=0.40 | 150 | 45.3% | 8.2% |
| VP>=0.30 | 399 | 34.3% | 1.6% |

## VP×TJ Compound (this dataset)

| | n | Win rate | ROI |
|---|---|---|---|
| VP≥0.30 + TJ_HIGH (global D8) | 211 | 35.1% | -13.5% |
| VP≥0.30 + no TJ_HIGH | 188 | 33.5% | 18.6% |

---

## Next Steps
1. Review TJ threshold diagnosis — if THRESHOLD_TOO_LOW, use TODAY_TOP20 for shadow model
2. Features with positive Spearman rho AND positive top-decile ROI → candidate model features
3. Flags with POSITIVE_SIGNAL verdict → include in shadow model feature set
4. Features with NEGATIVE_SIGNAL or neutral → deprioritise or drop
5. Step 5: train on rolling date split only (never random split)
6. NO sp_decimal as predictive feature in any production/shadow model
