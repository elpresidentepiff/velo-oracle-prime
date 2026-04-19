# VÉLØ Price Discovery Preparation
**Generated:** 2026-04-19  
**Status:** Pre-implementation specification. No live betting.

---

## The Core Problem

The organism has genuine signal. It is being taxed out of profitability by bookmaker margin.

| Tier | Strike% | Avg Win SP | Breakeven SP | Gap | ROI |
|------|---------|-----------|-------------|-----|-----|
| A | 41.2% | 2.28 | 2.43 | **-0.15** | -6.1% |
| B | 22.1% | 4.21 | 4.51 | **-0.30** | -8.0% |
| A (SP<3 only) | 60.3% | 1.75 | 1.66 | **+0.09** | **+5.4%** |
| A+B | 27.5% | 3.40 | 3.64 | **-0.24** | -7.5% |
| Organism | 20.5% | 4.15 | 4.89 | **-0.74** | -15.4% |

A-tier is **0.15 SP units from breakeven**. A-tier at SP<3 is **already positive** at +5.4% ROI.

The gap between the signal and the profit is not primarily a model problem. It is a pricing problem.

---

## Why This Is Solvable Without Retraining

A standard bookmaker takes 15–25% margin across a race. On a 4/1 horse, the true price might be 4.5/1 at Betfair. On a 2/1 horse, the true price might be 2.2/1 at BSP.

For A-tier at breakeven gap of -0.15:
- A-tier avg win SP (bookmaker): 2.28
- A-tier avg win SP (BSP estimate at 8% premium): ~2.46
- Breakeven SP: 2.43
- **BSP pushes A-tier into positive ROI.**

For B-tier at breakeven gap of -0.30:
- B-tier avg win SP (bookmaker): 4.21
- B-tier avg win SP (BSP estimate at 8% premium): ~4.55
- Breakeven SP: 4.51
- **BSP also pushes B-tier into marginal positive ROI.**

These are not large adjustments. They are within the typical BSP premium range. **The signal is at the tipping point.**

---

## What Price Discovery Means

Price discovery does NOT mean finding the best odds on a single horse. It means:

1. **Understanding the true price of our selections** — what Betfair SP pays vs bookmaker SP
2. **Identifying where our selections are most underpriced** — where the bookmaker takes the most margin
3. **Building a price model** — estimating the implied price for rank-1 from velo_prime_prob and comparing to market price

### Three-Phase Price Discovery Plan

**Phase 1: BSP data acquisition** (immediate)
- Obtain Betfair Starting Price (BSP) data for the 1,070 scored races
- Source: The Racing API (BSP is available per runner), Betfair historical data, or Racing Post SP data
- Match to sigma_audits by race_id and horse_id
- Compare bookmaker SP (current `actual_winner_sp`) to BSP

**Phase 2: BSP re-simulation** (after data)
- Re-run the full simulation (rank-1 and rank-2 filtered lanes) using BSP instead of bookmaker SP
- Quantify: does A-tier achieve positive ROI at BSP? At what BSP premium level does each tier break even?
- Expected finding: A-tier flips to positive at ~8% BSP premium; B-tier at ~10% premium

**Phase 3: Implied price model** (after BSP simulation proves positive)
- Build a lightweight SP estimation model using velo_prime_prob as input
- Compare estimated price to market price
- When model implies the horse is underpriced by >15%, treat as value bet flag
- This is a price-aware overlay on top of tier selection, not a replacement

---

## The MDS High-Strike Finding — Price Implications

MDS > 0.3 races produce a 72.9% win rate. At what price?

This needs a dedicated analysis: what is the avg SP of winners when MDS > 0.3?

**Hypothesis:** When MDS is high toward our pick (steam move supporting our selection), the bookmaker has already shortened the horse's price — meaning the SP available to us may be BELOW the true value. This is the paradox:
- The signal is at its strongest (72.9% win rate)
- But the horse may be at its most undervalued in the market (price has moved before we bet)

**Resolution:** Betfair early price vs BSP comparison in MDS > 0.3 races is critical. If the horse is available at pre-steam prices early, there is value. If we can only get post-steam prices, the 72.9% strike rate may not translate to positive ROI.

---

## Data Requirements for Price Discovery

| Data item | Source | Status |
|-----------|--------|--------|
| BSP per runner per race | Betfair API / Racing API | Not yet acquired |
| Pre-race early price movement | Betfair API exchange data | Not yet acquired |
| Bookmaker best price (not just SP) | Oddschecker API / price comparison | Not yet acquired |
| MDS > 0.3 races with SP data | Existing sigma_audits + verdict join | Available but BSP missing |

**First data acquisition priority: BSP for the 1,070 existing races.** This is a one-time historical pull. The Racing API may have BSP field. Check: `full_analysis[i].bsp` or similar.

---

## What "Exchange Ready" Means

Before the organism can be tested on exchange prices, it needs:

1. BSP data for historical races (to re-simulate) — PENDING
2. Exchange API access for live BSP or lay/back market data — NOT YET BUILT
3. A price floor model: when our implied price > market price by X%, it qualifies — NOT YET BUILT
4. A staking framework that accounts for exchange commission (typically 5%) — NOT YET BUILT

**None of this requires model changes.** It requires data plumbing and selection overlay logic.

---

## Immediate Next Step

Run this single check: does The Racing API's response for historical races include BSP data?

```python
# Check if BSP available in velo_verdicts or raw racing API payloads
# Look for: 'bsp', 'betfair_win_sp', 'starting_price_decimal'
# in the full_analysis JSON entries
```

If BSP data is available via the existing Racing API connection, Phase 1 can be completed in a single pull request against the historical race set.

If not, BSP must be sourced from Betfair's historical data product or a third-party provider.

---

## The +5.4% ROI Finding

A-tier at SP < 3.0 already returns +5.4% at bookmaker SP (68 races, 41 wins, avg SP 1.75). This is the organism's only confirmed positive-ROI lane at current pricing.

**What this proves:** The organism has positive edge in its cleanest zone. This is not noise — it is documented over 68 races. The path to commercial operation is:
1. Concentrate on A-tier SP < 3.0 as the primary selection
2. Move that lane to exchange pricing (BSP likely adds +8% → +13% combined)
3. Prove B-tier at exchange prices
4. Scale carefully

The +5.4% at bookmaker SP is not large enough to build a staking model on. At exchange prices it becomes the foundation of a real operation.
