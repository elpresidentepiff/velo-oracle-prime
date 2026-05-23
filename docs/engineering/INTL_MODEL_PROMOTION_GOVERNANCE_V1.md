# International Model Promotion Governance V1

**Date:** 2026-05-23  
**Status:** LOCKED — governs all international jurisdiction model promotion  
**Classification:** Permanent governance — survives context compaction

---

## ACTIVE BLOCKING GATE (as of 2026-05-23)

```
INTERNATIONAL_RATING_PROVENANCE_GATE_ACTIVE
LAGGED_ONLY_ARENA_REQUIRED
NO_MIGRATION
NO_WORKER_ACTIVATION
NO_PROMOTION
```

**The international expansion does not advance to migration, workers, training, or
deployment until this gate closes.**

**The gate closes only when the following question is answered YES:**

> Can VÉLØ beat favourite and RPR baselines using ONLY information that would have
> existed before the race started?

Current answer: **NO.** All 5 packs return NEEDS_FEATURE_ENGINEERING on lagged-only
arena. No pack beats the favourite SR on prior-run history alone.

**Gate close path — what must be built:**
- Sha Tin draw bias table (structural edge, publicly available from HKJC)
- HK class trajectory (class movement over last 4 runs — available from form history)
- FR penetrometer going mapping (PMU publishes numeric going pre-race)
- FR Quinté+ flag (race classification — known pre-race)
- FR distance preference from prior-run history (already in lagged features, needs tuning)
- Local market structure proxy (HK: morning HKJC tote odds / FR: PMU morning odds)

If re-running the lagged arena with these additional pre-race features produces a pack
that beats the favourite SR, the gate opens for that pack only. Each pack is independent.

If no pack beats the favourite after full pre-race feature set: the original arena was
a mirage driven by post-race RPR/TS. Rebuild from scratch on lagged signals only.

**Operator position (co-founder, 2026-05-23):**
- Dataset: trusted enough to audit
- Same-race ratings: untrusted until timestamp provenance proven
- Original arena (AUC 0.90-0.95): NOT ACCEPTED
- Safe arena: NOT ACCEPTED until lagged-only confirms
- Migration: BLOCKED
- Workers: BLOCKED
- Promotion: BLOCKED

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

14. SHUFFLE TEST PASSING IS INSUFFICIENT FOR VIABILITY.
    A clean shuffle test (AUC collapses to ~0.50) proves that within-race label
    randomisation destroys the model — i.e., the model uses real structure across
    runners in the same race. It does NOT prove those features were available BEFORE
    the race started. A post-race performance rating will also pass a shuffle test.

15. SAME-RACE RPR AND TS ARE BANNED unless pre-race provenance is proven.
    Provenance test: winner-max-rating rate across all races.
    - winner_max < 55% → PRE_RACE_SAFE (consistent with a top-pick SR)
    - winner_max 55–70% → TIMESTAMP_UNKNOWN (banned pending investigation)
    - winner_max > 70% → POST_RACE_LEAKAGE_CONFIRMED (ban permanently)
    
    Dominance audit findings (2026-05-23):
    - HK rpr_vs_field: 42–46% winner-max → PRE_RACE_SAFE
    - HK or_vs_field: 12–17% winner-max → PRE_RACE_SAFE (handicapper equalises)
    - FR rpr_vs_field: 70–73% winner-max → POST_RACE_LEAKAGE_CONFIRMED
    - FR ts_num: 75–77% winner-max → POST_RACE_LEAKAGE_CONFIRMED
    
    FR rpr_vs_field and FR ts_num are permanently banned from all FR arenas and
    models until Racing Post confirms the data source is pre-race.

16. LAGGED-ONLY ARENA IS THE MINIMUM ACCEPTABLE OFFLINE EVIDENCE.
    An arena that uses current-race rpr_num / or_num / ts_num where provenance is
    unconfirmed is not acceptable offline evidence even if it passes a shuffle test.
    The lagged-only arena (prev_rpr_num, max_rpr_num_last3, avg_rpr_num_last3,
    course_prior_wr, dist_prior_wr, days_since_last_run) is the minimum bar for
    any pack where same-race rating provenance is unconfirmed or POST_RACE.

17. NO MIGRATION UNTIL LAGGED-ONLY ARENA IS ASSESSED.
    Schema migration (intl_schemas_v1.sql) remains blocked until:
    (a) Lagged-only arena runs for all 5 packs
    (b) Results are credible and non-extreme (AUC ≤ 0.85 for lagged features)
    (c) Operator decision (El Presidente sign-off) on viability
    Reason: migration is irreversible without DROP SCHEMA CASCADE. Do not create
    production infrastructure for a model whose feature provenance is unproven.
```

---

## International Pack Status (as of 2026-05-23)

### Gate 0 Sub-gates
| Pack | Leakage Audit | Shuffle Test | Safe Arena | Provenance Test | Lagged Arena | Gate 0 |
|---|---|---|---|---|---|---|
| HK_SHA_TIN_V1 | PASS | PASS (0.47) | PASS | RPR PRE_RACE_SAFE / OR PRE_RACE_SAFE | IN_PROGRESS | **PENDING_LAGGED** |
| HK_HAPPY_VALLEY_V1 | PASS | PASS (0.51) | PASS | RPR PRE_RACE_SAFE / OR PRE_RACE_SAFE | IN_PROGRESS | **PENDING_LAGGED** |
| FR_CHANTILLY_V1 | PASS | MARGINAL (0.61) | PASS* | RPR POST_RACE / TS POST_RACE | IN_PROGRESS | **PROVENANCE_FAILED** |
| FR_FLAT_CORE | PASS | NOT_RUN | PASS* | RPR POST_RACE / TS POST_RACE | IN_PROGRESS | **PROVENANCE_FAILED** |
| FR_AUTEUIL_JUMPS_V1 | PASS | NOT_RUN | PASS* | RPR POST_RACE | IN_PROGRESS | **PROVENANCE_FAILED** |

*Safe arena passed but used same-race rpr_vs_field which is now POST_RACE_LEAKAGE_CONFIRMED for FR. Safe arena FR results are invalidated.

### Full Gate Status
| Pack | Gate 0 | Gate 1 | Gate 2 | Gate 3 | Gate 4 | Current Status |
|---|---|---|---|---|---|---|
| HK_SHA_TIN_V1 | PENDING | PENDING | NOT_PASSED | NOT_PASSED | NOT_STARTED | **PENDING_LAGGED_ARENA** |
| HK_HAPPY_VALLEY_V1 | PENDING | PENDING | NOT_PASSED | NOT_PASSED | NOT_STARTED | **PENDING_LAGGED_ARENA** |
| FR_CHANTILLY_V1 | FAILED | BLOCKED | NOT_PASSED | NOT_PASSED | NOT_STARTED | **PROVENANCE_FAILED — same-race RPR/TS banned** |
| FR_FLAT_CORE | FAILED | BLOCKED | NOT_PASSED | NOT_PASSED | NOT_STARTED | **PROVENANCE_FAILED — same-race RPR/TS banned** |
| FR_AUTEUIL_JUMPS_V1 | FAILED | BLOCKED | NOT_PASSED | NOT_PASSED | NOT_STARTED | **PROVENANCE_FAILED — same-race RPR banned** |

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
DOCUMENT_STATUS:                  LOCKED_GOVERNANCE
ACTIVE_BLOCKING_GATE:             INTERNATIONAL_RATING_PROVENANCE_GATE_ACTIVE
GATE_QUESTION:                    Can VELO beat fav/RPR baselines on pre-race info only?
GATE_CURRENT_ANSWER:              NO — all 5 packs NEEDS_FEATURE_ENGINEERING on lagged-only

GATE_0_HK_SHA_TIN:                NEEDS_FEATURE_ENGINEERING (lagged AUC=0.70, SR<FavSR)
GATE_0_HK_HAPPY_VALLEY:           NEEDS_FEATURE_ENGINEERING (lagged AUC=0.66, SR<FavSR)
GATE_0_FR_CHANTILLY:              PROVENANCE_FAILED + NEEDS_FEATURE_ENGINEERING
GATE_0_FR_FLAT_CORE:              PROVENANCE_FAILED + NEEDS_FEATURE_ENGINEERING
GATE_0_FR_AUTEUIL:                PROVENANCE_FAILED + NEEDS_FEATURE_ENGINEERING

HK_RPR_PROVENANCE:                PRE_RACE_SAFE (winner_max 42-46%)
HK_OR_PROVENANCE:                 PRE_RACE_SAFE (winner_max 12-17%)
FR_RPR_PROVENANCE:                POST_RACE_LEAKAGE_CONFIRMED (winner_max 70-73%)
FR_TS_PROVENANCE:                 POST_RACE_LEAKAGE_CONFIRMED (winner_max 75-77%)
FR_SAME_RACE_RPR_TS:              PERMANENTLY_BANNED

MIGRATION_STATUS:                 NOT_APPLIED — BLOCKED
WORKER_STATUS:                    BLOCKED
PROMOTION_STATUS:                 BLOCKED
SCORING_STATUS:                   OFFLINE_ONLY
UK_PIPELINE_STATUS:               UNCHANGED
SHUFFLE_IS_INSUFFICIENT:          TRUE — see Rule 14
LAGGED_ARENA_STATUS:              COMPLETE — NEEDS_FEATURE_ENGINEERING all packs
NEXT_REQUIRED_STEP:               Add draw/class/going/market features, re-run lagged arena
```
