# CASHRUN ACTIVATION AUDIT V1

## Purpose

Evidence-only audit of CASHRUN scoring bucket performance across all historical race days.
Measures whether CASHRUN signals (READY / WATCH / WEAK / SUPPRESS) have predictive
value on strike rate, place rate, and ROI. No live weighting applied. No activation.

## Current Classification

```
CASHRUN = OPERATOR_VISIBILITY_ONLY
```

CASHRUN must not be used as:
- a live model weight
- a staking input
- a suppression gate
- a Telegram trigger
- a routing rule

## Command

```bash
python scripts/cashrun_activation_audit.py
```

## Files

| File | Role |
|---|---|
| `scripts/cashrun_activation_audit.py` | Audit script |
| `data/reports/cashrun_activation_audit_latest.json` | Latest output JSON |
| `data/reports/cashrun_activation_audit_latest.md` | Latest output markdown |
| `docs/engineering/CASHRUN_ACTIVATION_AUDIT_V1.md` | This document |

## Inputs

| Source | Description |
|---|---|
| `data/cashrun_report_*.csv` | Historical CASHRUN scored rows (all dates) |
| `data/results_*.json` | Historical race results (all dates) |

Results are matched to CASHRUN rows by `(date, race_id, horse_name)`.
Unmatched rows (no results file for that date, or horse name mismatch) are excluded
from performance stats but counted in `unmatched_rows`.

## Audit Results (2026-05-15, n=2,543 rows, 52 dates)

### Bucket Performance

| Bucket | n | Results | SR | Place% | ROI | Avg SP | Verdict |
|---|---|---|---|---|---|---|---|
| CASHRUN_READY | 1 | 0 | — | — | — | — | INSUFFICIENT_SAMPLE |
| CASHRUN_WATCH | 15 | 6 | 16.7% | 33.3% | -0.250 | 5.5 | INSUFFICIENT_SAMPLE |
| WEAK_SIGNAL | 162 | 102 | 10.8% | 30.4% | +0.510 | 14.6 | EVIDENCE_BUILDING |
| SUPPRESS | 1,474 | 900 | 10.8% | 32.9% | -0.261 | 27.9 | EVIDENCE_BUILDING |

### VP30 Crossover

| Signal | n | Results | SR | Place% | ROI |
|---|---|---|---|---|---|
| WATCH + VP30 | 0 | 0 | — | — | — |
| WEAK + VP30 | 5 | 3 | 33.3% | — | +0.833 |
| SUPPRESS + VP30 | 26 | 17 | 58.8% | — | +0.699 |
| Any + VP30 | 31 | 20 | 55.0% | — | +0.719 |

## Interpretation

### CASHRUN_WATCH — INSUFFICIENT_SAMPLE

n=15 results is too small for any conclusion. Early ROI is -0.250 at avg SP 5.5.
The WATCH bucket is catching short-priced horses, which compresses ROI even on wins.

**Do not activate CASHRUN_WATCH as a signal. Accumulate more data.**

### WEAK_SIGNAL — Interesting but Unvalidated

n=102 results. ROI=+0.510 at avg SP=14.6. This looks promising but must be treated
with caution: high avg SP means variance is extreme at this sample size. A few outlier
winners could explain the entire positive ROI.

**Do not activate WEAK_SIGNAL. Track for another 20+ results before drawing conclusions.**

### SUPPRESS — Below Expectation

n=900 results. ROI=-0.261 at avg SP=27.9. The suppress bucket is dominated by long-priced
horses, which naturally have high variance. Negative ROI here is expected.

**SUPPRESS is behaving as designed — eliminating low-probability noise at scale.**

### WATCH + VP30 = 0

CASHRUN has never overlapped with VP30 signals in the WATCH or READY buckets.
This is a critical finding:

CASHRUN is not confirming VÉLØ's strongest picks. The two systems are operating
on different signal dimensions. This rules out using CASHRUN as a VP30 booster now.

### SUPPRESS + VP30 — Disagree-and-Win Pattern

SUPPRESS + VP30 shows SR=58.8%, ROI=+0.699 at n=26 results. This is early but striking:
horses that CASHRUN suppresses but VÉLØ scores VP≥0.30 appear to be winning at above
baseline rates.

Two interpretations:
1. CASHRUN suppress rules are miscalibrated — penalising trainer-intent absence too harshly
   for horses that have other structural advantages (class, market, model confidence)
2. VÉLØ is correctly identifying value that trainer-intent scoring cannot see

**This is evidence for further analysis, not activation.** The disagreement layer may be
more valuable than a confirmation layer — i.e., CASHRUN is most useful when it dissents
from VÉLØ, not when it agrees.

## Current Operating Policy

```
CASHRUN status: OPERATOR_VISIBILITY_ONLY
Live weighting: NO
Scoring changes: NO
Router changes: NO
Staking input: NO
Telegram input: NO
Suppress gate: NO
```

## Activation Thresholds (future review, not current)

| Bucket | Minimum n (results) | Required ROI | Required SR | Gate |
|---|---|---|---|---|
| CASHRUN_READY | 50 | > +0.05 | > 20% | Human review required |
| CASHRUN_WATCH | 50 | > 0 | > 15% | Human review required |
| CASHRUN as filter | 200 | Filtered pool SR lift > 5pp | — | Human review required |

No automatic activation at any threshold. Operator decision required.

## Next Steps

1. Continue accumulating CASHRUN results across daily scoring
2. Re-run this audit after 30+ more WATCH results
3. Investigate the SUPPRESS + VP30 disagree-and-win pattern with a dedicated query
4. Determine whether SUPPRESS rules should be relaxed for VP≥0.30 horses
5. Build trainer-specific CASHRUN performance tables (Trainer Intent Memory phase)

## Version History

| Version | Date | Changes |
|---|---|---|
| V1 | 2026-05-15 | Initial audit. 2,543 rows, 52 dates. WATCH insufficient, SUPPRESS+VP30 finding documented. |
