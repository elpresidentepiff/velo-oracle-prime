# VÉLØ Post-Burn-In Decision Board
Generated: 2026-07-01 02:33 UTC
Gate opens: VCP-03 Day 10/10
Status: REPORT_ONLY — no decision taken until gate open

---

## What Has Been Proven

**[RESULT_PATTERN]** VELO lands mostly short-to-mid selections
> Source: RESULTS-01 — Pick SP distribution skews below market mid-price. System over-trusts public strength/RPR signal.

**[RESULT_PATTERN]** 803 mid-price misses exist — 6–10 odds band is the core wound
> Source: RESULTS-01 + RESULTS-02 — 6–10 = 312 misses (core). 4–6 = 288. 10–16 = 65. Winners at 6–10 SP lost to wrong selection.

**[VERIFIED_FACT]** Old VELO is RPR/public-strength anchored
> Source: RESULTS-01 — Model heavily weighted on RPR and trainer/jockey public form. Creates short-price over-selection.

**[VERIFIED_FACT]** New Build is VALUE_SCOUT / EXOTIC_FILL_CANDIDATE — not replacement engine
> Source: RESULTS-01 model comparison ledger — New Build SR=24.2% but only N=1125 prospective rows. 4/4 unseen gates passed. Shadow only until N≥300 top-decile.

**[VERIFIED_FACT]** EW_CANDIDATE is PLACE_SIGNAL — not profit proof
> Source: RESULTS-01 EW analysis — EW place rate 37.3%. No pick_sp data. Cannot compute EW ROI without prices. VFU-21 required.

**[VERIFIED_FACT]** Exotics are SIGNAL_ONLY — dividends missing
> Source: RESULTS-01 — Top-3 containment signal exists but no dividend data captured. Cannot proof exotic profit without it.

**[VERIFIED_FACT]** Course intelligence is missing from VELO scoring
> Source: RESULTS-02 + COURSE-00 — Draw bias, pace map, course-position features are CRITICAL missing features. Not in any live model.

**[VERIFIED_FACT]** Draw/pace features are critical but not implemented
> Source: COURSE-00 feature readiness matrix — draw_bias_by_course_distance and pace_map_front_runner_flag are CRITICAL. Require COURSE-01 implementation.

**[VERIFIED_FACT]** All draw and pace course claims require provenance fields
> Source: COURSE-00A tribunal — No local draw or pace data exists. All public-guide claims = HYPOTHESIS_ONLY. Chester only at SECONDARY_HIGH_CONF.

**[CORRECTED_FACT]** Southwell surface was stale (Fibresand → Tapeta, changed 2021)
> Source: COURSE-00A tribunal — COURSE-00 had Southwell listed as Fibresand. Tapeta since 2021. Stale for 5 years. Now corrected.

**[RESULT_PATTERN]** Beverley is a drain course: 4.0% SR, pick avg SP 13.92 vs winner avg SP 7.21
> Source: RESULTS-02 Beverley deep dive — 50 races. −6.7 SP gap. Root cause: draw bias + uphill finish + pace dynamics not captured.

**[RESULT_PATTERN]** AW cluster has combined 86 mid-price misses and no draw/pace modelling
> Source: RESULTS-02 + COURSE-00 — Southwell, Kempton, Wolverhampton, Lingfield — all have draw/pace but VELO has none of it.

---

## Decision Queue — ordered by priority after VCP-03 Day 10/10

### Priority 1: COURSE-01 — Draw and Pace Shadow Feature Registry
**Status:** QUEUED_AFTER_VCP03
**Gate:** VCP-03 Day 10/10
**Blocked by:** VCP-03 10/10 gate
**Purpose:** Build shadow-only course eyes: draw bias, pace map, course-position per track/distance.

**Contract:**
- Every feature must carry source_status + confidence + last_checked.
- HYPOTHESIS features: shadow only, not promoted to scoring.
- UNKNOWN-safe fallbacks mandatory.
- Draw and pace must be LOCALLY CAPTURED before scoring use.
- Provenance violation = feature blocked.

### Priority 2: VFU-21 — pick_sp Price Truth Repair
**Status:** QUEUED_AFTER_VCP03
**Gate:** VCP-03 Day 10/10
**Blocked by:** VCP-03 10/10 gate
**Purpose:** Repair price truth for EW ROI, value band, and exotics. Required before any profit claim on EW/exotics.

**Contract:**
- Backfill pick_sp for all sigma rows where absent.
- EW ROI cannot be claimed until prices are clean.
- Exotics signal cannot be profit-proven without dividends.

### Priority 3: No-RPR GBM fold 2/3 decision
**Status:** BLOCKED
**Gate:** VCP-03 Day 10/10 + operator review
**Blocked by:** VCP-03 gate + training corpus gap (76 audit dates absent Jan–May 2026)
**Purpose:** Complete No-RPR GBM training (fold 2/3 was running). Evaluate vs legacy ensemble.

**Contract:**
- No promotion without N≥300 prospective shadow rows.
- Must not use --promote flag.
- Operator gate required at fold completion.

### Priority 4: New Build challenger promotion
**Status:** BLOCKED_NOT_READY
**Gate:** N≥300 prospective shadow rows + VCP-03 Day 10/10
**Blocked by:** Insufficient prospective shadow n. VCP-03 gate.
**Purpose:** Promote New Build from VALUE_SCOUT shadow to operational layer.

**Contract:**
- NB is VALUE_SCOUT / EXOTIC_FILL_CANDIDATE — not replacement engine.
- N=1125 ledger rows exist but need prospective shadow validation.
- Must pass 300+ runners, 75+ top-decile prospective rows before operator review.

### Priority 5: Model training decisions (corpus + source truth)
**Status:** BLOCKED
**Gate:** VFU-21 completion + VCP-03 Day 10/10
**Blocked by:** Training corpus gap. Price truth gap. VCP-03 gate.
**Purpose:** Retrain on clean corpus once price truth and source truth are repaired.

**Contract:**
- 76 audit dates absent from training corpus (Jan–May 2026).
- pick_sp missing in most rows — EW/value training corrupted until VFU-21.
- No training decisions before VFU-21 price truth repair.

### Priority 6: C-01 contradiction — RP_MERGED_CLEAN vs BLOCKED learning gate
**Status:** OPEN_HONEST
**Gate:** Not gated — requires operator resolution
**Blocked by:** Operator decision required. Do not auto-resolve.
**Purpose:** Mission Control reports RP_MERGED_CLEAN but learning gate is BLOCKED. Contradiction must not be suppressed.

**Contract:**
- C-01 is logged in contradictions.items[] with severity=WARN.
- Do not patch or suppress during burn-in.
- Operator must resolve after VCP-03: either open learning gate or update source truth label.

### Priority 7: next_safe_action stale label
**Status:** KNOWN_STALE_LABEL_COSMETIC
**Gate:** Operator-approved VCP maintenance patch
**Blocked by:** Do not patch during burn-in.
**Purpose:** next_safe_action field still reads VCP-01-REVIEW. VCP-01 was completed and signed off. Field is cosmetically stale.

**Contract:**
- Do not patch during burn-in without separate operator authorisation.
- Recommended treatment: VCP maintenance patch after Day 10/10.
- Label as KNOWN_STALE_LABEL_COSMETIC in all reporting until patched.

---

## Execution Order After Gate Opens

1. COURSE-01 — Draw and Pace Shadow Feature Registry (shadow only, provenance fields mandatory)
2. VFU-21 — pick_sp Price Truth Repair (unlocks EW/exotics analysis)
3. No-RPR GBM fold 2/3 decision (once corpus and price truth clean)
4. New Build promotion decision (once N≥300 prospective shadow rows)
5. Full model training decision (after VFU-21 + clean corpus)
6. Resolve C-01 contradiction (operator decision)
7. next_safe_action stale label patch (VCP maintenance patch)

---

## Hard Constraints Until Gate Opens

- REPORT_ONLY
- NO_SUPABASE_WRITES
- NO_TELEGRAM_SEND
- NO_COURSE_01_IMPLEMENTATION
- NO_VFU_21_START
- NO_VCP_04_START
- NO_LIVE_SCORING_CHANGE
- NO_MODEL_PROMOTION
- NO_TRAINING_DECISIONS
- NO_NEW_BUILD_PROMOTION
- NO_NORPR_FOLD_DECISIONS
- CANONICAL_HORSE_PASSPORT_NOT_MUTATED
- DO_NOT_SUPPRESS_CONTRADICTIONS