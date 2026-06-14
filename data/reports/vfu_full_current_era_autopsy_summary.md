# VFU-04 — Full Current-Era Autopsy Summary

**Generated:** 2026-06-14T20:39:59.683557+00:00
**Source:** enriched current-era sigma union, May 08–Jun 13 2026
**Canonical Passport mutated:** NO
**Supabase written:** NO

---

## 1. Rows Scanned and Autopsy Coverage

| Metric | Value |
|---|---|
| Total rows scanned | 1263 |
| Autopsies created | 1263 |
| Rows excluded (TIER_E) | 0 |

## 2. Evidence Quality Tiers

| Tier | Count | % |
|---|---|---|
| TIER_A_FULL | 107 | 8.5% |
| TIER_B_GOOD_NO_PICK_SP | 800 | 63.3% |
| TIER_C_LIMITED_IDENTITY | 62 | 4.9% |
| TIER_D_EVENT_ONLY | 294 | 23.3% |

> horse_id=None for ALL 1,263 rows — passport linkage by name only. All Tier A/B/C passport candidates require human review.

## 3. Field Coverage

| Field | Filled | % |
|---|---|---|
| race_date | 969/1263 | 76.7% |
| horse_name | 969/1263 | 76.7% |
| course | 1224/1263 | 96.9% |
| off_time | 969/1263 | 76.7% |
| vp | 1263/1263 | 100.0% |
| outcome | 1263/1263 | 100.0% |
| pick_sp | 107/1263 | 8.5% |
| actual_winner_sp | 907/1263 | 71.8% |
| horse_id | 0/1263 | 0.0% |
| actual_winner_name | 969/1263 | 76.7% |

## 4. Failure Class Distribution

| Failure Class | Count |
|---|---|
| INSUFFICIENT_EVIDENCE | 390 |
| VP_FALSE_NEGATIVE | 359 |
| VP_FALSE_POSITIVE | 77 |
| MID_PRICE_WALL | 75 |
| LONGSHOT_RELEASE_MISSED | 38 |
| COURSE_DRAIN_CONFIRMED | 17 |

## 5. Win Class Distribution

| Win Class | Count |
|---|---|
| VP_HIGH_WIN | 100 |
| VP_FALSE_NEGATIVE_WIN | 98 |
| VP_MID_WIN | 67 |
| VP_LOW_WIN | 37 |
| VP_CONFIRMED_FAVOURITE_WIN | 5 |

## 6. VP Threshold Performance

| VP >= | N | Wins | SR |
|---|---|---|---|
| 0.25 | 557 | 181 | 32.5% |
| 0.3 | 419 | 150 | 35.8% |
| 0.35 | 306 | 118 | 38.6% |
| 0.4 | 213 | 92 | 43.2% |
| 0.45 | 154 | 71 | 46.1% |
| 0.5 | 105 | 51 | 48.6% |
| 0.55 | 66 | 32 | 48.5% |
| 0.6 | 39 | 21 | 53.8% |

## 7. Course Tier Performance

| Course Tier | N | Wins | SR |
|---|---|---|---|
| EXCELLING | 68 | 33 | 48.5% |
| DRAIN | 34 | 3 | 8.8% |
| NEUTRAL | 867 | 220 | 25.4% |

## 8. SP Dead-Zone Evidence

**Note**: SP dead-zone analysis limited to rows with pick_sp only (n=107).

| Odds Band | Count (TIER_A only) |
|---|---|
| SP_1.5_4.0 | 54 |
| SP_4.0_6.0 | 15 |
| SP_6.0_PLUS | 38 |

## 9. Passport Candidates

- Total created: 69
- TIER_A: 9
- TIER_B: 53
- TIER_C: 7

All candidates have `do_not_merge=True` and `human_review_required=True`.

## 10. Pattern Evidence

- Total created: 207

## 11. Repeated Horses

- Horses appearing 2+ times: 46

| Horse | Count | Wins | SR | Avg VP | Label |
|---|---|---|---|---|---|
| kakirra | 3 | 3 | 100% | 0.2651 | NEEDS_REVIEW |
| chemistry | 2 | 0 | 0% | 0.1916 | NEEDS_REVIEW |
| hood wink | 2 | 0 | 0% | 0.2511 | NEEDS_REVIEW |
| mereside princess | 2 | 1 | 50% | 0.1779 | HIDDEN |
| jannas journey | 2 | 0 | 0% | 0.2968 | NEEDS_REVIEW |
| gentle warrior | 2 | 0 | 0% | 0.316 | NEEDS_REVIEW |
| tickettothestars | 2 | 0 | 0% | 0.2509 | NEEDS_REVIEW |
| cromac quay | 2 | 1 | 50% | 0.4031 | IMPROVING |
| amidst the chaos | 2 | 0 | 0% | 0.2697 | NEEDS_REVIEW |
| arths gold | 2 | 0 | 0% | 0.1746 | NEEDS_REVIEW |
| navy light | 2 | 0 | 0% | 0.4533 | UNRELIABLE |
| legacy link | 2 | 1 | 50% | 0.4162 | IMPROVING |
| man is king | 2 | 2 | 100% | 0.2296 | COURSE_DEPENDENT |
| alma latina | 2 | 1 | 50% | 0.3614 | IMPROVING |
| springhill warrior | 2 | 0 | 0% | 0.3445 | NEEDS_REVIEW |
| le diablo | 2 | 0 | 0% | 0.2251 | NEEDS_REVIEW |
| eye of a tiger | 2 | 0 | 0% | 0.2228 | NEEDS_REVIEW |
| wee mary | 2 | 1 | 50% | 0.2777 | NEEDS_REVIEW |
| gaelic approach | 2 | 0 | 0% | 0.5106 | UNRELIABLE |
| humble spark | 2 | 0 | 0% | 0.4357 | UNRELIABLE |

## 12. Data Quality Debts

| Debt | Count |
|---|---|
| horse_id_null — RP uid not in sigma row | 1263 |
| pick_sp_null — not stored in sigma union | 1156 |
| actual_winner_sp_null | 356 |
| actual_winner_name_null | 294 |
| off_time_null | 294 |

## 13. VFU-05 Pattern Prosecutor Recommendation

**PROCEED**

207 pattern evidence records created from 969 usable autopsies. Repeated horse tracker: 46 horses. Operator review of this summary required before Pattern Prosecutor opens.

---

## Hard Rule Confirmations

| Check | Status |
|---|---|
| Canonical Horse Passport NOT mutated | CONFIRMED |
| No Supabase writes | CONFIRMED |
| No Supabase staging created | CONFIRMED |
| No live scoring change | CONFIRMED |
| No model promotion | CONFIRMED |
| No Telegram send | CONFIRMED |
| No Racing API restoration | CONFIRMED |
| No Mar–Apr extraction | CONFIRMED |
| ROI limited to pick_sp rows | CONFIRMED |
| Passport candidates dry-run only | CONFIRMED |

## Final Classifications

- `VFU_04_FULL_CURRENT_ERA_AUTOPSY_COMPLETE`
- `EVIDENCE_QUALITY_TIERS_ENFORCED`
- `PASSPORT_CANDIDATES_DRY_RUN_ONLY`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `REPEATED_HORSE_TRACKER_BUILT`
- `PATTERN_EVIDENCE_CREATED`
- `ROI_LIMITED_TO_PICK_SP_ROWS`
- `NO_MAR_APR_EXTRACTION`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`