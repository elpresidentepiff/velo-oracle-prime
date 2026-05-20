# SQPE Alone Control Audit

- Generated: `2026-05-15T01:30:24.176214Z`
- Race inputs with outcomes: `378`

## Configuration Comparison

| Config | n | SR | Frame | Flat ROI | Avg SP | Median SP | VP30 | Changes vs SQPE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SQPE_ONLY | 333 | 0.1922 | 0.4745 | 0.0726 | 12.1180 | 7.0000 | 35 | 0 |
| FULL_ENSEMBLE | 338 | 0.2426 | 0.5473 | 0.1353 | 9.7370 | 5.5000 | 74 | 122 |
| SQPE_PLUS_IMPROVEMENT | 333 | 0.2012 | 0.4745 | 0.0385 | 11.6450 | 7.0000 | 52 | 96 |
| SQPE_PLUS_MDS | 342 | 0.2515 | 0.5848 | 0.0365 | 8.1810 | 5.0000 | 73 | 91 |
| SQPE_PLUS_PLACE | 343 | 0.2157 | 0.5277 | 0.0364 | 9.6650 | 5.5000 | 113 | 143 |
| SQPE_PLUS_LONGSHOT | 334 | 0.1527 | 0.4251 | -0.0651 | 14.3530 | 9.0000 | 54 | 94 |
| SQPE_PLUS_IMPROVE_MDS | 338 | 0.2426 | 0.5473 | 0.1353 | 9.7370 | 5.5000 | 74 | 122 |

## Sidecar Classifications

| Config | Sidecar | Classification | n | SR | ROI |
|---|---|---|---:|---:|---:|
| SQPE_PLUS_IMPROVEMENT | improvement_score | SIDECAR_BADGE_ONLY | 333 | 0.2012 | 0.0385 |
| SQPE_PLUS_MDS | market_deception_score | SIDECAR_HELPS_FRAME | 342 | 0.2515 | 0.0365 |
| SQPE_PLUS_PLACE | place_prob | SIDECAR_HELPS_FRAME | 343 | 0.2157 | 0.0364 |
| SQPE_PLUS_LONGSHOT | longshot_score | SIDECAR_FREEZE_CANDIDATE | 334 | 0.1527 | -0.0651 |
| SQPE_PLUS_IMPROVE_MDS | improvement_score + MDS | SIDECAR_HELPS_VALUE | 338 | 0.2426 | 0.1353 |

## Audit Questions

A. SQPE alone improves ROI vs ensemble: `False`
B. Ensemble improves frame but hurts ROI: `False`
C. Sidecars improve frame: `['improvement_score', 'market_deception_score', 'place_prob']`
D. Sidecars improve EV (ROI positive vs SQPE): `['improvement_score + MDS']`
E. Sidecars overbet short prices: `[]`
F. Sidecars that should be badges only: `['improvement_score']`

---
*Audit only. No scoring or model changes.*
