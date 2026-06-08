# International Rating Provenance Audit

**Generated:** 2026-05-23T21:26:43.112060+00:00

---

## Purpose

Determines whether `rpr_num`, `or_num`, `ts_num` in `raceform_v17_features.parquet`
represent pre-race ratings (known before the race) or post-race performance ratings
(assigned after the race based on finishing position and margins).

---

## Primary Test: Winner Max-Rating Dominance

**Logic:**
- If RPR is **post-race** (awarded based on performance): the winner almost always earns the highest rating.
  Expected winner-max rate: **> 70%**
- If RPR is **pre-race** (historical rating brought into the race): the top-rated horse wins ~40-50% of races.
  Expected winner-max rate: **~40-50%**

## Results by Pack

| Pack | Winner Max RPR Rate | Pos Corr | rpr_vs_field Verdict |
|---|---|---|---|
| HK_SHA_TIN_V1 | 45.9% | -0.6807 | **POST_RACE_LEAKAGE_SUSPECTED** |
| HK_HAPPY_VALLEY_V1 | 42.2% | -0.6882 | **POST_RACE_LEAKAGE_SUSPECTED** |
| FR_CHANTILLY_V1 | 68.5% | -0.6432 | **POST_RACE_LEAKAGE_SUSPECTED** |
| FR_FLAT_CORE | 68.7% | -0.6380 | **POST_RACE_LEAKAGE_SUSPECTED** |
| FR_AUTEUIL_JUMPS_V1 | 71.4% | -0.6746 | **POST_RACE_LEAKAGE_SUSPECTED** |

---

## Global RPR Adjacent-Race Stability

| Metric | Value |
|---|---|
| Adjacent pairs analyzed | 1,277,498 |
| Change rate race-to-race | 95.0% |
| Delta mean | 13.21 |
| Delta median | 9.0 |

95% change rate with mean delta 13 is ambiguous. PRE-RACE: RP updates ratings after each run — consistent with frequent changes. POST-RACE: performance-based ratings would also change per race. Winner-max-dominance rate is the more decisive test.

---

## Interpretation Guide

| Winner Max Rate | Verdict |
|---|---|
| > 70% | POST_RACE_LEAKAGE_SUSPECTED — winner almost always has highest rating |
| 55-70% | TIMESTAMP_UNKNOWN — ambiguous |
| 40-55% | PRE_RACE_SAFE — consistent with pre-race rating (same as top-pick SR) |

| Position Correlation | Verdict |
|---|---|
| < -0.60 | POST_RACE_SUSPECTED — rating tracks finishing order too closely |
| -0.35 to -0.60 | TIMESTAMP_UNKNOWN |
| -0.15 to -0.35 | PRE_RACE_CONSISTENT |

---

## Methodology

Primary test: `winner_max_rating_dominance` — for each race, is the winner the horse with the highest rating?
Secondary test: `position_correlation` — how strongly does the rating correlate with actual finishing position?

```
POST_RACE threshold: winner_max_rate > 0.70
PRE_RACE expectation: winner_max_rate ~ 0.40-0.50
```
