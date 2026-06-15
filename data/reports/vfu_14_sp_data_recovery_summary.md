# VFU-14 — SP Data Recovery Summary

**Generated:** 2026-06-15T19:03:21.911544+00:00
**SP Recovery Version:** VFU_14_SP_DATA_RECOVERY_V1
**VFU-10 Law:** *No evidence becomes doctrine unless it was knowable before the race.*

---

## Stats

| Metric | Value |
|---|---|
| Total FG cases (VFU-13) | 121 |
| Already had pick_sp | 12 |
| Missing pick_sp | 109 |
| Recovered this run | 89 |
| Still missing | 20 |
| Ambiguous cases | 0 |
| MISS (no place) | 56 |
| PLACED (2nd–4th) | 65 |
| VP threshold | 0.40 (UNCHANGED) |

---

## SP Sources

| Source | Cases |
|---|---|
| sp_original (already in VFU-13) | 12 |
| innovation_csv | 40 |
| sigma_2k_training | 19 |
| rp_results_new_format_numeric_rid | 11 |
| rp_results_new_format_cdo_fallback | 19 |
| unmatched | 20 |

---

## Final Classifications

- `VFU_14_SP_DATA_RECOVERY_COMPLETE`
- `FALSE_GREEN_PRICE_ATTRIBUTION_RERUN_COMPLETE`
- `PICK_SP_RECOVERY_REPORTED`
- `MISSING_PICK_SP_RECLASSIFIED_AS_ATTRIBUTION_BLOCKER`
- `MISS_AND_PLACED_CASES_SEPARATED`
- `PLACE_SIGNAL_NOT_WIN_SIGNAL_DECLARED`
- `NO_VP_THRESHOLD_CHANGE`
- `NO_LIVE_DOCTRINE_PROMOTION`
- `MAR_APR_QUARANTINE_MAINTAINED`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`

---

## Governing Rules

- All outputs: **DRY_RUN_ONLY**
- `blocked_from_live_use = True`
- `human_approval_required = True`
- NO Supabase writes | NO Passport mutation | NO live scoring change
- VP threshold: **0.40 — UNCHANGED**
