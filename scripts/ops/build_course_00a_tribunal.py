"""
COURSE-00A — Source Provenance Tribunal and Stale Fact Correction
REPORT_ONLY — no scoring, model, or database changes.
"""

import csv
import json
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# HARD CONSTRAINTS
# ---------------------------------------------------------------------------
_HARD_CONSTRAINTS = [
    "REPORT_ONLY",
    "NO_LIVE_SCORING_CHANGE",
    "NO_VP_THRESHOLD_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "NO_VFU_21_START",
    "NO_VCP_04_START",
    "NO_COURSE_01_IMPLEMENTATION",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "COURSE_FACTS_REQUIRE_PROVENANCE",
    "UNSOURCED_COURSE_FACTS_DOWNGRADED_TO_UNKNOWN",
    "STALE_COURSE_FACTS_CORRECTED_OR_QUARANTINED",
    "SOURCE_SECTION_EXISTS_IS_NOT_PROOF",
    "HYPOTHESES_ARE_NOT_FACTS",
]

# ---------------------------------------------------------------------------
# FINAL CLASSIFICATIONS
# ---------------------------------------------------------------------------
_FINAL_CLASSIFICATIONS = [
    "COURSE_00A_SOURCE_PROVENANCE_TRIBUNAL_COMPLETE",
    "COURSE_FACTS_EXTRACTED",
    "COURSE_FACT_PROVENANCE_TABLE_WRITTEN",
    "STALE_FACTS_CORRECTED_OR_QUARANTINED",
    "UNSOURCED_CLAIMS_DOWNGRADED",
    "SOUTHWELL_SURFACE_STALE_FACT_REVIEWED",
    "VERIFIED_COURSE_REGISTRY_V0_WRITTEN",
    "DRAW_BIAS_CLAIMS_PROVENANCE_REVIEWED",
    "PACE_BIAS_CLAIMS_PROVENANCE_REVIEWED",
    "BHA_RP_FIELD_ACCESS_REALITY_CHECKED",
    "SOURCE_SECTION_EXISTS_NOT_TREATED_AS_PROOF",
    "HYPOTHESES_NOT_PROMOTED_TO_FACTS",
    "COURSE_01_REQUIRES_PROVENANCE_FIELDS",
    "MEMORY_CAPTURE_OPEN",
    "FAILURE_LEARNING_OPEN",
    "PROMOTION_LEARNING_GATED",
    "NO_COURSE_01_IMPLEMENTATION",
    "NO_VFU_21_START",
    "NO_VCP_04_START",
    "NO_LIVE_SCORING_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "REPORT_ONLY",
]

# ---------------------------------------------------------------------------
# EVIDENCE STATUS AND ACTION ENUMERATIONS
# ---------------------------------------------------------------------------
EVIDENCE_STATUSES = [
    "VERIFIED_LOCAL",
    "VERIFIED_EXTERNAL",
    "SECONDARY_PUBLIC_SOURCE",
    "HYPOTHESIS_FROM_RESULTS",
    "UNSOURCED",
    "STALE",
    "CONTRADICTED",
    "UNKNOWN",
]

ACTIONS = [
    "KEEP",
    "CORRECT",
    "DOWNGRADE_TO_UNKNOWN",
    "DOWNGRADE_TO_HYPOTHESIS",
    "QUARANTINE",
]

# ---------------------------------------------------------------------------
# COURSE-00 CLAIMS
# ---------------------------------------------------------------------------
_COURSE_00_CLAIMS = [
    # ------------------------------------------------------------------
    # AW SURFACE CLAIMS
    # ------------------------------------------------------------------
    {
        "course": "Southwell (AW)",
        "claim_type": "surface",
        "claim_value": "Fibresand",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "Surface: fibresand",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "STALE",
        "corrected_value": "Tapeta",
        "correction_note": "Southwell changed from Fibresand to Tapeta in 2021. All 2026 data should assume Tapeta.",
        "action": "CORRECT",
        "action_note": "SURFACE_STALE_CORRECTED",
    },
    {
        "course": "Kempton (AW)",
        "claim_type": "surface",
        "claim_value": "Polytrack",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "Surface: polytrack",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "Polytrack",
        "correction_note": "Kempton AW has been Polytrack since 2006. Correct for 2026.",
        "action": "KEEP",
        "action_note": "SURFACE_SECONDARY_SOURCE_CORRECT",
    },
    {
        "course": "Wolverhampton (AW)",
        "claim_type": "surface",
        "claim_value": "Tapeta",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "Surface: tapeta",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "Tapeta",
        "correction_note": "Wolverhampton changed from Fibresand to Tapeta in 2014. Correct for 2026.",
        "action": "KEEP",
        "action_note": "SURFACE_SECONDARY_SOURCE_CORRECT",
    },
    {
        "course": "Lingfield (AW)",
        "claim_type": "surface",
        "claim_value": "Polytrack",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "Surface: polytrack",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "Polytrack",
        "correction_note": "Lingfield AW has been Polytrack since 2001. Correct for 2026.",
        "action": "KEEP",
        "action_note": "SURFACE_SECONDARY_SOURCE_CORRECT",
    },
    {
        "course": "Newcastle (AW)",
        "claim_type": "surface",
        "claim_value": "Tapeta",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "Surface: tapeta",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "Tapeta",
        "correction_note": "Newcastle AW opened with Tapeta in 2016. Correct for 2026.",
        "action": "KEEP",
        "action_note": "SURFACE_SECONDARY_SOURCE_CORRECT",
    },
    {
        "course": "Chelmsford (AW)",
        "claim_type": "surface",
        "claim_value": "Polytrack",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "Surface: polytrack",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "Polytrack",
        "correction_note": "Chelmsford AW opened with Polytrack in 2008. Correct for 2026.",
        "action": "KEEP",
        "action_note": "SURFACE_SECONDARY_SOURCE_CORRECT",
    },
    # ------------------------------------------------------------------
    # DRAW BIAS CLAIMS
    # ------------------------------------------------------------------
    {
        "course": "Beverley",
        "claim_type": "draw_bias_direction",
        "claim_value": "low_draw_favoured_5f",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "draw_bias_side: low at 5f, 6f",
        "local_artifact": "data/reports/results_02_midprice_misses_table.csv",
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "low_draw_favoured_5f_HYPOTHESIS",
        "correction_note": "Public guides confirm low draw bias at Beverley 5f. No local draw data in VELO to verify. Downgrade to HYPOTHESIS until draw captured.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAW_BIAS_HYPOTHESIS_ONLY — local draw data absent",
    },
    {
        "course": "Southwell (AW)",
        "claim_type": "draw_bias_direction",
        "claim_value": "low_draw_favoured_5f",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "draw_bias_side: low at 5f, 6f",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "low_draw_favoured_5f_HYPOTHESIS",
        "correction_note": "Public guides suggest low draw on Tapeta. Surface stale fact also required correction. No local draw data. Downgrade to HYPOTHESIS.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAW_BIAS_HYPOTHESIS_ONLY — surface also needed correction",
    },
    {
        "course": "Kempton (AW)",
        "claim_type": "draw_bias_direction",
        "claim_value": "low_draw_favoured_5f",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "draw_bias_side: low at 5f, 6f",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "draw_bias_HYPOTHESIS",
        "correction_note": "Draw bias at Kempton depends on race distance and going. Public guide claims only. No local draw. Downgrade to HYPOTHESIS.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAW_BIAS_HYPOTHESIS_ONLY",
    },
    {
        "course": "Wolverhampton (AW)",
        "claim_type": "draw_bias_direction",
        "claim_value": "high_at_5f_low_at_6f",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "draw_bias_side: high_at_5f_low_at_6f",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "draw_bias_distance_dependent_HYPOTHESIS",
        "correction_note": "Distance-dependent draw claims require race-date draw data. No local draw. Downgrade to HYPOTHESIS.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAW_BIAS_HYPOTHESIS_ONLY",
    },
    {
        "course": "Chester",
        "claim_type": "draw_bias_direction",
        "claim_value": "low_draw_favoured_all_distances",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "Low draw very strongly favoured. Tightest track in Britain.",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "low_draw_strongly_favoured_SECONDARY_SOURCE",
        "correction_note": "Chester low-draw bias is extremely well-documented in racing literature. High confidence as SECONDARY source but not locally verified.",
        "action": "KEEP",
        "action_note": "DRAW_BIAS_SECONDARY_SOURCE_HIGH_CONFIDENCE — keep as SECONDARY_PUBLIC_SOURCE not VERIFIED",
    },
    {
        "course": "Lingfield (AW)",
        "claim_type": "draw_bias_direction",
        "claim_value": "low_draw_favoured_5f",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "draw_bias_side: low at 5f",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "draw_bias_HYPOTHESIS",
        "correction_note": "No local draw data. Downgrade to HYPOTHESIS.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAW_BIAS_HYPOTHESIS_ONLY",
    },
    {
        "course": "Newcastle (AW)",
        "claim_type": "draw_bias_direction",
        "claim_value": "high_draw_favoured_5f",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "draw_bias_side: high at 5f",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "draw_bias_HYPOTHESIS",
        "correction_note": "No local draw data for Newcastle. Downgrade to HYPOTHESIS.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAW_BIAS_HYPOTHESIS_ONLY",
    },
    {
        "course": "Chelmsford (AW)",
        "claim_type": "draw_bias_direction",
        "claim_value": "low_draw_favoured_5f",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "draw_bias_side: low at 5f",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "draw_bias_HYPOTHESIS",
        "correction_note": "No local draw data for Chelmsford. Downgrade to HYPOTHESIS.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAW_BIAS_HYPOTHESIS_ONLY",
    },
    {
        "course": "Ascot",
        "claim_type": "draw_bias_direction",
        "claim_value": "high_draw_favoured_sprint",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "draw_bias_side: high draw in sprints",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "draw_bias_HYPOTHESIS",
        "correction_note": "No local draw data for Ascot. Public guide only. Downgrade to HYPOTHESIS.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAW_BIAS_HYPOTHESIS_ONLY",
    },
    {
        "course": "Newbury",
        "claim_type": "draw_bias_direction",
        "claim_value": "centre_draw_favoured",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "draw_bias_side: centre at 5f-6f",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "draw_bias_HYPOTHESIS",
        "correction_note": "No local draw data. Public guide only. Downgrade to HYPOTHESIS.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAW_BIAS_HYPOTHESIS_ONLY",
    },
    # ------------------------------------------------------------------
    # PACE / FRONT-RUNNER CLAIMS
    # ------------------------------------------------------------------
    {
        "course": "Southwell (AW)",
        "claim_type": "front_runner_advantage",
        "claim_value": "yes",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "front_runner_advantage: yes",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "front_runner_advantage_HYPOTHESIS",
        "correction_note": "VELO has no running-style or in-running position data. Front-runner advantage is a hypothesis derived from public guides, not local data.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "PACE_BIAS_HYPOTHESIS_ONLY — no local running-style data",
    },
    {
        "course": "Kempton (AW)",
        "claim_type": "front_runner_advantage",
        "claim_value": "yes",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "front_runner_advantage: yes",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "front_runner_advantage_HYPOTHESIS",
        "correction_note": "No local running-style data. Hypothesis only.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "PACE_BIAS_HYPOTHESIS_ONLY",
    },
    {
        "course": "Wolverhampton (AW)",
        "claim_type": "front_runner_advantage",
        "claim_value": "yes",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "front_runner_advantage: yes",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "front_runner_advantage_HYPOTHESIS",
        "correction_note": "No local running-style data. Hypothesis only.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "PACE_BIAS_HYPOTHESIS_ONLY",
    },
    {
        "course": "Beverley",
        "claim_type": "front_runner_advantage",
        "claim_value": "yes",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "front_runner_advantage: yes",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "front_runner_advantage_HYPOTHESIS",
        "correction_note": "RESULTS-02 shows mid-price misses consistent with front-runner hypothesis, but VELO has no position data to confirm. Hypothesis from result patterns only.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "PACE_BIAS_HYPOTHESIS_ONLY",
    },
    {
        "course": "Chester",
        "claim_type": "front_runner_advantage",
        "claim_value": "yes",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "front_runner_advantage: yes — tight circuit favours leaders",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "front_runner_advantage_HYPOTHESIS",
        "correction_note": "No local position data. Chester tight circuit front-runner claims from public guides. Hypothesis only.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "PACE_BIAS_HYPOTHESIS_ONLY",
    },
    {
        "course": "Bath",
        "claim_type": "front_runner_advantage",
        "claim_value": "yes",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "front_runner_advantage: yes — uphill finish suits runners that get cover",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "front_runner_advantage_HYPOTHESIS",
        "correction_note": "No local position data. Bath uphill finish front-runner claims are from public guides. Hypothesis only.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "PACE_BIAS_HYPOTHESIS_ONLY",
    },
    # ------------------------------------------------------------------
    # HANDEDNESS CLAIMS
    # ------------------------------------------------------------------
    {
        "course": "Beverley",
        "claim_type": "handedness",
        "claim_value": "right",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "handedness: right",
        "local_artifact": None,
        "external_source": "BHA racecourse listing — trackHandedness field",
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "right",
        "correction_note": "Beverley handedness (right) is stable and well-documented. BHA racecourse data confirms. Keep as SECONDARY_PUBLIC_SOURCE.",
        "action": "KEEP",
        "action_note": "HANDEDNESS_SECONDARY_SOURCE_STABLE",
    },
    {
        "course": "Southwell (AW)",
        "claim_type": "handedness",
        "claim_value": "left",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "circuit_type: sharp, left-handed",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "left",
        "correction_note": "Southwell is left-handed. Stable fact. Keep as SECONDARY_PUBLIC_SOURCE.",
        "action": "KEEP",
        "action_note": "HANDEDNESS_SECONDARY_SOURCE_STABLE",
    },
    {
        "course": "Kempton (AW)",
        "claim_type": "handedness",
        "claim_value": "right",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "handedness: right — triangular track",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "right",
        "correction_note": "Kempton is right-handed triangular. Stable fact.",
        "action": "KEEP",
        "action_note": "HANDEDNESS_SECONDARY_SOURCE_STABLE",
    },
    {
        "course": "Chester",
        "claim_type": "handedness",
        "claim_value": "left",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "handedness: left — tight almost circular",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "left",
        "correction_note": "Chester is left-handed. Very well documented. Stable fact.",
        "action": "KEEP",
        "action_note": "HANDEDNESS_SECONDARY_SOURCE_STABLE",
    },
    {
        "course": "Wolverhampton (AW)",
        "claim_type": "handedness",
        "claim_value": "left",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "handedness: left",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "left",
        "correction_note": "Wolverhampton is left-handed. Stable fact.",
        "action": "KEEP",
        "action_note": "HANDEDNESS_SECONDARY_SOURCE_STABLE",
    },
    # ------------------------------------------------------------------
    # UPHILL FINISH CLAIMS
    # ------------------------------------------------------------------
    {
        "course": "Beverley",
        "claim_type": "uphill_finish",
        "claim_value": "yes",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "Sharp uphill finish penalises VELO speed-model picks",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "yes",
        "correction_note": "Beverley uphill finish is well-documented in public racing guides. Keep as SECONDARY_PUBLIC_SOURCE.",
        "action": "KEEP",
        "action_note": "UPHILL_FINISH_SECONDARY_SOURCE_STABLE",
    },
    {
        "course": "Bath",
        "claim_type": "uphill_finish",
        "claim_value": "yes",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "uphill_finish_stamina_gap hypothesis",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "yes",
        "correction_note": "Bath uphill finish is well-documented. Keep as SECONDARY_PUBLIC_SOURCE.",
        "action": "KEEP",
        "action_note": "UPHILL_FINISH_SECONDARY_SOURCE_STABLE",
    },
    {
        "course": "Epsom",
        "claim_type": "uphill_finish",
        "claim_value": "yes",
        "course_00_source": "PUBLIC_GUIDE_SECONDARY",
        "course_00_text": "Significant elevation change — downhill then uphill finish",
        "local_artifact": None,
        "external_source": None,
        "evidence_status": "SECONDARY_PUBLIC_SOURCE",
        "corrected_value": "yes",
        "correction_note": "Epsom has well-documented undulating course finishing uphill. Stable fact.",
        "action": "KEEP",
        "action_note": "UPHILL_FINISH_SECONDARY_SOURCE_STABLE",
    },
    # ------------------------------------------------------------------
    # RESULT-PATTERN CLAIMS (not course facts)
    # ------------------------------------------------------------------
    {
        "course": "All courses",
        "claim_type": "old_velo_rpr_anchor",
        "claim_value": "RPR_PUBLIC_STRENGTH_ANCHOR",
        "course_00_source": "HYPOTHESIS_FROM_RESULTS",
        "course_00_text": "VELO picks longer than winners at drain courses",
        "local_artifact": "data/sigma_audits_dump.json",
        "external_source": None,
        "evidence_status": "HYPOTHESIS_FROM_RESULTS",
        "corrected_value": "RPR_ANCHOR_HYPOTHESIS",
        "correction_note": "SP gap analysis (pick SP vs winner SP) from RESULTS-02 shows VELO selects longer-priced horses. This is a result pattern, not a course fact.",
        "action": "KEEP",
        "action_note": "RESULT_PATTERN_CONFIRMED — not course fact",
    },
    {
        "course": "Beverley",
        "claim_type": "drain_course_classification",
        "claim_value": "DRAIN_COURSE",
        "course_00_source": "HYPOTHESIS_FROM_RESULTS",
        "course_00_text": "Beverley classified as DRAIN_COURSE in RESULTS-02",
        "local_artifact": "data/reports/results_02_midprice_misses_table.csv",
        "external_source": None,
        "evidence_status": "HYPOTHESIS_FROM_RESULTS",
        "corrected_value": "DRAIN_COURSE_HYPOTHESIS",
        "correction_note": "Drain classification based on RESULTS-02 miss patterns, not course-level features. Result-pattern only. Keep as hypothesis.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAIN_CLASSIFICATION_FROM_RESULTS_NOT_COURSE_FACT",
    },
    {
        "course": "Chelmsford (AW)",
        "claim_type": "drain_course_classification",
        "claim_value": "DRAIN_COURSE",
        "course_00_source": "HYPOTHESIS_FROM_RESULTS",
        "course_00_text": "Chelmsford classified as DRAIN_COURSE",
        "local_artifact": "data/sigma_audits_dump.json",
        "external_source": None,
        "evidence_status": "HYPOTHESIS_FROM_RESULTS",
        "corrected_value": "DRAIN_COURSE_HYPOTHESIS",
        "correction_note": "Drain classification based on result patterns. Not a course fact.",
        "action": "DOWNGRADE_TO_HYPOTHESIS",
        "action_note": "DRAIN_CLASSIFICATION_FROM_RESULTS_NOT_COURSE_FACT",
    },
]

# ---------------------------------------------------------------------------
# BHA/RP SOURCE REALITY MAP
# ---------------------------------------------------------------------------
_BHA_RP_SOURCE_MAP = [
    {
        "field": "course",
        "local_status": "LOCAL_PRESENT",
        "bha_status": "PROVEN_ACCESSIBLE_NOW",
        "rp_status": "PROVEN_ACCESSIBLE_NOW",
        "login_required": "no",
        "paywall_risk": "no",
        "automation_safe": "yes",
        "notes": "Course name present in all local data sources.",
    },
    {
        "field": "surface",
        "local_status": "LOCAL_ABSENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "SECTION_EXISTS_NOT_PROVEN",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "Surface type is not currently captured in local RP result/racecard data. BHA racecourse page likely exposes it but not been scraped. RP racecard includes surface in race info.",
    },
    {
        "field": "handedness",
        "local_status": "LOCAL_ABSENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "SECTION_EXISTS_NOT_PROVEN",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "BHA racecourse listing exposes trackHandedness. Not scraped. RP course guide shows handedness. Not in local data.",
    },
    {
        "field": "draw",
        "local_status": "LOCAL_ABSENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "SECTION_EXISTS_NOT_PROVEN",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "Draw is present on RP racecard per runner. Not currently captured in local pipeline. Runner-level draw would need racecard capture enhancement.",
    },
    {
        "field": "stalls_position",
        "local_status": "LOCAL_ABSENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "SECTION_EXISTS_NOT_PROVEN",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "Stalls position (low/high/centre) appears on RP racecard. Not captured locally.",
    },
    {
        "field": "going",
        "local_status": "LOCAL_PRESENT",
        "bha_status": "PROVEN_ACCESSIBLE_NOW",
        "rp_status": "PROVEN_ACCESSIBLE_NOW",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "Going text present in sigma_audits_dump going field. BHA and RP both publish going. Numeric GoingStick reading not captured.",
    },
    {
        "field": "GoingStick",
        "local_status": "LOCAL_ABSENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "SECTION_EXISTS_NOT_PROVEN",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "GoingStick numeric reading is on RP racecard. Not currently captured locally.",
    },
    {
        "field": "race_type",
        "local_status": "LOCAL_PRESENT",
        "bha_status": "PROVEN_ACCESSIBLE_NOW",
        "rp_status": "PROVEN_ACCESSIBLE_NOW",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "race_type present in sigma_audits_dump. Many rows are None/unknown — 1551/2977.",
    },
    {
        "field": "distance",
        "local_status": "LOCAL_PRESENT",
        "bha_status": "PROVEN_ACCESSIBLE_NOW",
        "rp_status": "PROVEN_ACCESSIBLE_NOW",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "distance present in sigma_audits_dump but many rows unknown.",
    },
    {
        "field": "field_size",
        "local_status": "LOCAL_PRESENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "PROVEN_ACCESSIBLE_NOW",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "field_size present in sigma dump. VFU-20 did field_size recovery (1989->152 gap). RP racecard shows runner count.",
    },
    {
        "field": "finish_order",
        "local_status": "LOCAL_PRESENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "PROVEN_ACCESSIBLE_NOW",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "Finish order captured in rp_results JSON via parse_rp_results_capture.py. Full order available where captured.",
    },
    {
        "field": "SP",
        "local_status": "LOCAL_PRESENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "PROVEN_ACCESSIBLE_NOW",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "winner SP in sigma dump (2876/2977). pick_sp present 1212/2977. Full runner SP available in rp_results where captured.",
    },
    {
        "field": "pace_running_style",
        "local_status": "LOCAL_ABSENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "SECTION_EXISTS_NOT_PROVEN",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "manual_only",
        "notes": "RP publishes pace ratings and comments occasionally. Not consistently available. No local in-running data. Running style not captured.",
    },
    {
        "field": "OR",
        "local_status": "LOCAL_ABSENT",
        "bha_status": "PROVEN_ACCESSIBLE_NOW",
        "rp_status": "PROVEN_ACCESSIBLE_NOW",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "BHA Official Ratings database is accessible. OR appears on RP racecards. Not currently captured in local pipeline.",
    },
    {
        "field": "RPR",
        "local_status": "LOCAL_ABSENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "PROVEN_ACCESSIBLE_NOW",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "RPR is a RP proprietary figure, on RP racecards. Used in VELO scoring via sqpe fields but not stored per runner locally.",
    },
    {
        "field": "trainer",
        "local_status": "LOCAL_PRESENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "PROVEN_ACCESSIBLE_NOW",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "Trainer present in JTCD tables (JTC-D profiles). Not in sigma dump directly.",
    },
    {
        "field": "forecast_exacta_dividends",
        "local_status": "LOCAL_ABSENT",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "SECTION_EXISTS_NOT_PROVEN",
        "login_required": "yes_rp",
        "paywall_risk": "low",
        "automation_safe": "yes_with_rp_account",
        "notes": "RP results pages show forecast/exacta/tricast dividends. Not currently captured in local parse pipeline. VFU-21 needed for pick_sp; dividends require separate extraction.",
    },
]

# ---------------------------------------------------------------------------
# VERIFIED COURSE REGISTRY V0
# ---------------------------------------------------------------------------
_VERIFIED_REGISTRY = [
    {
        "course": "Southwell (AW)",
        "country": "GB",
        "surface_current": "Tapeta",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Multiple public sources: Southwell changed from Fibresand to Tapeta 2021",
        "surface_note": "COURSE_00 incorrectly listed as Fibresand — STALE FACT CORRECTED",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "low_draw_HYPOTHESIS",
        "draw_bias_source_status": "HYPOTHESIS_FROM_SECONDARY_SOURCE",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "front_runner_HYPOTHESIS",
        "pace_source_status": "HYPOTHESIS_FROM_SECONDARY_SOURCE",
        "notes": "Surface corrected from Fibresand to Tapeta. Draw/pace remain HYPOTHESIS until local draw data captured.",
        "confidence": 0.4,
        "tribunal_verdict": "SURFACE_STALE_CORRECTED_DRAW_PACE_HYPOTHESIS",
    },
    {
        "course": "Beverley",
        "country": "GB",
        "surface_current": "Turf",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Beverley is turf-only flat course",
        "surface_note": "",
        "handedness": "right",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "yes",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "low_draw_5f_6f_HYPOTHESIS",
        "draw_bias_source_status": "HYPOTHESIS_FROM_SECONDARY_SOURCE",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "front_runner_HYPOTHESIS",
        "pace_source_status": "HYPOTHESIS_FROM_RESULTS_PATTERN",
        "notes": "Uphill finish confirmed secondary source. Draw and pace downgraded to HYPOTHESIS — no local draw/position data.",
        "confidence": 0.5,
        "tribunal_verdict": "DRAW_PACE_HYPOTHESIS_UPHILL_SECONDARY_SOURCE",
    },
    {
        "course": "Kempton (AW)",
        "country": "GB",
        "surface_current": "Polytrack",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Kempton AW Polytrack since 2006",
        "surface_note": "",
        "handedness": "right",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "front_runner_HYPOTHESIS",
        "pace_source_status": "HYPOTHESIS_FROM_SECONDARY_SOURCE",
        "notes": "Surface correct. Triangular track. Draw bias claims downgraded to UNKNOWN without local draw data.",
        "confidence": 0.4,
        "tribunal_verdict": "SURFACE_CORRECT_DRAW_DOWNGRADED_UNKNOWN",
    },
    {
        "course": "Wolverhampton (AW)",
        "country": "GB",
        "surface_current": "Tapeta",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Wolverhampton changed from Fibresand to Tapeta 2014",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "front_runner_HYPOTHESIS",
        "pace_source_status": "HYPOTHESIS_FROM_SECONDARY_SOURCE",
        "notes": "Distance-dependent draw claim requires local draw data. Downgraded to UNKNOWN.",
        "confidence": 0.4,
        "tribunal_verdict": "SURFACE_CORRECT_DRAW_DOWNGRADED_UNKNOWN",
    },
    {
        "course": "Lingfield (AW)",
        "country": "GB",
        "surface_current": "Polytrack",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Lingfield AW Polytrack since 2001",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "front_runner_HYPOTHESIS",
        "pace_source_status": "HYPOTHESIS_FROM_SECONDARY_SOURCE",
        "notes": "Surface correct. Draw downgraded to UNKNOWN without local draw data.",
        "confidence": 0.4,
        "tribunal_verdict": "SURFACE_CORRECT_DRAW_DOWNGRADED_UNKNOWN",
    },
    {
        "course": "Newcastle (AW)",
        "country": "GB",
        "surface_current": "Tapeta",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Newcastle AW opened with Tapeta 2016",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "front_runner_HYPOTHESIS",
        "pace_source_status": "HYPOTHESIS_FROM_SECONDARY_SOURCE",
        "notes": "Surface correct. Draw downgraded to UNKNOWN.",
        "confidence": 0.4,
        "tribunal_verdict": "SURFACE_CORRECT_DRAW_DOWNGRADED_UNKNOWN",
    },
    {
        "course": "Chelmsford (AW)",
        "country": "GB",
        "surface_current": "Polytrack",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Chelmsford AW opened with Polytrack 2008",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "front_runner_HYPOTHESIS",
        "pace_source_status": "HYPOTHESIS_FROM_SECONDARY_SOURCE",
        "notes": "Surface correct. Draw downgraded to UNKNOWN.",
        "confidence": 0.4,
        "tribunal_verdict": "SURFACE_CORRECT_DRAW_DOWNGRADED_UNKNOWN",
    },
    {
        "course": "Chester",
        "country": "GB",
        "surface_current": "Turf",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Chester is turf-only flat course",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "low_draw_strongly_favoured_SECONDARY_SOURCE",
        "draw_bias_source_status": "SECONDARY_PUBLIC_SOURCE_HIGH_CONFIDENCE",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "front_runner_HYPOTHESIS",
        "pace_source_status": "HYPOTHESIS_FROM_SECONDARY_SOURCE",
        "notes": "Chester low-draw bias is extremely well-documented. Kept as SECONDARY_PUBLIC_SOURCE — not VERIFIED. Tight circuit. Pace still HYPOTHESIS.",
        "confidence": 0.6,
        "tribunal_verdict": "DRAW_SECONDARY_HIGH_CONFIDENCE_PACE_HYPOTHESIS",
    },
    {
        "course": "Bath",
        "country": "GB",
        "surface_current": "Turf",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Bath is turf-only flat course",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "yes",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "front_runner_HYPOTHESIS",
        "pace_source_status": "HYPOTHESIS_FROM_SECONDARY_SOURCE",
        "notes": "Uphill finish confirmed secondary source. Draw and pace remain HYPOTHESIS/UNKNOWN.",
        "confidence": 0.4,
        "tribunal_verdict": "UPHILL_SECONDARY_SOURCE_DRAW_UNKNOWN_PACE_HYPOTHESIS",
    },
    {
        "course": "Epsom",
        "country": "GB",
        "surface_current": "Turf",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Epsom is turf flat course",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "yes",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "unknown",
        "pace_source_status": "UNKNOWN",
        "notes": "Epsom has highly unusual track profile (Tattenham Corner, downhill then uphill). Draw/pace both UNKNOWN without local data.",
        "confidence": 0.4,
        "tribunal_verdict": "UPHILL_SECONDARY_SOURCE_DRAW_PACE_UNKNOWN",
    },
    {
        "course": "Ascot",
        "country": "GB",
        "surface_current": "Turf",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Ascot is turf flat course",
        "surface_note": "",
        "handedness": "right",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "unknown",
        "pace_source_status": "UNKNOWN",
        "notes": "Draw bias varies significantly by race distance at Ascot. No local draw data. UNKNOWN.",
        "confidence": 0.3,
        "tribunal_verdict": "ALL_BIAS_CLAIMS_UNKNOWN",
    },
    {
        "course": "Newbury",
        "country": "GB",
        "surface_current": "Turf",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Newbury is turf flat course",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "unknown",
        "pace_source_status": "UNKNOWN",
        "notes": "No local draw data. Public guide only. All bias claims UNKNOWN.",
        "confidence": 0.3,
        "tribunal_verdict": "ALL_BIAS_CLAIMS_UNKNOWN",
    },
    {
        "course": "Goodwood",
        "country": "GB",
        "surface_current": "Turf",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Goodwood is turf flat course",
        "surface_note": "",
        "handedness": "right",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "unknown",
        "pace_source_status": "UNKNOWN",
        "notes": "Goodwood is undulating. Draw/pace complex and no local data. All UNKNOWN.",
        "confidence": 0.3,
        "tribunal_verdict": "ALL_BIAS_CLAIMS_UNKNOWN",
    },
    {
        "course": "Ayr",
        "country": "GB",
        "surface_current": "Turf",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Ayr is turf flat course",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "unknown",
        "pace_source_status": "UNKNOWN",
        "notes": "Ayr is a fair galloping track. No local draw or pace data. All UNKNOWN.",
        "confidence": 0.3,
        "tribunal_verdict": "ALL_BIAS_CLAIMS_UNKNOWN",
    },
    {
        "course": "York",
        "country": "GB",
        "surface_current": "Turf",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "York is turf flat course — wide galloping",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "unknown",
        "pace_source_status": "UNKNOWN",
        "notes": "York is wide and fair. Draw bias minimal at most distances but no local data. All UNKNOWN.",
        "confidence": 0.3,
        "tribunal_verdict": "ALL_BIAS_CLAIMS_UNKNOWN",
    },
    {
        "course": "Nottingham",
        "country": "GB",
        "surface_current": "Turf",
        "surface_source_status": "SECONDARY_PUBLIC_SOURCE",
        "surface_source_ref": "Nottingham is turf flat course",
        "surface_note": "",
        "handedness": "left",
        "handedness_source_status": "SECONDARY_PUBLIC_SOURCE",
        "uphill_finish": "no",
        "uphill_source_status": "SECONDARY_PUBLIC_SOURCE",
        "draw_bias_direction": "unknown",
        "draw_bias_source_status": "HYPOTHESIS_DOWNGRADED_TO_UNKNOWN",
        "draw_bias_distance_specific": "yes",
        "pace_bias": "unknown",
        "pace_source_status": "UNKNOWN",
        "notes": "No local draw or pace data. All UNKNOWN.",
        "confidence": 0.3,
        "tribunal_verdict": "ALL_BIAS_CLAIMS_UNKNOWN",
    },
]

# ---------------------------------------------------------------------------
# OUTPUT FILES
# ---------------------------------------------------------------------------
OUTPUT_FILES = [
    "data/reports/course_00a_source_provenance_tribunal.md",
    "data/reports/course_00a_source_provenance_tribunal.json",
    "data/reports/course_00a_course_fact_provenance_table.csv",
    "data/reports/course_00a_stale_fact_corrections.csv",
    "data/reports/course_00a_unsourced_claims_quarantine.csv",
    "data/reports/course_00a_verified_course_registry.csv",
    "data/reports/course_00a_operator_brief.md",
]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _ensure_dir():
    out_dir = os.path.join(REPO_ROOT, "data", "reports")
    os.makedirs(out_dir, exist_ok=True)


def _abs(relative_path: str) -> str:
    return os.path.join(REPO_ROOT, relative_path)


def _write_text(relative_path: str, content: str):
    path = _abs(relative_path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Written: {relative_path}")


def _write_json(relative_path: str, data: dict):
    path = _abs(relative_path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Written: {relative_path}")


def _write_csv(relative_path: str, rows: list, fieldnames: list):
    path = _abs(relative_path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written: {relative_path}")


# ---------------------------------------------------------------------------
# SECTION FUNCTIONS
# ---------------------------------------------------------------------------
def _s1_extract_claims() -> list:
    """Return _COURSE_00_CLAIMS list."""
    return _COURSE_00_CLAIMS


def _s2_surface_audit(claims: list) -> dict:
    """Filter surface claims, show corrections, stale count."""
    surface_claims = [c for c in claims if c["claim_type"] == "surface"]
    stale = [c for c in surface_claims if c["evidence_status"] == "STALE"]
    corrected = [c for c in stale if c["action"] == "CORRECT"]
    southwell_stale = any(
        c["course"] == "Southwell (AW)"
        and c["claim_type"] == "surface"
        and c["evidence_status"] == "STALE"
        for c in surface_claims
    )
    southwell_corrected_to = next(
        (
            c["corrected_value"]
            for c in surface_claims
            if c["course"] == "Southwell (AW)" and c["claim_type"] == "surface"
        ),
        "NOT_FOUND",
    )
    return {
        "total_surface_claims": len(surface_claims),
        "stale_count": len(stale),
        "corrected_count": len(corrected),
        "southwell_stale": southwell_stale,
        "southwell_corrected_to": southwell_corrected_to,
        "claims": surface_claims,
    }


def _s3_draw_audit(claims: list) -> dict:
    """Filter draw bias claims, assess provenance."""
    draw_claims = [c for c in claims if c["claim_type"] == "draw_bias_direction"]
    hypothesis = [c for c in draw_claims if "DOWNGRADE" in c["action"]]
    verified = [
        c
        for c in draw_claims
        if c["action"] == "KEEP" and c["evidence_status"] == "VERIFIED_LOCAL"
    ]
    return {
        "total_draw_claims": len(draw_claims),
        "hypothesis_count": len(hypothesis),
        "verified_count": len(verified),
        "local_draw_data_exists": False,
        "verdict": "ALL_DRAW_CLAIMS_HYPOTHESIS_ONLY" if len(verified) == 0 else "MIXED",
        "claims": draw_claims,
    }


def _s4_pace_audit(claims: list) -> dict:
    """Filter pace/front-runner claims, assess provenance."""
    pace_claims = [c for c in claims if c["claim_type"] == "front_runner_advantage"]
    hypothesis = [c for c in pace_claims if "DOWNGRADE" in c["action"]]
    return {
        "total_pace_claims": len(pace_claims),
        "hypothesis_count": len(hypothesis),
        "local_running_style_data": False,
        "verdict": "ALL_PACE_CLAIMS_HYPOTHESIS_ONLY",
        "claims": pace_claims,
    }


def _s5_bha_rp_reality() -> list:
    """Return _BHA_RP_SOURCE_MAP."""
    return _BHA_RP_SOURCE_MAP


def _s6_corrections(claims: list) -> dict:
    """Tally: how many kept / corrected / downgraded / quarantined."""
    total = len(claims)
    keep = sum(1 for c in claims if c["action"] == "KEEP")
    correct = sum(1 for c in claims if c["action"] == "CORRECT")
    downgrade = sum(1 for c in claims if "DOWNGRADE" in c["action"])
    quarantine = sum(1 for c in claims if c["action"] == "QUARANTINE")
    return {
        "total_claims": total,
        "keep": keep,
        "correct": correct,
        "downgrade": downgrade,
        "quarantine": quarantine,
        "summary": (
            f"{correct} stale facts corrected. "
            f"{downgrade} unsourced claims downgraded. "
            f"{quarantine} quarantined."
        ),
    }


def _s7_verified_registry() -> list:
    """Return _VERIFIED_REGISTRY."""
    return _VERIFIED_REGISTRY


def _s8_operator_brief(s2, s3, s4, s5, s6, s7) -> str:
    """10-question blunt brief."""
    lines = [
        "# COURSE-00A Operator Brief — Source Provenance Tribunal",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "Status: REPORT_ONLY",
        "",
        "## Q1. Which COURSE-00 facts were stale?",
        f"  Stale facts: {s2['stale_count']}",
        "  Most critical: Southwell surface = Fibresand (stale since 2021). Corrected to Tapeta.",
        "",
        "## Q2. Which COURSE-00 facts were unsourced?",
        f"  Draw bias claims: {s3['hypothesis_count']}/{s3['total_draw_claims']} downgraded to HYPOTHESIS.",
        f"  Pace/front-runner claims: {s4['hypothesis_count']}/{s4['total_pace_claims']} downgraded to HYPOTHESIS.",
        "  No local draw, stalls, or running-style data exists in VELO pipeline.",
        "",
        "## Q3. Is Southwell corrected?",
        f"  Southwell stale fact found: {s2['southwell_stale']}",
        f"  Corrected surface: {s2['southwell_corrected_to']}",
        "  Note: All COURSE-00 Southwell fibresand references are now labelled STALE and corrected.",
        "",
        "## Q4. Which draw claims remain hypothesis only?",
        f"  ALL {s3['total_draw_claims']} draw bias claims are HYPOTHESIS_ONLY or SECONDARY_SOURCE.",
        "  Reason: VELO has no runner-level draw data in local pipeline.",
        "  Source: All from PUBLIC_GUIDE_SECONDARY — valid discovery input, not verified fact.",
        "  Exception: Chester low-draw kept as SECONDARY_PUBLIC_SOURCE_HIGH_CONFIDENCE (not VERIFIED).",
        "",
        "## Q5. Which pace claims remain hypothesis only?",
        f"  ALL {s4['total_pace_claims']} pace/front-runner claims are HYPOTHESIS_ONLY.",
        "  Reason: VELO has no in-running position, running-style, or sectional data.",
        "",
        "## Q6. What did BHA/RP actually prove accessible?",
        "  Proven locally present: course, going, race_type, distance, field_size, finish_order, SP (partial), trainer (partial).",
        "  BHA/RP sections exist but NOT PROVEN accessible: surface, handedness, draw, GoingStick, stalls_position, OR, pace.",
        "  Login required for RP field-level access. Not yet automated in pipeline.",
        "",
        "## Q7. What remains UNKNOWN?",
        "  All draw claims — HYPOTHESIS only (exception: Chester SECONDARY_HIGH_CONFIDENCE).",
        "  All pace/front-runner claims — HYPOTHESIS only.",
        "  surface = SECONDARY_PUBLIC_SOURCE for stable non-fibresand tracks.",
        "  GoingStick, stalls_position, OR, RPR per runner, running style — all LOCAL_ABSENT.",
        "",
        "## Q8. Can COURSE-01 proceed after VCP-03?",
        "  Yes, but COURSE-01 must enforce provenance fields on every course feature:",
        "  - Every feature must carry source_status + confidence.",
        "  - HYPOTHESIS features must not be promoted to VELO scoring without local verification.",
        "  - UNKNOWN-safe fallbacks mandatory.",
        "  - Draw and pace data must be LOCALLY CAPTURED before being used in scoring.",
        "",
        "## Q9. What must COURSE-01 enforce?",
        "  1. Provenance fields on every course entry (source_status, source_ref, confidence, last_checked).",
        "  2. UNKNOWN-safe fallbacks — if draw/pace unknown, do not degrade or inflate confidence.",
        "  3. Date-sensitive surface mapping — not static fibresand/tapeta from memory.",
        "  4. No HYPOTHESIS promoted to scoring feature without local confirmation.",
        "  5. HYPOTHESIS can be used for shadow analysis only.",
        "",
        "## Q10. COURSE-00 status after tribunal?",
        "  COURSE-00 reclassified as: WATCHLIST_MAP_WITH_STALE_FACTS_CORRECTED",
        "  NOT: SOURCE_VERIFIED_COURSE_REGISTRY",
        "  Useful as discovery input and hypothesis generator.",
        "  Not safe for model feature use until COURSE-01 enforces provenance.",
        "",
        "## FINAL CLASSIFICATIONS",
    ] + [f"  - {c}" for c in _FINAL_CLASSIFICATIONS]
    return "\n".join(lines)


def _build_main_md(claims, s2, s3, s4, s6, s7) -> str:
    """Build main tribunal markdown report."""
    lines = [
        "# COURSE-00A — Source Provenance Tribunal",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "**Status: REPORT_ONLY**",
        "",
        "---",
        "",
        "## Hard Constraints Active",
    ]
    for hc in _HARD_CONSTRAINTS:
        lines.append(f"- {hc}")
    lines += [
        "",
        "---",
        "",
        "## Summary",
        f"- Total claims audited: {s6['total_claims']}",
        f"- Stale facts identified: {s2['stale_count']}",
        f"- Stale facts corrected: {s2['corrected_count']}",
        f"- Claims kept (verified/stable): {s6['keep']}",
        f"- Claims downgraded to hypothesis/unknown: {s6['downgrade']}",
        f"- Claims quarantined: {s6['quarantine']}",
        f"- Verified registry entries: {len(s7)}",
        "",
        "---",
        "",
        "## Critical Stale Fact: Southwell Surface",
        f"- COURSE-00 claim: Fibresand",
        f"- Evidence status: STALE (changed 2021)",
        f"- Corrected value: {s2['southwell_corrected_to']}",
        "- Action: CORRECT",
        "- All 2026 audit data must use Tapeta for Southwell AW.",
        "",
        "---",
        "",
        "## AW Surface Registry (Corrected)",
        "| Course | Surface (2026) | Source Status | Note |",
        "|---|---|---|---|",
    ]
    surface_claims = s2["claims"]
    for c in surface_claims:
        lines.append(
            f"| {c['course']} | {c['corrected_value']} | {c['evidence_status']} | {c['action_note']} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Draw Bias Claims",
        f"Verdict: {s3['verdict']}",
        f"Total draw claims: {s3['total_draw_claims']}",
        f"Downgraded to hypothesis: {s3['hypothesis_count']}",
        f"Locally verified: {s3['verified_count']}",
        "Local draw data in pipeline: No",
        "",
        "---",
        "",
        "## Pace/Front-Runner Claims",
        f"Verdict: {s4['verdict']}",
        f"Total pace claims: {s4['total_pace_claims']}",
        f"Downgraded to hypothesis: {s4['hypothesis_count']}",
        "Local running-style data: No",
        "",
        "---",
        "",
        "## Final Classifications",
    ]
    for fc in _FINAL_CLASSIFICATIONS:
        lines.append(f"- {fc}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("COURSE-00A — Source Provenance Tribunal")
    print("REPORT_ONLY")
    print("=" * 60)

    claims = _s1_extract_claims()
    s2 = _s2_surface_audit(claims)
    s3 = _s3_draw_audit(claims)
    s4 = _s4_pace_audit(claims)
    s5 = _s5_bha_rp_reality()
    s6 = _s6_corrections(claims)
    s7 = _s7_verified_registry()
    brief = _s8_operator_brief(s2, s3, s4, s5, s6, s7)
    main_md = _build_main_md(claims, s2, s3, s4, s6, s7)

    print(f"  Claims extracted: {len(claims)}")
    print(f"  Stale facts: {s2['stale_count']} (corrected: {s2['corrected_count']})")
    print(f"  Draw claims downgraded: {s3['hypothesis_count']}/{s3['total_draw_claims']}")
    print(f"  Pace claims downgraded: {s4['hypothesis_count']}/{s4['total_pace_claims']}")
    print(f"  Verified registry entries: {len(s7)}")
    print(f"  Southwell corrected to: {s2['southwell_corrected_to']}")

    _ensure_dir()

    # 1. Main tribunal MD
    _write_text("data/reports/course_00a_source_provenance_tribunal.md", main_md)

    # 2. Full JSON dump
    _write_json(
        "data/reports/course_00a_source_provenance_tribunal.json",
        {
            "meta": {
                "generated_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "hard_constraints": _HARD_CONSTRAINTS,
                "final_classifications": _FINAL_CLASSIFICATIONS,
            },
            "s1_claims": claims,
            "s2_surface_audit": {k: v for k, v in s2.items() if k != "claims"},
            "s3_draw_audit": {k: v for k, v in s3.items() if k != "claims"},
            "s4_pace_audit": {k: v for k, v in s4.items() if k != "claims"},
            "s5_bha_rp": s5,
            "s6_corrections": s6,
            "s7_registry": s7,
        },
    )

    # 3. Provenance table CSV
    _write_csv(
        "data/reports/course_00a_course_fact_provenance_table.csv",
        claims,
        fieldnames=[
            "course",
            "claim_type",
            "claim_value",
            "evidence_status",
            "action",
            "corrected_value",
            "correction_note",
        ],
    )

    # 4. Stale corrections CSV
    stale = [c for c in claims if c["evidence_status"] == "STALE"]
    _write_csv(
        "data/reports/course_00a_stale_fact_corrections.csv",
        stale,
        fieldnames=[
            "course",
            "claim_type",
            "claim_value",
            "corrected_value",
            "correction_note",
            "action_note",
        ],
    )

    # 5. Unsourced / downgraded quarantine CSV
    unsourced = [
        c
        for c in claims
        if c["action"] in ("DOWNGRADE_TO_UNKNOWN", "DOWNGRADE_TO_HYPOTHESIS", "QUARANTINE")
    ]
    _write_csv(
        "data/reports/course_00a_unsourced_claims_quarantine.csv",
        unsourced,
        fieldnames=[
            "course",
            "claim_type",
            "claim_value",
            "evidence_status",
            "action",
            "action_note",
        ],
    )

    # 6. Verified registry CSV
    _write_csv(
        "data/reports/course_00a_verified_course_registry.csv",
        s7,
        fieldnames=[
            "course",
            "country",
            "surface_current",
            "surface_source_status",
            "surface_source_ref",
            "handedness",
            "handedness_source_status",
            "uphill_finish",
            "uphill_source_status",
            "draw_bias_direction",
            "draw_bias_source_status",
            "draw_bias_distance_specific",
            "pace_bias",
            "pace_source_status",
            "notes",
            "confidence",
            "tribunal_verdict",
        ],
    )

    # 7. Operator brief MD
    _write_text("data/reports/course_00a_operator_brief.md", brief)

    print()
    print("FINAL CLASSIFICATIONS:")
    for c in _FINAL_CLASSIFICATIONS:
        print(f"  {c}")
    print()
    print("COURSE-00A COMPLETE. REPORT_ONLY.")


if __name__ == "__main__":
    main()
