# VFU-14 — False-GREEN Price Attribution Report

**Generated:** 2026-06-15T19:03:21.904271+00:00
**SP Recovery Version:** VFU_14_SP_DATA_RECOVERY_V1
**VFU-10 Law:** *No evidence becomes doctrine unless it was knowable before the race.*

---

## Scope

| Metric | Value |
|---|---|
| Total FG cases | 121 |
| MISS cases (VP≥0.40, no place) | 56 |
| PLACED cases (VP≥0.40, 2nd–4th) | 65 |
| VP threshold | 0.40 (UNCHANGED) |
| Era | Current era only (≥2026-05-08) |

---

## SP Recovery Summary

| Source | Cases Recovered |
|---|---|
| sp_original (already in VFU-13) | 12 |
| innovation_csv | 40 |
| sigma_2k_training | 19 |
| rp_results_new_format_numeric_rid | 11 |
| rp_results_new_format_cdo_fallback | 19 |
| unmatched | 20 |
| **Still missing** | **20** |
| **Total recovered** | **89** |

---

## Price Band Distribution (MISS cases only)

| Band | Cases |
|---|---|
| SHORT | 16 |
| MID_PRICE | 13 |
| UNKNOWN | 10 |
| DANGER | 9 |
| LONGSHOT | 5 |
| ODDS_ON | 3 |

---

## Attribution Label Distribution (all 121 FG cases)

| Attribution Label | Cases |
|---|---|
| PLACE_SIGNAL_NOT_WIN_SIGNAL | 65 |
| HIGH_VP_SHORT_PRICE_FAILURE | 18 |
| HIGH_VP_MID_PRICE_WALL | 12 |
| HIGH_VP_NO_PICK_SP_REMAINING | 10 |
| HIGH_VP_DANGER_ZONE_FAILURE | 9 |
| HIGH_VP_LONGSHOT_FALSE_CONFIDENCE | 5 |
| HIGH_VP_DRAIN_COURSE_WARNING | 2 |

---

## Key Findings

1. **PLACED cases (65/121)** are labelled `PLACE_SIGNAL_NOT_WIN_SIGNAL`. VP≥0.40 successfully identified place-worthy horses — this is not total VP failure.

2. **SP recovered: 89/109 missing cases** recovered across 4 local sources.

3. **20 cases remain UNMATCHED** with explicit `pick_sp_missing_reason` codes. Primary reasons: early-May dates not in RP results files (3), racing post rp_ prefix races with no runner-level SP (2), horse name unknown (2), and Food For Thought (rac_ prefix not in any local source).

4. **SHORT-priced MISS cases** (VP≥0.40, SP<4.0, non-placed, non-DRAIN) represent the clearest VP overconfidence cases — VP fired but the market was also short on a horse that didn't win.

---

## Governing Rules

- `blocked_from_live_use = True`
- `human_approval_required = True`
- `dry_run_only = True`
- NO Supabase writes
- NO Passport mutation
- NO VP threshold change (0.40 UNCHANGED)
- NO live scoring change
- Mar–Apr quarantine maintained
