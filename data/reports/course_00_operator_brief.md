# COURSE-00 Operator Brief
## VÉLØ Course Eyes Completion Pack
Generated: 2026-07-01 01:17 UTC
Status: REPORT_ONLY

---

## Q1. What is COURSE-00?

COURSE-00 is a pure analytical audit of course-level intelligence gaps in the VÉLØ system.
It produces a static course eye registry, draw/pace priority tables, deep dives on AW tracks
and Beverley, a mid-price 6-10 wound table, a feature readiness matrix, and a COURSE-01 design
spec. No live changes are made. All course rules are WATCHLIST_ONLY.

---

## Q2. What is the AW cluster situation?

6 AW tracks audited: Southwell (AW), Kempton (AW), Wolverhampton (AW), Lingfield (AW), Newcastle (Aw), Chelmsford (Aw).
Combined n=51, SR=21.6%.
All have draw_bias_known='yes' and front_runner_advantage='yes'.
Required features: DRAW_EYES_REQUIRED + PACE_EYES_REQUIRED + AW_PACE_EYES_REQUIRED.
Status: WATCHLIST_ONLY. No scoring change.

---

## Q3. What is the Beverley situation?

Beverley: sharp track, uphill finish, low draw bias at 5f/6f, front-runner hold-on pattern.
Mid-price misses from mp_misses CSV: 19 rows.
Root cause: draw bias + pace dynamics + uphill finish not captured in VÉLØ.
Status: BEVERLEY_WATCHLIST_ONLY. Required: DRAW_EYES_REQUIRED + PACE_EYES_REQUIRED.

---

## Q4. How many drain courses vs edge courses?

DRAIN courses identified: 8
EDGE courses identified: 51
Full breakdown in: course_00_course_watchlist.md

---

## Q5. What are the top 6-10 wound courses?

Total 6-10 band mid-price misses: 312
Top courses by count:
  - Southwell (AW): 13 misses
  - Bath: 11 misses
  - Newmarket: 10 misses
  - Beverley: 8 misses
  - Wolverhampton (AW): 8 misses

---

## Q6. What are the 2 CRITICAL missing features?

1. draw_bias_by_course_distance — CRITICAL, COURSE-01
2. pace_map_front_runner_flag — CRITICAL, COURSE-01

Additional CRITICAL: draw_bias_direction_by_distance.

---

## Q7. What is the feature readiness status?

Total features audited: 16
CRITICAL: 3
HIGH: 6
MEDIUM: 6
LOW: 1
Critical feature list: draw_bias_by_course_distance, pace_map_front_runner_flag, draw_bias_direction_by_distance

---

## Q8. How many courses have draw_bias_known='yes'?

32 course/distance combinations at CRITICAL priority (n>=20).
Full draw priority table: course_00_draw_bias_priority_table.csv

---

## Q9. How many courses have front_runner_advantage='yes'?

16 courses at CRITICAL pace priority.
Full pace priority table: course_00_pace_bias_priority_table.csv

---

## Q10. What does COURSE-01 do and is it implemented?

COURSE-01 creates shadow-only draw/pace/course-position features.
It is NOT implemented. This is a design spec only.
Constraint: NO_COURSE_01_IMPLEMENTATION active.
Implementation requires VCP-03 completion and operator gate.

---

## Q11. What are the active hard constraints?

- REPORT_ONLY
- NO_LIVE_SCORING_CHANGE
- NO_VP_THRESHOLD_CHANGE
- NO_MODEL_PROMOTION
- NO_SUPABASE_WRITES
- NO_TELEGRAM_SEND
- NO_VFU_21_START
- NO_VCP_04_START
- NO_COURSE_01_IMPLEMENTATION
- CANONICAL_HORSE_PASSPORT_NOT_MUTATED
- COURSE_RULES_WATCHLIST_ONLY
- DO_NOT_SUPPRESS_CONTRADICTIONS
- MISSING_ARTIFACTS_RESOLVE_UNKNOWN_NOT_CLEAN

---

## FINAL CLASSIFICATIONS

- COURSE_00_COURSE_EYES_COMPLETION_COMPLETE
- COURSE_REGISTRY_WRITTEN
- DRAW_BIAS_PRIORITY_TABLE_WRITTEN
- PACE_BIAS_PRIORITY_TABLE_WRITTEN
- AW_CLUSTER_DEEP_DIVE_WRITTEN
- BEVERLEY_WAR_BOOK_WRITTEN
- MIDPRICE_6_10_WOUND_TABLE_WRITTEN
- FEATURE_READINESS_MATRIX_WRITTEN
- EXTERNAL_SOURCE_FIELD_MAP_WRITTEN
- COURSE_WATCHLIST_WRITTEN
- COURSE_01_DESIGN_SPEC_WRITTEN_NOT_IMPLEMENTED
- DRAW_EYES_IDENTIFIED_CRITICAL
- PACE_EYES_IDENTIFIED_CRITICAL
- BEVERLEY_WATCHLIST_ONLY
- AW_CLUSTER_WATCHLIST_ONLY
- COURSE_RULES_WATCHLIST_ONLY
- MEMORY_CAPTURE_OPEN
- FAILURE_LEARNING_OPEN
- PROMOTION_LEARNING_GATED
- NO_COURSE_01_IMPLEMENTATION
- NO_VFU_21_START
- NO_VCP_04_START
- NO_LIVE_SCORING_CHANGE
- NO_MODEL_PROMOTION
- NO_SUPABASE_WRITES
- NO_TELEGRAM_SEND
- CANONICAL_HORSE_PASSPORT_NOT_MUTATED
- REPORT_ONLY
