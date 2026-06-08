# May 21 + May 22 Shadow Consume — Idempotency Verification

**Generated:** 2026-05-23  
**Verification type:** POST_CONSUME_IDEMPOTENCY  
**Dates verified:** 2026-05-21, 2026-05-22  
**Status:** ALL CHECKS PASS

---

## Summary

| Check | Expected | Actual | Result |
|---|---|---|---|
| May 21 unconsumed eligible rows | 0 | 0 | PASS |
| May 22 unconsumed eligible rows | 0 | 0 | PASS |
| consumed_shadow (total) | 80 | 80 | PASS |
| consumed_live (total) | 0 | 0 | PASS |
| shadow_full_train_v2 race_count | 2055 | 2055 | PASS |
| sentient_state.json hash unchanged | 1016d89dceb28da5 | 1016d89dceb28da5 | PASS |

All 6 checks pass. No action required.

---

## Per-Date Detail

### 2026-05-21

| Field | Value |
|---|---|
| total_rows | 44 |
| consumed_shadow | 44 |
| consumed_live | **0** |
| unconsumed | **0** |

### 2026-05-22

| Field | Value |
|---|---|
| total_rows | 36 |
| consumed_shadow | 36 |
| consumed_live | **0** |
| unconsumed | **0** |

---

## Combined Totals

| Field | Value |
|---|---|
| total_rows | 80 |
| consumed_shadow | 80 |
| consumed_live | **0** |

`consumed_live = 0` across all 80 rows — hard constraint maintained.

---

## Shadow Brain State

| Field | Value |
|---|---|
| shadow_full_train_v2 total_races_observed | **2055** |
| shadow_full_train_v2 hash | `570f6210adb56191` |
| sentient_state.json hash | `1016d89dceb28da5` |
| sentient_state.json unchanged | **True** |

---

## Governance Verification

```
No scoring changes applied            ✓
No VP model changes                   ✓
No candidate_route() changes          ✓
No router rule changes                ✓
No staking changes                    ✓
No Telegram runtime changes           ✓
No Playbook G promotion               ✓
consumed_live = 0 (all rows)          ✓
sentient_state.json unchanged         ✓
shadow_full_train_v2 at expected count ✓
```

Re-running Phase 3B on either date would produce 0 new consumed rows (idempotent). No additional consume actions required.
