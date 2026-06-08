# Race Shape V2 Precision Calibration Audit — 2026-05-22

**Generated:** 2026-05-23T08:09:52.660042+00:00
**Ledger rows:** 36
**Status:** SHADOW/RESEARCH ONLY — no scoring integration
**V1 finding:** SR_warned=22.6% vs SR_silent=40.0% — 17pp discriminative but too broad (31/36 warned)

---

## Per-Status Analysis

| Subset | n | Wins | SR | Visible% | Ranked23% | Midprice Miss% | Avg VP Gap | Verdict |
|---|---|---|---|---|---|---|---|---|
| CHAOTIC | 1 | 0 | 0.0% | 100.0% | 100.0% | 0.0% | 0.0795 | **NEEDS_MORE_DATA** |
| CLEAR_TOP | 3 | 1 | 33.3% | 100.0% | 100.0% | 50.0% | 0.3883 | **NEEDS_MORE_DATA** |
| COMPRESSED | 2 | 0 | 0.0% | 100.0% | 100.0% | 100.0% | 0.0267 | **NEEDS_MORE_DATA** |
| FAV_VULNERABLE | 23 | 6 | 26.1% | 88.2% | 35.3% | 64.7% | 0.0137 | **BROAD_WARNING_ONLY** |
| MIDPRICE_TRAP | 5 | 1 | 20.0% | 100.0% | 50.0% | 50.0% | 0.1526 | **ACTIONABLE_RISK_FLAG** |
| UNKNOWN | 2 | 1 | 50.0% | 100.0% | 0.0% | 100.0% | 0.1704 | **NEEDS_MORE_DATA** |

---

## FAV_VULNERABLE Precision Subsets

FAV_VULNERABLE is the dominant status (31 of 36 total warned). Subsets tested for V2 precision gate candidates.

| Subset | n | Wins | SR | Visible% | Ranked23% | Midprice Miss% | Avg VP Gap | Verdict |
|---|---|---|---|---|---|---|---|---|
| FAV_VULN_ULTRA_COMPRESSED | 16 | 3 | 18.8% | 84.6% | 30.8% | 69.2% | 0.0042 | **ACTIONABLE_RISK_FLAG** |
| FAV_VULN_VP_LT_15 | 12 | 3 | 25.0% | 88.9% | 44.4% | 77.8% | 0.0080 | **BROAD_WARNING_ONLY** |
| FAV_VULN_VP_LT_12 | 6 | 2 | 33.3% | 100.0% | 25.0% | 100.0% | 0.0073 | **NOT_USEFUL** |
| FAV_VULN_WINNER_MIDPRICE | 15 | 4 | 26.7% | 90.9% | 36.4% | 100.0% | 0.0087 | **BROAD_WARNING_ONLY** |

---

## Meta Comparisons

| Subset | n | Wins | SR | Visible% | Ranked23% | Midprice Miss% | Avg VP Gap | Verdict |
|---|---|---|---|---|---|---|---|---|
| ALL_RACES | 36 | 9 | 25.0% | 92.6% | 48.1% | 63.0% | 0.0755 | **BROAD_WARNING_ONLY** |
| SHAPE_WARNED | 31 | 7 | 22.6% | 91.7% | 45.8% | 62.5% | 0.0391 | **BROAD_WARNING_ONLY** |
| SHAPE_SILENT | 5 | 2 | 40.0% | 100.0% | 66.7% | 66.7% | 0.3011 | **NOT_USEFUL** |


**ACTIONABLE candidates:** MIDPRICE_TRAP, FAV_VULN_ULTRA_COMPRESSED

These subsets have SR ≤ 22% with n ≥ 5. Candidate for V2 precision warning gate — requires 300+ race corpus to confirm.

---

## V2 Precision Calibration — Key Findings

1. **FAV_VULNERABLE dominates** — 23/36 races. Single-status SR=26.1%. Not tight enough for suppression without VP scoring implications.

2. **Winner visibility is not the problem** — 92.6% of miss winners were visible in snapshots. The miss structure is ranking failure, not coverage failure.

3. **Midprice misses concentrate in FAV_VULNERABLE** — 11/17 FAV_VULNERABLE misses had winners in the 3.0–8.5 SP zone. This is the primary V2 research target.

4. **n=36 is too small for quartile SR analysis** — V2 requires 300+ races minimum. Current corpus: 36 races (May 22 only). Accumulate corpus daily.

5. **COMPRESSED and CHAOTIC** — n=2 and n=1 respectively. Architecturally interesting but statistically unusable at current corpus size.

---

## Promotion Gate

```
V2 actionable subsets:    requires n >= 300 races and quartile SR analysis
V1 broad warning:         CONFIRMED — 17pp discriminative but too broad
V2 precision gate:        NOT MET — insufficient corpus
Next milestone:           300+ races in shadow ledger corpus
```

Shadow ledger only. No scoring changes. No VP adjustments. No routing changes.
