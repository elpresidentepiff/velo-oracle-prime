# VÉLØ Forensics Unit V1 — Doctrine

**Status**: ACTIVE — DOCTRINE ONLY (Phase 1)
**Created**: 2026-06-14
**Branch**: main
**Hard rule**: Phase 1 is read/write doctrine and schema only. No autopsy execution. No Supabase writes. No scoring changes.

---

## Core Doctrine Sentence

> "Sigma learns patterns. Playbook G trains strategy. VP Gatekeeper controls engagement. VÉLØ Forensics investigates truth. Horse Passport remembers the living horse."

---

## Purpose

The VÉLØ Forensics Unit (VFU) is the investigative intelligence layer of VÉLØ Oracle Prime.

It exists to answer the questions that official form cannot:

- Why did VÉLØ miss this race?
- What was the horse becoming, not what had it done?
- Has VÉLØ been wrong about this horse before — in the same way?
- What setup does this horse need that VÉLØ did not recognise?
- Was the VP signal correct but the engagement wrong?
- Is there a repeating failure class?

Official ratings and form tell us **what happened**.
The Passport must tell us **what the horse is now becoming**.

---

## Canonical Architecture

```
Race Day
    │
    ├── VÉLØ scores runners (VP, improvement, MDS, RPDC)
    │
    └── Results close
            │
            ▼
    ┌──────────────────────────────────┐
    │     VÉLØ Forensics Unit (VFU)    │  ← investigator
    │                                  │
    │  1. Reads sigma results          │
    │  2. Reads VÉLØ verdicts          │
    │  3. Reads official outcomes      │
    │  4. Performs Race Autopsy        │
    │  5. Updates Horse Passport       │
    │  6. Flags Pattern Evidence       │
    └──────────────────────────────────┘
            │               │
            ▼               ▼
    Race Autopsy       Horse Passport
    Ledger             (canonical horse
    (per-race          life file)
    forensic record)
            │               │
            └───────┬───────┘
                    ▼
            Pattern Prosecutor
            (tests whether
            beliefs are real
            across many races)
```

---

## Relationship to Existing Systems

### Horse Passport — CANONICAL HORSE DOSSIER

The Horse Passport (`new_build_velo/horse_passport.py`) is the permanent, canonical life file for each horse.

VFU does **not** replace the Passport. VFU is the investigative feeder that writes forensic evidence **into** the Passport.

**What the Passport must eventually answer:**

1. What has this horse done in every VÉLØ-scored race?
2. What did VÉLØ think before each race?
3. Did VÉLØ understand the horse correctly?
4. Is the horse improving, declining, hidden, exposed, unreliable, trapped, or ready?
5. What setup does it need? What setup is wrong for it?
6. Has VÉLØ missed this horse before, in the same way?
7. Has VÉLØ been right about this horse before?
8. Is this horse becoming something different from its official form?
9. What should VÉLØ remember next time this horse appears?

### Sigma — PATTERN LEARNING LAYER

Sigma (`run_results_sigma.py`) records WIN/PLACE/MISS outcomes and extracts statistical patterns across the universe.

VFU does not replace Sigma. VFU operates at the **individual horse** and **individual race** level. Sigma operates at the **population** level.

VFU reads Sigma output. VFU does not write Sigma rows.

### Playbook G — STRATEGY TRAINING

Playbook G trains doctrine directives from accumulated evidence. VFU flags **candidate patterns** for Playbook G to learn from — it does not directly modify Playbook G state.

### VP Gatekeeper — ENGAGEMENT PERMISSION SIGNAL

VP Gatekeeper (`docs/current/VP_GATEKEEPER_PROMOTION_V1.md`) controls engagement intensity at the **day level**.

VFU operates at the **race and horse level**. VFU forensic findings may eventually inform VP thresholds — but only through the evidence gate and operator approval. VFU does not modify VP Gatekeeper directly.

### Pattern Prosecutor — BELIEF TESTING

Pattern Prosecutor is a separate logic layer that takes VFU-flagged patterns and tests them statistically across the full evidence universe.

Pattern Prosecutor does not execute autopsy. It consumes autopsy output and cross-checks it against Sigma and the innovation protocol.

---

## What VFU Does NOT Do

- VFU does not alter live scoring
- VFU does not change model weights
- VFU does not promote models
- VFU does not write Supabase (Phase 1)
- VFU does not send Telegram
- VFU does not restore Racing API
- VFU does not create a second dossier system that competes with the Horse Passport
- VFU does not execute race autopsies in Phase 1
- VFU does not modify Sigma output rows
- VFU does not modify VP Gatekeeper thresholds

---

## Safety Boundaries

| Boundary | Status |
|---|---|
| No Supabase writes | ENFORCED — Phase 1 |
| No live scoring change | ENFORCED — permanent until operator lifts |
| No model promotion | ENFORCED — permanent until evidence gate |
| No Telegram send | ENFORCED |
| No Racing API restoration | ENFORCED |
| No autopsy execution | ENFORCED — Phase 1 only |
| No Mar–Apr extraction | ENFORCED — pending 14-day VP dry-run validation |
| No duplicate dossier system | ENFORCED — Passport is canonical |

---

## Phase Plan

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Doctrine + schema + inventory | ACTIVE |
| Phase 2 | Autopsy generator — dry-run on 20 current-era races | LOCKED |
| Phase 3 | Passport forensic extension dry-run (repeated horses) | LOCKED |
| Phase 4 | Full current-era 1,263-row autopsy pass | LOCKED |
| Phase 5 | Pattern Prosecutor summary report | LOCKED |
| Phase 6 | Mar–Apr pre-surgery study consideration | LOCKED — awaits 14-day VP validation + operator approval |

---

## Final Classifications (Phase 1)

- `VFU_01_DOCTRINE_CREATED`
- `HORSE_PASSPORT_CONFIRMED_AS_CANONICAL_DOSSIER`
- `VFU_DEFINED_AS_INVESTIGATIVE_FEEDER`
- `NO_DUPLICATE_DOSSIER_SYSTEM`
- `NO_AUTOPSY_EXECUTION_YET`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`
