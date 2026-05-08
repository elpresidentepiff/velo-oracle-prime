# VÉLØ Sentient 7-Day Shadow Accumulation Protocol

**Version:** V1  
**Created:** 2026-05-07  
**Status:** ACTIVE — begin Day 1 on 2026-05-08  
**Classification:** SHADOW_SENTIENT_LEARNING_LOOP_READY / NOT_LIVE_CONTROL

---

## Purpose

This protocol governs the 7-day shadow accumulation window that must complete before any live promotion of the Playbook G sentient learning loop is considered. The daily EOD bridge (`scripts/eod_shadow_learning_bridge.py`) has been patched (commit `9f30f88`) to correctly compute MPI, chaos_bloom, real SP, and fire the learning_allowed gate. This protocol tracks whether the patched bridge accumulates clean signal across a full operating week.

The shadow state (`data/sentient_state_shadow_daily.json`) is the only file mutated. `data/sentient_state.json` (live) must never be touched by any daily bridge run.

**Not live sentience. Not live control. Shadow evidence accumulation only.**

---

## Prerequisite State (confirmed 2026-05-07)

| Check | Status |
|---|---|
| Bridge patch committed | `9f30f88` — DONE |
| Post-repair audit | 924/925 success, MPI=100%, chaos=99.9% — PASS |
| Daily bridge audit (2026-05-07) | 41/41 success, classification=READY — PASS |
| Live state hash | Verified unchanged before and after |
| HFS_TRAINING_SAFE gate | False — shadow-only, no live promotion |
| `sentient_state_shadow_daily.json` | Initialised, 41 races, aggression=0.55 |

---

## Daily Command Sequence

Run after results close each day (after sigma audit is complete):

```bash
# Step 1 — activate environment
source venv/bin/activate

# Step 2 — run the daily EOD shadow learning bridge
PYTHONPATH=. python scripts/eod_shadow_learning_bridge.py --date YYYY-MM-DD

# Step 3 — run the daily bridge audit (verifies today's events meet A-O criteria)
PYTHONPATH=. python scripts/audit_sentient_daily_bridge.py --date YYYY-MM-DD

# Step 4 — read audit classification from output
# Expected: SENTIENT_DAILY_BRIDGE_READY_FOR_7_DAY_SHADOW
# Fail: REPAIR_INCOMPLETE or BLOCKED
```

Both scripts write their outputs to `data/` (gitignored). Do not commit data files.

---

## Daily Pass Criteria

All criteria must pass for a day to count toward the 7-day window.

| Criterion | Threshold | Description |
|---|---|---|
| A — Observe success rate | ≥99% | `observe_race_outcome()` calls that succeed |
| B — MPI null count | 0 | No events with MPI=None |
| C — Chaos null count | 0 | No events with chaos_bloom=None |
| D — SP hardcoded count | 0 | No events with `sp_is_hardcoded=True` |
| E — Duplicate idempotency keys | 0 | No double-feeds of same race to same state |
| F — Live hash unchanged | PASS | SHA-256 of `sentient_state.json` same before/after |
| G — learning_allowed count | ≥1 | At least one race allowed learning that day |
| H — Shadow state race count | Increasing | `total_races_observed` grows each day |

---

## Daily Fail Criteria (immediate STOP)

Any of the following triggers an immediate halt — do not continue accumulation until resolved:

| Trigger | Action |
|---|---|
| MPI null > 0 | STOP. Debug `_compute_mpi()` against that day's prediction snapshot |
| Chaos null > 0 | STOP. Debug `_compute_chaos_bloom()` against that day's prediction snapshot |
| SP hardcoded > 0 | STOP. Debug `_extract_winner_sp()` against that day's result file |
| Duplicate key fired | STOP. Investigate idempotency key collision — check `playbook_g_outcome_events_shadow_daily.jsonl` |
| Live hash changed | IMMEDIATE HALT. This is a critical failure. Do not run bridge again until cause confirmed |
| observe success < 90% | STOP. Debug the failing race events before continuing |
| audit classification = BLOCKED | STOP. Read the block reason in audit output |

---

## 7-Day Ledger

Update this table after each day's audit. A day only counts if ALL pass criteria are met.

| Day | Date | n_events | Observe_OK | MPI_null | Chaos_null | SP_hard | Dup_keys | Live_hash | learning_allowed_n | Shadow_total | Classification | Counts? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 (baseline) | 2026-05-07 | 41 | 41/41 | 0 | 0 | 0 | 0 | PASS | 41 | 41 | READY | PRE-WINDOW |
| 1 | 2026-05-08 | — | — | — | — | — | — | — | — | — | — | PENDING |
| 2 | 2026-05-09 | — | — | — | — | — | — | — | — | — | — | PENDING |
| 3 | 2026-05-10 | — | — | — | — | — | — | — | — | — | — | PENDING |
| 4 | 2026-05-11 | — | — | — | — | — | — | — | — | — | — | PENDING |
| 5 | 2026-05-12 | — | — | — | — | — | — | — | — | — | — | PENDING |
| 6 | 2026-05-13 | — | — | — | — | — | — | — | — | — | — | PENDING |
| 7 | 2026-05-14 | — | — | — | — | — | — | — | — | — | — | PENDING |

**Days passed:** 0 / 7  
**Window status:** ACCUMULATING

---

## Promotion Gate

At 7-day window close (2026-05-15), evaluate:

| Gate | Requirement | Blocks |
|---|---|---|
| G1 — Days passed | 7/7 consecutive clean days | Any live promotion discussion |
| G2 — Total events | ≥200 shadow events accumulated | HFS_TRAINING_SAFE assessment |
| G3 — MPI coverage | ≥99% across all 7 days | HFS signal integrity audit |
| G4 — Chaos coverage | ≥99% across all 7 days | HFS signal integrity audit |
| G5 — SP real | 0 hardcoded across all 7 days | SP integrity sign-off |
| G6 — Live hash | Unchanged on every day | Any promotion |
| G7 — Aggression stability | aggression in [0.20, 0.80] | Learning dynamics review |

**All 7 gates must pass before any live promotion is discussed.**  
**Gate passage does not automatically trigger promotion — operator decision required.**

---

## Hard Rules (permanent — never override)

```
NEVER write to sentient_state.json from the daily bridge
NEVER commit data/ files (shadow state, ledger, audit outputs)
NEVER change scoring weights during this window
NEVER promote to live based on shadow evidence alone
NEVER skip the daily audit script — both steps (bridge + audit) are mandatory
NEVER count a day that did not run the audit script as a passing day
NO live staking during this window
NO HFS training promotion until G2-G4 pass
NO ACCA Lane wiring during this window
```

---

## Active Task Board State (as of 2026-05-07)

| Task | Status | Notes |
|---|---|---|
| Forensic audit | COMPLETE | LOOP_BROKEN confirmed, 0/61 HFS signals |
| Manual repair (repair_v1) | COMPLETE | 924/925 success, 0→930 state |
| Post-repair audit | COMPLETE | SENTIENT_LOOP_READY classification |
| Daily bridge patch | COMPLETE | commit 9f30f88 |
| 7-day shadow window | IN PROGRESS | Day 0 baseline clean |
| HFS signal integrity audit | BLOCKED — awaiting 7-day pass | Classify HFS_TRAINING_BLOCKED / REPAIRED_LOW_VOLUME / READY |
| CASHRUN deep dive | NEXT — after 7-day window | Build CASHRUN candidate lane |
| Live sidecar ablation | PENDING approval | Not started |
| Racing API stat enrichment | SHADOW ONLY | Not started |
| Live promotion | BLOCKED | Requires all 7 promotion gates |

---

## Suggested Commit for This Document

```
docs: add sentient 7-day shadow accumulation protocol

Governs the 7-day shadow window (2026-05-08 to 2026-05-14) that must
complete before any live promotion of the Playbook G sentient learning loop.
Defines daily command sequence, pass/fail criteria, 7-gate promotion
checklist, and permanent hard rules. Day 0 baseline (2026-05-07): PASS.
```

Files: `docs/engineering/VELO_SENTIENT_7_DAY_SHADOW_PROTOCOL.md` only.
