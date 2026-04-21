# VÉLØ Forensic Synthesis & Strategic Recovery Plan
**Date:** April 20, 2026  
**Analyst:** Manus (VÉLØ CTO / Strategic Edge Operator)  
**Scope:** Synthesis of the 1,107-race Sigma Forensic Audit (March 17 – April 19, 2026)

---

## Section A — Executive Verdict

VÉLØ is a functioning organism with a genuine, proven edge in specific conditions, but it is currently bleeding profit through structural leakage and inefficient pricing [1]. The system is exceptional at identifying the winner within its top two selections (36.1% top-2 coverage) and possesses a crown jewel in its A-Tier, which operates at a 41.2% strike rate [2] [3]. 

However, the model is not currently a profitable win-betting system at bookmaker Starting Price (SP) across its full volume. The organism as a whole runs at a -15.4% ROI, and every tested mechanical rank-2 lane produces negative win ROI [4] [5]. 

**What is working:**
The core probability ensemble is highly calibrated. The A-tier, particularly below 3/1 SP, is an elite lane (72.2% strike rate for odds-on, 46.9% for 2.0–3.0 SP) [2]. The system is structurally strong on All-Weather (AW) and National Hunt tracks [6].

**What is not working:**
The system fails catastrophically in the 5/1 to 20/1 SP mid-price band, which accounts for 23% of races but only a 5–11% win rate [1]. It is consistently deceived by market decoys on AW tracks [7]. Furthermore, it attempts to monetize tight-margin races and short-priced rank-2 horses where the bookmaker margin consumes the edge entirely [4].

**Where the main leakage is:**
1. **The Mid-Price Dead Zone (5.0–20.0 SP):** The model cannot accurately price competitive handicaps in this band, backing too many horses with place profiles rather than win profiles [1] [2].
2. **AW Market Decoys:** Following fake market steam on AW tracks accounts for 30% of all misses (167 races) [7].
3. **Bookmaker Margin:** The model's edge (+0.086 probability separation) is real, but smaller than the bookmaker's overround, turning a 20.5% strike rate into a -15.4% ROI [1] [5].

**The most likely root cause:**
The system is confusing "likely to run well" with "efficiently priced to win." It possesses a horse-finding engine that identifies live chances, but it lacks the price discipline and specific feature engineering (e.g., class drop, sectional pace) required to isolate true win-value bets in competitive mid-priced handicaps [8].

---

## Section B — Evidence-Based Forensic Findings

| Finding | Evidence from Data | Likely Cause | Impact |
|---|---|---|---|
| **A-Tier < 3.0 SP is Elite** | 119 A-tier races run at 41.2% win. Odds-on win at 72.2%. The 2.0–3.0 band wins at 46.9%. A-tier SP < 3.0 produces +5.4% ROI at bookmaker SP [2] [5]. | The core ensemble perfectly aligns with market reality at the top end of the confidence spectrum. | The only currently proven positive ROI lane. Must become the primary betting vehicle. |
| **The Mid-Price Killing Field** | 5–20 SP band accounts for 23% of races but only 5–11% win rate. Even A-tier drops to 6.2% win rate in the 5–8 SP band [1] [2]. | Missing feature engineering for class drops and sectional pace data. The model cannot separate competitive handicaps [8]. | Severe bankroll drain. Converts a winning system into a losing one through volume leakage. |
| **AW Market Decoy Contamination** | 167 misses (30% of total) are decoy races. AW tracks have a 19.3% decoy miss rate. Average decoy winner SP is 4.80 [7]. | Trainer-driven market dynamics on AW tracks. The `market_deception_score` detects it but is underweighted in selection [7] [8]. | High. Forces the model off the correct horse (often already in the top-3) onto a false favourite. |
| **Rank-2 is Vision, Not Profit** | Winner is rank-2 in 15.9% of races. However, 10 simulated rank-2 lanes all produced negative win ROI at SP (best was -7.6%) [3] [4]. | Bookmaker margin. Rank-2 winners average 5.41 SP, but breakeven requires 6.06 SP at the 16.5% strike rate [4]. | False hope. Do not implement a mechanical rank-2 win betting lane at bookmaker SP. |
| **Tight Margin Bleed** | 65.8% of all miss races had a `prob_gap` < 0.05 between rank-1 and rank-2 [8]. | The organism fires bets even when its confidence margin between the top two horses is statistically negligible. | Wasted stakes on coin-flip races where the model has no true conviction. |

---

## Section C — Racing Interpretation

Through a racing lens, VÉLØ is currently operating as a sophisticated form-reader that doesn't fully understand race-day intent or market mechanics. 

**The Mid-Price Handicap Problem:** In a 12-runner Class 4 handicap at Doncaster or the Curragh, VÉLØ identifies the horse with the most consistent recent speed figures and solid form [6]. However, it misses the horse dropping 5lb in the weights, fitted with first-time blinkers, and backed quietly from 12/1 to 6/1. VÉLØ's pick runs a solid 3rd (padding the frame rate), while the plot horse wins. This is why the system bleeds in the 5–20 SP band [8].

**The AW Decoy Dynamic:** On tracks like Lingfield and Wolverhampton, form is secondary to trainer intent. Connections will back their true contender early at 5/1. Later, a different horse from a high-profile yard is steamed into favouritism. VÉLØ's logic follows the late steam (the decoy), abandoning the actual winner, which was often sitting right there in VÉLØ's top-3 rankings [7]. 

**Track Regime Bias:** The model is a National Hunt and AW specialist (when decoy is filtered). NH races rely heavily on established form, jumping ability, and stamina—features VÉLØ handles well. It struggles profoundly at major flat venues (Nottingham 0 wins, Curragh 4.8%, Doncaster 6.2%) where class dynamics, draw bias, and tactical pace dictate the outcome [6].

---

## Section D — Root-Cause Tree

1. **Primary Leak:** Bookmaker Margin vs. True Edge
   - The system's probability separation is real, but it is betting into markets where the bookmaker overround is larger than the model's edge. Betting rank-1 or rank-2 blindly at SP is mathematically doomed [4] [5].

2. **Secondary Leaks:** The Mid-Price Dead Zone & Market Decoys
   - Betting into the 5.0–20.0 SP band without class-drop or pace features [8].
   - Following fake market steam on AW tracks (167 misses) [7].

3. **Structural Weaknesses:** Lack of Price Discipline & Confidence Gating
   - Firing bets when the `prob_gap` between rank-1 and rank-2 is < 0.05 [8].
   - Firing bets when the absolute `velo_prime_prob` is < 0.15 (11.6% win rate) [8].

4. **Execution Weaknesses:** Track Blindspots
   - Operating at tracks where the model is uncalibrated (Nottingham, Curragh, Doncaster, Ascot) [6].

5. **Things that look bad but are actually noise:**
   - The 9% strike rate day on April 18. This was variance caused by an unusual cluster of outsider wins, not a structural model collapse [1].

---

## Section E — Fix Plan

### 1. Immediate Cuts (Stop Right Now)
- **Cease all primary win bets in the 5.0+ SP band.** The model cannot price this zone. Let them come to us. If a horse drifts above 5.0, it becomes a frame/place candidate only [2].
- **Cut the track blindspots.** Hard-filter and suppress all bets at Nottingham, Curragh, Doncaster, and Ascot until Ireland-specific and premier-flat models are built [6].
- **Kill the mechanical Rank-2 SP lane.** The simulation proves it is a trap. Do not deploy a two-horse system at bookmaker SP [4].

### 2. Refinements (Tighten the Logic)
- **Implement the AW Decoy Containment Filter.** On AW tracks, if `market_deception_score` > 0.6, suppress the rank-1 pick. Do not follow the steam [7].
- **Enforce the `prob_gap` Gate.** No bets in C/D/X tiers if `prob_gap` < 0.05. In A/B tiers, flag for review [8].
- **Enforce the `velo_prime_prob` Floor.** Hard pass on any race where the top probability is < 0.15 [8].
- **Directional MDS Routing.** If `market_deception_score` > 0.3 AND the steam is *toward* our rank-1 pick, promote this to a maximum confidence bet (historical 72.9% strike) [8].

### 3. Expansion Opportunities (Press the Edge)
- **The A-Tier Fortress:** The A-Tier picks at SP < 3.0 are the gold standard. This lane should receive maximum staking priority [2] [5].
- **Exchange Pricing (BSP):** The model is 0.15 SP units away from breakeven. Transitioning execution to Betfair SP (which typically carries a 10-15% premium over bookmaker SP) will likely flip A-tier and B-tier into positive ROI [5].
- **Each-Way on High Place-Prob:** The rank-2 lane with `place_prob` > 0.5 is within 2% of breakeven on an EW basis. With BSP pricing, this becomes a viable expansion lane [4].

---

## Section F — Implementation Plan

**1. A-Tier Fortress Policy**
- **What to change:** Hard-gate automated execution to A-tier selections with an SP < 3.0.
- **Why it matters:** This is the only proven positive ROI lane (+5.4%). It stops the bleeding immediately.
- **How to implement:** Update the execution router to require `tier == 'A'` and `current_price < 3.0`.
- **Metric to track:** ROI of this specific lane.
- **Timeframe:** Immediate implementation; review after 100 races.

**2. AW Decoy Containment**
- **What to change:** Apply a suppression filter for AW tracks when `market_deception_score` > 0.6.
- **Why it matters:** Eliminates 30% of all misses caused by fake market moves.
- **How to implement:** Add a conditional in the selection logic: `if surface == 'AW' and market_deception_score > 0.6: return 'PASS'`.
- **Metric to track:** Reduction in `market_decoy_followed` misses.
- **Timeframe:** Immediate implementation.

**3. Confidence Gating (`prob_gap` and `prime_prob`)**
- **What to change:** Introduce hard floors for bet placement.
- **Why it matters:** Prevents the model from guessing in tight or low-quality races.
- **How to implement:** Add logic: `if prob_gap < 0.05 or velo_prime_prob < 0.15: return 'PASS'`.
- **Metric to track:** Strike rate improvement in remaining executed bets.
- **Timeframe:** Immediate implementation.

**4. Price Discovery & BSP Transition**
- **What to change:** Shift performance tracking and eventual execution from bookmaker SP to Betfair SP (BSP).
- **Why it matters:** Bookmaker margin is the primary leak. BSP is the only path to monetizing the existing signal.
- **How to implement:** Acquire historical BSP data for the 1,070 races. Re-simulate ROI. Prepare exchange API integration [5].
- **Metric to track:** BSP ROI vs Bookmaker SP ROI.
- **Timeframe:** Phase 1 (Data acquisition) immediately; Phase 2 (Execution) Q2 2026.

---

## Section G — Monitoring Dashboard

To ensure the fixes hold, the weekly review dashboard must track:

1. **A-Tier < 3.0 SP ROI:** The health of the core engine.
2. **BSP vs SP Beat Rate:** Are we consistently securing prices above the bookmaker SP?
3. **Decoy Miss Rate on AW:** Has the filter successfully suppressed the 19.3% leak?
4. **Strike Rate by Odds Band:** Specifically monitoring the 5.0–20.0 band to ensure we are no longer bleeding capital there.
5. **Tight Margin Avoidance:** Verifying that races with `prob_gap` < 0.05 are successfully being passed.
6. **Track Performance Alerts:** Flags for any track dropping below a 15% strike rate over a 20-race rolling window.

---

## Section H — Hard Truths

1. **You are currently betting the bookmaker's margin, not your edge.** The model is good, but it is not good enough to beat a 20% bookmaker overround at flat stakes. The obsession with rank-2 recovery is a distraction from the real issue: you need better prices, not more bets.
2. **The model cannot handicap competitive mid-price races.** The 5–20 SP band is a slaughterhouse. Stop trying to force the model to find 10/1 winners in 16-runner fields. It doesn't have the feature data (class drops, sectionals) to do it.
3. **Volume is vanity; ROI is sanity.** You have been taking pride in a 20.5% overall strike rate while ignoring a -15.4% ROI. The system needs to bet less frequently, with much tighter constraints, at better prices. 

---
### References
[1] `VELO_SIGMA_FORENSIC_AUDIT.md`  
[2] `VELO_A_TIER_FORENSIC_GOLD_STANDARD.md`  
[3] `VELO_RANK_DEPTH_RECOVERY_AUDIT.md`  
[4] `VELO_RANK2_SIMULATION_RESULTS.md`  
[5] `VELO_PRICE_DISCOVERY_PREP.md`  
[6] `VELO_TRACK_REGIME_BLINDSPOTS.md`  
[7] `VELO_MARKET_DECOY_FORENSIC.md`  
[8] `VELO_FEATURE_GAP_REFINEMENT_PLAN.md`  
