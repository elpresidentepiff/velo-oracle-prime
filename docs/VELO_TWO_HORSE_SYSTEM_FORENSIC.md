# VÉLØ Two-Horse System — Forensic Case
**Generated:** 2026-04-19 | **Verdict: CONDITIONAL CASE PROVEN**

---

## The Core Question

Does surfacing a second ranked horse convert enough misses into wins to justify operational complexity?

**Short answer:** Yes — but only in specific lanes. Not universally.

---

## The Evidence

### Rank-2 Recovery Across All 556 Misses

| Scenario | Count | % of misses |
|----------|-------|-------------|
| Winner was rank-2 | 91 | **16.4%** |
| Winner was rank-3 | 74 | 13.3% |
| Top-2 would have covered | 91 | 16.4% |
| Top-3 would have covered | 165 | 29.7% |
| Top-5 would have covered | 308 | 55.4% |

**Adding a 2nd pick converts 16.4% of all misses into wins.**  
That is 91 additional wins across 556 misses — or 91 additional wins across 1,070 total races.

If the single-pick system runs at 20.5% (219 wins), a top-2 system would recover 91 of the 556 misses:
- **New effective coverage: 378/1,070 = 35.3% of races have at least one of our top-2 correct.**

### SP Profile of Rank-2 Recoveries

| Metric | Value |
|--------|-------|
| Average SP | 5.4/1 |
| Maximum SP | 41.0/1 |
| Minimum SP | 1.3/1 |
| SP ≥ 5/1 | 32 (35.2%) |
| SP ≥ 10/1 | 7 (7.7%) |

**The 2nd pick average SP is 5.4/1.** Not an outsider system — these are competitive mid-range horses that the model correctly identified as second-best but did not surface.

---

## Where the Case Is Strong

### short_fav_won class (66 misses)
- Top-3 recovery: **51.5%**
- When a short favourite beats our pick, our top-3 contained it in half of cases.
- Both horses likely at similar prices (2–5/1).
- **A-B tier, 2nd pick, short-price race = strongest 2-horse lane.**

### market_decoy_followed class (94 misses)
- Top-3 recovery: **38.3%**
- When a decoy fires on AW, the real winner is often already in our top-3.
- Avg SP in decoy races: 4.8/1.
- **2nd pick in AW races with high market_deception_score = second-strongest lane.**

### Tight-margin races (rank-1 vs rank-2 gap < 0.05)
- 363 miss races had a gap < 0.05 between rank-1 and rank-2 scores.
- 59 of those (16.3%) had the winner at rank-2.
- **When our model is uncertain (small gap), the 2nd pick is disproportionately relevant.**

### Rank-2 with high place_prob (>0.5)
- 143 miss races where rank-2 had place_prob > 0.5
- 29 of those (20.3%) had the winner at rank-2.
- **The place_prob signal on the rank-2 horse is a real secondary surfacing criterion.**

---

## Where the Case Is Weak

### outsider_won class (90 misses)
- Top-3 recovery: **12.2%**
- When a genuine outsider (20/1+) wins, our rank-2 is almost never it.
- Adding a 2nd pick does not solve the outsider problem. It is variance.

### mid_priced_won class (241 misses)
- Top-3 recovery: **29.5%** — looks ok but misleading.
- These are 241 races where something in the 5–20 range won.
- Rank-2 recovery (18%) is in this zone, but avg rank-2 SP is 5.4 — meaning the 2nd pick is not the 12/1 winner, it is the 4/1 runner-up.
- **A 2nd pick in the mid-price miss zone catches close misses, not value misses.**

### outsider_hedge_omitted (29 misses, avg 18/1)
- Rank-2 recovery: only 7% (2 races).
- The 20/1+ winners in this class are typically rank 5–8 in the full_analysis.
- **The 2-horse system does not recover these. They require a dedicated longshot-signal hedge, not a rank-2 pick.**

---

## A-Tier 2-Horse Forensic

| Metric | Value |
|--------|-------|
| A-tier total misses | 26 |
| Winner at rank-2 | 5 |
| Winner in top-3 | 9 |
| Top-3 recovery on A misses | 34.6% |

**The 2-horse case is weakest on A-tier.** Only 5 rank-2 recoveries on 26 A-tier misses (19.2%). A-tier already wins at 41.2% — adding a 2nd pick gives marginal return on the premium lane.

The 2-horse system's primary value is on **B-tier and C-tier decoy/short-fav races**, not on A-tier.

---

## Forensic Conclusion

| Question | Answer |
|----------|--------|
| Is there a real 2-horse system? | **Yes, conditionally.** |
| Where is it strongest? | short_fav races (B-tier), AW decoy races, tight-margin races |
| Where does it not work? | outsider_won class, mid-priced 5–20 zone (value gap, not rank gap) |
| What's the 2nd pick selection criterion? | rank-2 by velo_prime_prob WHERE (place_prob > 0.5 OR prob_gap < 0.05 OR market_deception_score > threshold) |
| Does it work on A-tier? | Marginally. Not the priority lane for 2-horse. |
| Is the ROI case proven? | Not yet. Forensic case is proven. ROI case requires pricing model. |

---

## Next Step (Evidence-Based)

Before implementing operationally:

1. Simulate the 2-horse system on the 1,070-race base at realistic prices
2. Quantify: would 91 additional wins at avg 5.4/1 cover the cost of 91 additional losing positions?
3. Apply the conditional filter (tight margin OR high place_prob OR AW decoy flag) to reduce the 2nd pick to only the strongest cases
4. Target: B-tier short-fav and decoy races specifically

**Do not implement universally. Prove the ROI lane first.**
