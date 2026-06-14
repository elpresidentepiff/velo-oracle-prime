# International Signal Baseline Audit

**Generated:** 2026-05-23T18:52:59.243068+00:00
**Status:** SHADOW/RESEARCH — data audit only, no scoring

---

## Course Signal Matrix

| Course | Rows | Fav SR | RPR Corr | SP Rank Corr | OR% | RPR% | TS% | Draw% | Class% |
|---|---|---|---|---|---|---|---|---|---|
| Sha Tin (HK) | 50,976 | 32.1% | 0.3265 | -0.2621 | 97.1% | 97.6% | 0.0% | 100.0% | 92.7% |
| Happy Valley (HK) | 30,557 | 28.3% | 0.3266 | -0.2473 | 99.9% | 98.9% | 0.0% | 100.0% | 99.0% |
| Chantilly (FR) | 47,568 | 28.8% | 0.3274 | -0.2238 | 0.0% | 92.1% | 51.7% | 99.9% | 0.0% |
| Deauville (FR) | 46,926 | 27.8% | 0.3203 | -0.221 | 0.0% | 94.7% | 83.3% | 99.9% | 0.0% |
| Longchamp (FR) | 20,127 | 29.1% | 0.3129 | -0.2223 | 0.0% | 93.4% | 87.5% | 99.9% | 0.0% |
| Saint-Cloud (FR) | 27,731 | 27.8% | 0.3177 | -0.213 | 0.0% | 90.7% | 79.0% | 99.9% | 0.0% |
| Auteuil (FR) | 31,977 | 31.0% | 0.3943 | -0.2332 | 0.0% | 71.7% | 0.0% | 0.0% | 0.0% |

---

## Jurisdiction Signal Answers


**Q1_RPR_useful_in_FR:** YES  
Evidence: RPR correlation with win: Chantilly=0.3274, Deauville=0.3203  
Verdict: `KEEP_RPR_AS_PRIMARY_FR`

**Q2_RPR_useful_in_HK:** YES  
Evidence: RPR correlation: Sha Tin=0.3265, Happy Valley=0.3266  
Verdict: `KEEP_RPR_AS_PRIMARY_HK`

**Q3_OR_meaningful_in_HK:** YES — HK uses own 0-140 scale which maps to Racing Post OR  
Evidence: OR nonzero coverage: Sha Tin=97.1%, Happy Valley=99.9%  
Verdict: `OR_AVAILABLE_AND_USEFUL_IN_HK`

**Q4_TS_absent_in_HK:** YES — TS coverage is 0.0% at both HK courses  
Evidence: Sha Tin TS: 0.0%, Happy Valley TS: 0.0%  
Verdict: `DROP_TS_FROM_HK_FEATURES`

**Q5_class_num_matters_in_HK:** YES — HK class system 1-5 is the primary race structuring mechanism  
Evidence: Sha Tin class distribution: Class4=39%, Class3=30%, Class5=12%, Class2=10%, Class1=1.5%  
Verdict: `BUILD_CLASS_TRAJECTORY_FEATURE_FOR_HK`

**Q6_HK_fav_baselines_differ:** YES — Sha Tin 32.1% vs Happy Valley 28.3% (3.8pp difference)  
Evidence: Sha Tin fav SR=32.1%, Happy Valley fav SR=28.3%  
Verdict: `SEPARATE_BASELINE_PER_COURSE — do not pool HK courses`

**Q7_Chantilly_vs_Deauville:** SIMILAR — both flat FR, fav SR within 1pp, RPR correlation within 0.01  
Evidence: Chantilly fav SR=28.8%, Deauville=27.8%; RPR corr: 0.3274 vs 0.3203  
Verdict: `POOL_FR_FLAT_COURSES — Auteuil requires separate jumps model`

**Q8_Auteuil_separate:** YES — CRITICAL FINDING: Auteuil is 97% jump racing (Hurdle 20776, Chase 11186, Flat 15 rows)  
Evidence: Auteuil race type breakdown from parquet: Hurdle=64.9%, Chase=35.0%, Flat=0.05%  
Verdict: `AUTEUIL_IS_JUMPS_NOT_FLAT — separate from FR flat pack entirely`


---

## Draw Analysis (HK — Critical Signal)


**Sha Tin (HK):**
  Draw 1-3: n=12198, Win%=9.9%
  Draw 4-6: n=12193, Win%=8.7%
  Draw 7-9: n=11809, Win%=7.0%
  Draw 10-12: n=10398, Win%=6.9%
  Draw 13+: n=4377, Win%=6.2%

**Happy Valley (HK):**
  Draw 1-3: n=7887, Win%=12.3%
  Draw 4-6: n=7890, Win%=9.5%
  Draw 7-9: n=7786, Win%=7.1%
  Draw 10-12: n=6987, Win%=5.4%
  Draw 13+: n=7, Win%=14.3%

**Chantilly (FR):**
  Draw 1-3: n=11762, Win%=9.7%
  Draw 4-6: n=11647, Win%=10.5%
  Draw 7-9: n=10085, Win%=8.4%
  Draw 10-12: n=7379, Win%=6.0%
  Draw 13+: n=6656, Win%=6.0%

**Deauville (FR):**
  Draw 1-3: n=11342, Win%=8.2%
  Draw 4-6: n=11308, Win%=10.6%
  Draw 7-9: n=10004, Win%=8.7%
  Draw 10-12: n=7491, Win%=6.8%
  Draw 13+: n=6753, Win%=6.0%

**Longchamp (FR):**
  Draw 1-3: n=5440, Win%=11.7%
  Draw 4-6: n=5345, Win%=11.1%
  Draw 7-9: n=4226, Win%=8.2%
  Draw 10-12: n=2716, Win%=5.9%
  Draw 13+: n=2375, Win%=5.6%

**Saint-Cloud (FR):**
  Draw 1-3: n=7268, Win%=10.7%
  Draw 4-6: n=7141, Win%=10.2%
  Draw 7-9: n=5909, Win%=8.7%
  Draw 10-12: n=3905, Win%=6.4%
  Draw 13+: n=3477, Win%=6.6%


---

## Key Classification

```
FR_FLAT:  Chantilly, Deauville, Longchamp, Saint-Cloud — pool for model training
FR_JUMPS: Auteuil — SEPARATE pack, do not mix with flat
HK_ST:    Sha Tin — separate baseline from Happy Valley
HK_HV:    Happy Valley — separate baseline from Sha Tin
```

---

## Signal Priority by Jurisdiction

**HK:**
1. RPR (primary, >97% coverage, corr=0.33)
2. OR (>97% coverage, HK 0-140 scale)
3. SP/implied_prob (market signal)
4. Draw position (bias confirmed — 1-3 win 9.9%, 13+ win 6.2%)
5. Class_num (HK 1-5 system, trajectory)
6. TS: DROP — 0% coverage

**FR (Flat — Chantilly/Deauville/Longchamp/Saint-Cloud):**
1. RPR (primary, 90-95% coverage, corr=0.31-0.33)
2. SP/implied_prob (market signal)
3. TS (51-88% coverage — usable in Deauville/Longchamp/Saint-Cloud)
4. OR: DROP — 0% coverage (France uses Valeur rating, not UK OR)

**FR (Jumps — Auteuil only):**
1. RPR (primary, 71.7% coverage, corr=0.3943 — highest of all venues)
2. SP/implied_prob
3. TS: DROP — 0% coverage
4. Separate model required — do not mix with flat FR

---

## Governance

```
No scoring changes.
No model training until Phase 2 approved.
No live ingestion.
Data audit only.
```
