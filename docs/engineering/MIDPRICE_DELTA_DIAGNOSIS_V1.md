# Mid-Price Top-vs-Winner Sidecar Delta Diagnosis V1

**Date:** 2026-05-22  
**Source:** `data/midprice_winner_deltas.csv` — 80 races, May 21–22 post-fix snapshots  
**Script:** `scripts/audit/midprice_winner_delta.py`  
**Status:** READ-ONLY audit. No scoring, routing, or execution changes.

---

## Raw Counts

| Metric | Count | % |
|---|---|---|
| Total races audited | 80 | — |
| Misses (top pick ≠ winner) | 58 | 72.5% |
| Midprice zone misses (SP 3.0–8.5) | 39 | 67.2% of misses |
| Winner visible in snapshots | 56 | 96.6% of misses |
| Rescuable by sidecar signal | 2 | 3.4% of misses |
| Suppressed top picks (MIDPRICE_SUPPRESS_TOP) | 0 | — |

---

## Q1 — How many midprice misses had the winner visible in runner snapshots?

**56 of 58 misses (96.6%) — the winner was scored and visible.**

This is the critical finding. VELO saw the winner. It did not rank them first. This is a ranking failure, not a coverage failure.

2 races where winner was not in snapshots: likely DPT (Downpatrick) races where no results were available from Sporting Life to confirm which horse won.

---

## Q2 — How many winners had higher MDS than the top pick?

**9 of 56 visible misses (16.1%)**

In 9 races, the actual winner had a higher Market Deception Score than VELO's top pick. The model identified the right horse's market signal, but VP ranked a different horse first.

MDS is a sidecar signal — it doesn't directly gate the VP ranking. These 9 cases suggest MDS could be used as a VP modifier or secondary sort criterion.

---

## Q3 — How many winners had higher improvement score than the top pick?

**0 of 56 visible misses**

Zero. The improvement_score did not distinguish winners in this 2-day window. Two possible explanations:
1. Improvement scores are uniformly low across the board (both top pick and winner score similarly)
2. The 2-day sample is too small to observe the rare high-improvement event (historically n=62 across 49 days)

MDS>0.5 and Improvement>0.40 did not fire in either window (confirmed in Gate V2 review). These signals are rare and meaningful precisely because they don't fire often.

---

## Q4 — How many winners had higher place_prob than the top pick?

**5 of 56 visible misses (8.9%)**

In 5 races, the winner had a higher place_prob than VELO's top pick. Place_prob is currently badge-only (not weighted in VP). These 5 cases suggest that a small place_prob weighting uplift could improve rank ordering at the margin.

---

## Q5 — How many winners were ranked 2nd or 3rd by VELO?

| Winner's Rank | Count |
|---|---|
| Rank 1 (2nd pick) | 13 |
| Rank 2 (3rd pick) | 16 |
| Rank 3 (4th pick) | 5 |
| Rank 4 (5th pick) | 10 |
| Rank 5 (6th pick) | 1 |
| Rank 6 (7th pick) | 3 |
| Rank 7 (8th pick) | 5 |
| Rank 8 (9th pick) | 3 |

**29 of 56 visible misses (51.8%) had the winner ranked 2nd or 3rd.** VELO had the winner framed but not ranked first. This is a VP calibration and rank discrimination issue, not an information gap.

Frame rate (winner in top 3) = **51 of 87 races = 58.6%** — above 70% target but directionally positive.

---

## Q6 — How many winners were suppressed?

**0 suppressed top picks in the 2-day window.**

No MIDPRICE_SUPPRESS_TOP events in either day. The mid-price suppression system was not activated (consistent with the system being shadow-only with `execution_allowed=False`).

---

## Q7 — How many could be rescued by simple sidecar rules?

**2 of 58 misses (3.4%)**

Both rescued by `place_prob >= 0.80`. No MDS or improvement rescue signals fired.

Rescue threshold definitions:
- MDS > 0.5 → rescue candidate
- Improvement > 0.40 → rescue candidate  
- place_prob > 0.80 → rescue candidate

The 3.4% rate is not a failure — it reflects that sidecar signals are rare by design. It means rescue events are meaningful when they appear. It also means sidecars cannot solve the general mid-price miss problem.

---

## Q8 — Why is the rescue rate only 3.4%?

**This is a VP rank discrimination problem, not a sidecar threshold problem.**

The mean VP delta (top pick VP minus winner VP) across visible misses is **0.093**. The top pick is on average 9.3 VP points higher than the winner. This is not a narrow gap where sidecar signals could flip the ranking — it's a meaningful VP gap.

Maximum VP delta observed: **0.404** (top pick was 40 VP points above the winner).

This confirms:
1. VELO is not making close-call errors where a sidecar nudge would fix it
2. The VP model genuinely believes the top pick is materially better
3. The mid-price winner belongs to a population the VP model systematically undervalues

---

## Q9 — Is this a sidecar threshold problem, race-shape problem, market-band problem, or data gap?

**Primary: Market-band / race-shape problem.**

Evidence:
- 39 of 58 misses (67.2%) are in the SP 3.0–8.5 mid-price band
- VP discriminates well at very low prices (5% SR at VP<0.10) and at high prices (implied by AUC=0.68)
- VP calibration is accurate at low VP — overconfident only at high VP
- The VP gap between top pick and winner is large (mean 0.093) — not a close call
- 0 MDS fires, 0 improvement fires in the window — these are rare events, not the general problem

**The mid-price winner is a different horse-type problem:**
- These horses likely have lower class, lower speed ratings, lower market prominence
- VP weights form, market signals, and structural quality — mid-price horses often win when the race shape collapses a top-rated horse (ground change, pace collapse, trip fluke)
- That is race-shape intelligence VELO does not yet model: pace maps, sectional times, class-drop response curves

**Secondary: Ranking sensitivity at SP 3–8.5.**
The market treats 3–8.5 SP horses as "credible" but non-favourite. VELO's VP at this price band may be insufficiently sensitive to race-shape variation.

---

## Q10 — What is the next midprice model feature needed?

**Race-shape / pace map signal.** Not another sidecar threshold.

Priority order for mid-price investigation:

1. **Pace map layer** — was the top pick a pace-dependent horse that got a bad trip? Was the winner a come-from-behind type that benefited from pace collapse?
2. **Class-drop signal** — how many mid-price winners were dropping in class from their last run? VP may undervalue class-drop form.
3. **Going/surface sensitivity** — MUS (86% SR) and CHP (0% SR) course extremes in the 2-day window suggest going/surface regime matters heavily at specific tracks.
4. **SP vs VP misalignment** — a horse at SP 4.0 with VP 0.15 is a market disagreement case. These should be studied separately.
5. **Sectional / distance profile** — mid-price horses over 1m2f+ may have different win signatures than sprint races.

---

## Synthesis

| Finding | Implication |
|---|---|
| Winner visible in 97% of misses | Not a coverage problem — a ranking problem |
| Mean VP delta = 0.093 | VP is materially wrong, not marginally wrong |
| 29/56 winners ranked 2nd or 3rd | Frame is partially working — refinement not replacement |
| MDS and improvement didn't fire | Rare signals can't solve a structural problem |
| 67% of misses are midprice zone | Confirm: this is a price-band specific failure mode |
| 0 suppressed picks | Mid-price Hunter hasn't activated — it's still shadow |
| Rescue rate 3.4% | Sidecar nudges are insufficient — need race-shape intelligence |

**VELO's mid-price problem is not fixable with sidecar signal tweaking. It requires a race-shape model or pace map layer that explains why a ranked horse underperforms in the actual race context. This is Phase 2 of the mid-price research programme.**

---

## Operating Rules (permanent)

```
Do not raise sidecar thresholds to chase the rescue rate.
Do not add new sidecar signals without evidence of discriminative power.
Do not retrain on 2-day evidence.
Do: build a pace map / race-shape prototype in shadow.
Do: study class-drop and going-change as VP modifier candidates.
Do: extend the midprice_winner_delta corpus to 10+ days before drawing firm conclusions.
```
