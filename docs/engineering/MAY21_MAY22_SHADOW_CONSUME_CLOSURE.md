# May 21 + May 22 Shadow Consume Closure

**Date:** 2026-05-23  
**Target State:** `shadow_full_train_v2`  
**Classification:** Governance closure — shadow only, no live state mutation

---

## Final Classification

```
MAY21_SHADOW_CONSUME: COMPLETE
MAY22_SHADOW_CONSUME: COMPLETE
CONSUMED_LIVE: 0 (hard constraint maintained)
LIVE_SCORING_STATE: UNCHANGED
SHADOW_TRAIN_V2: UPDATED (1975 → 2055)
MODEL_PROMOTION: NOT APPROVED
SCORING_CHANGES: NONE
```

---

## May 21 — Eligible Rows

| Field | Value |
|---|---|
| source_truth | RP_MERGED_CLEAN |
| flatline_count | 0 |
| identity_failure_count | 0 |
| council_verdict | PASS_TO_LEARNING |
| learning_gate | OPEN |
| verdict_races_total | 44 |
| **eligible_rows** | **44** |
| excluded_rows | 0 |
| unresolved_rows | 0 |
| DPT exclusions | 0 (no DPT data gap on May 21) |

---

## May 21 — Consumed Rows

| Field | Value |
|---|---|
| events_built | 44 |
| events_written (build-only phase) | 44 |
| events_consumed (Phase 3B) | **44** |
| events_skipped | 0 |
| consumed_shadow_after | **44** |
| consumed_live_after | **0** |
| shadow races before | 1975 |
| shadow races after | 2019 |

Ops artifact: `data/ops_worker_dry_run/2026-05-21_learn-shadow_024709.json`

---

## May 22 — Eligible Rows

| Field | Value |
|---|---|
| source_truth | RP_MERGED_CLEAN |
| flatline_count | 0 |
| identity_failure_count | 0 |
| council_verdict | PASS_TO_LEARNING |
| learning_gate | OPEN |
| verdict_races_total | 43 |
| **eligible_rows** | **36** |
| excluded_rows | 7 |
| unresolved_rows | 0 |

**Excluded races (May 22):**

| Race ID | Tier | VP | Reason |
|---|---|---|---|
| rp_DPT_20260522_5.20 | X | 0.0847 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_5.52 | C | 0.1098 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_6.29 | X | 0.0851 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_7.00 | X | 0.1584 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_7.30 | **A** | **0.4700** | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_8.00 | B | 0.2297 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_8.30 | B | 0.3504 | NO_RESULT_DPT_DATA_GAP |

> All 7 excluded races are Downpatrick data-gap exclusions. These are not misses — outcomes are unknown.

---

## May 22 — Consumed Rows

| Field | Value |
|---|---|
| events_built | 36 |
| events_written (build-only phase) | 36 |
| events_consumed (Phase 3B) | **36** |
| events_skipped | 0 |
| consumed_shadow_after | **36** |
| consumed_live_after | **0** |
| shadow races before | 2019 |
| shadow races after | 2055 |

Ops artifact: `data/ops_worker_dry_run/2026-05-22_learn-shadow_024845.json`

---

## Consumed Shadow Totals (both dates)

| Date | Consumed Shadow | Consumed Live |
|---|---|---|
| 2026-05-21 | 44 | **0** |
| 2026-05-22 | 36 | **0** |
| **Total** | **80** | **0** |

`consumed_live = 0` across all rows — hard constraint maintained.

---

## shadow_full_train_v2 Race Count

| Stage | race_count |
|---|---|
| Before any consume | **1975** |
| After May 21 consume | **2019** |
| After May 22 consume | **2055** |
| Net change | **+80** |

---

## Live State Hash

| File | Hash Before Sequence | Hash After Sequence | Changed? |
|---|---|---|---|
| `sentient_state_shadow_full_train_v2.json` | `a1637542f7646aa9` | `570f6210adb56191` | **Yes — expected** |
| `sentient_state.json` (live scoring) | `1016d89dceb28da5` | `1016d89dceb28da5` | **No — correct** |

Shadow train hash changed: expected. This is the purpose of shadow consume.  
Live scoring hash unchanged: correct. Consume did not touch live scoring state.

---

## Cloud Backup

The ops worker does not auto-push cloud backups in Phase 3B shadow consume. The Supabase `velo_learning_events` table is the append-only audit record. The local `sentient_state_shadow_full_train_v2.json` is the source of truth for the shadow brain. No cloud backup was triggered.

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
```

---

## What Consumed Events Teach

Shadow_full_train_v2 now has 2055 race observations. Each event teaches:
- Whether the top pick won (WIN) or missed (MISS/PLACED)
- VP, MDS, improvement, place_prob at time of pick
- Which doctrine/pattern archetypes apply
- Race archetype and tier classification

This builds the pattern library for Playbook G's shadow brain — not the VP scoring model.

---

## Next Steps

1. Rebuild unified evidence corpus (`scripts/audit/build_unified_evidence_corpus.py`)
2. Rebuild CPU Shadow Gate V2 (`scripts/build_cpu_shadow_gate_v2.py`)
3. Update Mission Control (`scripts/ops/update_mission_control.py --date 2026-05-22`)
4. Run Race Shape Shadow Ledger
5. Accumulate corpus toward 300+ midprice miss races (V2 gate)
6. CPU Decision Policy Gate: needs 63 more top-pick decisions to first gate (150)
