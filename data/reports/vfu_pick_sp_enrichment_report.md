# VFU Pick_SP Local Enrichment Report — VFU-03

**Generated:** 2026-06-14T20:12:13.756461+00:00
**Version:** VFU_PICK_SP_ENRICHMENT_V1

## Coverage Summary

| Metric | Value |
|---|---|
| Total union rows | 1263 |
| pick_sp before enrichment | 0 (0.0%) |
| pick_sp after enrichment | 107 (8.47%) |
| Primary join (race_id+horse) | 107 |
| Secondary join (date+course+time+horse) | 0 |
| Fallback join (±2 min, unique) | 0 |
| Unmatched rows | 1156 |
| Ambiguous rows | 0 |
| Conflict rows | 0 |

## Coverage by Source Layer

| Layer | Total | SP Filled | % |
|---|---|---|---|
| LOCAL_ONLY | 294 | 0 | 0.0% |
| OVERLAP | 438 | 30 | 6.8% |
| SUPABASE_ONLY | 531 | 77 | 14.5% |

## Coverage by Date Block

| Block | Total | SP Filled | % |
|---|---|---|---|
| May08-May22 | 498 | 77 | 15.5% |
| May23-Jun13 | 471 | 30 | 6.4% |
| NO_DATE | 294 | 0 | 0.0% |

## Missing Reason Breakdown

| Reason | Count |
|---|---|
| UNMATCHED_LOCAL_ONLY | 537 |
| UNMATCHED_NO_CSV_ENTRY | 465 |
| MATCHED_SP_ZERO_OR_EMPTY | 154 |

## Top Unmatched Courses

| Course | Unmatched Count |
|---|---|
| Bath | 20 |
| York | 16 |
| Newbury | 15 |
| Killarney (IRE) | 14 |
| Uttoxeter | 14 |
| Doncaster | 13 |
| Perth | 12 |
| Newmarket | 11 |
| Thirsk | 11 |
| Ascot | 10 |

## Full 1,263-Row Pass Assessment

**Recommended:** PENDING OPERATOR REVIEW

107/1263 rows have pick_sp (8.5%). LOCAL_ONLY rows (294) are structurally unmatchable. Remaining unmatched are races not present in innovation CSV. Proceed with null-tolerant autopsy logic.

## Hard Rule Confirmations

| Check | Status |
|---|---|
| Supabase staging NOT created | CONFIRMED |
| Canonical Horse Passport NOT mutated | CONFIRMED |
| No Supabase writes | CONFIRMED |
| No live scoring change | CONFIRMED |
| No model promotion | CONFIRMED |
| No Telegram send | CONFIRMED |
| No Racing API restoration | CONFIRMED |

## Final Classifications

- `VFU_PICK_SP_LOCAL_ENRICHMENT_COMPLETE`
- `VFU_PICK_SP_COVERAGE_REPORTED`
- `SUPABASE_STAGING_NOT_CREATED`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `NO_SUPABASE_WRITES`