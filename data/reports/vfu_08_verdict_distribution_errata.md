# VFU-08 Verdict Distribution Errata

**Filed**: 2026-06-14  
**Type**: VERBAL_SUMMARY_CORRECTION — data files were always correct.

---

## Error Description

The final VFU-08 verbal report mixed cluster counts into the candidate verdict distribution.
The data files, scripts, and JSON outputs were correct throughout.

---

## Candidate Distribution — Correct vs Reported

| Verdict | Reported | Correct |
|---|---|---|
| NEEDS_IDENTITY_RECONCILIATION | 28 | 28 ✓ |
| APPROVE_FOR_PASSPORT_UPDATE_REVIEW | 25 | 25 ✓ |
| HOLD_FOR_MORE_EVIDENCE | 7 | **16** ✗ |
| PLACE_EW_PROFILE_ONLY | 3 | **0** ✗ (cluster-only) |
| VP_UNDERCOUNTING_WATCHLIST | 2 | **0** ✗ (cluster-only) |
| REJECT_AS_NOISE | 0 | 0 ✓ |
| **TOTAL** | **65** | **69** |

---

## Root Cause

1. **PLACE_EW_PROFILE_ONLY (3)**: Reported as candidate count. Actually cluster-only. No PLACED outcomes exist in the passport candidate file — all 69 are WIN or MISS. PLACE_EW_PROFILE_ONLY comes from PLACE_SPECIALIST repeated clusters.

2. **VP_UNDERCOUNTING_WATCHLIST (2)**: Kakirra and Man is King appear in clusters only, not in passport candidates. Passport candidate selection floor is **VP_at_race >= 0.503** (VP_HIGH_WIN class). Kakirra's VP was 0.175–0.343 — far below that floor. These horses were correctly captured in the repeated cluster analysis (VFU-07 truth tables) but are invisible to single-race candidate scoring.

3. **HOLD_FOR_MORE_EVIDENCE**: Reported as 7. Actual: **16**. The verbal report read `summary['approve_count']`, `summary['vp_undercounting_count']` etc. (which come from cluster_records counts) instead of reading `summary['verdict_distribution']['HOLD_FOR_MORE_EVIDENCE']`.

---

## Cluster Distribution — Was Always Correct

| Cluster Verdict | Count |
|---|---|
| REJECT_AS_NOISE | 8 |
| PLACE_EW_PROFILE_ONLY | 3 |
| VP_UNDERCOUNTING_WATCHLIST | 2 |
| LEARNABLE_VP_POSITIVE | 2 |
| HOLD_FOR_MORE_EVIDENCE | 4 |
| NEEDS_IDENTITY_RECONCILIATION | 1 |
| **TOTAL** | **20** |

---

## Key VFU-09 Implication

Kakirra and Man is King are invisible to passport candidate scoring because they won with VP below the candidate selection floor (0.503). VFU-09 investigates this systemic blind spot — **65.8% of all current-era wins (202/307) had VP < 0.40**. This is not a corner case. It is the dominant failure pattern.

---

## Files Corrected

| File | Status |
|---|---|
| `vfu_passport_review_candidates.jsonl` | ALWAYS CORRECT |
| `vfu_08_review_summary.json` | ALWAYS CORRECT |
| `vfu_passport_review_operator_decision_queue.json` | ALWAYS CORRECT |
| Verbal VFU-08 final report | CORRECTED BY THIS ERRATA |

## Final Classifications

- `VFU_08_VERDICT_DISTRIBUTION_RECONCILED`
- `REPORTING_ERROR_ONLY_DATA_WAS_ALWAYS_CORRECT`
- `NO_CODE_CHANGE_REQUIRED`
- `NO_DATA_FILE_CHANGE_REQUIRED`