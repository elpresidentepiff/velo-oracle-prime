# VÉLØ Rank-2 Selective Lane Simulation
**Generated:** 2026-04-19 | **Base:** 551 miss races, 1,070 total scored races  
**Method:** Win-at-SP simulation. Each bet = 1 unit staked on rank-2 horse. Win = actual SP returned. Loss = -1.

---

## VERDICT FIRST

**The rank-2 lane is real vision. It is not yet real money.**

The organism correctly identifies the winner at rank-2 in 91 miss races. Every tested filter produces negative win ROI. The market prices rank-2 winners efficiently — median SP 4.00, mean 5.41, but the breakeven SP at a 16.5% strike rate is 6.06. The gap is structural, not random.

**This is not a reason to abandon the lane. It is a reason to price it better.**

---

## Baseline Organism Context

Before reading rank-2 results: the rank-1 organism also runs at negative win-SP ROI.

| Metric | Value |
|--------|-------|
| Rank-1 bets | 1,070 |
| Rank-1 wins | 219 (20.5%) |
| Rank-1 avg win SP | 4.15 |
| Rank-1 breakeven SP | 4.89 |
| Rank-1 gap to breakeven | **-0.74** |
| Rank-1 ROI | **-15.4%** |

The organism has genuine signal (+0.086 prob separation, 41.2% on A-tier) but is not yet priced for positive flat-SP ROI. Rank-2 simulation must be read against this baseline.

---

## Simulation Table — All 10 Lanes

| Lane | Bets | Wins | Strike% | Avg Win SP | Breakeven SP | SP Gap | Profit | ROI |
|------|------|------|---------|-----------|-------------|--------|--------|-----|
| 1. Rank-2 always | 551 | 91 | 16.5% | 5.41 | 6.05 | **-0.65** | -58.98 | -10.7% |
| 2. prob_gap < 0.05 | 363 | 59 | 16.3% | 5.69 | 6.15 | **-0.47** | -27.55 | -7.6% |
| 3. A/B tier only | 175 | 28 | 16.0% | 5.12 | 6.25 | **-1.13** | -31.51 | -18.0% |
| 4. AW decoy only | 28 | 5 | 17.9% | 3.06 | 5.60 | **-2.54** | -12.71 | -45.4% |
| 5. place_prob > 0.50 | 143 | 29 | 20.3% | 4.49 | 4.93 | **-0.44** | -12.74 | -8.9% |
| 6. No outsider chaos | 403 | 82 | 20.3% | 4.28 | 4.91 | **-0.63** | -52.11 | -12.9% |
| 7. Combined filter (A/B+signal+no chaos) | 113 | 23 | 20.4% | 4.35 | 4.90 | **-0.55** | -12.84 | -11.4% |
| 8. short_fav_won only | 66 | 21 | 31.8% | 2.32 | 3.14 | **-0.83** | -17.34 | -26.3% |
| 9. market_decoy_followed | 94 | 18 | 19.1% | 3.58 | 5.22 | **-1.64** | -29.50 | -31.4% |
| 10. market_deception_score > 0.3 | 16 | 3 | 18.8% | 3.43 | 5.33 | **-1.90** | -5.71 | -35.7% |

**No lane produces positive win ROI. Best lane: Lane 2 (prob_gap < 0.05) at -7.6%.**

---

## Miss Classes Recovered by Lane

| Lane | short_fav | mid_priced | decoy | outsider_hedge | outsider_won | untracked |
|------|-----------|-----------|-------|---------------|-------------|----------|
| 1. Always | 21 | 43 | 18 | 2 | 4 | 3 |
| 2. prob_gap < 0.05 | 15 | 25 | 12 | 1 | 4 | 2 |
| 3. A/B tier | 8 | 14 | 4 | 2 | 0 | 0 |
| 5. place_prob > 0.50 | 9 | 11 | 7 | 1 | 0 | 1 |
| 7. Combined | 8 | 11 | 4 | 0 | 0 | 0 |
| 8. short_fav only | 21 | 0 | 0 | 0 | 0 | 0 |

---

## Drawdown by Lane

| Lane | Max Consecutive Losses |
|------|----------------------|
| 1. Rank-2 always | 29 |
| 2. prob_gap < 0.05 | 33 |
| 3. A/B tier | 17 |
| 5. place_prob > 0.50 | 12 |
| 7. Combined filter | 12 |
| 8. short_fav only | 8 |

Lane 5 and Lane 7 have the best drawdown profile (12 consecutive losses max).

---

## SP Band Breakdown of Rank-2 Wins

Understanding *where* the wins occur by winner SP band reveals where the edge pressure is real:

| Winner SP Band | Miss Races | Rank-2 Wins | Strike% | Avg Win SP | Win ROI |
|----------------|-----------|-------------|---------|-----------|---------|
| <2.0 | 15 | 5 | 33.3% | 1.55 | -48.3% |
| 2.0–3.0 | 68 | 26 | **38.2%** | 2.53 | **-3.4%** |
| 3.0–5.0 | 138 | 28 | 20.3% | 3.95 | -19.9% |
| 5.0–8.0 | 138 | 18 | 13.0% | 5.94 | -22.5% |
| 8.0–15.0 | 116 | 9 | 7.8% | 9.00 | -30.2% |
| 15.0+ | 76 | 5 | 6.6% | 24.00 | +57.9% |

**The 2.0–3.0 band is the only zone approaching breakeven at -3.4%.** These are short-price competitive races where our rank-2 horse also runs at a short price and wins at 38.2% — nearly 1 in 3. ROI is near-zero. The 15/1+ outlier band is high-variance noise (5 wins).

---

## Each-Way Simulation (Corrected)

Win-only simulation understates the lane because rank-2 horses have a genuine frame signal.  
**Proxy:** 30% of non-winning rank-2 bets estimated to place (conservative). 40% sensitivity test.  
**Note:** Actual place positions not available for rank-2 horses — these are estimates only.

| Lane | Bets | Staked | Wins | Est Places | Returned | EW ROI |
|------|------|--------|------|------------|---------|--------|
| All rank-2 (EW, 30%) | 551 | 1,102 | 91 | 138 | 976.5 | -11.4% |
| place_prob > 0.5 (EW, 30%) | 143 | 286 | 29 | 34 | 256.8 | -10.2% |
| prob_gap < 0.05 (EW, 30%) | 363 | 726 | 59 | 91 | 656.9 | -9.5% |
| A/B + place_prob > 0.40 (EW, 30%) | 85 | 170 | 16 | 20 | 160.2 | **-5.8%** |
| place_prob > 0.5 (EW, 40%) | 143 | 286 | 29 | 45 | 280.2 | **-2.0%** |

**At 40% estimated place rate, Lane 5 (place_prob > 0.5) gets to -2.0% EW ROI.**  
Exchange prices (Betfair SP typically 10–15% above bookmaker SP) could push this to break-even or marginal positive. This is the lane to watch.

---

## The Short Favourite Trap

Lane 8 (short_fav_won) looked like the strongest forensic lane — 31.8% strike rate, highest frame recovery.  
The simulation kills it cleanly.

| Metric | Value |
|--------|-------|
| Strike rate | 31.8% |
| All 21 win SPs | 1.29, 1.44, 1.44, 1.67, 2.0, 2.0, 2.2, 2.25, 2.38, 2.38, 2.5, 2.62, 2.62, 2.62, 2.62, 2.62, 2.75, 2.75, 2.75, 2.88, 2.88 |
| Avg win SP | 2.32 |
| Breakeven SP | 3.14 |
| ROI | **-26.3%** |

**The short_fav class is a trap.** When a short favourite beats our pick, our rank-2 horse is also short-priced. You win often, but the returns are too small. 31.8% strike at 2.32 SP is a structural loser.

---

## The Market Decoy False Promise

Lane 9 (market_decoy_followed) looked recoverable (38.3% top-3 coverage). Simulation result: **-31.4% ROI.**

The problem: when a decoy fires, our rank-2 horse is not the winner at a good price. It's the horse we were on (the decoy) who is now short. Our rank-2 horse in a decoy race isn't the real winner — the real winner was a different horse entirely, not rank-2.

The correct decoy fix is **suppression + better rank-1 selection**, not a rank-2 mechanical pick.

---

## Structural Diagnosis

**Why no lane beats the market at SP:**

1. The market is efficient at pricing short-range horses. The rank-2 winner's median SP is 4.00. The bookmaker's margin on a 4/1 horse is ~16–20%. The model's edge (+0.086 prob separation) is real but smaller than the bookmaker's take.

2. The organism and the market both see the same horse. When the model ranks a horse 2nd with high place_prob, the market already prices it at 4–5/1 — correctly. There is no hidden pricing advantage.

3. Short_fav races kill the lane's most promising strike rate. 31.8% at 2.32 avg SP is structurally losing.

4. Filtering by tier, place_prob, and prob_gap reduces volume but does not improve the fundamental SP:strike ratio enough to produce positive ROI at bookmaker prices.

---

## Where Viability Exists — The Honest Assessment

| Condition | Assessment |
|-----------|-----------|
| Win-only at bookmaker SP | **No lane viable.** Best: -7.6% (prob_gap < 0.05). |
| EW at bookmaker SP | Marginally viable approaching break-even at 40% place rate for place_prob > 0.5 filter. |
| EW at exchange (BSP) prices | **Potentially viable.** BSP typically 10–15% above SP. +2.0% push from EW near-break-even → marginal positive ROI zone. |
| Win at exchange with model-driven price floor | **Viable if model correctly identifies mispriced rank-2 horses.** The place_prob > 0.5 filter at 20.3% strike with avg SP 4.49 is -0.44 from breakeven. A 10% price improvement closes it. |
| Combination bet (rank-1 place + rank-2 place) | Not yet simulated — requires place-only market data |

---

## Viability Conditions — What Would Flip This Lane

For rank-2 to produce positive ROI, need **one** of the following:

1. **Better prices:** Exchange (BSP) prices rather than bookmaker SP. The -0.44 gap for place_prob > 0.5 is within Betfair's typical SP premium.

2. **Higher strike rate filter:** A filter that achieves >22% strike with avg win SP > 4.5. Not yet found in this dataset.

3. **SP floor targeting:** Only bet rank-2 when their predicted price (from r2_prob) suggests market underestimates them. This requires a calibrated SP model, not just a rank-2 filter.

4. **Each-way + higher place rate confirmation:** If actual rank-2 place rates are confirmed at 40%+ (not estimated), the EW lane at place_prob > 0.5 is marginal positive.

---

## What This Changes

| Claim | Before simulation | After simulation |
|-------|------------------|-----------------|
| Rank-2 adds wins | **True** — 91 additional wins | Confirmed |
| Rank-2 adds profit at SP | Untested | **False** — all lanes negative |
| short_fav is the strongest lane | Forensic evidence | **False** — structural SP trap |
| decoy filter + rank-2 = best lane | Forensic evidence | **False** — -31.4% ROI |
| place_prob > 0.5 is the best filter | Likely | **Confirmed** — closest to viable |
| EW with exchange prices could work | Speculative | **Plausible** — within 2% of break-even |
| 2-horse system is immediate operational lane | Assumed | **No. Pricing work required first.** |

---

## Next Step (Simulation-Derived)

The simulation changes the priority order:

1. **Do not implement a mechanical rank-2 SP betting lane.** The market prices these horses too efficiently.

2. **The real next step is price discovery:** Build a rank-2 SP estimation model. When VÉLØ's implied probability for rank-2 is materially higher than the bookmaker's implied probability, that is a priced edge. Bet then, not mechanically.

3. **Exchange simulation is the nearest viable test:** Re-run the place_prob > 0.5 lane using Betfair Starting Price (BSP) data. If BSP is 10%+ above SP, the EW lane tips positive. That data does not require model changes — it requires a BSP data source.

4. **The rank-1 organism needs the same treatment.** The rank-1 baseline runs at -15.4% ROI. The edge is in the model, not the price. Both lanes suffer from the same root cause: bookmaker margin consuming the signal. The path to monetisation is exchange pricing, not adding more bets.
