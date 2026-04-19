# VÉLØ Post-Training Truth Explainer

**Status:** COMPLETE | **Date:** 2026-04-19
**Source:** 1,107 Live Audited Races

This is the master explanation engine for the first 1,000+ live races. It answers exactly what VÉLØ learned that the 1.3M training corpus could not teach it alone.

---

## 1. Global Scoreboard

- **Total Races:** 1,107
- **Strike Rate:** 19.8% (219 Wins)
- **Frame Rate:** 46.4% (514 Frames)
- **A-Tier Win Rate:** 41.2%

## 2. The Core Wounds vs. The Model Strength

The 1k live stack definitively proves that VÉLØ's primary leak is **execution discipline, not vision blindness**.

1. **Vision is Real:** We hit the frame in nearly 50% of all races. 
2. **Discipline is Weak:** 417 of our misses come directly from C and D tier races—complete "Amputation Zones" that the execution engine should have passed.
3. **Mid-Price Misrouting:** When the model fails in the 5-20 SP zone, it splits into **False Rank-1 Authority** (overcommitting to tight margins) and **Blindspot Winners** (missing the winner outside the top 5 entirely).

## 3. Product Misassignment
The biggest single operational failure was treating all 1,107 races as "WIN_ONLY" products. Retroactive assignment shows that over 100 of our misses should have been treated as `EW_CANDIDATE` or `FRAME_ONLY` plays, which would have monetized the 295 `true_frame` losses.

---

*This document serves as the root index for the Post-Training Truth Explainer suite.*
