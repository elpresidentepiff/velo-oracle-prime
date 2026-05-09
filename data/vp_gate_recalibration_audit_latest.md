# VP Gate Recalibration Audit
Generated: 2026-05-08T20:53:48.235343
Dataset: data/sidecar_training_dataset_v1.csv (11542 rows)

## Recommendation: **KEEP_VP30**

## VP Gate Comparison (all splits)
| Gate | n | SR% | Frame% | ROI | AvgSP |
|---|---|---|---|---|---|
| ≥0.20 | 1147 | 24.8% | 60.7% | -0.1252 | 7.4 |
| ≥0.25 | 611 | 29.5% | 68.1% | -0.1801 | 5.8 |
| ≥0.28 | 427 | 34.2% | 73.5% | -0.0893 | 5.3 |
| ≥0.30 | 341 | 35.2% | 75.7% | -0.1159 | 5.1 |
| ≥0.32 | 261 | 37.9% | 78.5% | -0.0929 | 4.5 |
| ≥0.35 | 161 | 43.5% | 84.5% | -0.1001 | 3.5 |
| ≥0.40 | 87 | 48.3% | 90.8% | -0.1679 | 2.9 |

## Racing API Enrichment at VP30
| Filter | n | SR% | Frame% | ROI |
|---|---|---|---|---|
| vp30_baseline | 341 | 35.2% | 75.7% | -0.1159 |
| vp30_trainer_course_gt15 | 19 | 42.1% | 84.2% | +0.4632 |
| vp30_jockey_dist_gt15 | 96 | 51.0% | 85.4% | +0.1388 |
| vp30_trainer_jockey_gt15 | 101 | 44.5% | 79.2% | +0.1587 |

## Racing API Signal Assessment
- Improves WIN probability: YES
- Improves FRAME rate: YES
- Improves ROI: YES

## Sidecar Tier Table
| Component | Tier |
|---|---|
| sqpe_v17 | TIER 5 — LIVE_WEIGHT_CANDIDATE (active in SQPE_IMPROVEMENT_MDS_V1) |
| improvement_score | TIER 5 — LIVE_WEIGHT_CANDIDATE (active in SQPE_IMPROVEMENT_MDS_V1) |
| market_deception_score | TIER 5 — LIVE_WEIGHT_CANDIDATE (active in SQPE_IMPROVEMENT_MDS_V1) |
| place_prob | TIER 2 — SHADOW_SCORED / BADGE_ONLY (frozen from live VP, 2026-05-08) |
| longshot_score | TIER 2 — SHADOW_SCORED / FROZEN (FREEZE_CANDIDATE, ROI=-6.5%) |
| release_day_prob | TIER 1 — OPERATOR_VISIBLE (feature pipeline not wired) |
| comment_intel_score | TIER 1 — OPERATOR_VISIBLE (feature pipeline not wired) |
| trainer_course_stats | TIER 3 — CALIBRATION_TEST (in full_analysis, needs evidence gate) |
| trainer_dist_stats | TIER 3 — CALIBRATION_TEST (in full_analysis, needs evidence gate) |
| jockey_course_stats | TIER 2 — SHADOW_SCORED (Supabase live, calibration pending) |
| jockey_dist_stats | TIER 2 — SHADOW_SCORED (Supabase live, calibration pending) |
| trainer_jockey_combo | TIER 2 — SHADOW_SCORED (Supabase live, calibration pending) |
| rpdc_score | TIER 2 — SHADOW_SCORED (field mapping fixed 2026-05-08, observability only) |

## VP Gate Recalibration Status
VP gate threshold is **UNDER_CALIBRATION** due to Ensemble Surgery v1 VP compression.
Average VP dropped ~0.05 (improvement_score raw values lower than place_prob).
Collect 30 live sigma days before changing VP30 threshold.

**DO NOT change VP thresholds until 30-day monitoring period completes (~2026-06-08).**