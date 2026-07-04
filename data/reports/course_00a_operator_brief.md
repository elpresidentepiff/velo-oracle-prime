# COURSE-00A Operator Brief — Source Provenance Tribunal
Generated: 2026-07-01 02:04 UTC
Status: REPORT_ONLY

## Q1. Which COURSE-00 facts were stale?
  Stale facts: 1
  Most critical: Southwell surface = Fibresand (stale since 2021). Corrected to Tapeta.

## Q2. Which COURSE-00 facts were unsourced?
  Draw bias claims: 9/10 downgraded to HYPOTHESIS.
  Pace/front-runner claims: 6/6 downgraded to HYPOTHESIS.
  No local draw, stalls, or running-style data exists in VELO pipeline.

## Q3. Is Southwell corrected?
  Southwell stale fact found: True
  Corrected surface: Tapeta
  Note: All COURSE-00 Southwell fibresand references are now labelled STALE and corrected.

## Q4. Which draw claims remain hypothesis only?
  ALL 10 draw bias claims are HYPOTHESIS_ONLY or SECONDARY_SOURCE.
  Reason: VELO has no runner-level draw data in local pipeline.
  Source: All from PUBLIC_GUIDE_SECONDARY — valid discovery input, not verified fact.
  Exception: Chester low-draw kept as SECONDARY_PUBLIC_SOURCE_HIGH_CONFIDENCE (not VERIFIED).

## Q5. Which pace claims remain hypothesis only?
  ALL 6 pace/front-runner claims are HYPOTHESIS_ONLY.
  Reason: VELO has no in-running position, running-style, or sectional data.

## Q6. What did BHA/RP actually prove accessible?
  Proven locally present: course, going, race_type, distance, field_size, finish_order, SP (partial), trainer (partial).
  BHA/RP sections exist but NOT PROVEN accessible: surface, handedness, draw, GoingStick, stalls_position, OR, pace.
  Login required for RP field-level access. Not yet automated in pipeline.

## Q7. What remains UNKNOWN?
  All draw claims — HYPOTHESIS only (exception: Chester SECONDARY_HIGH_CONFIDENCE).
  All pace/front-runner claims — HYPOTHESIS only.
  surface = SECONDARY_PUBLIC_SOURCE for stable non-fibresand tracks.
  GoingStick, stalls_position, OR, RPR per runner, running style — all LOCAL_ABSENT.

## Q8. Can COURSE-01 proceed after VCP-03?
  Yes, but COURSE-01 must enforce provenance fields on every course feature:
  - Every feature must carry source_status + confidence.
  - HYPOTHESIS features must not be promoted to VELO scoring without local verification.
  - UNKNOWN-safe fallbacks mandatory.
  - Draw and pace data must be LOCALLY CAPTURED before being used in scoring.

## Q9. What must COURSE-01 enforce?
  1. Provenance fields on every course entry (source_status, source_ref, confidence, last_checked).
  2. UNKNOWN-safe fallbacks — if draw/pace unknown, do not degrade or inflate confidence.
  3. Date-sensitive surface mapping — not static fibresand/tapeta from memory.
  4. No HYPOTHESIS promoted to scoring feature without local confirmation.
  5. HYPOTHESIS can be used for shadow analysis only.

## Q10. COURSE-00 status after tribunal?
  COURSE-00 reclassified as: WATCHLIST_MAP_WITH_STALE_FACTS_CORRECTED
  NOT: SOURCE_VERIFIED_COURSE_REGISTRY
  Useful as discovery input and hypothesis generator.
  Not safe for model feature use until COURSE-01 enforces provenance.

## FINAL CLASSIFICATIONS
  - COURSE_00A_SOURCE_PROVENANCE_TRIBUNAL_COMPLETE
  - COURSE_FACTS_EXTRACTED
  - COURSE_FACT_PROVENANCE_TABLE_WRITTEN
  - STALE_FACTS_CORRECTED_OR_QUARANTINED
  - UNSOURCED_CLAIMS_DOWNGRADED
  - SOUTHWELL_SURFACE_STALE_FACT_REVIEWED
  - VERIFIED_COURSE_REGISTRY_V0_WRITTEN
  - DRAW_BIAS_CLAIMS_PROVENANCE_REVIEWED
  - PACE_BIAS_CLAIMS_PROVENANCE_REVIEWED
  - BHA_RP_FIELD_ACCESS_REALITY_CHECKED
  - SOURCE_SECTION_EXISTS_NOT_TREATED_AS_PROOF
  - HYPOTHESES_NOT_PROMOTED_TO_FACTS
  - COURSE_01_REQUIRES_PROVENANCE_FIELDS
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