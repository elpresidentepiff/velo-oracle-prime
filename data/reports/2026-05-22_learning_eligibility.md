# May 22 Learning Eligibility Audit

**Date:** 2026-05-22
**Generated:** 2026-05-23T02:28:21.484892+00:00
**Audit Status:** `ELIGIBLE`
**Target State:** `shadow_full_train_v2`

---

## Gate Checks

| Check | Value | Status |
|---|---|---|
| flatline_count | 0 | PASS |
| identity_failures | 0 | PASS |
| source_truth | RP_MERGED_CLEAN | PASS |
| learning_gate | OPEN | PASS |
| council_verdict | PASS_TO_LEARNING | PASS |
| consumed_live_before | 0 | PASS |
| unresolved_rows | 0 | PASS |

---

## Row Counts

| Category | Count |
|---|---|
| Verdict races total | 43 |
| Eligible for learning | **36** |
| Excluded | 7 |
| Unresolved | 0 |
| sigma_audits rows | 36 |
| Existing learning events (before) | 0 |
| consumed_shadow (before) | 0 |
| consumed_live (before) | 0 |

---

## Eligible Rows — Breakdown

| Outcome | Count |
|---|---|
| WIN | 9 |
| MISS | 19 |
| PLACED/OTHER | 8 |

### By Tier

| Tier | Count |
|---|---|
| A | 5 |
| B | 12 |
| C | 12 |
| X | 7 |

---

## Excluded Races

| Race ID | Tier | VP | Reason |
|---|---|---|---|
| rp_DPT_20260522_5.20 | X | 0.0847 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_5.52 | C | 0.1098 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_6.29 | X | 0.0851 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_7.00 | X | 0.1584 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_7.30 | A | 0.4700 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_8.00 | B | 0.2297 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_8.30 | B | 0.3504 | NO_RESULT_DPT_DATA_GAP |

> **DPT Tier A exclusion:** rp_DPT_20260522_7.30 — Downpatrick data gap. No result available. Not a miss — result unknown.

---

## Live State Snapshot

| Field | Value |
|---|---|
| live_state_hash_before | `a1637542f7646aa9` |
| shadow_full_train_v2 path | `data/sentient_state_shadow_full_train_v2.json` |

---

## Governance

```
target_state = shadow_full_train_v2
consumed_live = 0 (hard stop if > 0)
sentient_state_touched = False at build-events-only stage
playbook_g_promoted = False
live_state_hash unchanged until Phase 3B shadow consume
```

---

## Recommendation

**PROCEED to build-events-only** — all gates clear. 36 eligible rows, 0 hard stops.
