# CASHRUN Activation Audit

**Generated:** 2026-05-15T03:27:32.632240+00:00
**Date range:** 2026-05-01 → 2026-05-15
**Total rows:** 2543 | **Matched to results:** 1591

## Bucket Performance

| Bucket | n | Results | SR | Place% | ROI | Avg SP | VP30% | Verdict |
|--------|---|---------|-----|--------|-----|--------|-------|---------|
| CASHRUN_READY | 1 | 0 | 0.0% | 0.0% | +0.000 | 0.0 | 0.0% | INSUFFICIENT_SAMPLE |
| CASHRUN_WATCH | 15 | 6 | 16.7% | 33.3% | -0.250 | 5.5 | 0.0% | INSUFFICIENT_SAMPLE |
| WEAK_SIGNAL | 162 | 102 | 10.8% | 30.4% | +0.510 | 14.6 | 3.1% | EVIDENCE_BUILDING |
| SUPPRESS | 1474 | 900 | 10.8% | 32.9% | -0.261 | 27.9 | 1.8% | EVIDENCE_BUILDING |

## Crossover Analysis

| Signal | n | Results | SR | Place% | ROI |
|--------|---|---------|-----|--------|-----|
| WATCH + VP30 | 0 | 0 | 0.0% | 0.0% | +0.000 |
| WEAK + VP30 | 5 | 3 | 33.3% | 66.7% | +0.833 |
| SUPPRESS + VP30 | 26 | 17 | 58.8% | 82.3% | +0.699 |
| Any + VP30 | 31 | 20 | 55.0% | 80.0% | +0.719 |

## Verdict Key
- `BOOSTER_CANDIDATE` — ROI >5% at n≥20, consider signal weighting
- `FILTER_WATCHLIST` — Positive direction, accumulate more evidence
- `EVIDENCE_BUILDING` — n<20 or mixed signal, continue accumulation
- `SUPPRESS_REVIEW_REQUIRED` — Negative ROI at n≥20, review scoring rules
- `INSUFFICIENT_SAMPLE` — n<20 results, no conclusion possible

**No live weighting applied. Evidence accumulation only.**