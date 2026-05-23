# HK Happy Valley — Jurisdiction Pack V1

**Date:** 2026-05-23  
**Status:** DESIGN — no training, no scoring, no live deployment  
**Classification:** SHADOW/RESEARCH ONLY

---

## Pack Scope

Happy Valley is Hong Kong's night racing venue. It hosts Wednesday evening meetings and some weekend meetings. Tight oval configuration with unique pace dynamics.

| Metric | Value |
|---|---|
| Training rows | 30,557 |
| Race count | 2,644 |
| Date range | 2016-01-06 → 2025-06-25 |
| Avg field size | ~11 |
| Favourite SR | 28.3% |
| RPR correlation with win | 0.3266 |
| OR coverage | 99.9% |
| TS coverage | 0.0% |
| Win label coverage | 100.0% |
| Training verdict | TRAINING_SAFE |

**Key difference vs Sha Tin:** Favourite SR is 28.3% at Happy Valley vs 32.1% at Sha Tin — 3.8pp lower. These courses must NOT be pooled for baseline comparisons.

---

## Source Priority (Racing API Unavailable)

Identical to Sha Tin pack. HKJC publishes data for both courses.

| Priority | Source | URL | Auth | Status |
|---|---|---|---|---|
| P1 | HKJC Official | `racing.hkjc.com` | None | FREE |
| P2 | HKJC Sectionals | `racing.hkjc.com/en-us/local/information/displaysectionaltime` | None | FREE |
| P3 | HKJC Draw Stats | `racing.hkjc.com/en-us/local/horse-racing/draw-statistics` | None | FREE |
| BLOCKED | Racing API | `api.theracingapi.com` | Was Basic Auth | UNAVAILABLE |

---

## Canonical Course Code

| Venue | VÉLØ Code | HKJC Code | Timezone | Race Days |
|---|---|---|---|---|
| Happy Valley | `HAV` | `HV` | Asia/Hong_Kong (UTC+8) | Wed evenings + occasional other days |

---

## Why Happy Valley Needs Its Own Pack

Happy Valley is a **tight oval** — very different from Sha Tin's longer straights. Consequences:

1. **Different draw dynamics:** The oval configuration makes early pace critically important. High draws are more disadvantaged than at Sha Tin on certain distances.
2. **Lower favourite SR (28.3%):** More competitive races relative to field size. The model must be calibrated separately.
3. **Smaller training corpus:** 30,557 rows vs 50,976 at Sha Tin. Fewer training examples per class/distance combination.
4. **Night racing:** Course conditions and surface grip behave differently under artificial lighting. Going codes may be slightly different.
5. **Shorter distances:** Happy Valley predominantly runs 1000m, 1200m, 1650m, 1800m. No 2000m+ races.

**Rule: NEVER pool Happy Valley evidence into Sha Tin gates or vice versa.**

---

## Identity Rules

Same as Sha Tin pack. Generate `race_id` as `{date_YYYYMMDD}_HAV_{race_number}`.

---

## Class / Rating Mapping

Identical to Sha Tin pack. HK class system 1-5 + Griffin applies at both courses.

Happy Valley-specific note: Griffin races (debut horses) are common at Happy Valley on Wednesday evenings. Griffin flag must be set correctly.

---

## Draw Analysis

Draw analysis for Happy Valley requires separate tables from Sha Tin. The oval configuration means draw bias is MORE pronounced on short-course distances at HV.

Key distances at Happy Valley: 1000m, 1200m, 1650m, 1800m.

**Target: Build `hk_draw_stats` with rows for each `(course, distance_m, draw_position)` combination.**

Historical draw statistics available from HKJC draw stats page — separate entries for Happy Valley vs Sha Tin.

---

## Feature Availability

| Feature | Available | Notes |
|---|---|---|
| RPR | YES (98.9%) | Primary rating — highest coverage of any pack |
| OR (HK scale) | YES (99.9%) | Near-complete coverage |
| TS | NO (0.0%) | Drop entirely |
| Draw | YES | More deterministic than Sha Tin due to oval |
| Class | YES | Class 1-5 + Griffin |
| Class trajectory | COMPUTED | Same as Sha Tin |
| Griffin flag | YES | Common at Wednesday meetings |
| Barrier trial RPR | PARTIAL | For Griffins only |
| Sectional times | YES | HKJC official — same URL format as Sha Tin |
| Pace rank at 400m | COMPUTED | More impactful at HV than SHA due to tight oval |
| Night racing flag | YES | Binary — Happy Valley is ~90% night racing |
| Going | YES | UK scale applies |
| Distance | YES | Metres → furlongs |

---

## Night Racing Consideration

Happy Valley's night format may introduce a subtle feature: horses that run better under artificial light conditions. Track maintenance schedule differs from daytime Sha Tin.

**Phase 3 experiment (not Phase 1):** Test if adding `is_night_race` binary flag adds predictive lift. This requires confirming race time from HKJC and comparing SR day vs night for the same horse.

---

## Benter Model Integration

Same Benter model as Sha Tin pack. However, calibrate separately:
- Happy Valley has a different odds distribution (more outsiders win — lower fav SR)
- β (market weight) may differ from Sha Tin calibration
- Run `benter.calibrate()` on HV-only holdout data

Store calibration at: `models/specialist/benter_v1_hv/benter_v1_hv_calibration.json`

---

## Shadow Brain Target

Output: `hk_research.hk_verdicts` with `course='Happy Valley'`  
No Telegram output  
No UK verdict table writes  
Model tag: `HK_HAV_V1_SHADOW`

---

## Promotion Gates

| Gate | Threshold | Action |
|---|---|---|
| Gate 1 | 100 top-pick decisions (lower than SHA — smaller corpus) | First review |
| Gate 2 | 200 top-pick decisions | Full evidence review |
| Live promotion | OPERATOR DECISION ONLY | Never automatic |

Note: Happy Valley runs on Wednesday evenings only, approximately 40 meeting days per season. At ~8 races per meeting, Gate 1 takes roughly 3 months of shadow scoring.

---

## First Shadow Backtest Plan

When Phase 2 model training is approved:
1. Train `sqpe_v1_hv.pkl` on 2016-2022 HV data (n≈24K rows) — separate from Sha Tin model
2. Validate on 2023-2024 (n≈6K rows)
3. Calibrate Benter on HV holdout separately
4. Holdout: 2025 data — untouched
5. Compare fav SR calibration: model vs actual 28.3% baseline
6. Specifically validate: does model correctly differentiate HV vs SHA dynamics?

**Alternative approach (lower data volume):** If 24K rows is insufficient for a separate model, explore fine-tuning SHA model on HV data — re-training the top layers on HV-specific features. Evaluate vs standalone HV model on holdout.

---

## No Live Deployment Rule

```
HK_HAV_V1_SHADOW outputs go to hk_research.hk_verdicts ONLY
No Telegram messages for HK racing
No UK pipeline integration
No mixing with velo_verdicts table
Operator decision required at every gate
Happy Valley and Sha Tin have SEPARATE evidence gates
Do NOT pool evidence between courses
```
