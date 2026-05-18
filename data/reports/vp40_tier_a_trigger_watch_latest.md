# VP40_TIER_A TRIGGER WATCH
**Date:** 2026-05-17
**Run:** 2026-05-17 17:40 UTC
**Previous run:** none

Monitoring sub-lane n vs trigger thresholds. No modelling. No mutation.

---

## VP40_TIER_A_SP_2X
*embryo lane — healthiest sub-band*
`VP>=0.40 AND Tier A AND 2.0<=SP<3.0`

| Metric | Value |
|---|---|
| n | **24** / 50 — 48% to trigger |
| n delta | (no change) |
| SR | 45.8% |
| Frame | 83.3% |
| ROI | +3.6% |
| Avg SP | 2.36 |
| Top winner | Egotistical SP=2.6 (10.5% of return) |
| Status | **WAIT** |

Waiting — 26 more selections needed.

---

## VP40_TIER_A_SHORTPRICE
*outlier-clean lane — UNDER_REVIEW*
`VP>=0.40 AND Tier A AND SP<3.0`

| Metric | Value |
|---|---|
| n | **85** / 150 — 57% to trigger |
| n delta | (no change) |
| SR | 60.0% |
| Frame | 89.4% |
| ROI | -3.6% |
| Avg SP | 1.75 |
| Top winner | Egotistical SP=2.6 (3.2% of return) |
| Status | **WAIT** |

Waiting — 65 more selections needed.

---

## Status: WAIT

No trigger has fired. Continue daily accumulation.

## Lane Policy Summary

| Lane | Status | Note |
|---|---|---|
| VP40_LANE | WATCH_ONLY | Gate 4+7 FAIL — Roysse SP=34 |
| VP40_TIER_A | WATCH_ONLY | Gate 4+7 FAIL — Roysse is Tier A |
| VP40_TIER_A_SHORTPRICE | UNDER_REVIEW | n=85/150 — outlier resolved |
| VP40_TIER_A_SP_2X | WATCHING | embryo lane — n=24/50 |

```
NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE
NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION | TRIGGER_DISCIPLINE_ONLY
```

*VP40_TIER_A_TRIGGER_WATCH_V1 — advisory only, no execution impact*