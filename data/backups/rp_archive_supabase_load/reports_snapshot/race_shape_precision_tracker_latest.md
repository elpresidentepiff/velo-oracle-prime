# Race Shape Precision Tracker — 2026-05-22

**Generated:** 2026-05-23T09:37:09.188870+00:00
**Shadow ledger rows:** 36
**Status:** SHADOW/RESEARCH ONLY — no scoring integration

---

## Precision Flag Tracking

| Flag | n | SR | Loss Rate | Frame Rate | Visible% | Ranked23% | Midprice Miss% | Avg VP Gap | To 150 | To 300 | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FAV_VULN_ULTRA_COMPRESSED | 16 | 18.8% | 81.2% | 84.6% | 84.6% | 30.8% | 69.2% | 0.0042 | 134 | 284 | **PROVISIONAL_RISK_FLAG** |
| MIDPRICE_TRAP | 5 | 20.0% | 80.0% | 100.0% | 100.0% | 50.0% | 50.0% | 0.1526 | 145 | 295 | **PROVISIONAL_RISK_FLAG** |
| HIGH_COMPRESSION | 19 | 21.1% | 79.0% | 86.7% | 86.7% | 33.3% | 73.3% | 0.0060 | 131 | 281 | **PROVISIONAL_RISK_FLAG** |
| FAV_VULNERABLE | 23 | 26.1% | 73.9% | 88.2% | 88.2% | 35.3% | 64.7% | 0.0137 | 127 | 277 | **BROAD_WARNING_ONLY** |
| CLEAR_TOP | 3 | 33.3% | 66.7% | 100.0% | 100.0% | 100.0% | 50.0% | 0.3883 | 147 | 297 | **NOT_USEFUL** |
| CHAOTIC | 1 | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0795 | 149 | 299 | **NEEDS_MORE_DATA** |
| SHAPE_SILENT | 5 | 40.0% | 60.0% | 100.0% | 100.0% | 66.7% | 66.7% | 0.3011 | 145 | 295 | **BASELINE_REFERENCE** |


Gate 1 = 150 races | Gate 2 = 300 races
ACTIONABLE_CANDIDATE requires n ≥ 50 and SR ≤ 22%
PROVISIONAL_RISK_FLAG requires n ≥ 5 and SR ≤ 22%

**Provisional risk flags (requires 300+ corpus to confirm):**
- FAV_VULN_ULTRA_COMPRESSED: n=16, SR=18.8%, 134 more to Gate 1
- MIDPRICE_TRAP: n=5, SR=20.0%, 145 more to Gate 1
- HIGH_COMPRESSION: n=19, SR=21.1%, 131 more to Gate 1

---

## Key Comparisons

| Pair | SR | Difference |
|---|---|---|
| FAV_VULN_ULTRA_COMPRESSED vs FAV_VULNERABLE | 18.8% vs 26.1% | 7.3% |
| FAV_VULNERABLE vs SHAPE_SILENT | 26.1% vs 40.0% | 13.9% |
| MIDPRICE_TRAP vs ALL | 20.0% vs 25.0% | 5.0% |

---

## Corpus Progress

| Target | Current | Gate 1 (150) | Gate 2 (300) | Status |
|---|---|---|---|---|
| Total shadow ledger rows | 36 | 150 | 300 | ACCUMULATING |
| FAV_VULN_ULTRA_COMPRESSED | 16 | 50 (provisional) | 150 | PROVISIONAL_RISK_FLAG |
| MIDPRICE_TRAP | 5 | 20 | 50 | PROVISIONAL_RISK_FLAG |

---

## Governance

```
Shadow tracking only.
No scoring changes.
No VP adjustments.
No routing changes.
Promotion gate: operator decision required after 300+ corpus.
```
