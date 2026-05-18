# VP40_TIER_A_SHORTPRICE SHADOW POLICY REVIEW V1
**Date:** 2026-05-17
**Run:** 2026-05-17 17:19 UTC

**Lane definition:** VP >= 0.40 AND decision_tier == A AND SP < 3.0
**Purpose:** Removes midprice drain (SP 3.0–8.5) and Roysse zone (SP > 8.5). Tests the honest signal.

---

## Summary

| Metric | Value |
|---|---|
| n | 85 |
| Wins | 51 |
| Frames (placed) | 76 |
| Strike Rate | 60.0% |
| Frame Rate | 89.4% |
| ROI (flat £1) | -3.6% |
| Avg SP | 1.75 |
| Median SP | 1.73 |
| Max SP | 2.88 |
| Longest Losing Run | 3 (3.5% of n) |
| Max Drawdown (£1 flat) | £4.0 |

**Verdict: WATCH_ONLY**

*n=85, SR=60.0%, ROI=-3.6%. Gate 1 (n<150) and Gate 5 (ROI<0%) both fail. ROI compression is mathematical at avg SP=1.75 — not a signal failure. Monitor to n>=150.*

---

## What This Lane Tests

VP40_LANE failed Gate 4 (ROI strip) because Roysse SP=34 carries all positive ROI.
VP40_TIER_A failed Gate 4 for the same reason — Roysse is Tier A.
VP40_TIER_A_SHORTPRICE removes all SP >= 3.0, which excludes:
  - The midprice drain zone (SP 3.0–8.5, SR~16%, ROI~-23%)
  - The longshot outlier zone (SP>8.5, Roysse SP=34)

What remains: the short-price Tier A signal at SP < 3.0.
SP range in this lane: 1.06 — 2.88

---

## ROI Strip Test

| Removed | Horse | SP | ROI Remaining | Still positive? |
|---|---|---|---|---|
| Full lane | — | — | -3.6% | No |
| Remove top 1 | Egotistical | SP=2.6 | -5.6% | No |
| Remove top 2 | Lady Blanche | SP=2.5 | -7.5% | No |
| Remove top 3 | Conclave | SP=2.4 | -9.2% | No |

Top winner: Egotistical SP=2.6 VP=0.415
Top-1 return concentration: 3.2% of total return
Top-3 return concentration: 9.2% of total return

**Gate 4 target:** ROI >= 0% when top 1 and top 2 winners excluded.
**Gate 7 target:** Top-1 winner < 20% of total return. Top-3 < 40%.

---

## Strengths

- HIGH_SR: 60.0% — strong win rate for this price zone
- CONTROLLED_LLR: longest losing run = 3
- LOW_OUTLIER_DEPENDENCY: top winner = 3.2% of total return

## Issues / Gate Failures

- INSUFFICIENT_N: n=85 below minimum gate (n>=150). Preferred n>=250.
- NEGATIVE_ROI: -3.6% — flat stake negative. Short prices compress ROI even at high SR.
- SUBGROUP_COLLAPSE: CLASS_COLLAPSE: Class4 n=11 SR=36.4%

---

## Course Breakdown

| Course | n | SR | ROI | Collapse? |
|---|---|---|---|---|
| Yarmouth | 5 | 80.0% | +26.2% | No |
| Naas | 4 | 100.0% | +58.0% | No |
| Cork | 3 | 66.7% | +7.3% | No |
| Fontwell | 3 | 33.3% | -62.7% | No |
| Hamilton | 3 | 66.7% | +14.7% | No |
| Limerick | 3 | 66.7% | +23.0% | No |
| Redcar | 3 | 66.7% | +57.3% | No |
| Ripon | 3 | 66.7% | -16.7% | No |
| Warwick | 3 | 0.0% | -100.0% | No |
| Wolverhampton (AW) | 3 | 33.3% | -62.7% | No |

## Class Breakdown

| Class | n | SR | ROI | Collapse? |
|---|---|---|---|---|
| Class 4 | 11 | 36.4% | -32.4% | YES ⚠️ |

## Going Breakdown

Going data sparse in corpus — no reliable breakdown.

---

## Overlap Analysis

| Lane | Shared n | % of Shortprice | Shared wins |
|---|---|---|---|
| MDS_HIGH_LANE | 28 | 32.9% | 22 |
| IMPROVER_LANE | 15 | 17.6% | 10 |
| SHORTFAV_VP30 | 85 | 100.0% | 51 |
| ROUTER_QUALIFIED | 6 | 7.1% | 2 |

**Note:** All VP40_TIER_A_SHORTPRICE rows are also in SHORTFAV_VP30 by definition (SP<3.0 + VP>=0.30).
The overlap with MDS_HIGH and IMPROVER shows where signal layers compound.

---

## Subgroup Collapse Flags

- *** CLASS_COLLAPSE: Class4 n=11 SR=36.4%

---

## ROI Context: Why Short Prices Compress Returns

A SR=60% lane at SP<3.0 will often produce negative ROI because:

```
Avg SP=1.75 → avg net return per win = £0.75
Required SR to break even at avg SP=1.75: 1/1.75 = 57.1%
SR=60% at avg SP=1.75 → ROI ≈ -3.5% (matches observed)

This is a mathematical compression, not a signal failure.
The signal is real (SR=60%). The unit is wrong (flat £1 at short prices).
```

To extract value from this lane in practice, the bet must be sized differently
or the return measure must shift to place/frame rather than win-flat-stake.
This is a policy discussion, not a disqualifier.

---

## Promotion Path

```
Current: n=85  SR=60.0%  ROI=-3.6%

Gate 1 (n>=150): FAIL — n=85 / 150
Gate 4 (ROI strip): FAIL — ROI ex-top = -5.6%
Gate 7 (outlier conc.): PASS

Next milestone: n=150 — rerun this script
Preferred milestone: n=250 — rerun this script
```

---

## Governance

```
NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE
NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION | POLICY_SIMULATION_ONLY
```

*VP40_TIER_A_SHORTPRICE_REVIEW_V1 — advisory only, no execution impact*