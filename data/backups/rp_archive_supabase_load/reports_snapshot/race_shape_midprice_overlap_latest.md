# Race Shape vs Midprice Miss Overlap — 2026-05-22

**Generated:** 2026-05-23T02:34:54.451957+00:00
**Research status:** SHADOW/RESEARCH ONLY — no scoring changes

---

## V2 Research Questions

| Question | Finding |
|---|---|
| Q1: Midprice misses in COMPRESSED races | **2** of 27 misses |
| Q2: Midprice misses in FAV_VULNERABLE races | **17** of 27 misses |
| Q2b: FAV_VULNERABLE flag fired | **20** of 27 misses |
| Q3: High top3 VP compression (<0.05) | **17** of 27 misses |
| Q4: Winner ranked 2nd or 3rd in snapshots | **13** of 27 misses (48.1%) |
| Q5: Winner visible in snapshots | **25/27** = 92.6% |
| Q6: Shadow tracking candidates (shape flags fired) | **24** races |

---

## Shape Status in Misses

| Race Shape Status | Miss Count | % of Misses |
|---|---|---|
| FAV_VULNERABLE | 17 | 63.0% |
| MIDPRICE_TRAP | 4 | 14.8% |
| COMPRESSED | 2 | 7.4% |
| CLEAR_TOP | 2 | 7.4% |
| CHAOTIC | 1 | 3.7% |
| UNKNOWN | 1 | 3.7% |

---

## Winner Visibility

Winner visible in snapshots: **25/27** = **92.6%**

This confirms the V2 hypothesis: the model *sees* the winner but ranks it wrong. This is a ranking failure, not a coverage failure.

Winner ranked 2nd or 3rd (VP rank 1 or 2): **13/27** = **48.1%**

These are the races where a small VP adjustment could flip the pick correctly.

---

## Shadow Tracking Recommendations

Race-shape tags that fired most in misses:
  - COMPRESSED — 2 misses
  - FAV_VULNERABLE — 17 misses
  - MIDPRICE_TRAP races — shadow track midprice_density >= 0.45
  - High top3 compression (VP spread < 0.05) — 17 misses

**Candidate races for shadow tracking:**
  - rp_GOO_20260522_1.57
  - rp_GOO_20260522_3.07
  - rp_GOO_20260522_3.42
  - rp_GOO_20260522_4.17
  - rp_GOO_20260522_4.52
  - rp_HAY_20260522_1.45
  - rp_HAY_20260522_2.20
  - rp_HAY_20260522_3.30
  - rp_HAY_20260522_4.05
  - rp_HAY_20260522_5.15
  ... (14 more)

---

## Corpus Size Note

Current corpus: 27 miss races from 2026-05-22 (1 day).
Corpus needs 300+ races before quartile SR analysis (see MIDPRICE_HUNTER_V2_RESEARCH_PLAN.md).
Run `midprice_winner_delta.py` daily to accumulate.

---

## Governance

```
No scoring changes.
No VP adjustments.
No routing changes.
All findings are research hypotheses — need 300+ race corpus to validate.
```
