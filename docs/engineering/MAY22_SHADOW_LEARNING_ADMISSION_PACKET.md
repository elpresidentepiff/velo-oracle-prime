# May 22 Shadow Learning Admission Packet

**Date:** 2026-05-22  
**Generated:** 2026-05-23  
**Target State:** `shadow_full_train_v2`  
**Classification:** Operator approval required before shadow consume

---

## Council Verdict

| Field | Value |
|---|---|
| council_verdict | **PASS_TO_LEARNING** |
| source_truth | RP_MERGED_CLEAN |
| flatline_count | 0 |
| identity_failure_count | 0 |
| learning_gate | **OPEN** |
| promotion_gate | OPEN |

Council run: `data/council_runs/council_run_2026-05-22.json`  
Mission Control: `data/mission_control/2026-05-22_mission_control.json`

---

## Gate Status

| Gate | Status |
|---|---|
| CPU Runner Calibration Gate | REVIEW_THRESHOLD_MET (n=786) |
| CPU Decision Policy Gate | NEEDS_MORE_DAYS (n=87 top picks) |
| Learning Gate | **OPEN** |
| Promotion Gate | OPEN (promotion not approved, operator decision required) |

---

## Eligible Rows

| Category | Count |
|---|---|
| Verdict races total | 43 |
| **Eligible for learning** | **36** |
| Excluded (no result) | 7 |
| Unresolved | 0 |
| sigma_audits rows | 36 |

**Excluded races (all DPT — Downpatrick data gap):**

| Race ID | Tier | VP | Reason |
|---|---|---|---|
| rp_DPT_20260522_5.20 | X | 0.0847 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_5.52 | C | 0.1098 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_6.29 | X | 0.0851 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_7.00 | X | 0.1584 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_7.30 | **A** | **0.4700** | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_8.00 | B | 0.2297 | NO_RESULT_DPT_DATA_GAP |
| rp_DPT_20260522_8.30 | B | 0.3504 | NO_RESULT_DPT_DATA_GAP |

> DPT Tier A exclusion (VP=0.470) is notable. Outcome unknown — not counted as miss. This is a data gap, not a prediction failure. DPT data gap documented in CPU_SHADOW_GATE_V2_REVIEW_2026_05_22.md.

---

## Event Build Result

| Field | Value |
|---|---|
| events_built | **36** |
| events_written_to_db | **36** |
| events_skipped | 0 |
| db_result.status | `ok` |
| sentient_state_touched | **False** |
| playbook_g_promoted | **False** |
| playbook_g_consumed | **False** |
| build_events_only | **True** |

Ops artifact: `data/ops_worker_dry_run/2026-05-22_learn-shadow_022857.json`

---

## Consumed State — Before / After Build

| Field | Before | After Build-Only |
|---|---|---|
| consumed_shadow | 0 | **0** (unchanged) |
| consumed_live | 0 | **0** (unchanged) |
| live_state_hash | `a1637542f7646aa9` | `a1637542f7646aa9` (**unchanged**) |

Build-only phase does not touch the shadow state. consumed_shadow and consumed_live remain
false until Phase 3B is explicitly approved and run.

---

## Sigma Summary

| Metric | Value |
|---|---|
| evaluated_count | 36 |
| wins | 9 |
| SR | 25.0% |
| baseline | 20% |
| status | ABOVE BASELINE |

---

## Governance Verification

```
NO scoring changes applied
NO VP model changes
NO candidate_route() changes
NO router rule changes
NO staking changes
NO Telegram runtime changes
NO Playbook G promotion
NO live-state mutation
NO consume_live actions
sentient_state_touched = False
live_state_hash = unchanged (a1637542f7646aa9)
```

---

## Recommendation

**APPROVE_SHADOW_CONSUME**

All hard gates clear:
- flatline_count = 0
- identity_failures = 0
- council_verdict = PASS_TO_LEARNING
- consumed_live_before = 0
- live_state_hash = unchanged
- events_built = events_eligible = 36

**Caveats:**
1. May 21 events not yet built. Build May 21 events before or alongside May 22 consume.
2. CPU Decision Policy Gate is NEEDS_MORE_DAYS (n=87). Shadow consume is Playbook G state, NOT CPU model promotion. These are separate gates.
3. DPT Tier A race (VP=0.470) excluded due to data gap. Outcome not known. Consider DPT data sourcing if this recurs.
4. Operator decision required before running Phase 3B consume command:
   ```bash
   python workers/velo_ops_worker.py learn-shadow --date 2026-05-22 --execute --target-state shadow_full_train_v2
   ```

---

## What Consume Does

Phase 3B shadow consume will:
- Read 36 unconsumed events from `velo_learning_events`
- Feed them into `sentient_state_shadow_full_train_v2.json` (Playbook G pattern learning)
- Set `consumed_shadow=True` for each event
- NOT change VP scores
- NOT change routing
- NOT change live betting
- NOT promote CPU model

This is Playbook G's shadow brain accumulating race outcome patterns, not a VP model change.

---

## Hard Stop Conditions (none currently firing)

If any of these become true before consume, STOP immediately:
- consumed_live_before > 0
- flatline_count > 0
- identity_failures > 0
- council_verdict changes from PASS_TO_LEARNING
- live_state_hash changes before Phase 3B is run
