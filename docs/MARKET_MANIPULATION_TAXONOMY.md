# 🎭 Market Manipulation Taxonomy - Future Implementation

**Source:** External research document  
**Date Saved:** October 21, 2025  
**Status:** 📋 REFERENCE - Not yet implemented  
**Priority:** High - Oracle 3.0 candidate feature

---

## 📖 Overview

This document contains a comprehensive taxonomy of **15 market manipulation tactics** commonly seen in horse racing betting markets, along with detection signals, data capture requirements, and exploitation strategies.

**Purpose:** Future enhancement to Oracle's manipulation detection capabilities beyond the current basic implementation.

---

## 🎯 15 Manipulation Tactics

### 1. Late-Money Push (Bookmakers)
**What:** Heavy betting late before off pushes odds to trap retail or influence SP/tote prices.

**Detection Signals:**
- Sudden odds shortening on bookmaker apps in final minutes
- Exchange volume spike
- Favourite shortens sharply while market depth thins

**Data to Capture:**
- Time-stamped bookmaker odds (every minute)
- Exchange matched volume
- Best back/lay prices
- Timestamp of change

**Action:**
- Treat strong late-money favourites as possibly market-driven
- Reduce stake or wait for exchange confirmation
- Consider backing runners pushed out if they still show early exchange liquidity

**Confidence:** Medium–High

---

### 2. Fake Favourite / "Pinned" Favourite
**What:** Horse presented as favourite but strategically supported to block value elsewhere.

**Detection Signals:**
- Favourite shortens across many bookies without exchange liquidity
- Sudden "flash odds" movement without volume

**Data to Capture:**
- Discrepancy between bookmaker odds and exchange price
- Spread across bookies
- Early vs late position

**Action:**
- Treat bookmaker-only favourites with suspicion
- Use exchange for confirmation or fade if trainer/jockey pattern flags

**Confidence:** Medium

---

### 3. Stable-Stacking / Pacemaker Inflation
**What:** Trainers enter multiple horses to control pace and market perception, sometimes to set up a stablemate.

**Detection Signals:**
- Multiple runners same trainer
- One gets heavy money early/late
- Jockey/trainer notes show saddle orders or pacemaker history

**Data to Capture:**
- Trainer
- All runners from same stable
- Declarations
- Jockey bookings
- Weights

**Action:**
- Identify stablemates
- If one gets heavy late money while others drift, edge to moneyed stablemate
- Or fade the "public" horse if pattern matches

**Confidence:** High

---

### 4. Jockey Switch Signalling
**What:** Late jockey change (upgrading to big jockey) signals extra intention from trainer/owner.

**Detection Signals:**
- Jockey declared change close to race
- Odds shorten after change

**Data to Capture:**
- Jockey at declaration vs final
- Timing of change
- Previous form with jockey

**Action:**
- Treat late positive jockey upgrades as uplift indicator
- Increase weight in model

**Confidence:** High

---

### 5. Non-Runner and Rule Changes (Scratches)
**What:** Non-runners cause rules deductions, forecast/tricast reshuffles, can manipulate related markets.

**Detection Signals:**
- Withdrawal lists
- "Rule 4" deductions noted
- Forecast adjustments

**Data to Capture:**
- Non-runners list + time
- Deductions applied
- Final field size

**Action:**
- Always re-evaluate markets when non-runner appears
- Adjust place/each-way calculations and stakes accordingly

**Confidence:** Certain

---

### 6. False Drift / Engineered Drift
**What:** Misleading early market drift encourages punters to back bigger odds elsewhere while insiders back the short.

**Detection Signals:**
- Early drift across bookies followed by abrupt shortening in last minutes
- Inconsistent exchange backing

**Data to Capture:**
- Minute-by-minute odds tempo
- Time of drift/reversal
- Bookmaker breadth

**Action:**
- Avoid backing on early drift alone
- Prefer live/late checks

**Confidence:** Medium

---

### 7. Exchange Overlay / Lay Layering
**What:** Large lay offers on exchanges to change perception, often by matched or hidden liquidity.

**Detection Signals:**
- Large visible lay stacks
- Sudden collapse in available back depth

**Data to Capture:**
- Exchange orderbook snapshots
- Matched volume
- Best back/lay spread

**Action:**
- Watch exchange depth
- If large layers appear, treat favourite as potential trap

**Confidence:** Medium

---

### 8. Odds Band Manipulation
**What:** Markets repeatedly push certain odds bands (e.g., 3.0–4.5) to protect house margin; value outside those bands may exist.

**Detection Signals:**
- Most winners cluster in small band
- Bookies shorten many horses into that band late

**Data to Capture:**
- Final odds distribution histograms
- Win frequency by odds band

**Action:**
- Model favourite hit-rate by band
- Look for value outside crowded bands

**Confidence:** High

---

### 9. Forecast/Tricast Engineering
**What:** Manipulating place/forecast tote to inflate dividends (used to offset liabilities).

**Detection Signals:**
- Odd forecast/tricast dividends (very high) vs SP
- Big price for combinations including long-odds runners

**Data to Capture:**
- Forecast/dividend
- Tote vs SP differences
- Position combos

**Action:**
- Track which bookmakers/tote produce odd dividends
- Opportunistically play where forecast shows value

**Confidence:** Medium

---

### 10. Late Equipment/Claim Change Shills
**What:** Fast last-minute gear changes (blinkers on/off) signal insider info or market change.

**Detection Signals:**
- Declaration notes: gear changes very late
- Jockeys riding differently

**Data to Capture:**
- Equipment changes
- Timing
- Subsequent market move

**Action:**
- Treat late positive gear fits as upgrade signal
- Weight into model

**Confidence:** Medium

---

### 11. Trainer/Jockey Patterns (Systemic)
**What:** Certain trainers/jockeys show repeatable market behavior.

**Detection Signals:**
- Historical correlation between trainer/jockey and market moves/results

**Data to Capture:**
- Trainer/jockey win%
- Strike rate when market moves
- Time-of-day patterns

**Action:**
- Build trainer/jockey historical metrics
- Use as model features

**Confidence:** High

**Note:** Oracle already implements this partially via profitable connections filter.

---

### 12. Bookmaker Liability Balancing (Book-Bait)
**What:** Bookies shift odds to balance books, sometimes making long price artificially attractive.

**Detection Signals:**
- Sudden generous odds on one bookie alone
- Often followed by limits or price pullback after money

**Data to Capture:**
- Cross-bookie prices
- Exposure limits
- Availability changes

**Action:**
- Be cautious taking isolated generous prices
- Watch for rapid limits

**Confidence:** High

---

### 13. Quiet Market (Low Liquidity) Traps
**What:** On small meetings or early hours, thin markets make it easy to move prices with small money.

**Detection Signals:**
- Big odds moves with tiny traded volume
- Inconsistent exchange data

**Data to Capture:**
- Volume
- Number of matched bets
- Field size

**Action:**
- Avoid assuming moves are meaningful on thin markets
- Require extra confirmation

**Confidence:** High

---

### 14. Insider Late Knowledge (Illegal) — Detection Only
**What:** Declarations or coordinated deposits combined with very precise late market moves may indicate illegal insider information.

**Detection Signals:**
- Consistent anomalous short-priced winners following unusual deposit spikes or equipment changes

**Data to Capture:**
- All timestamps
- Deposit patterns if available
- Cross-referencing stable ownership

**Action:**
- Flag, log, and treat as strong market signal
- **Do not facilitate illegal activity**
- Report anomalies to authorities if necessary

**Confidence:** Low–Medium (hard to prove)

**Note:** Oracle will detect patterns but not facilitate illegal exploitation.

---

### 15. Broadcast/Media Signal Pumping
**What:** Tipsters, pundits, or media sway retail flows to protect books.

**Detection Signals:**
- Odds shortening following publicity or social media tip

**Data to Capture:**
- Time of post vs odds
- Source of tip

**Action:**
- Treat media-driven moves differently (often public, less informed)
- Consider fading retail-driven moves

**Confidence:** Medium

---

## 📊 Required Data Fields (Spreadsheet/Database Schema)

### Core Race Data
1. Date
2. Meeting (racecourse)
3. Race time & race ID
4. Horse name
5. Horse number (saddle)
6. Trainer
7. Jockey
8. Weight
9. Age
10. Barrier / Draw

### Market Data
11. Declared gear/equipment + timestamp of change
12. Non-runner flag
13. Initial bookmaker price (opening)
14. **Minute-by-minute bookmaker odds** (T-30, T-15, T-5, T-1, Off)
15. **Exchange back/lay and matched volume snapshots** (same timestamps)
16. Tote/SP/final bookmaker prices

### Results Data
17. Start-to-finish position (finish order)
18. Distances (lengths)
19. Forecast / Tricast dividends
20. Rule deductions (e.g., Rule 4)

### Analysis Fields
21. Market comments (free text)
22. Suggested pick (Top strike) + reason tags
23. Fade (who to fade) + reason
24. Exacta/trifecta suggestions (numbers)
25. Replay check note (post-race)
26. Confidence score (0–100)
27. Source (bookmaker app/exchange/screenshot filename)

---

## 📈 Derived Metrics (Auto-Calculated)

1. **Favorite-hit rate** (by day/week)
2. **% winners from backed suggestions vs fades**
3. **ROI per suggestion** (for each strategy)
4. **Odds band win frequency** (histogram buckets: <2.0, 2–3, 3–5, 5–10, 10+)
5. **Trainer/jockey strike rates vs market move signal**
6. **Late-money success ratio** (shortenings that won / total shortenings)
7. **Forecast/tricast ROI and frequency**

---

## 🚨 Automated Alerts (Future Implementation)

1. Alert if exchange matched volume > X and odds shorten > Y in last 10 minutes
2. Flag when 2+ stablemates present and one shortens > 30% near off
3. Flag late jockey upgrade inside 24 hours
4. Flag odd forecast dividends > historical mean * 2

---

## 🎯 Exploitation Rules (High-Level)

### Stablemate Rule
If multiple runners from same stable and one shortens heavily in final 30min while another was the listed favourite:
- Increase weight for shortened runner
- Check exchange volumes first

### Fade Favorite Rule
If favourite shortened only on single bookmaker with no exchange volume and historical favourite hit rate that day is low:
- Consider fading

### Exacta/Trifecta Rule
Use top 3 suggestions + a stablemate to generate exacta/trifecta boxes:
- Track historical success rate
- Adjust box sizes by confidence

---

## 🔧 Implementation Roadmap (Oracle 3.0)

### Phase 1: Data Collection Enhancement
- [ ] Add minute-by-minute odds tracking (currently only snapshots)
- [ ] Implement exchange orderbook depth capture
- [ ] Add bookmaker cross-comparison (multiple bookies)
- [ ] Track gear changes and timestamps

### Phase 2: Detection Algorithms
- [ ] Implement all 15 manipulation detection algorithms
- [ ] Build historical pattern database
- [ ] Create confidence scoring system
- [ ] Add automated alert system

### Phase 3: Exploitation Framework
- [ ] Build stablemate detection and analysis
- [ ] Implement fade-favorite logic
- [ ] Add exacta/trifecta suggestion engine
- [ ] Create ROI tracking per strategy

### Phase 4: Reporting & Analytics
- [ ] Weekly manipulation report generator
- [ ] Trainer/jockey pattern dashboard
- [ ] Odds band histogram analysis
- [ ] Success rate tracking per tactic

---

## 📝 Data Hygiene Requirements

1. **Always keep timestamps** for every data point
2. **Store screenshot filenames** and which bookmaker/exchange they came from
3. **Keep raw snapshots** aside from derived fields for backtesting
4. **Version control** all data schemas and feature definitions

---

## 🚀 Integration with Current Oracle

### Already Implemented (Partial)
- ✅ Trainer/jockey patterns (Tactic #11) - via profitable connections filter
- ✅ Basic manipulation detection - via `manipulation_detector.py`
- ✅ Market movement tracking - via Betfair API integration

### Not Yet Implemented
- ❌ Minute-by-minute odds tracking
- ❌ Exchange orderbook depth analysis
- ❌ Stablemate detection
- ❌ Gear change tracking
- ❌ Forecast/tricast analysis
- ❌ Cross-bookmaker comparison
- ❌ Automated alert system
- ❌ 13 of 15 manipulation tactics

---

## 💡 Priority Recommendations

**High Priority (Oracle 3.0):**
1. Stablemate detection (#3) - High confidence, easy to implement
2. Jockey switch signalling (#4) - High confidence, straightforward
3. Odds band manipulation (#8) - High confidence, valuable insight
4. Trainer/jockey patterns (#11) - Already partially implemented, expand

**Medium Priority:**
5. Late-money push (#1) - Requires minute-by-minute tracking
6. Bookmaker liability balancing (#12) - Requires cross-bookie data
7. Quiet market traps (#13) - Easy to detect, useful filter

**Low Priority (Advanced):**
8. Exchange overlay (#7) - Requires orderbook depth
9. Forecast engineering (#9) - Niche application
10. Media signal pumping (#15) - Requires external data sources

---

## 📚 References

- Original source: External market manipulation research document
- Date received: October 21, 2025
- Saved for future Oracle enhancement

---

**Status:** 📋 REFERENCE DOCUMENT - Not yet implemented  
**Next Steps:** Review and prioritize for Oracle 3.0 development  
**Estimated Implementation:** 4-6 weeks for Phase 1, 3-4 months for complete system

---

*"Every manipulation tactic is a pattern. Every pattern is an edge. Every edge is profit."*

🎭 **Market Manipulation Taxonomy - Saved for Oracle 3.0**

