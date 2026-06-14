# Current-Era Sigma Union
## VÉLØ Oracle Prime — May 08–Jun 13 2026

**Status**: READ_ONLY LOCAL ARTIFACT — no Supabase writes, no scoring change
**Generated**: 2026-06-14
**Era boundary**: 2026-05-08 (Ensemble Surgery v1 cutover)
**Universe**: May 08–Jun 13 2026, CURRENT_ERA only

---

## Union Row Counts

| Source layer | Rows |
|---|---|
| SUPABASE_ONLY | 531 |
| LOCAL_ONLY | 294 |
| OVERLAP | 438 |
| **TOTAL** | **1263** |

---

## 8-Row Discrepancy — Reconciled

8 duplicate rows in `sigma_results_2026_05_31.json`. Six race_ids (919055, 919056, 919058–919061) written 2–3× each. Identical outcome and VP — sigma writer double-logged on May 31. Deduped by first occurrence. **732 is the correct unique local count.**

---

## Baseline and VP Coverage

| Metric | Value |
|---|---|
| Total rows | 1263 |
| VP coverage | **100%** |
| Outcome coverage | **100%** |
| Baseline SR | **24.3%** (307 wins) |
| Mean VP | 0.2953 |

---

## VP Threshold Table

| Threshold | n | Wins | SR |
|---|---|---|---|
| VP >= 0.25 | 681 | 209 | 30.7% |
| VP >= 0.30 | 512 | 172 | 33.6% |
| VP >= 0.35 | 372 | 134 | 36.0% |
| **VP >= 0.40** | **253** | **105** | **41.5%** |
| VP >= 0.45 | 181 | 81 | 44.8% |
| VP >= 0.50 | 125 | 57 | 45.6% |
| VP >= 0.55 | 81 | 37 | 45.7% |
| VP >= 0.60 | 50 | 25 | 50.0% |

---

## False-GREEN Days

**Jun 09 only.** avg VP=0.358, 9 VP>=0.40 picks, SR=13.8%.

---

## Classifications

```
VP_FULL_GATEKEEPER_PROMOTION_COMPLETE
CURRENT_ERA_SIGMA_UNION_BUILT
MAY08_SURGERY_SPLIT_ENFORCED
PRE_SURGERY_ROWS_EXCLUDED_FROM_CURRENT_ERA
NO_LIVE_SCORING_CHANGE
NO_SUPABASE_WRITES
NO_MODEL_PROMOTION
```

---

*CURRENT_ERA_SIGMA_UNION — May 08–Jun 13 2026 — 1263 rows — READ_ONLY*
