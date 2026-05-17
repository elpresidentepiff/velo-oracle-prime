# MIDPRICE ROUTER SUPPRESSION AUDIT V1
**Run:** 2026-05-17 11:58 UTC
**SP Zone:** 3.0–8.5

---

## The Money Question

If we suppress SP 3.0–8.5 selections without router qualification,
how many losers do we remove — and how many winners do we lose?

| Metric | Value |
|---|---|
| Total corpus (with results) | 893 |
| Global SR | 14.8% |
| Global Frame | 36.2% |

## Mid-Price Universe

| Group | n | SR | Frame | Winners | Losers |
|---|---|---|---|---|---|
| All mid-price | 279 | 17.2% | 53.4% | 48 | 231 |
| Router-qualified | 18 | 33.3% | 72.2% | 6 | 12 |
| Router-suppressed (advisory) | 261 | 16.1% | 52.1% | 42 | 219 |

## Suppression Impact

| Question | Answer |
|---|---|
| Winners we would suppress | **42** (31.8% of all winners) |
| Losers we would remove | **219** (28.8% of all losers) |
| Loser:winner ratio (suppressed group) | **5.2:1** |

## Net Effect If Suppression Had Been Active

| Metric | Before | After | Delta |
|---|---|---|---|
| n | 893 | 526 | -367 |
| SR | 14.8% | 17.1% | **+2.3pp** |
| Frame | 36.2% | 35.6% | **-0.6pp** |

## Router Lane Breakdown (Mid-Price Qualifiers)

| Lane | n in mid-price | SR | Frame | Wins |
|---|---|---|---|---|
| V1_BASE | 18 | 33.3% | 72.2% | 6 |
| V2_CLASS4 | 15 | 33.3% | 66.7% | 5 |
| V6_GOLD_SEAM | 10 | 40.0% | 70.0% | 4 |

## Tier Breakdown of Suppressed Group

| Tier | n | SR | Frame | Wins |
|---|---|---|---|---|
| A | 33 | 9.1% | 57.6% | 3 |
| B | 103 | 19.4% | 53.4% | 20 |
| C | 53 | 9.4% | 49.1% | 5 |
| D | 11 | 18.2% | 63.6% | 2 |
| X | 30 | 13.3% | 40.0% | 4 |

## Governance

**This audit is ADVISORY ONLY. No changes made:**
- Scoring: NO CHANGE
- Model weights: NO CHANGE
- Staking: NONE (paper only)
- Router rules: NO CHANGE
- Telegram format: NO CHANGE

*MIDPRICE_ROUTER_SUPPRESSION_AUDIT_V1 — scripts/midprice_router_suppression_audit.py*