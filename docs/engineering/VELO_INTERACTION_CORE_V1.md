# VÉLØ Interaction Core V1

**Status:** DESIGN ONLY  
**Phase:** 4 — Event-Driven Intelligence OS  
**Classification:** `INTERACTION_CORE_DEFINED` / `NO_IMPLEMENTATION_YET` / `DESIGN_ONLY`

---

## Purpose

VÉLØ currently runs as a batch script: score races → close sigma → report. This is adequate but not sufficient for an intelligence OS.

The Interaction Core moves VÉLØ from batch-script to event-sliced architecture. Every meaningful event in the pipeline gets a status, a responsible subsystem, and a learning-eligibility assessment. Not just at sigma close — at every step.

---

## Core Doctrine

Do not wait until final Sigma to say "good day" or "bad day."

Each event must produce:
- `status`: success / failure / warning / skipped
- `responsible_subsystem`: which module is accountable
- `failure_reason`: why it failed (if applicable)
- `confidence_impact`: how this event changes our prediction confidence
- `learning_eligibility`: should this event feed learning? yes/no/conditional

This is the answer to sparse RL feedback.

---

## Event Catalogue

| Event | Trigger | Learning-Eligible |
|---|---|---|
| `racecard_loaded` | Daily racecard fetch complete | No |
| `source_truth_verified` | RP/Racing API source confirmed | No |
| `identity_verified` | Horse name / jockey / trainer identity matched | No |
| `feature_safety_checked` | Feature provenance audit passed | No |
| `model_score_generated` | SQPE + ensemble score produced | No |
| `race_shape_evaluated` | Race Shape context appended | No |
| `council_policy_checked` | Council governance pass completed | No |
| `mission_control_command_issued` | MC directive issued for this race | No |
| `sigma_closed` | Post-race sigma result confirmed | YES (if eligible day) |
| `learning_admitted` | Result admitted to learning pipeline | YES |
| `shadow_consumed` | Shadow model received result | YES (shadow only) |
| `contamination_flagged` | Day or event flagged as contaminated | No |
| `quarantine_applied` | Race/day quarantined from learning | No |
| `council_escalation` | Event escalated to Council review | No |

---

## Event Payload Schema

```json
{
  "event_type": "sigma_closed",
  "race_id": "12345",
  "date": "2026-05-23",
  "timestamp": "2026-05-23T18:42:00Z",
  "status": "success",
  "responsible_subsystem": "run_results_sigma.py",
  "failure_reason": null,
  "vp": 0.42,
  "tier": "A",
  "predicted_winner": "Horse A",
  "actual_winner": "Horse B",
  "confidence_impact": -0.05,
  "learning_eligibility": true,
  "learning_eligibility_reason": "Day clean, VP >= 0.30, not contaminated"
}
```

---

## Interaction with Micro-Feedback Ledger

See `VELO_MICRO_FEEDBACK_LEDGER_V1.md` for how events feed the micro-feedback loop.

The Interaction Core defines what events exist. The Micro-Feedback Ledger defines what to do with them.

```
INTERACTION_CORE_V1_STATUS: DEFINED
IMPLEMENTATION: PHASE 4 — no code changes until Phase 3 harness is established
```
