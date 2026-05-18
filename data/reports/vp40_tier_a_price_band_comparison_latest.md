# VP40_TIER_A — PRICE BAND COMPARISON
**Date:** 2026-05-17
**Run:** 2026-05-17 17:21 UTC

Side-by-side comparison of all VP40_TIER_A price band cuts.
Advisory only. No execution.

---

## Band Summary Table

| Band | n | SR | Frame | ROI | ROI ex-top1 | Top-1 % | Top-3 % | LLR | Stability |
|---|---|---|---|---|---|---|---|---|---|
| VP40_TIER_A_ALL | 132 | 44.7% | 80.3% | +10.3% | -15.1% | 23.5% | 32.9% | 7 (5.3%) | UNSTABLE: OUTLIER_DEP+WINNER_CONC |
| VP40_TIER_A_SHORTPRICE | 85 | 60.0% | 89.4% | -3.6% | -5.6% | 3.2% | 9.2% | 3 (3.5%) | UNSTABLE: NEG_ROI |
| VP40_TIER_A_SP_2X | 24 | 45.8% | 83.3% | +3.6% | -3.3% | 10.5% | 30.2% | 3 (12.5%) | UNSTABLE: OUTLIER_DEP |
| VP40_TIER_A_SP_LT2 | 61 | 65.6% | 91.8% | -6.4% | -8.1% | 3.3% | 9.9% | 2 (3.3%) | UNSTABLE: NEG_ROI |
| VP40_TIER_A_MIDPRICE | 37 | 16.2% | 70.3% | -23.0% | -43.1% | 28.1% | 63.2% | 12 (32.4%) | UNSTABLE: LOW_SR+NEG_ROI+WINNER_CONC |
| VP40_TIER_A_LONGSHOT | 9 | 11.1% | 33.3% | +277.8% | -100.0% | 100.0% | 100.0% | 8 (88.9%) | INSUFFICIENT_N |
| VP40_TIER_A_NO_MIDPRICE | 94 | 55.3% | 84.0% | +23.3% | -11.9% | 29.3% | 33.7% | 5 (5.3%) | UNSTABLE: OUTLIER_DEP+WINNER_CONC |
| VP40_TIER_A_NO_MIDPRICE_NO_LONGSHOT | 85 | 60.0% | 89.4% | -3.6% | -5.6% | 3.2% | 9.2% | 3 (3.5%) | UNSTABLE: NEG_ROI |

---

## Band Detail

### VP40_TIER_A_ALL
*All VP40_TIER_A (baseline)*

n=132  SR=44.7%  Frame=80.3%  ROI=+10.3%  avg_SP=3.32  median_SP=2.0  max_SP=34.0
ROI ex top winner: -15.1% (ex Roysse SP=34.0)
Top-1 return concentration: 23.5%  Top-3: 32.9%
LLR: 7 (5.3% of n)
**Stability verdict: UNSTABLE: OUTLIER_DEP+WINNER_CONC**

### VP40_TIER_A_SHORTPRICE
*SP < 3.0 — removes drain + Roysse*

n=85  SR=60.0%  Frame=89.4%  ROI=-3.6%  avg_SP=1.75  median_SP=1.73  max_SP=2.88
ROI ex top winner: -5.6% (ex Egotistical SP=2.6)
Top-1 return concentration: 3.2%  Top-3: 9.2%
LLR: 3 (3.5% of n)
**Stability verdict: UNSTABLE: NEG_ROI**

### VP40_TIER_A_SP_2X
*SP 2.0–2.99 — healthiest sub-band*

n=24  SR=45.8%  Frame=83.3%  ROI=+3.6%  avg_SP=2.36  median_SP=2.38  max_SP=2.88
ROI ex top winner: -3.3% (ex Egotistical SP=2.6)
Top-1 return concentration: 10.5%  Top-3: 30.2%
LLR: 3 (12.5% of n)
**Stability verdict: UNSTABLE: OUTLIER_DEP**

### VP40_TIER_A_SP_LT2
*SP < 2.0 — short-price favourites*

n=61  SR=65.6%  Frame=91.8%  ROI=-6.4%  avg_SP=1.51  median_SP=1.5  max_SP=1.91
ROI ex top winner: -8.1% (ex Dunstall Star SP=1.9)
Top-1 return concentration: 3.3%  Top-3: 9.9%
LLR: 2 (3.3% of n)
**Stability verdict: UNSTABLE: NEG_ROI**

### VP40_TIER_A_MIDPRICE
*SP 3.0–8.5 — confirmed drain zone*

n=37  SR=16.2%  Frame=70.3%  ROI=-23.0%  avg_SP=4.35  median_SP=4.0  max_SP=8.0
ROI ex top winner: -43.1% (ex Pageant Girl SP=8.0)
Top-1 return concentration: 28.1%  Top-3: 63.2%
LLR: 12 (32.4% of n)
**Stability verdict: UNSTABLE: LOW_SR+NEG_ROI+WINNER_CONC**

### VP40_TIER_A_LONGSHOT
*SP > 8.5 — outlier / Roysse zone*

n=9  SR=11.1%  Frame=33.3%  ROI=+277.8%  avg_SP=13.89  median_SP=12.0  max_SP=34.0
ROI ex top winner: -100.0% (ex Roysse SP=34.0)
Top-1 return concentration: 100.0%  Top-3: 100.0%
LLR: 8 (88.9% of n)
**Stability verdict: INSUFFICIENT_N**

### VP40_TIER_A_NO_MIDPRICE
*SP<3.0 OR SP>8.5 — excl drain zone*

n=94  SR=55.3%  Frame=84.0%  ROI=+23.3%  avg_SP=2.91  median_SP=1.77  max_SP=34.0
ROI ex top winner: -11.9% (ex Roysse SP=34.0)
Top-1 return concentration: 29.3%  Top-3: 33.7%
LLR: 5 (5.3% of n)
**Stability verdict: UNSTABLE: OUTLIER_DEP+WINNER_CONC**

### VP40_TIER_A_NO_MIDPRICE_NO_LONGSHOT
*SP<3.0 only — excl drain + excl Roysse*

n=85  SR=60.0%  Frame=89.4%  ROI=-3.6%  avg_SP=1.75  median_SP=1.73  max_SP=2.88
ROI ex top winner: -5.6% (ex Egotistical SP=2.6)
Top-1 return concentration: 3.2%  Top-3: 9.2%
LLR: 3 (3.5% of n)
**Stability verdict: UNSTABLE: NEG_ROI**

---

## Key Findings

### What This Comparison Proves

```
SHORTPRICE (SP<3.0):
  - Roysse (SP=34) is GONE — top-1 return concentration drops to ~3%
  - No outlier dependency at current n
  - SR=60% is structural (not driven by one horse)
  - ROI=-3.6% is mathematical compression at avg SP=1.75, not signal failure
  - Needs n>=150 before gate assessment

MIDPRICE (SP 3.0–8.5):
  - Confirmed drain in all VP40 lenses
  - SR~16% is MIDPRICE_SUPPRESS level — VP40 filter does not qualify these
  - ROI~-23% — structural negative

LONGSHOT (SP>8.5):
  - Roysse lives here (SP=34)
  - Without Roysse: dead zone at SR=0%, ROI=-100%
  - Do not include in any candidate lane

NO_MIDPRICE (SP<3.0 OR SP>8.5):
  - ROI=+23.3% — looks great but includes Roysse
  - Strip test required on this band before declaring it a candidate

SHORTPRICE ONLY (SP<3.0 = NO_MIDPRICE_NO_LONGSHOT):
  - Same as SHORTPRICE — the honest isolated signal
```

### Price Hygiene Rule (confirmed)

```
The SP 3.0–8.5 drain is structural across ALL VP40_TIER_A lenses.
The SP>8.5 zone is outlier-contaminated (Roysse).
Only SP<3.0 produces a stable, non-outlier-dependent SR.
Price hygiene is now mandatory for any VP40 policy candidate.
```

---

## Governance

```
NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE
NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION | POLICY_SIMULATION_ONLY
```

*VP40_TIER_A_PRICE_BAND_COMPARISON_V1 — advisory only, no execution impact*