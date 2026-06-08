# Innovation Protocol Corpus Rebuild — 2026-05-22

**Generated:** 2026-05-23  
**Type:** INCREMENTAL_APPEND (May 21 + May 22 only)  
**Status:** COMPLETE — May 20 excluded (SCORING_FLATLINE_CONTAMINATED)

---

## Dates Added

| Date | Rows Added | Dedup Removed | Net |
|---|---|---|---|
| 2026-05-21 | 44 | 0 | **+44** |
| 2026-05-22 | 43 | 0 | **+43** |
| **Total** | **87** | **0** | **+87** |

**2026-05-20 excluded** — SCORING_FLATLINE_CONTAMINATED. Must not enter training or promotion evidence. May 20 rows in corpus: **0 (verified)**.

> May 22 has 43 verdict rows built, 7 of which have no results (Downpatrick data gap). These rows appear in the corpus with `won=null, placed=null`. This is a data gap, not contamination.

---

## Corpus Totals

| Metric | Value |
|---|---|
| Rows before rebuild | 931 |
| Rows after rebuild | **1,018** |
| Net added | **87** |
| Total dates | 7 |

### Dates in Corpus

| Date | Rows |
|---|---|
| 2026-05-02 | 55 |
| 2026-05-03 | 36 |
| 2026-05-04 | 59 |
| 2026-05-17 | 30 |
| 2026-05-19 | 38 |
| 2026-05-21 | 44 |
| 2026-05-22 | 43 |
| **Total** | **1,018** |

---

## Router Lane Summary (after rebuild)

Rows with results: 699

| Lane | n | Wins | ROI |
|---|---|---|---|
| V1_BASE_SHADOW | 10 | 3 | -20.2% |
| V2_CLASS4_SHADOW | 14 | 6 | +16.1% |
| V6_GOLD_SEAM_WATCHLIST | 11 | 5 | +59.1% |

V2 now at n=14 (+1 from n=13). Still needs n≥20 for WATCHLIST gate.  
V6 now at n=11. Still needs n≥20 for SHADOW_CANDIDATE gate.

---

## Governance

```
May 20 excluded from corpus          ✓ (0 rows confirmed)
No scoring changes                   ✓
No model changes                     ✓
No live betting                      ✓
Corpus file: data/velo_innovation_protocol_1k_deduped.csv
```
