# VÉLØ Operating Truth Board V1

**Evidence basis:** 49 race days | 1391 sigma rows
**Last updated:** 2026-04-28
**This document is the single authoritative answer to: "What does VÉLØ actually do?"**

---

## A. What Is Working

**1. Contender detection is real.**
VP ≥ 0.30 produces 69.3% frame rate across 345 races over 49 days. The system is consistently identifying horses that finish in the top 3. This is not random �� it is a structured, reproducible signal.

**2. Tier A is proven.**
162 Tier A races: SR=40.1%, Frame=77.2%. VÉLØ's highest-confidence tier is performing at 2× global baseline SR and above the 70% frame target. Tier A picks are landing in the frame on almost 4 in 5 races.

**3. VP ≥ 0.40 is exceptional.**
100 races at VP ≥ 0.40: SR=44.0%, Frame=85.0%. This is the strongest VP band. When VÉLØ fires with VP above 40%, the pick finishes in the top 3 in 85 of 100 races.

**4. Market deception score is a major asset.**
31 races where market_deception_score > 0.5: SR=54.8%, Frame=96.8%. This is the highest-lift signal in the entire system — +34% lift over global baseline. When VÉLØ detects market structure supporting its pick, it is almost always correct.

**5. Improvement score predicts winners.**
62 races with improvement_score > 0.40: SR=43.5%, Frame=82.3%. The improvement specialist model is identifying horses about to step forward in performance, and those horses are winning.

**6. The VP-performance relationship is monotonic and consistent.**
The clean monotonic VP band table (VP<0.20=14.5% SR → VP≥0.40=44.0% SR) holds across all 49 days. VP is a real signal, not noise.

---

## B. What Is Not Working

**1. Winner conversion in the SP 3.0–8.5 zone.**
58% of all misses are in this price zone. VÉLØ is framing correctly but failing to separate the winner from the frame in mid-priced races. This is the primary unsolved problem.

**2. Tier B / VP < 0.30 volume.**
SR=16.9%, Frame=44.1%, n=272. These picks are below random. They make up 22% of the system's prediction volume but add no edge. They are diluting the global frame rate from 70%+ to 48.4%.

**3. Market decoy misses.**
87 races classified as `market_decoy_followed` — the system followed a market signal that turned out to be a decoy. This is the third-largest miss class. The market deception model is intended to address this, but the interaction is not yet fully wired.

**4. Short-favourite misses.**
81 races where a short favourite won despite VÉLØ backing a different horse. These represent races where the market's signal (strong implied probability at short price) should have overridden the model's ranking.

**5. Tier C, D, X drag.**
Combined n=709 (57% of all predictions), SR ranges from 12–16%. These tiers provide essentially no edge and are dragging the global frame rate. The system is generating too much low-confidence volume.

---

## C. What Is Promising

**1. VP ≥ 0.30 + Tier A lane.**
This combination has 49-day proof at n=162. It is the most natural first candidate lane for future paper execution trials.

**2. V2_CLASS4_ONLY router lane.**
17 qualifying results, SR=41.2%, ROI=+30.2%. The class 4 / Structure archetype combination is performing strongly in the innovation protocol dataset. 3 more qualifying results reaches the WATCHLIST gate.

**3. MDS > 0.5 combined with VP ≥ 0.30.**
Two independently strong signals converging on the same pick is the highest-confidence intersection available. This combination does not yet have dedicated tracking — it is the next candidate lane to design.

**4. Improvement score + VP ≥ 0.30.**
Two proven signals. Combined they should produce even stronger SR. Not yet tracked as a combined lane.

---

## D. What Should Be Suppressed

**1. Tier B VP < 0.30 predictions.**
Confirmed drag. SR=16.9%. These predictions should not be acted upon and should be excluded from any candidate lane design.

**2. Archetype=Compression as standalone signal.**
No lift over global baseline (-0.6%). Not a predictor.

**3. Market-aware variants that incorporate live odds as primary input.**
Recrowding risk. Market is a benchmark, not a boss.

**4. Any Tier C/D/X prediction without a strong secondary signal (VP≥0.40 + proven sidecar).**
These tiers are confirmed low-edge zones. Acting on them requires exceptional secondary evidence.

---

## E. What Stays Shadow-Only

**1. All router lanes (V1, V2, V6).**
Shadow annotation only. No staking until n≥100 on any lane.

**2. Candidate lane combinations (MDS>0.5+VP≥0.30, improvement_score>0.40+VP≥0.30).**
Must be tracked as shadow lanes for 30+ qualifying results before any paper execution consideration.

**3. Playbook G V3 core.**
Offline research candidate only. Has not run on live data. Cannot be promoted without shadow validation producing closed results.

---

## F. What Deserves Candidate-Lane Tracking

In priority order — these lanes should be created as shadow annotations and tracked:

1. **VP_30_TIER_A** — VP ≥ 0.30 + Tier A (existing evidence: n=162, PROVEN)
2. **MDS_GT_0.5** — market_deception_score > 0.5 + VP ≥ 0.30 (n=31, exceptional lift)
3. **IMPROVEMENT_GT_0.4** — improvement_score > 0.40 + VP ≥ 0.30 (n=62, strong)
4. **PLACE_PROB_COMBINED** — place_prob > 0.80 + VP ≥ 0.30 (n=392, large sample)

None of these lanes should be staked. They should produce shadow P&L for ledger accumulation.

---

## G. What Needs More Data

- V6_GOLD_SEAM: n=5. Need n=20 before any conclusion.
- V2_CLASS4_ONLY: n=17. Need n=30 for SHADOW_CANDIDATE.
- G Shadow multiplier: wiring broken. Fix before next audit.
- RPDC cash window flag: n=1. Needs months of accumulation.
- MDS > 0.5 as standalone lane: n=31. Watch for regression.
- Improvement score > 0.40 as standalone lane: n=62. Track separately.

---

## H. What The Company Should Say Publicly

**VÉLØ is an auditable racing intelligence operating system.**

It analyses race data, generates predictions with measurable confidence bands, audits every prediction against closed results, and accumulates evidence to improve over time.

The system has demonstrated:
- Consistent contender identification (VP ≥ 0.30 band: 69.3% frame rate across 49 days)
- Strong high-confidence performance (Tier A: SR=40.1%, Frame=77.2%, n=162)
- Exceptional sidecar signal lift (market_deception_score: SR=54.8% at n=31)
- Reproducible VP-performance relationship across all operating days

These results are from a live closed-result audit. Every prediction is timestamped, traceable, and reconciled against public race outcomes.

VÉLØ is not a gambling bot. It is a decision-support and analytics system for horse racing intelligence.

---

## I. What The Company Must Not Overclaim

1. **Do not claim the system is profitable.** Router lanes are shadow-only. No live staking has occurred. P&L figures are research estimates only.

2. **Do not claim the frame rate is 70%+.** Global frame rate is 48.4%. The 70%+ figure applies to specific bands (VP≥0.30, Tier A). Use the correct numbers in the correct context.

3. **Do not claim modifications caused improvements.** Modification impact is observed correlation, not proven causality. The VeloPrimeEnsemble is the foundational change; everything else is incremental and under ongoing measurement.

4. **Do not claim V6_GOLD_SEAM is real.** n=5. The 115% ROI figure is not meaningful at that sample size.

5. **Do not claim VÉLØ solves mid-priced winner selection.** 58% of misses are in the SP 3–8.5 zone. This is the primary open research problem.

6. **Do not claim any signal guarantees winners.** VP ≥ 0.40 hits at 44%. Even the best bands miss more than half the time.

---

## System Summary

> VÉLØ finds contenders reliably. It converts those contenders to winners most convincingly when VP ≥ 0.30 + Tier A + high sidecar scores align. Its primary weakness is mid-priced winner separation. Its strongest unexploited asset is the market_deception_score sidecar. The router lanes are accumulating evidence but are not yet promoted. The evidence basis is 49 live race days, 1391 predictions, and zero simulated or hypothetical results.

---

*VÉLØ Oracle Prime — Operating Truth Board V1*
*Updated when signal rankings change or after each Unified Evidence Audit*
