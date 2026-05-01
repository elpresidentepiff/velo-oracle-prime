# VELO Operating Truth Board V1

**Evidence basis:** 49 race days | 1391 sigma rows  
**Last updated:** 2026-04-30 | Phase 6A commit: 3f65b1c  
**Purpose:** Single authoritative answer to "What does VELO actually do?"

---

## ETCSLV Status

VELO is now explicitly aligned to ETCSLV:

- **Execution Loop:** daily scoring, product routing, Telegram render, sigma reconciliation
- **Tool Registry:** VP, tier, sidecars, router lanes, candidate lanes, Signal Stack badges
- **Context Manager:** racecards, macro regime, race archetypes, class/going/course context
- **State Store:** Supabase live state plus Git Evidence Vault and router ledgers
- **Life Cycle Hooks:** special-day reporting, router thresholds, candidate-lane promotion and suppression
- **Verification Interface:** Sigma Audit, Router Evidence Engine, Signal Stack, special-day reports, Evidence Vault

VELO does not just predict. It executes, records, audits, learns, verifies, and explains its own confidence.

---

## A. What Is Working

**1. Contender detection is real.**  
VP >= 0.30 produces 69.3% frame rate across 345 races over 49 days.

**2. Tier A is proven.**  
Tier A: 40.1% SR, 77.2% frame, n=162.

**3. VP >= 0.40 is exceptional.**  
44.0% SR, 85.0% frame, n=100.

**4. MDS_HIGH is a major asset.**  
54.8% SR, 96.8% frame, n=31.

**5. IMPROVE_HIGH predicts winners.**  
43.5% SR, 82.3% frame, n=62.

**6. VP monotonicity is real.**  
VP bands rise cleanly from 14.5% SR at VP < 0.20 to 44.0% SR at VP >= 0.40.

**7. The operator layer is becoming legible.**  
Signal Stack can now surface VP30_TIER_A, MDS_HIGH, IMPROVE_HIGH, PLACE_PROB_HIGH, B_LOW_VP_SUPPRESS, and MID_PRICE_ZONE_WATCH without changing scoring or routing.

---

## B. What Is Not Working

**1. Winner conversion in the SP 3.0-8.5 zone.**  
58% of all misses sit in this zone.

**2. Tier B / VP < 0.30 drag.**  
16.9% SR, 44.1% frame, n=272.

**3. Market decoy misses.**  
The system still has races where market shape misleads downstream behavior.

**4. Short-favourite misses.**  
Short-priced market leaders still override VELO in too many missed races.

**5. Low-tier drag.**  
Too much C/D/X volume still contributes low edge.

**6. Candidate-lane shadow ledger is partially active.**  
The router shadow ledger is live. The paper execution ledger is live (POWER_ANCHOR_MODE tracking, n=3). Full candidate-lane annotation fields in velo_verdicts/sigma_audits not yet wired — promotion from candidate-lane perspective still blocked until ledger reaches n≥20.

---

## C. What Is Promising

**1. VP30_TIER_A**  
The first proven trust boundary.

**2. V2_CLASS4_ONLY router lane**  
Strong but still under threshold.

**3. MDS_HIGH + VP >= 0.30 combinations**  
Potential elite lane once ledgered.

**4. IMPROVE_HIGH + VP >= 0.30 combinations**  
Strong candidate-lane material.

---

## D. What Should Be Suppressed

**1. Tier B VP < 0.30 predictions**  
Confirmed drag.

**2. Market-aware variants that recrowd the core**  
Rejected until separation is proven.

**3. Low-tier predictions without strong secondary evidence**  
No reason to elevate these.

---

## E. What Stays Shadow-Only

- router lanes
- candidate-lane combinations
- Playbook G V3 core
- anything without closed-result ledger proof

---

## F. What Deserves Candidate-Lane Tracking

1. **VP30_TIER_A**
2. **MDS_HIGH**
3. **IMPROVE_HIGH**
4. **PLACE_PROB_HIGH**
5. **B_LOW_VP_SUPPRESS**
6. **MID_PRICE_ZONE_WATCH** as forensics-only

---

## G. What Needs More Data

- V6_GOLD_SEAM
- V2 router lane
- candidate-lane shadow ledger
- live Signal Stack outcomes
- mid-price winner forensics

---

## H. What The Company Should Say Publicly

VELO is an auditable racing intelligence operating system.

It analyses race data, generates confidence-weighted predictions, audits every prediction against closed results, ranks which signals deserve trust, and exposes that truth to the operator.

ETCSLV is the architecture.  
Evidence Vault is the memory.  
Signal Stack is the operator interface.  
Router and sigma are the verification layer.  
Candidate lanes are lifecycle-controlled promotion paths.

---

## I. What The Company Must Not Overclaim

1. No profitability claim
2. No live router proof beyond shadow status
3. No solved mid-price winner problem
4. No production-ready Playbook G claim
5. No guarantee language

---

## System Summary

VELO finds contenders reliably. It becomes strongest when VP30_TIER_A, MDS_HIGH, and IMPROVE_HIGH align. Its primary weakness remains winner separation in the SP 3.0-8.5 zone. Its current job is to accumulate evidence, surface risk, and refuse promotion without proof.

---

## J. Paper Execution Layer State (Phase 6 — as of 2026-04-30)

**VeloExecutionBridge** is live in SIM/PAPER mode. Betting is NOT live.

| Layer | Status |
|---|---|
| VeloExecutionBridge | PAPER_EXECUTION_LEDGER_ACTIVE |
| VELO_EXECUTION_MODE=LIVE | RuntimeError — permanently blocked |
| Paper ledger directive count | POWER_ANCHOR n=3, WATCH_ONLY n=6, BLOCKED n=29 |
| POWER_ANCHOR closed results | 2/2 wins (Hickory Lad SP=1.36, Infraad SP=1.80), P&L=+1.16 |
| Gate delta | +83.3pp (POWER_ANCHOR vs WATCH_ONLY) — gate non-decorative confirmed |
| Racing API enrichment | 374,639 rows, leakage risk flagged, no weight changes |
| Next gate | POWER_ANCHOR n≥20 before first review |

---

*VELO Operating Truth Board V1*
