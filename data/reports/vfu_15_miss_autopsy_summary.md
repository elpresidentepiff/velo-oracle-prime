# VFU-15 — False-GREEN MISS Autopsy

**Generated:** 2026-06-15T19:24:51.771725+00:00
**Validation Version:** VFU_15_FALSE_GREEN_MISS_AUTOPSY_V1
**VFU-10 Law:** *No evidence becomes doctrine unless it was knowable before the race.*

---

## Scope

56 MISS cases only (VP≥0.40, not WIN, not PLACED).
The 65 PLACED cases are **excluded** — future EW/frame layer territory.

| Metric | Value |
|---|---|
| Total FG cases (VFU-13) | 121 |
| MISS cases investigated | 56 |
| PLACED cases excluded | 65 |
| MISS with pick_sp | 46 |
| MISS without SP | 10 |
| MISS with component data | 7 |
| VP threshold | 0.40 (UNCHANGED) |

---

## SP Classification Distribution (56 MISS cases)

| Classification | Count |
|---|---|
| SHORT_PRICE_MISS | 16 |
| MID_PRICE_MISS | 12 |
| DANGER_ZONE_MISS | 9 |
| SOURCE_GAP_NO_SP | 5 |
| LONGSHOT_MISS | 5 |
| DRAIN_MISS | 4 |
| SP_SOURCE_ZERO_BLOCKER | 3 |
| ODDS_ON_MISS | 2 |

**Dominant failure mode:** `SHORT_PRICE_MISS`

---

## Component Analysis (7 MISS cases with 2K data)

| Component | Avg (MISS) |
|---|---|
| place_prob | 0.8357 |
| sqpe_v17_prob | 0.0489 |
| improvement_score | 0.1964 |
| market_deception_score | 0.2475 |

**Finding:** PLACE_PROB_DOMINANT in 5/7 MISS cases with data (avg place_prob=0.836). Place model badge fires for horses that are place-worthy but not win-worthy — VP inherits this signal even though place_prob is badge-only in ensemble. EXCEPTION: Lightsoutandaway (VP=0.522, SHORT, small-field Chase, SQPE=0.099, place_prob=0.49) — SQPE-driven overconfidence, not place_prob. Martymill (VP=0.419, SHORT): improvement=0.636 + MDS=0.746 double signal that was wrong — extreme improvement/market-deception co-fire.

---

## Denominator Audit (121 vs 109)

12 of the 121 FG cases already had pick_sp in VFU-13 original data (sp_source=vfu_13_original). These 12 were excluded from SP recovery because they did not require it. VFU-14's recovery target was the remaining 109. Recovered 89, still missing 20.

| Step | Count |
|---|---|
| Total FG cases | 121 |
| Already had SP (VFU-13) | 12 |
| SP recovery target | 109 |
| Recovered by VFU-14 | 89 |
| Still missing | 20 |

---

## Key Findings

1. SHORT_PRICE_MISS is the dominant failure mode (16 cases). Market agreed with VP — both wrong. This is genuine VP+market overconfidence.
2. PLACE_PROB_DOMINANT in 5/7 MISS cases with component data (avg place_prob=0.836). Place badge inflates VP even when horse cannot win.
3. Lightsoutandaway is the SQPE-driven MISS exception: VP=0.522, SHORT, small-field Chase, sqpe=0.099, place_prob=0.49. Different failure mechanism from the rest.
4. Martymill: extreme improvement=0.636 + MDS=0.746 co-fire on a SHORT-price horse that missed completely. Double signal that was wrong.
5. June 5 = 3 SP_SOURCE_ZERO_BLOCKER cases in MISS set. Source failure, not model failure.
6. Food For Thought (rac_11930100, Beverley): P0 named evidence gap with no SP in any local source. RAC_PREFIX_NOT_IN_ANY_SOURCE.

---

## Final Classifications

- `VFU_15_FALSE_GREEN_MISS_AUTOPSY_COMPLETE`
- `MISS_CASES_SCOPE_56_ONLY`
- `PLACED_CASES_EXCLUDED`
- `SHORT_PRICE_MISS_IS_DOMINANT_FAILURE_MODE`
- `PLACE_PROB_DOMINANT_IN_MISS_COMPONENT_CASES`
- `SP_SOURCE_ZERO_BLOCKER_LOGGED`
- `DENOMINATOR_AUDIT_COMPLETE`
- `NAMED_EVIDENCE_GAPS_DOCUMENTED`
- `NO_VP_THRESHOLD_CHANGE`
- `NO_LIVE_DOCTRINE_PROMOTION`
- `MAR_APR_QUARANTINE_MAINTAINED`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`

---

## Governing Rules

- All outputs: **DRY_RUN_ONLY**
- `blocked_from_live_use = True`
- `human_approval_required = True`
- NO Supabase writes | NO Passport mutation | NO live scoring change
- VP threshold: **0.40 — UNCHANGED**
- Mar–Apr quarantine: **MAINTAINED**
