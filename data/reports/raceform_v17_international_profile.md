# Raceform V17 International Data Profile

**Generated:** 2026-05-23  
**Source:** data/raceform_v17_features.parquet  
**Status:** DATA AUDIT — no scoring, no training, no activation

---

## Summary

| Metric | Value |
|---|---|
| Total parquet rows | 1,702,741 |
| UK rows | 1,446,879 |
| Target international rows | 255,862 |
| Parquet date range | 2015-01-01 → 2025-07-05 |
| International date range | 2015-01-03 → 2025-07-05 |

Note: 255,862 target rows from 7 specific venues. The previously cited figure of 270,743 referenced a broader international set including other non-UK courses not in the current target list.

---

## Course Coverage Table

| Course | Rows | Races | Date Min | Date Max | Avg Field | Label% | OR% | RPR% | TS% | SP% | Draw% | Class% | RPR Corr | Dups | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Sha Tin (HK) | 50,976 | 4,080 | 2015-01-25 | 2025-07-05 | 12.8 | 100.0% | 97.1% | 97.6% | 0.0% | 100.0% | 100.0% | 92.7% | 0.3265 | 0 | TRAINING_SAFE |
| Happy Valley (HK) | 30,557 | 2,644 | 2016-01-06 | 2025-06-25 | 11.6 | 100.0% | 99.9% | 98.9% | 0.0% | 100.0% | 100.0% | 99.0% | 0.3266 | 0 | TRAINING_SAFE |
| Chantilly (FR) | 47,568 | 4,043 | 2015-01-23 | 2025-06-28 | 12.9 | 100.0% | 0.0% | 92.1% | 51.7% | 99.9% | 99.9% | 0.0% | 0.3274 | 0 | TRAINING_SAFE |
| Deauville (FR) | 46,926 | 3,907 | 2015-01-03 | 2025-07-05 | 13.0 | 100.0% | 0.0% | 94.7% | 83.3% | 99.8% | 99.9% | 0.0% | 0.3203 | 0 | TRAINING_SAFE |
| Longchamp (FR) | 20,127 | 1,868 | 2015-04-06 | 2025-07-03 | 12.1 | 100.0% | 0.0% | 93.4% | 87.5% | 100.0% | 99.9% | 0.0% | 0.3129 | 0 | TRAINING_SAFE |
| Saint-Cloud (FR) | 27,731 | 2,499 | 2015-03-07 | 2025-07-04 | 12.4 | 100.0% | 0.0% | 90.7% | 79.0% | 100.0% | 99.9% | 0.0% | 0.3177 | 0 | TRAINING_SAFE |
| Auteuil (FR) | 31,977 | 3,081 | 2015-03-01 | 2025-05-31 | 11.5 | 100.0% | 0.0% | 71.7% | 0.0% | 99.9% | 0.0% | 0.0% | 0.3943 | 0 | TRAINING_SAFE |

---

## Key Findings

### 1. Win Label Coverage
All 7 target courses: **100.0%** win label coverage. Every row has a valid target. Safe to train.

### 2. OR Coverage (Critical)
- **HK (Sha Tin, Happy Valley): 97-100% OR coverage** — HK uses 0-140 scale, directly usable.
- **France (all venues): 0.0% OR coverage** — France does not use UK OR system. RPR must replace OR as primary rating.

### 3. TS Coverage (Critical)
- **HK (Sha Tin, Happy Valley): 0.0% TS coverage** — drop TS from all HK feature sets.
- **Auteuil: 0.0% TS coverage** — Auteuil is 97% jump racing. No TS for jumps.
- **FR flat (Chantilly, Deauville, Longchamp, Saint-Cloud): 51-88% TS coverage** — usable in feature set.

### 4. Auteuil — JUMP RACING ALERT
Auteuil race type breakdown from parquet:
- Hurdle: 20,776 rows (64.9%)
- Chase: 11,186 rows (35.0%)
- Flat: 15 rows (0.05%)

**AUTEUIL IS NOT A FLAT COURSE.** It must not be pooled with Chantilly/Deauville/Longchamp/Saint-Cloud.
Separate pack required: FR_JUMPS_AUTEUIL.

### 5. RPR Signal
RPR vs field correlation with win target:
- Sha Tin: 0.3265 | Happy Valley: 0.3266 | Chantilly: 0.3274 | Deauville: 0.3203 | Auteuil: 0.3943

**RPR is the primary cross-jurisdiction signal.** Auteuil's 0.3943 correlation is the highest of all venues — strong jumps signal.

### 6. Duplicate Count
All courses: 0 duplicates on (race_id, horse). Data is clean.

### 7. Training Verdicts
All 7 courses: **TRAINING_SAFE**

---

## Classification


