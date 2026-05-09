# VÉLØ Ensemble Profile Monitor
**Profile:** SQPE_IMPROVEMENT_MDS_V1  
**Surgery commit:** b7e4e0c  
**Monitor start:** 2026-05-08  
**Target:** 30 live race days before gate recalibration decision

---

## Active Component Map

| Component | Status | Weight |
|---|---|---|
| sqpe_v17 | LIVE | 0.45 |
| improvement_score | LIVE | 0.12 |
| market_deception_score | LIVE | 0.10 |
| place_prob | BADGE_ONLY | — |
| longshot_score | FROZEN | — |
| release_window_score | STORED_ONLY | — |
| comment_intel_score | STORED_ONLY | — |

---

## VP Gate Status

| Gate | Legacy value | New profile | Status |
|---|---|---|---|
| VP30 | 17/41 (41.5%) | 9/41 (22.0%) | UNDER_CALIBRATION |
| VP25 | 23/41 (56.1%) | 14/41 (34.1%) | MONITORING |
| VP20 | 32/41 (78.0%) | 22/41 (53.7%) | REFERENCE |

**VP delta:** -0.0495 avg (improvement_score raw 0.02-0.15 vs place_prob 0.40-0.80)  
**Threshold decision:** Hold VP30 as official gate. Monitor VP25-30 band as UNDER_CALIBRATION zone.

---

## Daily Log (append after each sigma close)

| Date | Races | SR% | Frame% | VP30_n | VP25_n | MDS_HIGH_n | IMPROVE_HIGH_n | Avg_SP | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-05-08 | 41 | — | — | 9 | 14 | — | — | — | Baseline day (no results yet) |

---

## Warning Triggers

- [ ] ROI negative 3 consecutive days → ALERT
- [ ] Frame rate < 40% over 5+ days → ALERT
- [ ] VP30 volume < 5% of races → ALERT
- [ ] SR% < 15% over 5+ days → ALERT
- [ ] Top selection flip rate > 30% in a single day → ALERT

---

## Rollback Gate

If any 2 warning triggers fire in the same 5-day window:  
→ Set `VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE` and notify operator.

---

## 30-Day Decision Gate (expected: ~2026-06-08)

Required before VP threshold change:
- n ≥ 30 resolved race days
- SR data confirmed from sigma_audits
- ROI calculation verified against shadow
- VP25-30 band SR compared to VP30+ band SR
