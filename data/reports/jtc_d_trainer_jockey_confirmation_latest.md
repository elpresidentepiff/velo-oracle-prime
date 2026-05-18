# JTC-D Trainer-Jockey Confirmation V1

n=733 VÉLØ candidates | 733 with trainer_jockey_sr

Post-score confirmation audit. TJ signal applied AFTER VÉLØ scores — not blended into VP.
Shadow analysis only. No scoring change. No live mutation.

---

## TJ Quartile Analysis

| Quartile | n | Win Rate | Frame | ROI | Avg VP | Avg TJ |
|---|---|---|---|---|---|---|
| Q1 (lowest) | 184 | **15.2%** | 41.3% | -14.8% | 0.236 | 0.0728 |
| Q2 | 183 | **17.5%** | 51.4% | -33.3% | 0.259 | 0.1120 |
| Q3 | 184 | **21.2%** | 58.2% | -23.2% | 0.274 | 0.1497 |
| Q4 (highest) | 182 | **37.4%** | 71.4% | +4.5% | 0.297 | 0.2212 |

Monotonically increasing Q1→Q4: **YES**
Win rate lift (Q4 vs Q1): **+22.2pp**
ROI delta (Q4 vs Q1): **+19.3pp**

---

## Winner Concentration

- Q4 contains **40.7%** of all 167 wins
- Top decile (D10) contains **16.2%** of wins

---

## VP × TJ Interaction

| Group | n | Win Rate | ROI | Avg SP |
|---|---|---|---|---|
| VP<0.30 + TJ_low | 263 | 11.4% | -25.8% | 11.96 |
| VP<0.30 + TJ_high | 232 | 22.4% | -12.2% | 6.68 |
| VP≥0.30 + TJ_low | 104 | 28.8% | -19.4% | 5.89 |
| VP≥0.30 + TJ_high | 134 | 41.0% | -4.8% | 3.04 |

---

## Breakdown by Distance

| Distance | n | ALL WR | Q4 WR | Q1-3 WR | Lift | Q4 ROI |
|---|---|---|---|---|---|---|
| sprint | 229 | 21.4% | **46.9%** | 17.3% | +29.6pp | +11.8% |
| mile | 162 | 24.1% | **45.7%** | 15.5% | +30.2pp | +9.8% |
| route | 342 | 23.1% | **30.8%** | 19.7% | +11.1pp | -0.2% |

## Breakdown by Race Type (Flat vs Jumps)

| Type | n | ALL WR | Q4 WR | Q1-3 WR | Lift | Q4 ROI |
|---|---|---|---|---|---|---|
| Flat | 466 | 22.5% | **43.0%** | 16.9% | +26.1pp | +19.7% |
| Jumps | 267 | 23.2% | **30.5%** | 20.0% | +10.5pp | -14.1% |

## Handicap vs Non-Handicap

| Type | n | ALL WR | Q4 WR | Q1-3 WR | Lift | Q4 ROI |
|---|---|---|---|---|---|---|
| Handicap | 451 | 14.0% | **18.3%** | 13.2% | +5.1pp | -2.4% |
| Non-Handicap | 282 | 36.9% | **49.5%** | 28.7% | +20.8pp | +8.9% |

## SP Band Breakdown

| SP Band | n | ALL WR | Q4 WR | Q1-3 WR | Lift |
|---|---|---|---|---|---|
| short(<3) | 217 | 44.2% | **43.9%** | 44.5% | -0.6pp |
| fav(3-5) | 168 | 20.8% | **30.8%** | 17.8% | +13.0pp |
| mid(5-8.5) | 141 | 15.6% | **26.9%** | 13.0% | +13.9pp |
| long(8.5-15) | 101 | 10.9% | **50.0%** | 9.3% | +40.7pp |
| outsider(15+) | 105 | 1.9% | **0.0%** | 2.0% | -2.0pp |

## TJ Decile Strip

| Decile | n | Win Rate | ROI |
|---|---|---|---|
| D1 | 79 | 17.7% | -12.7% |
| D2 | 69 | 15.9% | +16.3% |
| D3 | 74 | 16.2% | -41.2% |
| D4 | 71 | 15.5% | -38.1% |
| D5 | 74 | 16.2% | -43.0% |
| D6 | 73 | 17.8% | -21.5% |
| D7 | 73 | 20.5% | -33.4% |
| D8 | 74 | 29.7% | +3.1% |
| D9 | 73 | 41.1% | +17.7% |
| D10 | 73 | 37.0% | -13.4% |

---

## Summary Verdict

**STRONG — TJ monotonically increases WR, Q4 ROI positive. Use as quality filter.**

```
JTC_D_TJ_CONFIRMATION = SHADOW_ONLY
NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE
trainer_jockey_sr = post-score confirmation signal only
```

*JTC_D_TRAINER_JOCKEY_CONFIRMATION_V1 — advisory only*