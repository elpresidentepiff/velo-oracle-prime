# VP40 vs VP40_TIER_A — COMPARISON REPORT
**Date:** 2026-05-17
**Run:** 2026-05-17 16:47 UTC

Side-by-side policy comparison. Advisory only. No execution.

---

## Verdict Comparison

| Lane | n | SR | Frame | ROI | Verdict |
|---|---|---|---|---|---|
| VP40_LANE | 150 | 45.3% | 80.7% | +8.2% | **WATCH_ONLY** |
| VP40_TIER_A_LANE | 132 | 44.7% | 80.3% | +9.4% | **WATCH_ONLY** |

**Both lanes: WATCH_ONLY. Same critical failures confirmed.**

---

## What Tier A Filtering Changes

| Metric | VP40_LANE | VP40_TIER_A | Delta |
|---|---|---|---|
| n | 150 | 132 | 18 removed (12.0%) |
| Winners | 68 | 59 | 9 removed |
| Losers removed | — | — | 9 |
| SR | 45.3% | 44.7% | -0.6pp |
| Frame | 80.7% | 80.3% | -0.4pp |
| ROI | +8.2% | +9.4% | +1.2pp |

---

## Top-Winner Outlier Dependency

| | VP40_LANE | VP40_TIER_A |
|---|---|---|
| Full ROI | +8.2% | +9.4% |
| ROI ex-top-winner | -13.9% | -15.7% |
| Top winner | Roysse SP=34.0 | Same |
| Same outlier? | — | YES — Roysse is Tier A |

**Finding:** Roysse (SP=34.0) is Tier A.
Tier A filtering does not remove the outlier. Both lanes fail Gate 4 (ROI strip test).

---

## Midprice Drain (SP 3.0–8.5)

| | VP40_LANE | VP40_TIER_A | Change |
|---|---|---|---|
| Midprice n | 45 | 37 | -8 |
| Midprice SR | 17.8% | 16.2% | minimal |
| Midprice ROI | -18.9% | -23.0% | worse |

The midprice drain is slightly smaller within Tier A (37 vs 45 rows) but the SR/ROI are nearly identical.
This confirms **the drain is an SP band issue, not a tier issue.**

---

## Is VP40_TIER_A Materially Safer?

**Answer: MARGINALLY — same critical failures**

VP40_TIER_A removes 18 noisy rows (Tier B/C/X) but Roysse is Tier A, so both lanes share the same outlier dependency. Midprice drain persists within Tier A at SP3.0-8.5 (SR=16.2%, ROI=-23.0%). The Tier A filter is not a fix for the structural problems — it is a tighter lens on the same edge.

Tier A does slightly improve:
- Removes 9 non-Tier-A winners (13.2% of VP40 wins) — but these were mostly positive contributors
- Removes 9 losers net (more losers excluded than winners)
- ROI slightly higher (+9.4% vs +8.2%) before strip test

Tier A does not fix:
- The Roysse SP=34 outlier dependency (same horse, same problem)
- The SP3.0-8.5 drain zone (persists within Tier A)
- The SP8.51-16.0 dead zone

---

## The Real Signal: NO_MIDPRICE Simulation

VP40_TIER_A excluding SP3.0-8.5 (removing the drain zone):

```
VP40_TIER_A + (SP<3.0 OR SP>8.5)
n=94   SR=55.3%   ROI=+23.3%
```

This is a strong simulation result. The drain zone accounts for almost all ROI degradation.
However: this simulation still includes Roysse (SP=34 is in SP>16 band, not excluded).
A true structural test would require the strip test on this filtered set too.

**Insight:** The real policy refinement is `VP40_TIER_A + SP exclusion of 3.0–8.5`.
This needs its own named lane tracking once n on this sub-lane reaches ≥50.

---

## Path Forward

```
1. Neither VP40_LANE nor VP40_TIER_A is promotable at n=132-150.
   Both fail Gate 4 (ROI strip) and Gate 7 (winner concentration).

2. Wait for n >= 250. At n=250, Roysse's return dilutes below 14% of total
   return (from ~50% now), potentially passing Gate 7 naturally.

3. Consider naming a new candidate lane:
   VP40_TIER_A_SHORTPRICE (VP>=0.40 AND Tier A AND SP<3.0)
   as a tracked lane once the corpus grows to n>=50 for this sub-lane.

4. Re-run both policy reviews at n=200 and n=250 as milestones.
```

---

## Governance

```
NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE
NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION | POLICY_SIMULATION_ONLY
```

*VP40_LANE_COMPARISON_V1 — advisory only, no execution impact*