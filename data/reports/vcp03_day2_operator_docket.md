# VCP-03 Day 2 Operator Docket
Generated: 2026-07-01 02:33 UTC
Status: REPORT_ONLY

---

## SECTION 1 — VCP-03 Day 2 Burn-In Status

  Day count:           2/10 PASS
  Remaining days:      8
  Started:             2026-06-29
  Pass dates:          2026-06-30, 2026-07-01
  Burn-in valid:       True

  Truth lock:          LOCKED
  Source truth:        RP_MERGED_CLEAN
  Repo head:           a8b3e8a

  Contradiction count: 1
    [C-01] Mission Control reports RP_MERGED_CLEAN source but learning gate is BLOCKED (severity=WARN)

  Memory capture:      OPEN
  Failure learning:    OPEN
  Promotion learning:  ELIGIBLE
  VFU-21 gate:         CLOSED

  next_safe_action:    VCP-01-REVIEW
  Label:               KNOWN_STALE_LABEL_COSMETIC — still reads VCP-01-REVIEW; VCP-01 was completed and signed off. No patch during burn-in without separate operator authorisation.

---

## SECTION 2 — COURSE-00A Findings Summary

  Total claims audited: 33

### Evidence Status Tally
    HYPOTHESIS_FROM_RESULTS: 3
    SECONDARY_PUBLIC_SOURCE: 29
    STALE: 1

### Action Tally
    CORRECT: 1
    DOWNGRADE_TO_HYPOTHESIS: 17
    KEEP: 15

### Stale Facts
  Count: 1
    Course: Southwell (AW) | Type: surface
    Stale value: Fibresand → Corrected: Tapeta
    Note: Southwell changed from Fibresand to Tapeta in 2021. All 2026 data should assume Tapeta.
    Label: STALE_FACT → CORRECTED_FACT

### Southwell Surface Verdict
  Stale claim:    Fibresand
  Corrected to:   Tapeta
  Note:           Southwell changed from Fibresand to Tapeta in 2021. All 2026 data should assume Tapeta.
  Label:          STALE_FACT_CORRECTED

### AW Surface Verdicts
  Southwell (AW)
    Surface (current): Tapeta | Source: SECONDARY_PUBLIC_SOURCE
    Draw bias status:  HYPOTHESIS_FROM_SECONDARY_SOURCE | Confidence: 0.4
    Verdict:           SURFACE_STALE_CORRECTED_DRAW_PACE_HYPOTHESIS
  Kempton (AW)
    Surface (current): Polytrack | Source: SECONDARY_PUBLIC_SOURCE
    Draw bias status:  HYPOTHESIS_DOWNGRADED_TO_UNKNOWN | Confidence: 0.4
    Verdict:           SURFACE_CORRECT_DRAW_DOWNGRADED_UNKNOWN
  Wolverhampton (AW)
    Surface (current): Tapeta | Source: SECONDARY_PUBLIC_SOURCE
    Draw bias status:  HYPOTHESIS_DOWNGRADED_TO_UNKNOWN | Confidence: 0.4
    Verdict:           SURFACE_CORRECT_DRAW_DOWNGRADED_UNKNOWN
  Lingfield (AW)
    Surface (current): Polytrack | Source: SECONDARY_PUBLIC_SOURCE
    Draw bias status:  HYPOTHESIS_DOWNGRADED_TO_UNKNOWN | Confidence: 0.4
    Verdict:           SURFACE_CORRECT_DRAW_DOWNGRADED_UNKNOWN
  Newcastle (AW)
    Surface (current): Tapeta | Source: SECONDARY_PUBLIC_SOURCE
    Draw bias status:  HYPOTHESIS_DOWNGRADED_TO_UNKNOWN | Confidence: 0.4
    Verdict:           SURFACE_CORRECT_DRAW_DOWNGRADED_UNKNOWN
  Chelmsford (AW)
    Surface (current): Polytrack | Source: SECONDARY_PUBLIC_SOURCE
    Draw bias status:  HYPOTHESIS_DOWNGRADED_TO_UNKNOWN | Confidence: 0.4
    Verdict:           SURFACE_CORRECT_DRAW_DOWNGRADED_UNKNOWN

### Draw Bias Claim Verdicts
  Total draw claims:    10
  Hypothesis only:      9
  Verified local:       0
  Reason:               No local draw data in VELO pipeline. All draw bias from public guides = HYPOTHESIS_ONLY
  Exception:            Chester low-draw = SECONDARY_PUBLIC_SOURCE_HIGH_CONFIDENCE (not VERIFIED)
  Label:                HYPOTHESIS_ONLY — must not be promoted to scoring

### Pace / Front-Runner Claim Verdicts
  Total pace claims:    6
  Hypothesis only:      6
  Verified local:       0
  Reason:               No in-running position, running-style, or sectional data in VELO pipeline
  Label:                HYPOTHESIS_ONLY — must not be promoted to scoring

### BHA/RP Field Access Reality
  Proven locally present: course, going, race_type, distance, field_size, finish_order, SP (partial), trainer (partial)
  Sections exist but NOT proven: surface, handedness, draw, GoingStick, stalls_position, OR_per_runner, pace
  Login required for RP field access: True
  Login automated in pipeline: False
  Doctrine: SOURCE_SECTION_EXISTS_IS_NOT_PROOF

### COURSE-01 Readiness
  Safe to consume now:          course, going, race_type, distance
  Blocked until local capture:  draw_bias, pace_map, stalls_position, GoingStick, OR_per_runner, surface_subtype
  COURSE-00 reclassified as: WATCHLIST_MAP_WITH_STALE_FACTS_CORRECTED
  COURSE-00 is NOT:          SOURCE_VERIFIED_COURSE_REGISTRY
  Verified registry entries: 16

---

## SECTION 3 — Proven Strategic Facts

  [RESULT_PATTERN] VELO lands mostly short-to-mid selections
    Source: RESULTS-01
    Detail: Pick SP distribution skews below market mid-price. System over-trusts public strength/RPR signal.

  [RESULT_PATTERN] 803 mid-price misses exist — 6–10 odds band is the core wound
    Source: RESULTS-01 + RESULTS-02
    Detail: 6–10 = 312 misses (core). 4–6 = 288. 10–16 = 65. Winners at 6–10 SP lost to wrong selection.

  [VERIFIED_FACT] Old VELO is RPR/public-strength anchored
    Source: RESULTS-01
    Detail: Model heavily weighted on RPR and trainer/jockey public form. Creates short-price over-selection.

  [VERIFIED_FACT] New Build is VALUE_SCOUT / EXOTIC_FILL_CANDIDATE — not replacement engine
    Source: RESULTS-01 model comparison ledger
    Detail: New Build SR=24.2% but only N=1125 prospective rows. 4/4 unseen gates passed. Shadow only until N≥300 top-decile.

  [VERIFIED_FACT] EW_CANDIDATE is PLACE_SIGNAL — not profit proof
    Source: RESULTS-01 EW analysis
    Detail: EW place rate 37.3%. No pick_sp data. Cannot compute EW ROI without prices. VFU-21 required.

  [VERIFIED_FACT] Exotics are SIGNAL_ONLY — dividends missing
    Source: RESULTS-01
    Detail: Top-3 containment signal exists but no dividend data captured. Cannot proof exotic profit without it.

  [VERIFIED_FACT] Course intelligence is missing from VELO scoring
    Source: RESULTS-02 + COURSE-00
    Detail: Draw bias, pace map, course-position features are CRITICAL missing features. Not in any live model.

  [VERIFIED_FACT] Draw/pace features are critical but not implemented
    Source: COURSE-00 feature readiness matrix
    Detail: draw_bias_by_course_distance and pace_map_front_runner_flag are CRITICAL. Require COURSE-01 implementation.

  [VERIFIED_FACT] All draw and pace course claims require provenance fields
    Source: COURSE-00A tribunal
    Detail: No local draw or pace data exists. All public-guide claims = HYPOTHESIS_ONLY. Chester only at SECONDARY_HIGH_CONF.

  [CORRECTED_FACT] Southwell surface was stale (Fibresand → Tapeta, changed 2021)
    Source: COURSE-00A tribunal
    Detail: COURSE-00 had Southwell listed as Fibresand. Tapeta since 2021. Stale for 5 years. Now corrected.

  [RESULT_PATTERN] Beverley is a drain course: 4.0% SR, pick avg SP 13.92 vs winner avg SP 7.21
    Source: RESULTS-02 Beverley deep dive
    Detail: 50 races. −6.7 SP gap. Root cause: draw bias + uphill finish + pace dynamics not captured.

  [RESULT_PATTERN] AW cluster has combined 86 mid-price misses and no draw/pace modelling
    Source: RESULTS-02 + COURSE-00
    Detail: Southwell, Kempton, Wolverhampton, Lingfield — all have draw/pace but VELO has none of it.

---

## SECTION 4 — Post-Burn-In Decision Board (Day-10 Queue)

### A. COURSE-01 — Draw and Pace Shadow Feature Registry
  Status:     QUEUED_AFTER_VCP03
  Gate:       VCP-03 Day 10/10
  Priority:   1
  Purpose:    Build shadow-only course eyes: draw bias, pace map, course-position per track/distance.
  Blocked by: VCP-03 10/10 gate
  Contract:
    - Every feature must carry source_status + confidence + last_checked.
    - HYPOTHESIS features: shadow only, not promoted to scoring.
    - UNKNOWN-safe fallbacks mandatory.
    - Draw and pace must be LOCALLY CAPTURED before scoring use.
    - Provenance violation = feature blocked.

### B. VFU-21 — pick_sp Price Truth Repair
  Status:     QUEUED_AFTER_VCP03
  Gate:       VCP-03 Day 10/10
  Priority:   2
  Purpose:    Repair price truth for EW ROI, value band, and exotics. Required before any profit claim on EW/exotics.
  Blocked by: VCP-03 10/10 gate
  Contract:
    - Backfill pick_sp for all sigma rows where absent.
    - EW ROI cannot be claimed until prices are clean.
    - Exotics signal cannot be profit-proven without dividends.

### C. No-RPR GBM fold 2/3 decision
  Status:     BLOCKED
  Gate:       VCP-03 Day 10/10 + operator review
  Priority:   3
  Purpose:    Complete No-RPR GBM training (fold 2/3 was running). Evaluate vs legacy ensemble.
  Blocked by: VCP-03 gate + training corpus gap (76 audit dates absent Jan–May 2026)
  Contract:
    - No promotion without N≥300 prospective shadow rows.
    - Must not use --promote flag.
    - Operator gate required at fold completion.

### D. New Build challenger promotion
  Status:     BLOCKED_NOT_READY
  Gate:       N≥300 prospective shadow rows + VCP-03 Day 10/10
  Priority:   4
  Purpose:    Promote New Build from VALUE_SCOUT shadow to operational layer.
  Blocked by: Insufficient prospective shadow n. VCP-03 gate.
  Contract:
    - NB is VALUE_SCOUT / EXOTIC_FILL_CANDIDATE — not replacement engine.
    - N=1125 ledger rows exist but need prospective shadow validation.
    - Must pass 300+ runners, 75+ top-decile prospective rows before operator review.

### E. Model training decisions (corpus + source truth)
  Status:     BLOCKED
  Gate:       VFU-21 completion + VCP-03 Day 10/10
  Priority:   5
  Purpose:    Retrain on clean corpus once price truth and source truth are repaired.
  Blocked by: Training corpus gap. Price truth gap. VCP-03 gate.
  Contract:
    - 76 audit dates absent from training corpus (Jan–May 2026).
    - pick_sp missing in most rows — EW/value training corrupted until VFU-21.
    - No training decisions before VFU-21 price truth repair.

### F. C-01 contradiction — RP_MERGED_CLEAN vs BLOCKED learning gate
  Status:     OPEN_HONEST
  Gate:       Not gated — requires operator resolution
  Priority:   6
  Purpose:    Mission Control reports RP_MERGED_CLEAN but learning gate is BLOCKED. Contradiction must not be suppressed.
  Blocked by: Operator decision required. Do not auto-resolve.
  Contract:
    - C-01 is logged in contradictions.items[] with severity=WARN.
    - Do not patch or suppress during burn-in.
    - Operator must resolve after VCP-03: either open learning gate or update source truth label.

### G. next_safe_action stale label
  Status:     KNOWN_STALE_LABEL_COSMETIC
  Gate:       Operator-approved VCP maintenance patch
  Priority:   7
  Purpose:    next_safe_action field still reads VCP-01-REVIEW. VCP-01 was completed and signed off. Field is cosmetically stale.
  Blocked by: Do not patch during burn-in.
  Contract:
    - Do not patch during burn-in without separate operator authorisation.
    - Recommended treatment: VCP maintenance patch after Day 10/10.
    - Label as KNOWN_STALE_LABEL_COSMETIC in all reporting until patched.

---

## SECTION 5 — Tomorrow's Triple

  Run in order:
    PYTHONPATH=. venv/bin/python scripts/ops/build_velo_living_state.py
    PYTHONPATH=. venv/bin/python scripts/ops/build_velo_heartbeat.py
    PYTHONPATH=. venv/bin/python scripts/ops/build_vcp03_burn_in_log.py

  Report after:
    - Day 3/10 PASS or FAIL
    - contradiction count
    - promotion gate state
    - stale label state
    - any new anomaly

---

## FINAL CLASSIFICATIONS

  - VCP03_DAY2_DOCKET_COMPLETE
  - VCP03_DAY2_PASS_SIGNED_OFF
  - COURSE_00A_FINDINGS_SUMMARISED
  - POST_BURNIN_DECISION_BOARD_WRITTEN
  - KNOWN_STALE_LABEL_RECORDED
  - CONTRADICTION_C01_RECORDED_NOT_SUPPRESSED
  - COURSE_01_QUEUED_NOT_STARTED
  - VFU_21_QUEUED_NOT_STARTED
  - MODEL_TRAINING_BLOCKED
  - NEW_BUILD_PROMOTION_BLOCKED
  - NO_RPR_TRAINING_BLOCKED
  - MEMORY_CAPTURE_OPEN
  - FAILURE_LEARNING_OPEN
  - PROMOTION_LEARNING_GATED
  - NO_COURSE_01_IMPLEMENTATION
  - NO_VFU_21_START
  - NO_VCP_04_START
  - NO_LIVE_SCORING_CHANGE
  - NO_MODEL_PROMOTION
  - NO_SUPABASE_WRITES
  - NO_TELEGRAM_SEND
  - REPORT_ONLY