# VFU-06 — Horse Identity Bridge Report

**Generated**: 2026-06-14T21:43:55Z
**Bridge version**: VFU_HORSE_IDENTITY_BRIDGE_V1
**Canonical Passport mutated**: NO
**Supabase written**: NO

---

## Coverage

| Metric | Before | After |
|---|---|---|
| horse_id filled | 0/1263 (0.0%) | 703/1263 (55.7%) |

## Confidence Breakdown

| Confidence | Count |
|---|---|
| HIGH | 559 |
| MEDIUM | 124 |
| LOW | 20 |
| AMBIGUOUS | 1 |
| UNMATCHED | 559 |

## Namespace Breakdown

| Namespace | Count |
|---|---|
| UNKNOWN | 560 |
| RP_UID | 559 |
| EOD_NUMERIC | 110 |
| CONSTRUCTED_RP_NAME | 27 |
| RACING_API_HRS | 7 |

## Source Breakdown

| Source | Count |
|---|---|
| PASSPORT_NORM_MATCH | 559 |
| EOD_RACE_MATCH | 124 |
| EOD_NAME_MATCH | 20 |

## Special Cases

- Structurally unmatchable (no horse_name): **322**
- Ambiguous: **1**
- Conflicts: **0**
- Passport ambiguous norm names: **1**

## Kakirra

- horse_id: **8866972**
- namespace: **RP_UID**
- source: **PASSPORT_NORM_MATCH**
- confidence: **HIGH**

## Repeated Clusters

- Found: 20
- With identity: 19

## Passport Candidates

- Gaining canonical RP_UID: **41**
- Gaining non-canonical EOD ID: **14**
- Passport automation status: **PARTIALLY_UNBLOCKED_FOR_RP_UID_ROWS**

## Hard Rule Confirmations

| Check | Status |
|---|---|
| Canonical Horse Passport NOT mutated | CONFIRMED |
| No Supabase writes | CONFIRMED |
| No live scoring change | CONFIRMED |
| No model promotion | CONFIRMED |
| No Telegram send | CONFIRMED |
| No Racing API restoration | CONFIRMED |
| No Mar–Apr extraction | CONFIRMED |

## Final Classifications

- `VFU_06_HORSE_IDENTITY_BRIDGE_COMPLETE`
- `HORSE_ID_COVERAGE_REPORTED`
- `HORSE_ID_NAMESPACE_PRESERVED`
- `PASSPORT_RP_UID_CONFIRMED_AS_CANONICAL_WHEN_UNIQUE`
- `EOD_IDENTITIES_RECORDED_AS_DRY_RUN_NON_CANONICAL_WHEN_NEEDED`
- `AMBIGUOUS_IDENTITIES_NOT_FILLED`
- `CONFLICTING_IDENTITIES_NOT_OVERRIDDEN`
- `UNMATCHED_IDENTITIES_DECLARED`
- `STRUCTURALLY_UNMATCHABLE_ROWS_DECLARED`
- `PASSPORT_CANDIDATES_IDENTITY_ENRICHED_DRY_RUN_ONLY`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `REPEATED_HORSE_TRACKER_IDENTITY_REBUILT`
- `NO_MAR_APR_EXTRACTION`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`