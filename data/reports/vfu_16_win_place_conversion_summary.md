# VFU-16 — Win/Place Conversion Tribunal

**Version:** VFU_16_WIN_PLACE_CONVERSION_TRIBUNAL_V1
**Generated:** 2026-07-12T15:58:56.533198Z
**VP_THRESHOLD:** 0.40 (UNCHANGED)

## Scope

| | Count |
|---|---|
| Total false-GREEN cases | 121 |
| MISS (not placed) | 56 |
| PLACED (not won) | 65 |

## Mechanism Split

| Mechanism | Count |
|---|---|
| PLACE_STRONG_WIN_WEAK | 68 |
| INSUFFICIENT_COMPONENT_DATA | 23 |
| MARKET_AND_VP_JOINT_OVERCONFIDENCE | 16 |
| DATA_LINEAGE_REQUIRED | 3 |
| DRAIN_COURSE_CONTEXT | 3 |
| SOURCE_GAP_NO_SP | 3 |
| SP_SOURCE_ZERO_BLOCKER | 3 |
| SQPE_SMALL_FIELD_EXCEPTION | 1 |
| TRUE_WIN_SIGNAL_FAILED | 1 |

## Key Findings

- **PLACE_STRONG_WIN_WEAK:** 68 cases (65 PLACED definitionally + MISS with confirmed place_prob dominance)
- **MARKET_AND_VP_JOINT_OVERCONFIDENCE:** 16 MISS cases — market AND VP agreed, both wrong (dominant in short-price misses)
- **PLACE_PROB_DOMINANT confirmed:** 19 cases with component data and place_prob >= 0.80
- **Guardrail retrospective candidates:** 4 cases would have triggered PLACE_STRONG_WIN_UNPROVEN (DRY_RUN_ONLY)

## 8 Core Questions

| Q | Answer |
|---|---|
| Q1 PLACE_PROB_DOMINANT MISS count | 5 confirmed (component data) |
| Q2 Short-price joint overconfidence | 16 MISS cases |
| Q3 Place-strong win-weak total | 68 (MISS + PLACED) |
| Q4 Data lineage repair needed | 3 MISS cases |
| Q5 Is place_prob too influential? | YES |
| Q6 Calibration vs signal issue? | CALIBRATION_ISSUE |
| Q7 VFU-17 focus on guardrail? | YES |
| Q8 Live scoring change now? | **NO** |

## Named Exception Cases (retained verbatim)

- **Lightsoutandaway:** SQPE_SMALL_FIELD_EXCEPTION — sqpe=0.099, place_prob=0.49, field_size=6, Chase. Separate mechanism, not place_prob inflation.
- **Food For Thought (rac_11930100, Beverley):** DATA_LINEAGE_REQUIRED — P0 evidence gap, RAC_PREFIX_NOT_IN_ANY_SOURCE. Not classifiable until lineage resolved.
- **Martymill:** TRUE_WIN_SIGNAL_FAILED — improvement_score=0.636, MDS=0.746. Both WIN signals co-fired strongly. Both wrong. Highest-priority P0 review.

## Doctrine Implications (NOT YET ACTIVE)

1. VP needs a win/place **separation layer** — not a threshold change
2. place_prob inflating VP is a **calibration issue**, not a signal failure
3. Proposed guardrail: **PLACE_STRONG_WIN_UNPROVEN** (DRY_RUN_ONLY)
   - Trigger: place_prob >= 4 cases retrospectively
   - Effect: flag only — no VP change, no scoring block
   - Status: **OPERATOR REVIEW REQUIRED before any live use**

## Hard Rules (permanent)

- VP threshold: **0.40 UNCHANGED**
- No live scoring change
- No Passport mutation
- No Supabase writes
- No doctrine promotion
- No model promotion
- No Telegram send
- No Racing API restoration

## Final Classifications (15)

- `VFU_16_WIN_PLACE_CONVERSION_TRIBUNAL_COMPLETE`
- `PLACE_PROB_DOMINANT_FAILURE_CONFIRMED`
- `WIN_PLACE_SEPARATION_REQUIRED`
- `FALSE_GREEN_MECHANISMS_SPLIT`
- `FOOD_FOR_THOUGHT_DATA_LINEAGE_RETAINED`
- `LIGHTSOUTANDAWAY_EXCEPTION_RETAINED`
- `GUARDRAIL_PROPOSAL_DRY_RUN_ONLY`
- `NO_LIVE_SCORING_CHANGE`
- `NO_VP_THRESHOLD_CHANGE`
- `NO_LIVE_DOCTRINE_PROMOTION`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`
