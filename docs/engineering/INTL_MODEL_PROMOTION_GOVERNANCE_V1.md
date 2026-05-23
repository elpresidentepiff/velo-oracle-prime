# International Model Promotion Governance V1

**Date:** 2026-05-23  
**Status:** LOCKED — governs all international jurisdiction model promotion  
**Classification:** Permanent governance — survives context compaction

---

## Why This Document Exists

Phase 1A offline arena produced AUC=0.95 and SR=80%+ for HK packs. These values are outside normal
racing model benchmarks (expected AUC: 0.72–0.85 for a strong pre-race model). They are leakage-suspicious
and triggered a full audit cycle before any model can be called viable.

This document defines the gates that MUST be cleared before any international model can be promoted,
called viable, or used in shadow scoring.

---

## Gate 0 — Leakage Audit REQUIRED Before Any Promotion

No international model result from an offline arena may be classified as VIABLE or used for any
decision until:

- [ ] Leakage audit script run (`scripts/audit_international_arena_leakage.py`)
- [ ] All arena features classified KEEP or UNKNOWN_REVIEW (no DROP features used)
- [ ] Shuffle test run (`scripts/audit_international_arena_sanity.py`)
- [ ] Shuffle AUC confirmed < 0.55 (label shuffle collapses model — genuine signal)
- [ ] Safe-features arena run (`scripts/audit_international_baseline_arena_safe.py`)
- [ ] Safe arena verdict per pack documented

**If shuffle test AUC ≥ 0.65: LEAKAGE_CONFIRMED. Stop. Do not promote. Fix feature pipeline.**

**If shuffle test AUC < 0.55: CLEAN. Proceed to safe arena for calibrated result.**

---

## Gate 1 — Offline Safe Arena Minimum Bars

After Gate 0 leakage check passes, the safe arena result is the authoritative offline result.

| Metric | Minimum bar | Pass/Fail |
|---|---|---|
| Safe AUC | ≥ 0.65 | required |
| Beats favourite SR | YES | required |
| Beats RPR-only baseline | YES | required |
| Shuffle test AUC | < 0.55 | required |
| Time split verified CLEAN | YES | required |
| Race group split verified CLEAN | YES | required |
| No DROP features in model | YES | required |

Any FAIL on Gate 1 → verdict is **NOT_VIABLE**. Do not proceed.

**Classification at Gate 1 pass:** `SAFE_SHADOW_CANDIDATE` — not yet live, offline only.

---

## Gate 2 — Schema Migration Prerequisite

Before any live shadow scoring begins:

- [ ] Supabase migration applied (`migrations/intl_schemas_v1.sql`)
- [ ] Schema exposed in PostgREST settings
- [ ] Schema verified via verification queries
- [ ] UK table contamination confirmed zero
- [ ] Operator approval confirmed (El Presidente sign-off)

**Status as of 2026-05-23: MIGRATION_NOT_APPLIED — awaiting operator approval**

---

## Gate 3 — Live Ingest Worker Prerequisite

Before any live shadow scoring begins:

- [ ] HKJC ingest worker built and tested (HK packs)
- [ ] PMU API collector built and tested (FR packs)
- [ ] Dry-run mode verified (no accidental DB writes)
- [ ] Data quality checks passing (field completeness, date parsing)
- [ ] Racing API unavailability handled gracefully (fallback or skip)

**Status as of 2026-05-23: NO WORKERS BUILT — HKJC and PMU workers do not yet exist**

---

## Gate 4 — Forward Shadow Lane (150 decisions)

After live ingest is running and shadow scoring is active:

- Accumulate minimum 150 live decisions per jurisdiction before any review
- Each decision = one scored race where model's top-pick is recorded
- No early review, no exception — n=150 is the hard floor
- Record: top-pick SR, frame rate, VP band, comparison to favourite

**HK_SHA_TIN_V1: Gate 4 at n=150 decisions**
**HK_HAPPY_VALLEY_V1: Gate 4 at n=100 decisions** (smaller corpus — lower gate)
**FR_CHANTILLY_V1: Gate 4 at n=150 decisions**
**FR_FLAT_CORE: Gate 4 at n=150 decisions**
**FR_AUTEUIL_JUMPS_V1: Gate 4 at n=150 decisions**

---

## Gate 5 — Full Evidence Review (300 decisions)

- Minimum 300 live decisions per jurisdiction
- VP band monotonicity must hold
- Top-decile SR must exceed favourite SR
- SR trend must be non-declining over rolling 50-decision windows
- Benter calibration review for HK packs (α/β recalibration if needed)
- FR penetrometer mapping validation

**No promotion discussion until Gate 5.**

---

## Permanent Rules (Never Override)

```
1. No international model can be called viable from offline arena alone.
   An offline result is a CANDIDATE signal, not a VIABLE signal.

2. Leakage audit (Gate 0) is MANDATORY before any classification of VIABLE.

3. Safe feature contract required — fit scores excluded until time-gating confirmed.

4. Race-level top-pick evaluation required — never report runner-level accuracy.

5. Forward shadow gate required before any live discussion.

6. Per-jurisdiction evidence gates are independent — HK_SHA_TIN does not benefit
   from HK_HAPPY_VALLEY's evidence and vice versa.

7. Sha Tin and Happy Valley evidence NEVER pooled in the same gate.

8. FR Flat and FR Auteuil (jumps) NEVER pooled in the same model or gate.

9. No UK model contamination — UK trainer profiles, UK OR, UK race type patterns
   must not be used as features in FR or HK models.

10. No Telegram for international verdicts until Gate 5 AND operator decision.

11. No staking, no Betfair, no exchange integration at any gate until separate
    live-execution review (equivalent to UK CPU Gate V2).

12. Scoring pipeline changes to accommodate international DO NOT modify
    UK live pipeline — separate scripts, separate Supabase schemas, separate logs.

13. May 20 (SCORING_FLATLINE_CONTAMINATED) exclusion applies to UK pipeline only.
    International gates are independent of UK contamination dates.
```

---

## International Pack Status (as of 2026-05-23)

| Pack | Gate 0 | Gate 1 | Gate 2 | Gate 3 | Gate 4 | Status |
|---|---|---|---|---|---|---|
| HK_SHA_TIN_V1 | IN_PROGRESS | PENDING | NOT_PASSED | NOT_PASSED | NOT_STARTED | **LEAKAGE_AUDIT_IN_PROGRESS** |
| HK_HAPPY_VALLEY_V1 | IN_PROGRESS | PENDING | NOT_PASSED | NOT_PASSED | NOT_STARTED | **LEAKAGE_AUDIT_IN_PROGRESS** |
| FR_CHANTILLY_V1 | IN_PROGRESS | PENDING | NOT_PASSED | NOT_PASSED | NOT_STARTED | **LEAKAGE_AUDIT_IN_PROGRESS** |
| FR_FLAT_CORE | IN_PROGRESS | PENDING | NOT_PASSED | NOT_PASSED | NOT_STARTED | **LEAKAGE_AUDIT_IN_PROGRESS** |
| FR_AUTEUIL_JUMPS_V1 | IN_PROGRESS | PENDING | NOT_PASSED | NOT_PASSED | NOT_STARTED | **LEAKAGE_AUDIT_IN_PROGRESS** |

---

## First Strategic Pack Priority

**HK_SHA_TIN_V1** is the first strategic pack:
- Largest HK corpus (50,976 rows, 4,080 races)
- Strongest draw bias signal (structural edge)
- Sha Tin draw confirmed: 1-3 win 9.9%, 13+ win 6.2%
- Benter model calibration most relevant at Sha Tin (tote pool depth)
- Gate 4 target: n=150 decisions at Sha Tin specifically

**FR_CHANTILLY_V1** is the second strategic pack:
- Largest FR flat corpus (47,568 rows, 4,043 races)
- Penetrometer going is the unique FR signal unavailable elsewhere for free
- PMU API (grey area legality, rate-limited) is the primary FR data source
- Gate 4 target: n=150 decisions at Chantilly specifically

---

```
DOCUMENT_STATUS:      LOCKED_GOVERNANCE
GATE_0_CURRENT:       IN_PROGRESS
ALL_PACKS_STATUS:     LEAKAGE_AUDIT_IN_PROGRESS
MIGRATION_STATUS:     NOT_APPLIED
WORKER_STATUS:        BLOCKED
SCORING_STATUS:       OFFLINE_ONLY
UK_PIPELINE_STATUS:   UNCHANGED
```
