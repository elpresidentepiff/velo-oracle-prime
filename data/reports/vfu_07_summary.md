# VFU-07 — Identity-Confirmed Passport Review

**Generated**: 2026-06-14T21:55:49Z
**Review version**: VFU_PASSPORT_REVIEW_V1
**Canonical Passport mutated**: NO
**Supabase written**: NO

---

## Phase A — Passport Candidates

| Category | Count |
|---|---|
| Total candidates | 69 |
| RP_UID canonical | 41 |
| EOD non-canonical | 14 |
| No identity | 14 |

### Verdicts

| Verdict | Count |
|---|---|
| PROMOTE_TO_PASSPORT_REVIEW | 30 |
| EOD_ID_NEEDS_RECONCILIATION | 21 |
| OBSERVE_ONLY | 18 |

### Top PROMOTE_TO_PASSPORT_REVIEW candidates

| Horse | RP_UID | Outcome | VP | Tier | Score | Passport exists |
|---|---|---|---|---|---|---|
| Vidmiyr | 8018230 | WIN | 0.5489 | TIER_A_FULL | 9 | YES |
| Undercover Affair | 9153298 | WIN | 0.6346 | TIER_A_FULL | 9 | YES |
| Cleodolinda | 9254402 | WIN | 0.5472 | TIER_A_FULL | 9 | YES |
| Red Spells Danger | 7436366 | WIN | 0.5323 | TIER_B_GOOD_NO_PICK_SP | 8 | YES |
| Real Trouble | 9115839 | WIN | 0.583 | TIER_B_GOOD_NO_PICK_SP | 8 | YES |
| Ron's Angel | 9184996 | WIN | 0.7255 | TIER_B_GOOD_NO_PICK_SP | 8 | YES |
| Loriko | 7258540 | WIN | 0.7921 | TIER_B_GOOD_NO_PICK_SP | 8 | YES |
| Coumeenoole | 5884272 | WIN | 0.646 | TIER_B_GOOD_NO_PICK_SP | 8 | YES |
| Pearl Eye | 4273988 | WIN | 0.6861 | TIER_B_GOOD_NO_PICK_SP | 8 | YES |
| Sunshine Star | 8227212 | WIN | 0.5428 | TIER_B_GOOD_NO_PICK_SP | 8 | YES |

---

## Phase B — Repeated Horse Truth Tables

| Cluster verdict | Count |
|---|---|
| NOISE | 8 |
| NEEDS_MORE_RUNS | 4 |
| PLACE_SPECIALIST | 3 |
| VP_UNDERCOUNTING | 2 |
| LEARNABLE_VP_POSITIVE | 2 |
| IDENTITY_UNRESOLVED | 1 |

### VP_UNDERCOUNTING clusters

| Horse | ID | Wins | Apps | Avg VP | All below threshold |
|---|---|---|---|---|---|
| kakirra | 8866972 | 3 | 3 | 0.265 | True |
| man is king | 3839266 | 2 | 2 | 0.230 | True |

### LEARNABLE_VP_POSITIVE clusters

| Horse | ID | Wins | Apps | Avg VP | Trend |
|---|---|---|---|---|---|
| legacy link | 7947750 | 1 | 2 | 0.416 | None |
| cromac quay | 8214881 | 1 | 2 | 0.403 | None |

---

## Phase C — Kakirra Case Study

- **RP_UID**: 8866972
- **VFU appearances**: 3 | **VFU wins**: 3 | **VFU SR**: 100%
- **VP range**: 0.175–0.343 (avg 0.265)
- **All wins below VP threshold (0.40)**: True
- **Passport**: 5 runs, win_rate=0.6, SP=SHORTENING
- **Pattern**: VP_UNDERCOUNTING — Passport truth ahead of VP

---

## Review Queue Summary

Total entries: **37**

| Queue type | Count |
|---|---|
| PASSPORT_CANDIDATE_REVIEW | 30 |
| PLACE_SPECIALIST_CLUSTER | 3 |
| LEARNABLE_CLUSTER | 2 |
| KAKIRRA_CASE_STUDY | 1 |
| VP_UNDERCOUNTING_CLUSTER | 1 |

---

## Hard Rule Confirmations

| Check | Status |
|---|---|
| Canonical Horse Passport NOT mutated | CONFIRMED |
| No Passport merge executed | CONFIRMED |
| No Supabase writes | CONFIRMED |
| No live scoring change | CONFIRMED |
| No model promotion | CONFIRMED |
| No live doctrine promotion | CONFIRMED |
| No Telegram send | CONFIRMED |
| No Racing API restoration | CONFIRMED |
| No Mar–Apr extraction | CONFIRMED |

## Final Classifications

- `VFU_07_PASSPORT_REVIEW_COMPLETE`
- `PASSPORT_CANDIDATES_SCORED`
- `REPEATED_HORSE_TRUTH_TABLES_BUILT`
- `KAKIRRA_CASE_STUDY_COMPLETE`
- `VP_UNDERCOUNTING_PATTERN_DOCUMENTED`
- `LEARNABLE_PATTERNS_IDENTIFIED`
- `NO_PASSPORT_MERGE_EXECUTED`
- `NO_LIVE_DOCTRINE_PROMOTION`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `NO_SUPABASE_WRITES`
- `NO_LIVE_SCORING_CHANGE`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`
- `NO_MAR_APR_EXTRACTION`