# VFU-13 — False-GREEN Feature Autopsy
**Version:** VFU_13_FALSE_GREEN_FEATURE_AUTOPSY_V1  
**Timestamp:** 2026-06-18T01:33:09.673107+00:00  
**VP Threshold:** 0.4 (UNCHANGED)  

---

## VFU-10 Law (carried forward permanently)

> *No evidence becomes doctrine unless it was knowable before the race.*

---

## Executive Summary

- Total current-era VP≥0.40 losing cases: **121**
- True MISS (not placed): **56**
- PLACED not won (each-way signal): **65**
- Named P0 horses found: **7** / 7
- FG cases with component data: **22**
- Dominant cause: **PLACE_PROB_CORRELATION + MISSING_PICK_SP_LIMITATION**

**Key finding:** PLACE_PROB_CORRELATION is the dominant mechanical pattern in FG cases with component data. FG avg place_prob=0.901 vs WIN avg=0.718. SQPE fires higher in FG than wins (counterintuitive — suggests SQPE over-rates talent in race conditions where the horse placed but did not win). MISSING_PICK_SP_LIMITATION is the dominant data blocker (91.9% of autopsy FG cases).

---

## Component Analysis

| Component | FG Average | WIN Average | Delta |
|-----------|-----------|------------|-------|
| sqpe_v17_prob | 0.0807 | 0.0591 | 0.0216 |
| improvement_score | 0.1879 | 0.1704 | 0.0175 |
| market_deception_score | 0.2567 | 0.1974 | 0.0593 |
| place_prob | 0.8933 | 0.7178 | 0.1755 |

*FG cases with component data: 22 (from 2K training subset)*  
*SQPE null in FG cases: 6*  

---

## Cause Distribution

| Cause | Count |
|-------|-------|
| MISSING_PICK_SP_LIMITATION | 109 |
| MISSING_FRAME_CONTEXT | 65 |
| PASSPORT_OVERRIDE_CONTAMINATION_RISK | 59 |
| SOURCE_LAYER_WEAKNESS | 44 |
| IDENTITY_WEAKNESS | 43 |
| DAY_LEVEL_CHAOS | 19 |
| PLACE_PROB_CORRELATION | 18 |
| SQPE_OVERCONFIDENCE | 16 |
| COURSE_TRAP | 10 |
| PRICE_BAND_TRAP | 9 |
| MARKET_DECEPTION_OVERCONFIDENCE | 2 |
| IMPROVEMENT_SCORE_OVERCONFIDENCE | 1 |

---

## Named P0 Horse Deep Dive

| Horse | VP | Outcome | Course | Course Tier | Primary Cause | Note |
|-------|----|---------|----|-------------|--------------|------|
| Saucy Jane | 0.4318 | MISS | Beverley | DRAIN | MISSING_PICK_SP_LIMITATION | VP=0.432 MISS on Beverley (DRAIN). DRAIN course trap confirm |
| Food For Thought | 0.5035 | MISS | Beverley | DRAIN | MISSING_PICK_SP_LIMITATION | VP=0.504 MISS on Beverley (DRAIN). DRAIN course trap confirm |
| Martymill | 0.4187 | MISS | Clonmel (IRE) | NEUTRAL | MISSING_PICK_SP_LIMITATION | VP=0.419 MISS. improvement_score=0.636 + mds=0.746 dominant. |
| African Spirit | 0.4444 | MISS | Newmarket | NEUTRAL | MISSING_PICK_SP_LIMITATION | VP=0.444 MISS. place_prob=0.837 dominant, SQPE=0.016. Place- |
| Letmeseethecolts | 0.4299 | MISS | redcar | NEUTRAL | MISSING_PICK_SP_LIMITATION |  |

---

## Dry-Run Warning Proposals

All warnings: `blocked_from_live_use=True`, `human_approval_required=True`, `dry_run_only=True`

### HIGH_VP_NO_PICK_SP_WARNING
**Trigger:** `VP >= 0.40 AND pick_sp IS NULL`  
**Rationale:** 109/121 (90.1%) FG cases lacked pick_sp. Cannot verify market alignment when SP absent. Highest risk of false confidence when market evidence missing.  
**Proposed action:** Flag race in operator dashboard; do not increase confidence level  

### HIGH_VP_DRAIN_COURSE_WARNING
**Trigger:** `VP >= 0.40 AND course_tier = DRAIN`  
**Rationale:** 10/121 FG cases on DRAIN-tier courses. Beverley produced 2 named P0 cases (Saucy Jane VP=0.43, Food For Thought VP=0.50). DRAIN courses show elevated false-positive rate.  
**Proposed action:** Flag in operator dashboard; suppress B-tier picks on DRAIN courses  

### HIGH_VP_PLACE_PROB_DOMINANT_WARNING
**Trigger:** `VP >= 0.40 AND place_prob > 0.80 AND sqpe_v17_prob < 0.15`  
**Rationale:** place_prob dominated in 18/121 FG cases with component data. FG avg place_prob=0.901 vs win avg=0.718. High place_prob indicates each-way quality, not outright win confidence. When sqpe_v17 is low and place_prob is driving VP, win confidence is inflated.  
**Proposed action:** Flag as EACH_WAY_CANDIDATE, not WIN_CANDIDATE; do not use for outright prediction  

### HIGH_VP_LOW_SOURCE_CONFIDENCE
**Trigger:** `VP >= 0.40 AND evidence_quality_tier IN (TIER_C_LIMITED_IDENTITY, TIER_D_EVENT_ONLY)`  
**Rationale:** 44/121 FG cases had limited identity or event-only evidence quality. Without TIER_A or TIER_B evidence, VP signal is less reliable.  
**Proposed action:** Flag confidence level as EVIDENCE_LIMITED in operator output  

---

## Required Report Answers

**Q1 — Total current-era VP≥0.40 losses:** 121
**Q2 — MISS vs PLACED:** MISS=56, PLACED=65
**Q3 — Dominant component:** PLACE_PROB_CORRELATION is dominant in all 23 FG cases with component data. FG avg place_prob=0.901 vs WIN avg=0.718. place_prob is badge-only in SQPE_IMPROVEMENT_MDS_V1 but co-occurs with VP due to co...
**Q4 — Top FG courses:** [('Lingfield', 5), ('Hexham', 5), ('Beverley', 4), ('Bath', 4), ('Hamilton', 4)]
**Q5 — Top source layers:** {'OVERLAP': 87, 'SUPABASE_ONLY': 34}
**Q6 — Missing pick_sp:** 109
**Q7 — Missing horse_id:** 43
**Q8 — DRAIN/CAUTION course count:** 10
**Q9 — Day cluster findings:** [('2026-06-06', 13), ('2026-06-11', 11), ('2026-06-05', 9)]
**Q10 — Isolated vs day-level:** Mix of isolated horse misses and probable day-level failures. Beverley appears twice in P0 named cases — same-day DRAIN course trap likely. No single day dominates (('2026-06-06', 13)). Day-level clus...
**Q11 — Dry-run warnings proposed:** ['HIGH_VP_NO_PICK_SP_WARNING', 'HIGH_VP_DRAIN_COURSE_WARNING', 'HIGH_VP_PLACE_PROB_DOMINANT_WARNING', 'HIGH_VP_LOW_SOURCE_CONFIDENCE']
**Q12 — Live rule recommended:** NO — insufficient evidence for any live rule. All proposals DRY_RUN_ONLY.
**Q13 — VP threshold recommendation:** NO CHANGE. VP threshold remains 0.4.
**Q14 — VFU-14 focus:** OPTION A (recommended): SP Data Recovery Sprint — 109/121 FG cases lack pick_sp. Without SP, cannot verify market alignment. Target: recover SP for TIER_A/TIER_B cases via sigma_audits_dump actual_winner_sp backfill. OPTION B: Day-Level Chaos Classifier — correlate FG-heavy days with eod_sigma_study...

---

## Priority Band Audit (VFU-12 Retrospective)

**VFU-12 distribution:** P0=41, P1=0, P2=0, P3=0, P4=159  
**Diagnosis:** P0=41, P1-P3=0 is too blunt. All 41 current-era entries landed in P0 because they shared FALSE_GREEN + PASSPORT_OVERRIDE flags. P0 should require stronger evidence of systemic or urgent risk.  

**Recommended future P0 criterion:**
- VP >= 0.60 MISS (severe false confidence) on any era + RP_UID confirmed; OR confirmed DRAIN course trap with named horse; OR repeated false-GREEN pattern (same horse ≥2 false-GREEN races)

**VFU-13 severity reclassification:**
- SEVERE: 18
- HIGH: 36
- MODERATE: 67
- Would be P0 by new criteria: 28

---

## Hard Rules — Confirmed

- VP threshold: 0.40 — UNCHANGED
- Canonical Horse Passport: NOT MUTATED
- Supabase: NOT WRITTEN
- Live scoring: NOT CHANGED
- Model: NOT PROMOTED
- Telegram: NOT SENT
- Racing API: NOT RESTORED
- Mar–Apr: QUARANTINE ONLY
- All warnings: DRY_RUN_ONLY

---

## Final Classifications

```
VFU_13_FALSE_GREEN_FEATURE_AUTOPSY_COMPLETE
FALSE_GREEN_CASES_CLASSIFIED
FALSE_GREEN_WARNINGS_DRY_RUN_ONLY
NO_VP_THRESHOLD_CHANGE
NO_LIVE_DOCTRINE_PROMOTION
MAR_APR_QUARANTINE_MAINTAINED
CANONICAL_HORSE_PASSPORT_NOT_MUTATED
NO_LIVE_SCORING_CHANGE
NO_SUPABASE_WRITES
NO_MODEL_PROMOTION
NO_TELEGRAM_SEND
NO_RACING_API_RESTORATION
```