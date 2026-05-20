# VÉLØ Safe Ensemble Simulation — Variant Comparison

Corpus: 794 rows | Usable (won+SP): 721 | V0 selections at VP≥0.25: 321

**All variants match V0 coverage (top-N by re-blended score).**
**No production weight change. Simulation and governance only.**

## Full Variant Table

| Variant | n | SR% | FR% | P&L | ROI% | AvgSP | MedSP | MaxDD | LossRun | VP30n | VP30_SR% | VP30_ROI% | Changed | W_Gain | W_Lost | ROI_Δ | FR_Δ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V0_CURRENT_LIVE | 321 | 26.5 | 64.5 | -78.25 | -24.38 | 6.06 | 3.50 | 84.33 | 16 | 210 | 31.4 | -17.62 | — | — | — | — | — |
| V1_SQPE_ONLY | 321 | 17.1 | 50.8 | -39.41 | -12.28 | 9.20 | 5.50 | 59.87 | 19 | 93 | 20.4 | -41.15 | 354 | 25 | 55 | +12.10 | -13.71 |
| V2_SQPE_MDS_PLACE | 321 | 26.5 | 60.1 | -93.16 | -29.02 | 6.03 | 3.50 | 93.16 | 17 | 155 | 34.8 | -25.59 | 232 | 24 | 24 | -4.64 | -4.37 |
| V3_SQPE_MDS_ONLY | 321 | 27.1 | 59.5 | -25.00 | -7.79 | 6.05 | 3.50 | 83.24 | 16 | 149 | 36.9 | -15.40 | 262 | 24 | 22 | +16.59 | -4.99 |
| V4_REMOVE_HARMFUL | 321 | 25.6 | 60.1 | -96.14 | -29.95 | 6.29 | 3.75 | 96.39 | 14 | 159 | 32.7 | -27.14 | 228 | 23 | 26 | -5.57 | -4.37 |
| V5_VALUE_DISCIPLINE | 321 | 26.2 | 59.5 | -26.76 | -8.34 | 6.48 | 4.00 | 85.78 | 21 | 151 | 35.8 | -17.72 | 260 | 22 | 23 | +16.04 | -4.99 |
| V6_SHADOW_RACING_API_AWARE | 321 | 26.2 | 59.5 | -26.76 | -8.34 | 6.48 | 4.00 | 85.78 | 21 | 151 | 35.8 | -17.72 | 260 | 22 | 23 | +16.04 | -4.99 |
| ABL_sqpe_v17_prob | 321 | 25.6 | 59.8 | -85.24 | -26.55 | 6.57 | 3.75 | 87.06 | 16 | 173 | 31.2 | -25.40 | 196 | 22 | 25 | -2.17 | -4.68 |
| ABL_improvement_score | 321 | 25.6 | 59.8 | -85.37 | -26.60 | 6.53 | 4.00 | 86.85 | 14 | 153 | 34.0 | -19.70 | 244 | 23 | 26 | -2.22 | -4.68 |
| ABL_release_day_prob | 321 | 24.9 | 59.5 | -82.59 | -25.73 | 6.83 | 4.00 | 90.69 | 12 | 162 | 33.3 | -21.15 | 230 | 20 | 25 | -1.35 | -4.99 |
| ABL_market_deception_score | 321 | 23.7 | 58.3 | -95.75 | -29.83 | 7.11 | 4.33 | 95.75 | 19 | 153 | 32.0 | -22.99 | 246 | 21 | 30 | -5.45 | -6.23 |
| ABL_place_prob | 321 | 24.3 | 57.0 | -74.56 | -23.23 | 7.12 | 4.33 | 84.69 | 11 | 149 | 33.6 | -19.33 | 260 | 21 | 28 | +1.15 | -7.48 |
| ABL_comment_intel_score | 321 | 24.9 | 59.5 | -82.59 | -25.73 | 6.83 | 4.00 | 90.69 | 10 | 162 | 33.3 | -21.15 | 230 | 20 | 25 | -1.35 | -4.99 |
| ABL_longshot_prob | 321 | 25.6 | 60.4 | -83.67 | -26.07 | 6.44 | 4.00 | 94.84 | 22 | 156 | 34.0 | -23.89 | 240 | 22 | 25 | -1.69 | -4.05 |

## Ablation Table (Current Minus One, Same Coverage)

| Ablated | n | SR% | FR% | P&L | ROI% | ROI_Δ | FR_Δ | Changed | W_Gained | W_Lost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sqpe_v17_prob | 321 | 25.6 | 59.8 | -85.24 | -26.55 | -2.17 | -4.68 | 196 | 22 | 25 |
| improvement_score | 321 | 25.6 | 59.8 | -85.37 | -26.60 | -2.22 | -4.68 | 244 | 23 | 26 |
| release_day_prob | 321 | 24.9 | 59.5 | -82.59 | -25.73 | -1.35 | -4.99 | 230 | 20 | 25 |
| market_deception_score | 321 | 23.7 | 58.3 | -95.75 | -29.83 | -5.45 | -6.23 | 246 | 21 | 30 |
| place_prob | 321 | 24.3 | 57.0 | -74.56 | -23.23 | +1.15 | -7.48 | 260 | 21 | 28 |
| comment_intel_score | 321 | 24.9 | 59.5 | -82.59 | -25.73 | -1.35 | -4.99 | 230 | 20 | 25 |
| longshot_prob | 321 | 25.6 | 60.4 | -83.67 | -26.07 | -1.69 | -4.05 | 240 | 22 | 25 |

## Direct Answers

- Q1 remove release_day_prob: ROI -24.38% → -25.73% (Δ-1.35pp) — WORSENS | SR Δ-1.56pp | Frame Δ-4.99pp
- Q2 remove comment_intel_score: ROI -24.38% → -25.73% (Δ-1.35pp) — WORSENS | SR Δ-1.56pp | Frame Δ-4.99pp
- Q3 remove improvement_score: ROI -24.38% → -26.60% (Δ-2.22pp) — WORSENS | SR Δ-0.93pp | Frame Δ-4.68pp
- Q4 MDS: KEEP_MDS (removing ROI Δ-5.45pp)
- Q5 place_prob: FRAME_ONLY (removing ROI Δ+1.15pp)
- Q6 SQPE-only better: YES_SQPE_BETTER (SQPE=-12.28% vs current=-24.38%)
- Q7 safest candidate: V3_SQPE_MDS_ONLY ROI=-7.79%

## Racing API Enrichment (Shadow Annotation — No Live Weight)

  racing_api_connection_shadow_score: avg=0.0191
  racing_api_course_shadow_score: avg=0.0174
  racing_api_distance_shadow_score: avg=0.0215
  racing_api_enrichment_shadow_score: avg=0.0225
High enrichment (>0.5) rows: 5 SR=40.0%
Note: Racing API enrichment SHADOW ONLY — no live weight applied

## Governance Recommendation

See `docs/engineering/VELO_PROCESS_WIRING_MAP_V1.md` → Safe Ensemble Candidate Review.

**Operating decision**: Do not touch production weights blindly.
Prove safer blend first. If it beats current on ROI/drawdown without
killing strike/frame → create SHADOW_SAFE_BLEND. Only then does live
weight change become a formal discussion.
