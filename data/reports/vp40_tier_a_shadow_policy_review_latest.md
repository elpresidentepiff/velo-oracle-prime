# VP40 TIER A SHADOW POLICY REVIEW V1
**Date:** 2026-05-17
**Run:** 2026-05-17 14:46 UTC

Policy simulation and forensic review. Advisory only.
No scoring change. No model change. No router change. No staking.

---

## Policy Recommendation: WATCH_ONLY

> Same critical blockers as full VP40_LANE. Roysse (SP=34) is Tier A — the outlier dependency carries through. Mid-price drain persists within Tier A (SP3.0-8.5: SR=16.2%, ROI=-23.0%). Both VP40_LANE and VP40_TIER_A fail Gate 4 (ROI strip) and Gate 7 (winner concentration) of the 10-gate protocol. Wait for n>=250 and natural Roysse ROI dilution.

**Issues:**

- 🚨 OUTLIER_DEPENDENCY: ROI collapses to -15.7% without top SP winner (Roysse SP=34.0)
- 🚨 MIDPRICE_DRAIN: VP40_TIER_A+SP3.0-8.5 SR=16.2% ROI=-23.0% at n=37 — confirmed drain subzone within Tier A
- ⚠️ LONGSHOT_DEAD_ZONE: SP8.51-16.0 SR=0% n=8
- ⚠️ n=132 below minimum 150

**Strengths:**

- ✅ SR=44.7% above 40.0% floor
- ✅ Frame=80.3% above 75.0% floor
- ✅ ROI=+9.4% — positive flat stake

---

## Overall VP40_TIER_A Stats

| Metric | Value |
|---|---|
| n (resulted) | 132 |
| Wins | 59 |
| Frames | 106 |
| Strike rate | 44.7% |
| Frame rate | 80.3% |
| ROI (flat £1) | +9.4% |
| Avg SP | 3.32 |
| Median SP | 2.0 |
| Max winner SP | 34.0 |
| Biggest winner | Roysse |
| Longest losing run | 7 |
| Max drawdown | £19.48 |

---

## ROI Outlier Strip Test

| Excluding top N winners | Excluded horse | Excluded SP | ROI stripped |
|---|---|---|---|
| 1 | Roysse | 34.0 | -15.7% |
| 2 | Pageant Girl | 8.0 | -21.2% |
| 3 | Braganza Bay | 5.5 | -24.9% |

**Finding:** Roysse (SP=34) is Tier A. Same outlier dependency confirmed.
VP40_TIER_A shares the Gate 4 failure with full VP40_LANE.

---

## SP Band Breakdown

| SP Band | n | SR | Frame | ROI |
|---|---|---|---|---|
| SP<2.0 | 61 | 65.6% | 91.8% | -6.4% |
| SP3.0-8.5 | 37 | 16.2% | 70.3% | -23.0% |
| SP2.0-2.99 | 24 | 45.8% | 83.3% | +3.6% |
| SP8.51-16.0 | 8 | 0.0% | 25.0% | — |

SP3.0-8.5 drain persists within Tier A (SR=16.2%, ROI=-23.0%). Midprice contamination is not a tier issue.

---

## Course Breakdown

| Course | n | SR | ROI |
|---|---|---|---|
| Bath | 5 | 40.0% | -19.4% |
| Beverley | 5 | 0.0% | — |
| Doncaster | 5 | 20.0% | -40.0% |
| Hereford | 5 | 40.0% | -70.0% |
| Southwell (AW) | 5 | 40.0% | +1.4% |
| Warwick | 5 | 20.0% | -10.0% |
| Yarmouth | 5 | 80.0% | +26.2% |

---

## Overlap Analysis

| Lane | Overlap n | % of VP40_TIER_A | Shared winners |
|---|---|---|---|
| MDS_HIGH_LANE | 31 | 23.5% | 23 |
| IMPROVER_LANE | 20 | 15.2% | 10 |
| SHORTFAV_VP30 | 85 | 64.4% | 51 |
| MIDPRICE_ROUTER_QUAL | 3 | 2.3% | 1 |
| MIDPRICE_SUPPRESS | 34 | 25.8% | 5 |

MIDPRICE_SUPPRESS overlap (25.8%) shows the drain zone is inside Tier A — it is an SP band issue, not a tier issue.

---

## Refined Simulations

| Simulation | n | SR | Frame | ROI |
|---|---|---|---|---|
| VP40_TIER_A_SP_LT3 | 85 | 60.0% | 89.4% | -3.6% |
| VP40_TIER_A_SP_2X | 24 | 45.8% | 83.3% | +3.6% |
| VP40_TIER_A_NO_MIDPRICE | 94 | 55.3% | 84.0% | +23.3% |

---

## Key Finding vs Full VP40_LANE

Both VP40_LANE and VP40_TIER_A fail the 10-gate protocol for the same reasons:

```
1. Roysse is Tier A → outlier dependency carries through
2. SP3.0-8.5 drain exists within Tier A → midprice contamination is not tier-filtered
3. SP8.51-16.0 dead zone exists within Tier A
```

VP40_TIER_A is marginally cleaner (18 fewer noisy rows, slightly higher ROI).
But the structural problems are identical.

**Path forward:**
Wait for n>=250. As Roysse's SP=34 return gets diluted by more results,
the outlier dependency ratio improves naturally.
At n=250+, a single winner contributes < 14% of total return (vs ~50% now at n=132).

---

## Governance

```
NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE
NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION | POLICY_SIMULATION_ONLY | WATCH_ONLY
```

*VP40_TIER_A_SHADOW_POLICY_REVIEW_V1 — advisory only, no execution impact*