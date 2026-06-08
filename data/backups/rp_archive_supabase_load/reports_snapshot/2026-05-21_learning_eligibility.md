# May 22 Learning Eligibility Audit

**Date:** 2026-05-21
**Generated:** 2026-05-23T02:45:56.320142+00:00
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
| Verdict races total | 44 |
| Eligible for learning | **44** |
| Excluded | 0 |
| Unresolved | 0 |
| sigma_audits rows | 44 |
| Existing learning events (before) | 0 |
| consumed_shadow (before) | 0 |
| consumed_live (before) | 0 |

---

## Eligible Rows — Breakdown

| Outcome | Count |
|---|---|
| WIN | 13 |
| MISS | 22 |
| PLACED/OTHER | 9 |

### By Tier

| Tier | Count |
|---|---|
| A | 6 |
| B | 25 |
| C | 10 |
| X | 3 |

---

## Excluded Races

| Race ID | Tier | VP | Reason |
|---|---|---|---|

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

**PROCEED to build-events-only** — all gates clear. 44 eligible rows, 0 hard stops.
