# VFU-21 — pick_sp Backfill — Operator Brief

## Summary
| Metric | Value |
|---|---|
| Total ledger rows | 3052 |
| Backfill candidates (null / 0.0 / 10.0) | 2214 |
| Recovered | 996 (45.0% of candidates with results files) |
| Unrecoverable | 1218 |
| Real pick_sp coverage after backfill | 1845/3052 (60.5%) |

## Method Breakdown
| Method | Count |
|---|---|
| RECOVERED_FROM_RP_RESULTS | 996 |
| UNRECOVERABLE_NO_RESULTS_FILE | 931 |
| ORIGINAL_PRESENT | 838 |
| UNRECOVERABLE_SP_NOT_IN_FILE | 186 |
| UNRECOVERABLE_HORSE_NOT_FOUND | 101 |

## Evidence Tier Changes
| Tier | Before | After |
|---|---|---|
| TIER_A_FULL | 107 | **430** |
| TIER_B_GOOD | 0 | **12** |
| TIER_B_GOOD_NO_PICK_SP | 800 | **465** |
| TIER_C_LIMITED_IDENTITY | 62 | 62 |
| high | 5 | 5 |
| low | 290 | 290 |
| normal | 31 | 31 |

## Classifications
- VFU_21_PICK_SP_BACKFILL_COMPLETE
- SP_RECOVERED_FROM_RP_RESULTS
- UNRECOVERABLE_CLASSIFIED_BY_REASON
- EVIDENCE_TIER_UPGRADED_WHERE_POSSIBLE
- NO_VP_THRESHOLD_CHANGE
- NO_LIVE_SCORING_CHANGE
- NO_SUPABASE_WRITES
- REPORT_ONLY

## Operating Lock (unchanged)
- NO Passport mutation
- NO Supabase writes
- NO live scoring change
- NO model promotion
- Validated by: VFU_21_PICK_SP_BACKFILL_V1