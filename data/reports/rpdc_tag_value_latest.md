# RPDC Tag Value Audit

**Generated:** 2026-05-24  
**Overlap period:** 2026-03-17 → 2026-05-23  
**Total sigma rows:** 2025  
**Matched to RPDC:** 304 (15.0%)  
**Global SR baseline:** 20.9%  
**Global Frame baseline:** 48.4%  

---

## Per-Tag Results (primary tag, sorted by SR)

| Tag | n | SR | Frame | SR Lift | Frame Lift | Cash Window | Classification |
|---|---|---|---|---|---|---|---|
| MARK_NEAR | 3 | 66.7% | 66.7% | +45.7pp | +18.3pp | 3 (100%) | **INSUFFICIENT_SAMPLE** |
| MARK_READY | 6 | 33.3% | 66.7% | +12.4pp | +18.3pp | 6 (100%) | **INSUFFICIENT_SAMPLE** |
| CYCLE_RUN_2 | 32 | 31.2% | 53.1% | +10.3pp | +4.7pp | 10 (31%) | **WATCHLIST** |
| STABLE_WARM | 40 | 30.0% | 62.5% | +9.1pp | +14.1pp | 0 (0%) | **VALUE_POSITIVE** |
| UNKNOWN | 125 | 28.0% | 55.2% | +7.1pp | +6.8pp | 0 (0%) | **WATCHLIST** |
| CYCLE_RUN_3 | 4 | 25.0% | 50.0% | +4.1pp | +1.6pp | 0 (0%) | **INSUFFICIENT_SAMPLE** |
| CYCLE_RUN_1 | 94 | 22.3% | 58.5% | +1.4pp | +10.1pp | 26 (28%) | **WATCHLIST** |
| NO_RPDC_HISTORY | 1511 | 20.1% | 46.9% | — | — | — | BASELINE_UNMATCHED |

---

## Classification Guide

| Class | Criteria |
|---|---|
| VALUE_POSITIVE | SR ≥ 30%, Frame ≥ 60% |
| FRAME_POSITIVE | Frame ≥ 60% (SR below threshold) |
| WATCHLIST | Between NOISE and VALUE_POSITIVE |
| NOISE | SR < 18%, Frame < 45% |
| TRAP_WARNING | SR ≤ 12%, n ≥ 30 |
| INSUFFICIENT_SAMPLE | n < 15 |
| BASELINE_UNMATCHED | No RPDC history (no tag) |

---

## Immutability

```
SUPABASE_MUTATED:    FALSE
SCORING_CHANGE:      NONE
MODEL_CHANGE:        NONE
```