# fingerprint_v1_historical_softsqpe — Version Record

## Version Identity
- **Feature version:** `fingerprint_v1_historical_softsqpe`
- **Signal version:** `phase35_locked` (unchanged)
- **Created:** 2026-04-08
- **Status:** ACTIVE — historical mode only

## What Distinguishes This From fingerprint_v1

| Property | fingerprint_v1 (live) | fingerprint_v1_historical_softsqpe |
|---|---|---|
| SQPE source | Real VÉLØ SQPE | sqpe_proxy (derived) |
| SQPE filter | Hard band equality | None (soft proximity) |
| SQPE comparison | Exact band match | Percentile rank proximity |
| Weighting | Cosine only | 0.85× cosine + 0.15× sqpe_proximity |
| Min similarity | 0.70 | 0.55 |
| Zero SQPE handling | Skipped from index | Indexed with sqpe=0 |
| Encoder | vector_encoder (standard) | vector_encoder (standard) |
| Feature set | 13 locked features | 13 locked features (UNCHANGED) |

## sqpe_proxy Formula

```
sqpe_proxy = trainer_ae × 0.10 × form_modifier × days_modifier

form_modifier:
  improving   → 1.20
  consistent → 1.00
  mixed      → 0.90
  declining  → 0.80
  untested   → 0.95

days_modifier:
  normal_8_14   → 1.10  (peak fitness window)
  quick_5_7     → 1.05
  very_quick     → 0.85
  layoff_14_30   → 0.95
  layoff_30plus  → 0.70

cap: 0.80
```

## Percentile Normalization

- Computed during `build_index()` over the full historical population
- Each state's sqpe_proxy is ranked within the population: 0.0 (lowest) → 1.0 (highest)
- sqpe_proximity = 1.0 - |query_percentile - candidate_percentile|
- Applied as 15% weight in combined similarity score

## Combined Score Formula

```
similarity_score = 0.85 × cosine_similarity(features)
                 + 0.15 × sqpe_proximity(percentile)
```

## Scope Constraints
- Do NOT use in live VÉLØ predictions
- Do NOT widen the 13-feature set
- Do NOT connect to trading systems
- Only use for historical analog memory / Track B backfill

## Files That Implement This
- `analog_index.py` — `_query_historical()`, `_compute_percentiles()`
- `raceform_feature_deriver.py` — `_derive_sqpe()`
- `shadow_runner.py` — `ShadowRunner(mode=Mode.HISTORICAL)`

## Population Requirements
- Minimum recommended population for stable percentile ranks: 5,000 states
- Current test: 5,000 states ✅
- Target for production: 100,000+ states
