# Core V0_OR Challenger — Decision Report
Generated: 2026-05-25T21:59:13.614500Z

## OR Diagnosis
- `or_rating = '–'` for ~41% of Flat runners (genuine unrated horses: maidens, novices)
- Not a bug — `or_num` nulls correctly reflect real absence of handicap mark
- Fix: `official_rating` (numeric, 0=unrated) + `is_rated` binary flag
- `or_vs_field` (relative OR within race) already in Core V0 — retained

## Metrics Comparison
| Metric | Champion (Core V0) | Challenger (Core V0_OR) | OR Baseline | Delta |
|---|---|---|---|---|
| AUC | 0.6735 | 0.6777 | — | +0.0042 |
| Brier | 0.0861 | 0.0859 | — | -0.0002 |
| SR | 21.8% | 21.9% | 15.6% | +0.1% |
| Frame | 50.3% | 50.8% | 40.9% | +0.5% |

## Decision: **OR_FIX_CONFIRMED_AND_IMPROVES**

| Classification | Meaning |
|---|---|
| OR_FIX_CONFIRMED_AND_IMPROVES | OR was missing, challenger beats champion |
| OR_FIX_CONFIRMED_NO_LIFT | OR was missing but no meaningful improvement |
| OR_MAPPING_BUG_NOT_FOUND | OR already captured via or_vs_field |