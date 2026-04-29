# VÉLØ Special Day Report — 2026-04-28

**75.0% VP≥0.30 frame | 17.2% overall SR | 58.6% overall frame**

*Generated: 2026-04-29 00:44 UTC*

---

## Summary

| Metric | Value | Context |
|---|---|---|
| Total verdicts | 29 | — |
| Matched outcomes | 29 | non-X tier |
| X-tier excluded | 0 | correct behaviour |
| Strike rate | **17.2%** | baseline 20% |
| Frame rate | **58.6%** | target 70% |
| Baseline | SR AT baseline (20%) | Frame BELOW target (70%) | — |

---

## VP Band Performance

| Band | n | Wins | SR | Frame |
|---|---|---|---|---|
| VP<0.20 | 2 | 0 | 0.0% | 100.0% |
| VP 0.20-0.30 | 15 | 1 | 6.7% | 40.0% |
| VP 0.30-0.40 | 7 | 2 | 28.6% | 85.7% |
| VP>=0.40 | 5 | 2 | 40.0% | 60.0% |
| **VP≥0.30 combined** | **12** | **4** | **33.3%** | **75.0%** |
| **VP≥0.30 + Tier A** | **6** | **2** | **33.3%** | **66.7%** |

---

## Tier Performance

| Tier | n | Wins | SR | Frame |
|---|---|---|---|---|
| Tier A | 6 | 2 | 33.3% | 66.7% |
| Tier B | 6 | 1 | 16.7% | 33.3% |
| Tier C | 14 | 2 | 14.3% | 57.1% |
| Tier D | 3 | 0 | 0.0% | 100.0% |

---

## Sidecar Highlights

- MDS>0.5: 2 races fired
- Improvement>0.40: 1 races fired
- Place prob>0.80: 8 races fired

---

## Miss Class Breakdown

| Miss Class | Count |
|---|---|
| mid_priced_won | 10 |
| short_fav_won | 2 |

**Mid-price misses (SP 3.0–8.5):** 10 (83.3% of all misses)
Winner SPs: [3.25, 3.5, 3.5, 4.0, 5.0, 6.5, 7.0, 7.0, 7.0, 8.5]

**Short-favourite misses (SP <3.0):** 2
Winner SPs: [1.5, 1.83]

---

## Course Notes

| Course | n | Wins | SR | Frame |
|---|---|---|---|---|
| Lingfield (AW) | 7 | 1 | 14.3% | 71.4% |
| Southwell (AW) | 7 | 0 | 0.0% | 42.9% |
| Epsom | 6 | 1 | 16.7% | 33.3% |
| Yarmouth | 6 | 2 | 33.3% | 100.0% |
| Punchestown (IRE) | 3 | 1 | 33.3% | 33.3% |

---

## Learned Patterns

Patterns saved: 9

- PRIME hit: Balgowan @ prob=0.2567 won Lingfield (AW) 2:15
- PRIME hit: Travel Agent @ prob=0.3009 won Lingfield (AW) 2:45
- PRIME hit: Port Road @ prob=0.2589 won Lingfield (AW) 3:45
- PRIME hit: Force Noir @ prob=0.6742 won Naas (IRE) 6:45
- PRIME hit: Runman @ prob=0.6162 won Epsom 2:05
- PRIME hit: Wild Thoughts @ prob=0.4754 won Lingfield (AW) 7:50
- PRIME hit: Sword Of Wessex @ prob=0.3564 won Yarmouth 3:57
- PRIME hit: Moonhall Lass @ prob=0.3751 won Yarmouth 5:03
- PRIME hit: Il Etait Temps @ prob=0.2980 won Punchestown (IRE) 6:05

---

## Router Evidence Contribution

| Lane | n | ROI | Status |
|---|---|---|---|
| V1_BASE | 27 | +11.5% | WATCHLIST |
| V2_CLASS4_ONLY | 17 | +30.2% | LANE_ACTIVE |
| V6_GOLD_SEAM | 5 | +115.0% | LOW_SAMPLE |

**Day contribution:** NEUTRAL — no qualifying results added to innovation protocol from this date

---

## Audit Conclusion

SR at baseline — normal day for winner conversion. Frame rate 58.6% below 70% target — partial contender detection. Primary miss class: mid-priced winners (83.3% of misses in SP 3–8.5 zone).

---

## Research Tags

- `MID_PRICE_WINNER_MISS_CLASS`
- `VP30_FRAME_STRENGTH`
- `VP30_SR_STRONG`
- `SHORT_FAV_OVERRIDE_NEEDED`

---

## Signal Attribution Analysis

Candidate lane conditions evaluated against today's races.
Shadow evidence only — no execution decisions.

### Lane Firing Summary

| Lane | Fired | Wins | Frames | Day SR | Day Frame |
|---|---|---|---|---|---|
| 🔥 MDS_HIGH | 2 | 1 | 2 | 50% | 100% |
| ✅ VP30_TIER_A | 6 | 2 | 4 | 33% | 67% |
| 📈 IMPROVE_HIGH | 1 | 1 | 1 | 100% | 100% |
| 🟡 PLACE_HIGH | 8 | 3 | 6 | 38% | 75% |
| ⚠️ B_LOW_VP | 3 | 0 | 0 | 0% | 0% |
| 🔬 MID_PRICE_FORENSICS | 10 | 0 | 0 | 0% | 0% |

**Strongest signal today:** MARKET_DECEPTION_HIGH — fired 2x, day SR 50.0%, Elite signal. Historical SR=54.8% at n=31.

### Race-Level Attribution (signal races only)

| Time | Course | Outcome | VP | Tier | Lanes Fired |
|---|---|---|---|---|---|
| 2:05 | Epsom | WIN | 0.616 | A | MARKET_DECEPTION_HIGH VP30_TIER_A IMPROVEMENT_SCORE_HIGH PLACE_PROB_HIGH |
| 2:20 | Southwell (AW) | MISS | 0.241 | C | MID_PRICE_WINNER_FORENSICS |
| 2:30 | Punchestown (IRE) | MISS | 0.494 | A | VP30_TIER_A MID_PRICE_WINNER_FORENSICS |
| 2:40 | Epsom | MISS | 0.591 | A | VP30_TIER_A PLACE_PROB_HIGH MID_PRICE_WINNER_FORENSICS |
| 2:47 | Yarmouth | PLACED | 0.491 | A | MARKET_DECEPTION_HIGH VP30_TIER_A PLACE_PROB_HIGH |
| 3:15 | Epsom | MISS | 0.257 | B | B_TIER_LOW_VP_SUPPRESS MID_PRICE_WINNER_FORENSICS |
| 3:30 | Southwell (AW) | MISS | 0.251 | B | B_TIER_LOW_VP_SUPPRESS |
| 3:50 | Epsom | MISS | 0.306 | B | MID_PRICE_WINNER_FORENSICS |
| 3:57 | Yarmouth | WIN | 0.356 | C | PLACE_PROB_HIGH |
| 4:35 | Southwell (AW) | MISS | 0.25 | C | MID_PRICE_WINNER_FORENSICS |
| 4:43 | Lingfield (AW) | PLACED | 0.369 | A | VP30_TIER_A PLACE_PROB_HIGH |
| 4:58 | Epsom | MISS | 0.222 | C | MID_PRICE_WINNER_FORENSICS |
| 5:25 | Punchestown (IRE) | MISS | 0.2 | C | MID_PRICE_WINNER_FORENSICS |
| 5:35 | Yarmouth | PLACED | 0.32 | C | PLACE_PROB_HIGH |
| 5:42 | Southwell (AW) | MISS | 0.213 | C | MID_PRICE_WINNER_FORENSICS |
*... +3 more races in JSON*

---

## Elite Day Flag

**Elite day:** ✅ YES
**Reason:** MDS_HIGH fired
**Dashboard watch recommended:** ✅ YES
**Note:** Elite signal fired today — add to daily dashboard accumulation tracker.

---

## Operator Visibility Gaps

**ELITE_SIGNAL_NOT_SURFACED** (6 races)

*6 races fired elite candidate lane signals (MDS_HIGH / VP30_TIER_A / IMPROVE_HIGH) that were not visible in the standard Telegram output.*

Fix: Add VÉLØ SIGNAL STACK panel to Telegram output (see design doc).

**SUPPRESS_WARNING_NOT_SURFACED** (3 races)

*3 races were in the Tier B VP<0.30 suppress zone but no warning appeared in Telegram output.*

Fix: Add suppress warnings to VÉLØ SIGNAL STACK panel.

> **Telegram Signal Attribution Panel required.** See `docs/evidence/VELO_TELEGRAM_SIGNAL_ATTRIBUTION_PANEL_V1.md`

---

## Operator Visibility Gap

**A. Which elite signals fired or would have fired**

- `MARKET_DECEPTION_HIGH` fired 2 times
- `VP30_TIER_A` fired 6 times
- `IMPROVEMENT_SCORE_HIGH` fired 1 time
- `PLACE_PROB_HIGH` fired 8 times
- `B_TIER_LOW_VP_SUPPRESS` fired 3 times

**B. Whether the operator saw them**

- No candidate-lane badge was surfaced in the standard Telegram day-of output.
- The operator saw Tier, reasons, execution state, and numeric MDS context, but not the badge stack.
- Result: 6 elite-signal races and 3 suppress-zone races were materially under-explained at the operator layer.

**C. What Telegram should show in future**

- explicit VP line
- `VP30_TIER_A`, `MDS_HIGH`, `IMPROVE_HIGH`, `PLACE_HIGH` badges
- `B_LOW_VP` suppress warning
- `MID_PRICE_FORENSICS` risk warning
- per-badge evidence line: `n / SR / frame / status`
- operator footer: `SHADOW EVIDENCE ONLY - NO STAKING AUTOMATION`

**D. Why 2026-04-28 matters**

- It was the first proven elite-day attribution test after the candidate-lane work.
- `MDS_HIGH` fired twice and produced a 50% day SR with 100% day frame.
- The day proves the signal layer can identify meaningful compression that the operator still could not fully see.

**E. What remains shadow-only**

- candidate lanes
- signal attribution panel
- shadow ledger promotion logic
- all staking and execution promotion decisions

---
*VÉLØ Special Day Report — 2026-04-28 | 2026-04-29 00:44 UTC*
