# VP40 SHADOW POLICY REVIEW V1
**Date:** 2026-05-17
**Run:** 2026-05-17 13:57 UTC

Policy simulation and forensic review. Advisory only.
No scoring change. No model change. No router change. No staking.

---

## Policy Recommendation: WATCH_ONLY

> Critical issues block promotion: ROI is driven by outlier winner(s) and mid-price VP40 (SP 3.0-8.5) is a confirmed drain zone. The real edge lives in VP40+SP<3.0. Refine to VP40_SP_LT3 or VP40_TIER_A before policy review.

**Issues:**

- 🚨 OUTLIER_DEPENDENCY: ROI collapses to -13.9% without top SP winner (Roysse SP=34.0)
- ⚠️ LONGSHOT_DEAD_ZONE: SP8.51-16.0 at SR=0% n=8
- ⚠️ n=150 above minimum 150 but below preferred 250

**Strengths:**

- ✅ Mid-price subzone SP3.0-8.5: SR=17.8%
- ✅ SR=45.3% above 40.0% floor
- ✅ Frame=80.7% above 75.0% floor
- ✅ ROI=+8.2% — positive flat stake

---

## Overall VP40_LANE Stats

| Metric | Value |
|---|---|
| n (resulted) | 150 |
| Wins | 68 |
| Frames | 121 |
| Strike rate | 45.3% |
| Frame rate | 80.7% |
| ROI (flat £1) | +8.2% |
| Avg SP | 3.45 |
| Median SP | 2.25 |
| Max winner SP | 34.0 |
| Biggest winner | Roysse |
| Longest losing run | 8 |
| Max drawdown | £17.89 |

---

## SP Band Breakdown — CRITICAL

| SP Band | n | SR | Frame | ROI |
|---|---|---|---|---|
| SP<2.0 | 65 | 67.7% | 92.3% | -3.3% |
| SP3.0-8.5 | 45 | 17.8% | 68.9% | -18.9% |
| SP2.0-2.99 | 28 | 46.4% | 85.7% | +3.4% |
| SP8.51-16.0 | 8 | 0.0% | 25.0% | — |

**Key finding:** VP40+SP<3.0 (n=71, SR=67.6%) is the edge zone. VP40+SP3.0-8.5 (n=41) is a drain.

---

## ROI Outlier Strip Test

| Excluding top N winners | Excluded horse | Excluded SP | ROI stripped |
|---|---|---|---|
| 1 | Roysse | 34.0 | -13.9% |
| 2 | Pageant Girl | 8.0 | -18.7% |
| 3 | Braganza Bay | 5.5 | -21.9% |

**Finding:** ROI collapses when top winner removed — edge is partially driven by outlier SP=34 winner.

---

## Course Breakdown

| Course | n | SR | ROI |
|---|---|---|---|
| Bath | 6 | 50.0% | -12.8% |
| Hereford | 6 | 33.3% | -75.0% |
| Beverley | 5 | 0.0% | — |
| Chepstow | 5 | 40.0% | +10.0% |
| Doncaster | 5 | 20.0% | -40.0% |
| Ripon | 5 | 80.0% | +210.0% |
| Southwell (AW) | 5 | 40.0% | +1.4% |
| Warwick | 5 | 20.0% | -10.0% |
| Yarmouth | 5 | 80.0% | +26.2% |

---

## Tier Breakdown

| Tier | n | SR | Frame | ROI |
|---|---|---|---|---|
| Tier A | 132 | 44.7% | 80.3% | +9.4% |
| Tier B | 14 | 50.0% | 85.7% | +13.3% |

---

## Overlap Analysis

| Lane | Overlap n | % of VP40 | Shared winners |
|---|---|---|---|
| VP40_TIER_A_LANE | 132 | 88.0% | 59 |
| MDS_HIGH_LANE | 34 | 22.7% | 25 |
| IMPROVER_LANE | 22 | 14.7% | 11 |
| SHORTFAV_VP30 | 93 | 62.0% | 57 |
| MIDPRICE_ROUTER_QUAL | 5 | 3.3% | 2 |

**Winners lost if restricted to VP40_TIER_A:** 9 (13.2% of VP40 wins)

---

## Refined Lane Simulations

| Simulation | n | SR | Frame | ROI |
|---|---|---|---|---|
| VP40_SP_LT3 | 93 | 61.3% | 90.3% | -1.3% |
| VP40_SP_LT4 | 114 | 52.6% | 86.8% | -11.1% |
| VP40_TIER_A_ONLY | 132 | 44.7% | 80.3% | +9.4% |
| VP40_SP_LT3_TIER_A | 85 | 60.0% | 89.4% | -3.6% |

**Implication:** VP40+SP<3.0 and VP40_TIER_A are the robust sub-lanes.
Full VP40_LANE ROI is partially synthetic (outlier SP=34 winner).

---

## Promotion Requirements (not yet met)

```
n >= 250 preferred (current: 150)
ROI stable without top winner (current: fails — ROI=-13.9% ex-top-winner)
SP band drain resolved (VP40+SP3.0-8.5 at SR=14.6%, ROI=-25.6% is a blocker)
Either restrict lane to SP<3.0 or separate mid-price into MIDPRICE_ROUTER_QUAL
```

---

## Governance

```
NO_SCORING_CHANGE
NO_MODEL_CHANGE
NO_ROUTER_CHANGE
NO_STAKING_CHANGE
NO_TELEGRAM_CHANGE
NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION
POLICY_SIMULATION_ONLY
```

*VP40_SHADOW_POLICY_REVIEW_V1 — advisory only, no execution impact*