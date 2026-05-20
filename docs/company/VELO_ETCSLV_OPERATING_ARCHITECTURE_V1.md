# VELO ETCSLV Operating Architecture V1

**Date:** 2026-04-29  
**Status:** Doctrine reference  
**Purpose:** Translate ETCSLV into VELO operating language

---

## 1. VELO Version of ETCSLV

ETCSLV is the architecture that explains how VELO actually behaves as a system:

- **Execution Loop** - how VELO scores, routes, reports, and reconciles
- **Tool Registry** - what intelligence tools and signal families VELO has available
- **Context Manager** - what race context VELO carries when it makes a judgment
- **State Store** - what VELO remembers and where that memory lives
- **Life Cycle Hooks** - when VELO updates, audits, freezes, promotes, or suppresses
- **Verification Interface** - how humans inspect whether VELO was right, wrong, safe, or still unproven

This is not a theoretical overlay. It is the operating doctrine behind the repo.

---

## 2. Layer Mapping

| ETCSLV Layer | VELO Meaning | Current VELO Components |
|---|---|---|
| Execution Loop | Daily intelligence cycle | `scripts/run_prime_today.py`, `score_race_velo_prime()`, Telegram render paths, `scripts/run_results_sigma.py` |
| Tool Registry | Model and signal inventory | `VeloPrimeEnsemble`, SQPE, specialist sidecars, signal glossary, Signal Stack badges, router lanes, candidate lanes |
| Context Manager | Race and regime context | merged racecards, course/going/class fields, archetypes, macro regime, sidecar values, odds context |
| State Store | Live + immutable memory | Supabase verdict/audit tables, `data/evidence_vault/`, `data/velo_current_state.json`, `data/velo_artifact_index.json`, router ledgers |
| Life Cycle Hooks | Controlled system transitions | sigma reconciliation, special-day reports, router threshold tracking, freeze rules, candidate-lane promotion gates, Playbook G offline lifecycle |
| Verification Interface | Human inspection and governance | Unified audits, Router Evidence Engine, Operating Truth Board, signal reports, Signal Stack, special-day reports |

---

## 3. Where Key VELO Systems Fit

### Sigma Audit

- ETCSLV layer: **Verification Interface** and **Life Cycle Hooks**
- Role: post-race truth reconciliation
- Why it matters: no claim survives without closed-result audit

### Router Evidence Engine

- ETCSLV layer: **Verification Interface** plus **State Store**
- Role: append-only lane evidence, threshold movement, freeze status
- Why it matters: prevents premature routing promotion

### Evidence Vault

- ETCSLV layer: **State Store**
- Role: immutable memory and investor-grade proof archive
- Why it matters: converts system behavior into auditable history

### Signal Stack

- ETCSLV layer: **Tool Registry** exposed through the **Verification Interface**
- Role: show which proven or risky signal families fired on a pick
- Why it matters: turns hidden model intelligence into operator-visible truth

### Telegram Attribution

- ETCSLV layer: **Verification Interface**
- Role: live operator delivery surface
- Why it matters: the intelligence is useless if the operator cannot see it

### Candidate Lanes

- ETCSLV layer: **Tool Registry** plus **Life Cycle Hooks**
- Role: lifecycle-controlled promotion paths for discovered signals
- Why it matters: signals become lanes only after governed evidence

### Playbook G

- ETCSLV layer: **Tool Registry**, **State Store**, and **Life Cycle Hooks**
- Role: offline doctrine-learning program
- Why it matters: expands VELO intelligence without contaminating live governance

---

## 4. Current Signal Doctrine Inside ETCSLV

### Trust boundary

- `VP30_TIER_A`
- meaning: VELO confidence plus top decision quality
- evidence: 40.1% SR / 77.2% frame / n=162

### Hidden upside signal

- `MDS_HIGH`
- meaning: market structure is disguising a real contender
- evidence: 54.8% SR / 96.8% frame / n=31

### Improvement signal

- `IMPROVE_HIGH`
- meaning: the horse is likely stepping forward
- evidence: 43.5% SR / 82.3% frame / n=62

### Cautionary signal

- `B_LOW_VP_SUPPRESS`
- meaning: low-confidence B-tier drag
- evidence: 16.9% SR / 44.1% frame / n=272

### Forensics watch

- `MID_PRICE_ZONE_WATCH`
- meaning: main winner-conversion battlefield
- evidence: SP 3.0-8.5 zone accounts for 58% of misses

---

## 5. First Era vs Second Era

### First era: build VELO

- create the ensemble
- run daily scoring
- reconcile results
- accumulate evidence

### Second era: make VELO legible

- audit VP lineage
- audit Telegram visibility
- expose Signal Stack
- design candidate lanes
- align company narrative with system truth

Second era is the shift from "model quality" to "auditable operating system."

---

## 6. Non-Negotiable Governance

- no staking automation
- no router promotion without evidence
- no candidate promotion without shadow ledger proof
- no production use of offline research candidates
- no market recrowding into the core learner
- no public claim beyond what the evidence artifacts prove

---

## 7. Why ETCSLV Matters

ETCSLV gives VELO a language for turning scattered model outputs into a coherent company:

- execution is controlled
- tools are named
- context is preserved
- memory is immutable
- life cycles are governed
- verification is visible

That is how VELO becomes commercially credible.

---

*VELO ETCSLV Operating Architecture V1*
