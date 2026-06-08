# VÉLØ Policy RL Sandbox V1

**Status:** DESIGN ONLY — RESEARCH  
**Phase:** 7 — Research  
**Classification:** `POLICY_RL_SHADOW_ONLY` / `NO_LIVE_RL` / `NO_STAKING` / `DESIGN_ONLY`

---

## Purpose

Define the reward/penalty framework for a shadow-only reinforcement learning sandbox that explores optimal policy decisions without touching live state.

No live RL. No staking. No router mutation. No production scoring.

---

## Action Space

| Action | Description |
|---|---|
| TRUST | Score this race with full confidence, admit to learning |
| HOLD | Score but flag as uncertain — do not admit to learning |
| SUPPRESS | Do not score — confidence below threshold |
| ESCALATE_TO_COUNCIL | Flag for Council review before scoring |
| QUARANTINE_DAY | Quarantine entire race day — do not admit any results to learning |
| SHADOW_LEARN | Admit to shadow learning only (not live learning) |

---

## Reward Structure

| Outcome | Reward |
|---|---|
| Correct winner (VP≥0.40 TRUST) | +1.0 |
| Correct winner (VP 0.30–0.40 TRUST) | +0.6 |
| Correct frame (any VP, TRUST) | +0.2 |
| Correct suppression (low-VP SUPPRESS) | +0.4 |
| Contaminated day blocked (QUARANTINE_DAY) | +0.8 |
| Calibration preserved (Brier ≤ baseline) | +0.3 |

---

## Penalty Structure

| Violation | Penalty |
|---|---|
| Timestamp leakage detected (TRUST used) | -1.5 |
| Learning from contaminated day (TRUST on blackout) | -1.0 |
| False high confidence (VP≥0.40, miss) | -0.7 |
| Live-state mutation attempted | -2.0 |
| Unsafe promotion (below evidence threshold) | -2.0 |
| Shadow/live contamination | -1.5 |
| Missed QUARANTINE on flagged day | -1.0 |

---

## Sandbox Architecture

The RL sandbox:
1. Reads historical race evidence from `data/velo_unified_evidence_audit_v1.json`
2. Simulates policy decisions for each race (action selection)
3. Computes rewards and penalties from actual outcomes
4. Accumulates policy performance metrics
5. Reports to Council — never directly modifies any live configuration

---

## Hard Invariants

```
NO_LIVE_RL: sandbox runs on historical data only
NO_STAKING: no order submission, ever
NO_ROUTER_MUTATION: sandbox cannot change router lane definitions
NO_PRODUCTION_SCORING: sandbox outputs are research artifacts only
NO_TELEGRAM_MUTATION: sandbox cannot change Telegram delivery format
NO_PLAYBOOK_G_MUTATION: sandbox cannot change Playbook G configuration
SHADOW_ONLY: any "learning" from RL is shadow_consume=true only
```

```
POLICY_RL_SANDBOX_V1_STATUS: DEFINED
IMPLEMENTATION: PHASE 7 — research only, no live RL ever
```
