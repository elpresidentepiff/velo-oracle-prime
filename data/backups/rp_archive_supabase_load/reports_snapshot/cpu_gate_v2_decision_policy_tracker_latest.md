# CPU Gate V2 Decision Policy Tracker

**Generated:** 2026-05-23T09:37:03.956948+00:00
**FIX_DATE:** 2026-05-21 (first clean day after a33c5bd flatline fix)
**Status:** SHADOW/RESEARCH ONLY — NOT_APPROVED

---

## Decision Policy Progress

| Metric | Value |
|---|---|
| Top-pick decisions made | **87** |
| Decisions with outcomes | 80 |
| Excluded (no result) | 7 |
| Wins | 22 |
| SR | 27.5% |
| Baseline SR | 20% |
| SR vs baseline | +7.5% |
| Brier score | 0.2091 |
| Brier skill score | -0.0455 |
| Top-decile SR (n=8) | 37.5% |
| Best subgroup | B |
| Worst subgroup | X |
| Needed to Gate 1 (150) | **63** |
| Needed to Gate 2 (300) | **213** |
| Verdict | **NEEDS_MORE_DAYS** |

---

## Tier Breakdown

| Tier | n | Wins | SR | vs Baseline |
|---|---|---|---|---|
| A | 11 | 3 | 27.3% | +7.3% |
| B | 37 | 13 | 35.1% | +15.1% |
| C | 22 | 6 | 27.3% | +7.3% |
| X | 10 | 0 | 0.0% | -20.0% |

---

## VP Band Breakdown

| VP Band | n | Wins | SR | vs Baseline |
|---|---|---|---|---|
| VP_LT_20 | 41 | 10 | 24.4% | +4.4% |
| VP_20_30 | 22 | 7 | 31.8% | +11.8% |
| VP_30_40 | 12 | 3 | 25.0% | +5.0% |
| VP_GE_40 | 5 | 2 | 40.0% | +20.0% |

---

## By Date

| Date | n | Wins | SR |
|---|---|---|---|
| 2026-05-21 | 44 | 13 | 29.5% |
| 2026-05-22 | 36 | 9 | 25.0% |

---

## Promotion Gate

```
Gate 1 (n=150): First review — SR, Brier, top-decile analysis. NOT automatic promotion.
Gate 2 (n=300): Full policy review. NOT automatic promotion.
Verdict:        NEEDS_MORE_DAYS
Action:         ACCUMULATE_EVIDENCE — no promotion discussion until Gate 1
Production:     NOT_APPROVED (operator decision required at every gate)
```

No scoring changes. No model promotion. No live-state mutation.
