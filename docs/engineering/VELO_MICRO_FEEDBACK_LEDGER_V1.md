# VÉLØ Micro-Feedback Ledger V1

**Status:** DESIGN ONLY  
**Phase:** 4 — Sparse RL Answer  
**Classification:** `MICRO_FEEDBACK_DEFINED` / `SHADOW_ONLY` / `NO_LIVE_RL` / `DESIGN_ONLY`

---

## Problem

VÉLØ's current feedback loop is sparse: predict → wait → sigma → one signal per day.

This means:
- 20+ predictions per day, one outcome signal per closed race
- No within-day correction signal
- No way to differentiate "good model, bad luck" from "bad model, systematic miss"
- Playbook G gets doctrine-level feedback but not prediction-level feedback

---

## Solution

The Micro-Feedback Ledger captures a fine-grained reward/penalty signal per race event, building an evidence trail that doesn't require waiting for sigma to assess system quality.

---

## Ledger Schema

```json
{
  "ledger_entry_id": "uuid",
  "race_id": "12345",
  "date": "2026-05-23",
  "event_type": "sigma_closed",
  "responsible_subsystem": "run_results_sigma.py",
  "outcome": "miss",
  "miss_class": "mid_priced_won",
  "vp": 0.38,
  "tier": "B",
  "sp_actual_winner": 5.5,
  "sp_velo_pick": 2.8,
  "reward_signal": -0.3,
  "learning_eligible": true,
  "shadow_admit": true,
  "live_admit": false,
  "contamination_flag": false,
  "subsystem_confidence_delta": -0.02
}
```

---

## Reward / Penalty Matrix

| Outcome | Signal | Magnitude |
|---|---|---|
| Correct winner (VP≥0.40, Tier A) | +reward | +1.0 |
| Correct winner (VP 0.30–0.40) | +reward | +0.6 |
| Correct winner (VP<0.30) | +reward | +0.3 |
| Correct frame but miss winner | +partial | +0.2 |
| Correct suppression (low-VP) | +reward | +0.4 |
| Winner was in bottom 50% by VP | -penalty | -0.5 |
| Contaminated day admitted to learning | -penalty | -1.0 |
| False confidence (VP≥0.40, miss) | -penalty | -0.7 |
| Timestamp leakage detected post-hoc | -penalty | -1.5 |
| Unsafe promotion applied | -penalty | -2.0 |

---

## Integration Points

- Interaction Core events → Micro-Feedback Ledger entries
- Ledger → Council policy simulation (Phase 7)
- Ledger → Playbook G doctrine refinement (shadow only)
- Ledger → VP gate recalibration evidence
- Ledger → Router lane evidence (parallel to existing router_shadow_audit.py)

---

## Hard Rules

```
NO_LIVE_RL: feedback loop is shadow-only
NO_LIVE_WEIGHT_CHANGES: ledger cannot trigger live scoring changes
NO_AUTOMATIC_PROMOTION: ledger is evidence, not decision
SHADOW_CONSUME_ONLY: any learning from ledger is shadow-consume=true only
```

```
MICRO_FEEDBACK_LEDGER_V1_STATUS: DEFINED
IMPLEMENTATION: PHASE 4 — after Phase 3 harness established
```
