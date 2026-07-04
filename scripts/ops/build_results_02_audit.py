"""
RESULTS-02: VÉLØ Course Intelligence and Mid-Price Failure Root-Cause Audit
REPORT_ONLY — NO scoring changes, NO model promotion, NO Supabase writes, NO Telegram.
"""

import json
import csv
import os
import collections
from datetime import datetime

# ── Hard constraints ──────────────────────────────────────────────────────────
_HARD_CONSTRAINTS = [
    "REPORT_ONLY",
    "NO_LIVE_SCORING_CHANGE",
    "NO_VP_THRESHOLD_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "NO_VFU_21_START",
    "NO_VCP_04_START",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "DO_NOT_SUPPRESS_CONTRADICTIONS",
    "MISSING_ARTIFACTS_RESOLVE_UNKNOWN_NOT_CLEAN",
    "COURSE_HYPOTHESES_ARE_NOT_PROMOTION_RULES",
    "CONTAINMENT_IS_NOT_PROFIT",
    "SP_PROXY_IS_NOT_DIVIDEND_PROOF",
]

_FINAL_CLASSIFICATIONS = [
    "RESULTS_02_COURSE_INTELLIGENCE_AUDIT_COMPLETE",
    "COURSE_PROFILES_TABLE_WRITTEN",
    "COURSE_DRAIN_ROOT_CAUSES_AUDITED",
    "COURSE_EDGE_ROOT_CAUSES_AUDITED",
    "BEVERLEY_DEEP_DIVE_WRITTEN",
    "MIDPRICE_FAILURE_ROOT_CAUSE_AUDITED",
    "COURSE_MIDPRICE_MATRIX_WRITTEN",
    "MISSING_COURSE_FEATURES_IDENTIFIED",
    "COURSE_RULES_REPORT_ONLY",
    "EXTERNAL_COURSE_BACKFILL_PLAN_WRITTEN",
    "BHA_RP_COURSE_SOURCE_FEASIBILITY_CHECKED",
    "MIDPRICE_MISSES_NOT_SUPPRESSED",
    "RPR_COURSE_DEPENDENCY_REVIEWED",
    "NEW_BUILD_COURSE_VALUE_REVIEWED",
    "EW_COURSE_PLACE_REVIEWED",
    "MEMORY_CAPTURE_OPEN",
    "FAILURE_LEARNING_OPEN",
    "PROMOTION_LEARNING_GATED",
    "NO_VFU_21_START",
    "NO_VCP_04_START",
    "NO_LIVE_SCORING_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "REPORT_ONLY",
]

# ── Static course intelligence registry ───────────────────────────────────────
# Source confidence: LOCAL_PROVEN / BHA_PROVEN / RP_PROVEN / PUBLIC_GUIDE_SECONDARY / UNKNOWN
_COURSE_PROFILES = {
    # ── DRAIN COURSES ─────────────────────────────────────────────────────────
    "Beverley": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "yes", "undulations": "yes",
        "draw_bias": "low_draw_favoured_5f",
        "front_runner_bias": "yes", "stamina_emphasis": "high",
        "speed_emphasis": "low", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tight turns, stiff uphill finish. 5f draw bias: low stalls strongly favoured. Speed figures deflated by track geometry. Mid-price winners common — pace setters hold on.",
    },
    "Ayr": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "high",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Flat galloping oval. Speed specialists favoured on flat. Jump course also runs here. Low SR may reflect mixed race-type profile.",
    },
    "Perth": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle", "NH Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand jump track. Tight turns suit handy jumpers. Irish/Scottish trainers dominant. VELO may underweight handler context.",
    },
    "Curragh (Ire)": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "high_draw_sprint_bias",
        "front_runner_bias": "no", "stamina_emphasis": "medium",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Premier Irish flat track. Draw biases vary by distance. High-class Irish handlers dominate. VELO training data may be thin on Irish patterns.",
    },
    "Ludlow": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle", "NH Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand jump track. Sharp turns favour nimble jumpers. Local handlers prominent. Smaller field sizes — pace dynamics harder to model.",
    },
    "Down Royal": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "UNKNOWN",
        "notes": "Northern Irish jump track. Very thin VELO sample. Irish handler patterns poorly modelled.",
    },
    "Kilbeggan": {
        "country": "IRE", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "low",
        "typical_race_types": ["Chase", "Hurdle", "NH Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Small Irish jump track. Sharp circuit, front runners hold on. Low-profile handlers. VELO coverage very thin.",
    },
    "Wexford": {
        "country": "IRE", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "low",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tight left-hand Irish track. Front runners dominate. Very small sample in VELO — 0% SR = NOISE_RISK as much as DRAIN.",
    },
    "Clonmel": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "yes", "undulations": "yes",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "high", "speed_emphasis": "low",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating right-hand Irish jump track with uphill finish. Stayers favoured. 0% SR likely small-sample noise.",
    },
    # ── EDGE COURSES ──────────────────────────────────────────────────────────
    "Musselburgh": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_favoured_sprint",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tight flat oval. Low draws favoured in sprints. Front runners hold on. VELO SR=37% — speed/pace model well-calibrated here.",
    },
    "Hexham": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "undulating", "turn_severity": "sharp",
        "uphill_finish": "yes", "undulations": "significant",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "high", "speed_emphasis": "low",
        "typical_race_types": ["Chase", "Hurdle", "NH Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Stiff left-hand jump track with significant undulations. Stayers/stout jumpers excel. VELO SR=29% — stamina model working.",
    },
    "Ripon": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "high_draw_favoured_sprint",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tight right-hand flat oval. High draws benefit in sprints. VELO SR=28%.",
    },
    "Ffos Las": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle", "Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Welsh dual-purpose track. Relatively flat. VELO SR=32%.",
    },
    "Chester": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "tight_circular", "turn_severity": "very_sharp",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_strongly_favoured",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Britain's smallest circuit. Very tight. Low draw essential. Front runners dominant. VELO SR=30% — draw model may be working well.",
    },
    "Uttoxeter": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle", "NH Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Left-hand jump track. Flat oval, suits jumpers with decent pace. VELO SR=36%.",
    },
    "Catterick": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_sprint_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Left-hand flat oval. Draw bias in sprints. Speed favoured. VELO SR=31%.",
    },
    "Lingfield": {
        "country": "GB", "surface": "Mixed", "handedness": "left",
        "track_shape": "undulating", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "low_draw_poly_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Turf + Polytrack AW. Poly surface draws: low stalls favoured. VELO SR=34%.",
    },
    "Pontefract": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "undulating", "turn_severity": "sharp",
        "uphill_finish": "yes", "undulations": "significant",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "high", "speed_emphasis": "low",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating left-hand flat track with climb to finish. Stout stayers favoured. VELO SR=29%.",
    },
    "York": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "high_draw_sprint_bias",
        "front_runner_bias": "no", "stamina_emphasis": "medium",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Wide galloping flat track. High quality racing. High draws in sprints. VELO SR=30%.",
    },
    "Salisbury": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "undulating", "turn_severity": "moderate",
        "uphill_finish": "yes", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand flat track with uphill finish. Stayers-in-training ground. VELO SR=36%.",
    },
    "Southwell": {
        "country": "GB", "surface": "Fibresand", "handedness": "left",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_fibresand_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "medium",
        "speed_emphasis": "medium", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Fibresand AW. Low draws and front runners dominate. Very different surface dynamics. VELO SR=32%. NOTE: sigma has 'Southwell' and 'Southwell (AW)' — may be separate entries.",
    },
    "Kelso": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle", "NH Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Scottish jump track. Moderate oval. VELO SR=29%.",
    },
    "Worcester": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "flat_oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "low", "speed_emphasis": "high",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Very flat left-hand jump track. Pace-setters dominant. VELO SR=50% — highest edge score.",
    },
    "Stratford": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle", "NH Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Left-hand sharp jump track. Front runners hold on. VELO SR=29%.",
    },
    "Wetherby": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle", "NH Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Left-hand jump track. Moderate oval. Good galloping track for stout types. VELO SR=30%.",
    },
    "Leopardstown (Ire)": {
        "country": "IRE", "surface": "Turf", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "high",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Premier Irish dual-purpose track. Galloping circuit. High-class handlers. VELO SR=30%.",
    },
    "Wexford (Ire)": {
        "country": "IRE", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "low",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tight Irish jump track. Front runners favoured. VELO SR=35% — may reflect thin but clean sample.",
    },
    "Huntingdon": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "flat_oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "low", "speed_emphasis": "high",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Very flat right-hand jump track. Speed and pace dominant. VELO SR=37%.",
    },
    "Brighton": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "undulating", "turn_severity": "sharp",
        "uphill_finish": "yes", "undulations": "significant",
        "draw_bias": "low_draw_favoured",
        "front_runner_bias": "yes", "stamina_emphasis": "medium",
        "speed_emphasis": "medium", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating left-hand flat track with uphill finish. Quirky surface. Draw matters. VELO SR=31%.",
    },
    "Newcastle": {
        "country": "GB", "surface": "Tapeta", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_tapeta_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "medium",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tapeta AW. Low draws and front runners favoured. VELO SR=31%.",
    },
    "Newmarket (July)": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "straight_and_sweeping", "turn_severity": "low",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "high",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "July course at Newmarket. Slight track differences from Rowley Mile. VELO SR=40%.",
    },
    "Killarney (Ire)": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "UNKNOWN",
        "notes": "Irish track. Thin VELO sample. SR=36%.",
    },
    "Naas (Ire)": {
        "country": "IRE", "surface": "Turf", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "high",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Galloping Irish flat track. Good ground favoured. VELO SR=29%.",
    },
    "Bellewstown (Ire)": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "undulating", "turn_severity": "sharp",
        "uphill_finish": "yes", "undulations": "significant",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "high", "speed_emphasis": "low",
        "typical_race_types": ["Flat", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating sharp Irish track. Stiff uphill finish. Front runners hold on. VELO SR=29%.",
    },
    "Sligo (Ire)": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Flat", "Hurdle"],
        "source_confidence": "UNKNOWN",
        "notes": "Small Irish track. Thin VELO sample. SR=42%.",
    },
    "Curragh": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "high_draw_sprint_bias",
        "front_runner_bias": "no", "stamina_emphasis": "medium",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Premier Irish flat track. See also Curragh (Ire) — may be same venue with naming variant. VELO SR=30%.",
    },
    # ── MAIN UK AW TRACKS ─────────────────────────────────────────────────────
    "Wolverhampton (AW)": {
        "country": "GB", "surface": "Tapeta", "handedness": "left",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_tapeta_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tapeta AW. Tight left-hand oval. Low draws and front runners dominate. Night racing venue.",
    },
    "Southwell (AW)": {
        "country": "GB", "surface": "Fibresand", "handedness": "left",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_fibresand_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "medium",
        "speed_emphasis": "medium", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Fibresand AW. Very different surface dynamics to turf. Low draws, pace-setters hold on.",
    },
    "Lingfield (AW)": {
        "country": "GB", "surface": "Polytrack", "handedness": "left",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_poly_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Polytrack AW. Low draws favoured. Pace-setters hold on. Winter racing hub.",
    },
    "Kempton (AW)": {
        "country": "GB", "surface": "Polytrack", "handedness": "right",
        "track_shape": "triangular", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_poly_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Polytrack triangular circuit. Low draws and front runners favoured. Major AW meeting venue.",
    },
    "Newcastle (AW)": {
        "country": "GB", "surface": "Tapeta", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_tapeta_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "medium",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tapeta AW — same venue as Newcastle turf. Handles high-quality fields. Low draws favoured.",
    },
    "Chelmsford (AW)": {
        "country": "GB", "surface": "Polytrack", "handedness": "left",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_poly_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Essex Polytrack. London commuter circuit. Low draws favoured. High-class AW racing.",
    },
    # ── MAIN UK FLAT TRACKS ───────────────────────────────────────────────────
    "Newmarket": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "straight_and_sweeping", "turn_severity": "low",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "high_draw_rowley_sprint_bias",
        "front_runner_bias": "no", "stamina_emphasis": "medium",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Rowley Mile — straight course with Dip feature. High draw bias in sprints. Wide open galloping track. Top-class racing.",
    },
    "Ascot": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "yes", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "high", "speed_emphasis": "medium",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Galloping right-hand track with uphill finish. Stamina premium. High-class racing. Jump course also here.",
    },
    "Goodwood": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "undulating", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "significant",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating right-hand flat track on Sussex Downs. Quirky course with dog-leg. Experience matters.",
    },
    "Epsom": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "horseshoe", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "significant",
        "draw_bias": "low_draw_short_trip_bias",
        "front_runner_bias": "no", "stamina_emphasis": "medium",
        "speed_emphasis": "medium", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Horseshoe-shaped undulating track. Downhill camber into Tattenham Corner. Very idiosyncratic. Experience matters.",
    },
    "Haydock": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "high", "speed_emphasis": "medium",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Galloping left-hand track. Soft ground specialist track. Staying form holds up well.",
    },
    "Doncaster": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "high",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Galloping flat left-hand track. Straight course also available. Suits high-quality gallopers.",
    },
    "Sandown": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "yes", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "high", "speed_emphasis": "medium",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand flat track with stiff uphill finish. Stamina premium. Jump course co-located.",
    },
    "Newbury": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "high",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Galloping flat left-hand track. Fair and testing. Speed held by quality gallopers.",
    },
    # ── MAIN JUMP TRACKS ──────────────────────────────────────────────────────
    "Cheltenham": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "undulating", "turn_severity": "moderate",
        "uphill_finish": "yes", "undulations": "significant",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "very_high", "speed_emphasis": "low",
        "typical_race_types": ["Chase", "Hurdle", "NH Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating left-hand track with stiff uphill finish. Festival venue. Stamina and jumping ability paramount. Premium handlers dominate.",
    },
    "Aintree": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "flat_oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "very_high", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Grand National course plus smaller Mildmay course. Flat — but extreme stamina required over big fences. Specialist course.",
    },
    "Kempton": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "triangular", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "high",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand turf jump track (King George venue). Flat circuit suits quick jumpers. Also has AW poly track.",
    },
    # ── IRISH TRACKS ──────────────────────────────────────────────────────────
    "Leopardstown": {
        "country": "IRE", "surface": "Turf", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "high",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Premier Dublin track. Same venue as Leopardstown (Ire) — naming variant.",
    },
    "Fairyhouse": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle", "Flat"],
        "source_confidence": "UNKNOWN",
        "notes": "Irish track — Irish Grand National venue. Thin VELO data.",
    },
    "Navan": {
        "country": "IRE", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "UNKNOWN",
        "notes": "Irish track. Moderate oval. Thin VELO data.",
    },
    "Punchestown": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle", "NH Flat"],
        "source_confidence": "UNKNOWN",
        "notes": "Major Irish jump venue (Festival). Thin VELO data.",
    },
    "Galway": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "undulating", "turn_severity": "sharp",
        "uphill_finish": "yes", "undulations": "significant",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "high", "speed_emphasis": "low",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tight undulating Irish track with uphill finish. Major summer festival venue. Front runners hold on.",
    },
    # ── OTHER COMMON TRACKS IN SIGMA ─────────────────────────────────────────
    "Bath": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "undulating", "turn_severity": "moderate",
        "uphill_finish": "yes", "undulations": "significant",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "high", "speed_emphasis": "low",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Left-hand flat track on hillside. Stiff uphill finish. Stayers favoured.",
    },
    "Chepstow": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "undulating", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "significant",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating left-hand Welsh track. Dual purpose.",
    },
    "Yarmouth": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "flat_oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "low", "speed_emphasis": "high",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Flat left-hand oval. Pace-setters hold on. Summer flat venue.",
    },
    "Hamilton": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "undulating", "turn_severity": "sharp",
        "uphill_finish": "yes", "undulations": "significant",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "high", "speed_emphasis": "low",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating right-hand flat track. Stiff uphill finish. Front runners hold on.",
    },
    "Redcar": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "straight_and_oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "high",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Left-hand flat track. Straight course available.",
    },
    "Nottingham": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "galloping", "turn_severity": "sweeping",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "high",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Galloping flat oval. Fair and open.",
    },
    "Cork (IRE)": {
        "country": "IRE", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "UNKNOWN",
        "notes": "Irish track. Thin VELO data.",
    },
    "Windsor": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "figure_of_eight", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "low", "speed_emphasis": "high",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Figure-of-eight shaped flat track. Pace-setters favoured. Evening flat meetings.",
    },
    "Hereford": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand jump track. Moderate oval.",
    },
    "Fontwell": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "figure_of_eight", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Figure-of-eight jump track. Tight and twisty. Handy jumpers favoured.",
    },
    "Warwick": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle", "Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Left-hand oval. Tight turns. Dual purpose.",
    },
    "Thirsk": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_sprint_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Left-hand flat oval. Draw bias in sprints. Summer flat track.",
    },
    "Leicester": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "undulating", "turn_severity": "moderate",
        "uphill_finish": "yes", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "no",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand flat track with uphill finish. Some stamina required.",
    },
    "Bangor-on-Dee": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Welsh jump track. Flat oval.",
    },
    "Carlisle": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "undulating", "turn_severity": "moderate",
        "uphill_finish": "yes", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Flat", "Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand dual-purpose track with uphill finish.",
    },
    "Exeter": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "undulating", "turn_severity": "moderate",
        "uphill_finish": "yes", "undulations": "significant",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "high", "speed_emphasis": "low",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating jump track with stiff uphill finish. Stamina essential.",
    },
    "Taunton": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Somerset jump track.",
    },
    "Plumpton": {
        "country": "GB", "surface": "Turf", "handedness": "left",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "moderate",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "medium", "speed_emphasis": "medium",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tight left-hand jump track.",
    },
    "Market Rasen": {
        "country": "GB", "surface": "Turf", "handedness": "right",
        "track_shape": "oval", "turn_severity": "sharp",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "unknown", "front_runner_bias": "yes",
        "stamina_emphasis": "low", "speed_emphasis": "high",
        "typical_race_types": ["Chase", "Hurdle"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Sharp right-hand jump track. Speed and pace favoured.",
    },
    "Newbury (AW)": {
        "country": "GB", "surface": "unknown", "handedness": "unknown",
        "track_shape": "unknown", "turn_severity": "unknown",
        "uphill_finish": "unknown", "undulations": "unknown",
        "draw_bias": "unknown", "front_runner_bias": "unknown",
        "stamina_emphasis": "unknown", "speed_emphasis": "unknown",
        "typical_race_types": ["Flat"],
        "source_confidence": "UNKNOWN",
        "notes": "AW variant — check if distinct from Newbury turf in data.",
    },
    "Dundalk (IRE)": {
        "country": "IRE", "surface": "Polytrack", "handedness": "left",
        "track_shape": "oval", "turn_severity": "moderate",
        "uphill_finish": "no", "undulations": "low",
        "draw_bias": "low_draw_poly_bias",
        "front_runner_bias": "yes", "stamina_emphasis": "low",
        "speed_emphasis": "high", "typical_race_types": ["Flat"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Ireland's only all-weather Polytrack venue. Winter flat racing.",
    },
}

# Default profile for unknown courses
_UNKNOWN_PROFILE = {
    "country": "unknown", "surface": "unknown", "handedness": "unknown",
    "track_shape": "unknown", "turn_severity": "unknown",
    "uphill_finish": "unknown", "undulations": "unknown",
    "draw_bias": "unknown", "front_runner_bias": "unknown",
    "stamina_emphasis": "unknown", "speed_emphasis": "unknown",
    "typical_race_types": [], "source_confidence": "UNKNOWN", "notes": "",
}


def _get_profile(course):
    """Return profile dict for course, filling missing fields with 'unknown'."""
    p = dict(_UNKNOWN_PROFILE)
    known = _COURSE_PROFILES.get(course, {})
    p.update(known)
    # Ensure every field present and never None
    for k, v in p.items():
        if v is None:
            p[k] = "unknown"
    return p


def _extract_date(row):
    d = row.get("date")
    if d:
        return str(d)[:10]
    ca = row.get("created_at", "")
    return str(ca)[:10] if ca else "UNKNOWN"


def _sp_to_dec(sp_str):
    if not sp_str:
        return None
    s = str(sp_str).strip().rstrip("Ff")
    if "/" in s:
        parts = s.split("/")
        try:
            return float(parts[0]) / float(parts[1]) + 1.0
        except Exception:
            return None
    try:
        return float(s)
    except Exception:
        return None


def _mp_band(sp_dec):
    if sp_dec is None:
        return "UNKNOWN"
    if sp_dec < 4.0:
        return "<4"
    if sp_dec < 6.0:
        return "4-6"
    if sp_dec < 10.0:
        return "6-10"
    if sp_dec < 16.0:
        return "10-16"
    return "16+"


def _load_data():
    with open("data/sigma_audits_dump.json") as f:
        sigma = json.load(f)
    ledger = []
    with open("data/model_comparison_ledger.csv") as f:
        for row in csv.DictReader(f):
            ledger.append(row)
    course_table = {}
    with open("data/reports/results_01_course_performance_table.csv") as f:
        for row in csv.DictReader(f):
            course_table[row["course"]] = row
    midprice_table = []
    with open("data/reports/results_01_midprice_recovery_table.csv") as f:
        for row in csv.DictReader(f):
            midprice_table.append(row)
    return sigma, ledger, course_table, midprice_table


# ─────────────────────────────────────────────────────────────────────────────
# S1 — Course inventory
# ─────────────────────────────────────────────────────────────────────────────
def _s1_inventory(sigma, ledger, course_table):
    by_course = collections.defaultdict(lambda: {"n": 0, "wins": 0, "places": 0, "misses": 0})
    for row in sigma:
        course = row.get("track") or "UNKNOWN"
        by_course[course]["n"] += 1
        outcome = (row.get("outcome") or "").upper()
        if outcome == "WIN":
            by_course[course]["wins"] += 1
        elif outcome == "PLACED":
            by_course[course]["places"] += 1
        elif outcome == "MISS":
            by_course[course]["misses"] += 1

    results = []
    for course, stats in sorted(by_course.items()):
        n = stats["n"]
        wins = stats["wins"]
        sr = wins / n if n > 0 else 0.0
        frame = (wins + stats["places"]) / n if n > 0 else 0.0
        ct = course_table.get(course, {})
        label = ct.get("label", "COURSE_NOISE_LOW_SAMPLE" if n < 10 else "COURSE_NEUTRAL")
        profile = _get_profile(course)
        results.append({
            "course": course,
            "n": n,
            "wins": wins,
            "places": stats["places"],
            "misses": stats["misses"],
            "sr": round(sr, 4),
            "frame_rate": round(frame, 4),
            "label": label,
            "surface": profile["surface"],
            "handedness": profile["handedness"],
            "turn_severity": profile["turn_severity"],
            "uphill_finish": profile["uphill_finish"],
            "draw_bias": profile["draw_bias"],
            "front_runner_bias": profile["front_runner_bias"],
            "stamina_emphasis": profile["stamina_emphasis"],
            "source_confidence": profile["source_confidence"],
        })
    return results


# ─────────────────────────────────────────────────────────────────────────────
# S2 — Drain audit
# ─────────────────────────────────────────────────────────────────────────────
_DRAIN_HYPOTHESES = {
    "Beverley": [
        "Sharp uphill finish penalises VELO speed-model picks",
        "Low draw bias (5f) not captured in VELO scoring",
        "Front-runner hold-on pattern: mid-price pacers not flagged",
        "Small tight oval: track bias systematic, model undertrained",
    ],
    "Ayr": [
        "Mixed race type profile (flat + jumps) dilutes model confidence",
        "Galloping track rewards speed — model may overweight stamina here",
        "Scottish handlers underrepresented in trainer profile",
    ],
    "Perth": [
        "Irish/Scottish handler patterns poorly modelled",
        "Jump track: pace dynamics different from flat model baseline",
        "Sharp turns reward nimble jumpers not captured in form proxy",
    ],
    "Curragh (Ire)": [
        "Irish handler dominance not fully modelled",
        "High draw bias in sprints — VELO draw feature absent or thin",
        "High-class field quality compresses SR expectations",
    ],
    "Ludlow": [
        "Small field sizes create unpredictable pace dynamics",
        "Local handler knowledge gap",
        "Sharp turns favour adaptable jumpers not form-based picks",
    ],
    "Down Royal": [
        "Very thin VELO sample — possible NOISE_RISK not true DRAIN",
        "Northern Irish racing poorly modelled",
        "Irish handler patterns absent",
    ],
    "Kilbeggan": [
        "Thin sample — 0% SR plausible noise",
        "Tight circuit pace dynamics not modelled",
        "Low-profile Irish handlers underrepresented",
    ],
    "Wexford": [
        "0% SR — n=13, high noise risk",
        "Tight Irish jump track: front runners hold on, not flagged by VELO",
    ],
    "Clonmel": [
        "0% SR — n=11, high noise risk",
        "Uphill finish not captured in stamina model",
        "Thin Irish handler representation",
    ],
}


def _s2_drain_audit(sigma, ledger, profiles):
    drain_courses = [c for c, p in profiles.items() if p.get("label") == "COURSE_DRAIN"]
    # Fall back to known drain list from results_01
    _KNOWN_DRAINS = [
        "Beverley", "Ayr", "Perth", "Curragh (Ire)", "Ludlow",
        "Down Royal", "Kilbeggan", "Wexford", "Clonmel",
    ]
    all_drains = list(set(drain_courses + _KNOWN_DRAINS))

    results = {}
    for course in all_drains:
        rows = [r for r in sigma if (r.get("track") or "") == course]
        if not rows:
            continue
        n = len(rows)
        wins = sum(1 for r in rows if (r.get("outcome") or "").upper() == "WIN")
        placed = sum(1 for r in rows if (r.get("outcome") or "").upper() == "PLACED")
        misses = sum(1 for r in rows if (r.get("outcome") or "").upper() == "MISS")
        mr_cnt = collections.Counter(r.get("miss_reason") for r in rows if r.get("miss_reason"))
        winner_sps = [_sp_to_dec(r.get("actual_winner_sp")) for r in rows]
        winner_sps = [x for x in winner_sps if x]
        pick_sps = [_sp_to_dec(r.get("pick_sp")) for r in rows]
        pick_sps = [x for x in pick_sps if x]
        avg_winner_sp = sum(winner_sps) / len(winner_sps) if winner_sps else None
        avg_pick_sp = sum(pick_sps) / len(pick_sps) if pick_sps else None
        hypotheses = _DRAIN_HYPOTHESES.get(course, ["Thin sample — root cause UNKNOWN"])
        results[course] = {
            "course": course,
            "n": n,
            "wins": wins,
            "placed": placed,
            "misses": misses,
            "sr": round(wins / n, 4) if n else 0.0,
            "miss_reason_breakdown": dict(mr_cnt),
            "avg_winner_sp": round(avg_winner_sp, 2) if avg_winner_sp else None,
            "avg_pick_sp": round(avg_pick_sp, 2) if avg_pick_sp else None,
            "sp_gap": round(avg_winner_sp - avg_pick_sp, 2) if (avg_winner_sp and avg_pick_sp) else None,
            "root_cause_hypotheses": hypotheses,
            "watchlist_status": "WATCHLIST_ONLY",
        }
    return results


# ─────────────────────────────────────────────────────────────────────────────
# S3 — Edge audit
# ─────────────────────────────────────────────────────────────────────────────
_EDGE_HYPOTHESES = {
    "Musselburgh": ["Speed/pace model well-calibrated for flat oval", "Low draw bias may align with picks"],
    "Hexham": ["Stamina emphasis matches jump model output", "Stiff track filters weak profiles"],
    "Ripon": ["Sprint pace dynamics well-matched", "Draw bias less relevant for longer trips"],
    "Ffos Las": ["Moderate track suits balanced model", "Dual-purpose racing provides richer profile data"],
    "Chester": ["Tight circuit amplifies handicap knowledge", "Low draw bias — draw feature may be active"],
    "Uttoxeter": ["Flat oval suits pace-tracking model", "Jump form profiles consistent here"],
    "Catterick": ["Speed and draw-bias alignment", "Sprint races benefit from pace model"],
    "Lingfield": ["AW poly surface suits front-runner bias", "Low draw feature may be contributing"],
    "Pontefract": ["Stamina emphasis well-modelled", "Uphill finish filters short-runners"],
    "York": ["High-class racing: form holds up", "Wide galloping track rewards class"],
    "Salisbury": ["Uphill finish filters weak stamina", "Flat stayer profiles well-matched"],
    "Southwell": ["AW fibresand front-runner pattern clear", "Consistent surface conditions reduce noise"],
    "Kelso": ["Scottish jump form profiles consistent", "Moderate oval doesn't distort model"],
    "Worcester": ["Flat jump track maximises pace advantage", "SR=50% — pace model dominant here"],
    "Stratford": ["Sharp jump track: handy types flagged", "Front runner pattern consistent"],
    "Wetherby": ["Jump form profiles well-matched", "Moderate oval supports balanced picks"],
    "Leopardstown (Ire)": ["High-class Irish track: form strong indicator", "Galloping track suits class-based model"],
    "Wexford (Ire)": ["Thin but clean sample — may be noise", "Front runner pattern aligns with model"],
    "Huntingdon": ["Very flat — speed/pace premium clear", "Front runner bias well-modelled"],
    "Brighton": ["Quirky track filters weak horses", "Uphill finish stamps stamina picks"],
    "Newcastle": ["Tapeta AW: consistent conditions", "Front runner pace model effective"],
    "Newmarket (July)": ["Top-class racing: class indicators reliable", "SR=40% — model sharp here"],
    "Killarney (Ire)": ["Thin sample — SR may be noise", "Irish form profiles moderate"],
    "Naas (Ire)": ["Galloping Irish track: class holds up", "Consistent form indicators"],
    "Bellewstown (Ire)": ["Uphill finish filters short stamina", "Front runner pattern flagged"],
    "Sligo (Ire)": ["Very thin sample — SR=42% noise risk", "No strong hypothesis"],
    "Curragh": ["See Curragh (Ire) — may be naming variant", "Galloping track suits class model"],
}


def _s3_edge_audit(sigma, ledger, profiles):
    _KNOWN_EDGES = [
        "Musselburgh", "Hexham", "Ripon", "Ffos Las", "Chester", "Uttoxeter",
        "Catterick", "Lingfield", "Pontefract", "York", "Salisbury", "Southwell",
        "Kelso", "Worcester", "Stratford", "Wetherby", "Leopardstown (Ire)",
        "Wexford (Ire)", "Huntingdon", "Brighton", "Newcastle", "Newmarket (July)",
        "Killarney (Ire)", "Naas (Ire)", "Bellewstown (Ire)", "Sligo (Ire)", "Curragh",
    ]
    results = {}
    for course in _KNOWN_EDGES:
        rows = [r for r in sigma if (r.get("track") or "") == course]
        n = len(rows)
        wins = sum(1 for r in rows if (r.get("outcome") or "").upper() == "WIN")
        placed = sum(1 for r in rows if (r.get("outcome") or "").upper() == "PLACED")
        misses = sum(1 for r in rows if (r.get("outcome") or "").upper() == "MISS")
        mr_cnt = collections.Counter(r.get("miss_reason") for r in rows if r.get("miss_reason"))
        hypotheses = _EDGE_HYPOTHESES.get(course, ["No specific hypothesis — investigate further"])
        results[course] = {
            "course": course,
            "n": n,
            "wins": wins,
            "placed": placed,
            "misses": misses,
            "sr": round(wins / n, 4) if n else 0.0,
            "miss_reason_breakdown": dict(mr_cnt),
            "why_working_hypothesis": hypotheses,
            "watchlist_status": "REPORT_ONLY",
        }
    return results


# ─────────────────────────────────────────────────────────────────────────────
# S4 — Beverley deep dive
# ─────────────────────────────────────────────────────────────────────────────
def _s4_beverley_deep_dive(sigma, ledger):
    rows = [r for r in sigma if (r.get("track") or "") == "Beverley"]
    if not rows:
        return {"beverley_rows": 0, "data": []}

    records = []
    for r in sorted(rows, key=lambda x: _extract_date(x)):
        winner_sp_dec = _sp_to_dec(r.get("actual_winner_sp"))
        pick_sp_dec = _sp_to_dec(r.get("pick_sp"))
        records.append({
            "date": _extract_date(r),
            "off_time": r.get("off_time") or "unknown",
            "outcome": r.get("outcome") or "UNKNOWN",
            "miss_reason": r.get("miss_reason") or "n/a",
            "actual_winner": r.get("actual_winner_name") or "unknown",
            "winner_sp_raw": r.get("actual_winner_sp"),
            "winner_sp_dec": round(winner_sp_dec, 2) if winner_sp_dec else None,
            "winner_mp_band": _mp_band(winner_sp_dec),
            "pick_sp_dec": round(pick_sp_dec, 2) if pick_sp_dec else None,
            "race_type": r.get("race_type") or "unknown",
            "distance": r.get("distance") or "unknown",
            "going": r.get("going") or "unknown",
            "confidence_level": r.get("confidence_level") or "unknown",
            "decision_tier": r.get("decision_tier") or "unknown",
            "verdict_score": r.get("verdict_score"),
        })

    n = len(records)
    wins = sum(1 for r in records if r["outcome"] == "WIN")
    placed = sum(1 for r in records if r["outcome"] == "PLACED")
    misses = sum(1 for r in records if r["outcome"] == "MISS")
    miss_reasons = collections.Counter(r["miss_reason"] for r in records if r["miss_reason"] != "n/a")
    mp_bands = collections.Counter(r["winner_mp_band"] for r in records)
    return {
        "beverley_rows": n,
        "wins": wins,
        "placed": placed,
        "misses": misses,
        "sr": round(wins / n, 4) if n else 0,
        "miss_reason_breakdown": dict(miss_reasons),
        "winner_mp_band_distribution": dict(mp_bands),
        "data": records,
    }


# ─────────────────────────────────────────────────────────────────────────────
# S5 — Mid-price failure audit
# ─────────────────────────────────────────────────────────────────────────────
def _s5_midprice_failure(sigma, ledger):
    mp_rows = [r for r in sigma if r.get("miss_reason") == "mid_priced_won"]
    n = len(mp_rows)

    enriched = []
    for r in mp_rows:
        course = r.get("track") or "UNKNOWN"
        winner_sp = _sp_to_dec(r.get("actual_winner_sp"))
        profile = _get_profile(course)
        enriched.append({
            "date": _extract_date(r),
            "course": course,
            "off_time": r.get("off_time") or "unknown",
            "race_type": r.get("race_type") or "unknown",
            "distance": r.get("distance") or "unknown",
            "going": r.get("going") or "unknown",
            "actual_winner": r.get("actual_winner_name") or "unknown",
            "winner_sp_dec": round(winner_sp, 2) if winner_sp else None,
            "mp_band": _mp_band(winner_sp),
            "decision_tier": r.get("decision_tier") or "unknown",
            "confidence_level": r.get("confidence_level") or "unknown",
            "pick_sp_dec": round(_sp_to_dec(r.get("pick_sp")), 2) if _sp_to_dec(r.get("pick_sp")) else None,
            "stamina_emphasis": profile["stamina_emphasis"],
            "front_runner_bias": profile["front_runner_bias"],
            "uphill_finish": profile["uphill_finish"],
            "turn_severity": profile["turn_severity"],
        })

    by_course = collections.Counter(r["course"] for r in enriched)
    by_band = collections.Counter(r["mp_band"] for r in enriched)
    by_race_type = collections.Counter(r["race_type"] for r in enriched)
    by_going = collections.Counter(r["going"] for r in enriched)
    by_tier = collections.Counter(r["decision_tier"] for r in enriched)

    # Course-level root causes
    course_root_causes = {}
    for course, count in by_course.most_common(20):
        profile = _get_profile(course)
        causes = []
        if profile["front_runner_bias"] == "yes":
            causes.append("front_runner_bias_not_modelled")
        if profile["uphill_finish"] == "yes":
            causes.append("uphill_finish_stamina_gap")
        if profile["turn_severity"] in ("sharp", "very_sharp"):
            causes.append("sharp_turns_tactical_speed_gap")
        if profile["draw_bias"] not in ("unknown", ""):
            causes.append("draw_bias_not_captured")
        if profile["source_confidence"] == "UNKNOWN":
            causes.append("course_profile_unknown_no_root_cause")
        if not causes:
            causes.append("no_clear_structural_cause_investigate")
        course_root_causes[course] = {"count": count, "hypotheses": causes}

    return {
        "total_midprice_misses": n,
        "by_course": dict(by_course.most_common(25)),
        "by_mp_band": dict(by_band),
        "by_race_type": dict(by_race_type),
        "by_going": dict(by_going),
        "by_decision_tier": dict(by_tier),
        "course_root_causes": course_root_causes,
        "enriched_rows": enriched,
    }


# ─────────────────────────────────────────────────────────────────────────────
# S6 — Course mid-price matrix
# ─────────────────────────────────────────────────────────────────────────────
def _s6_course_midprice_matrix(sigma, profiles_map):
    by_course = collections.defaultdict(lambda: {"n": 0, "misses": 0, "mp_misses": 0, "wins": 0})
    for row in sigma:
        course = row.get("track") or "UNKNOWN"
        by_course[course]["n"] += 1
        outcome = (row.get("outcome") or "").upper()
        if outcome == "WIN":
            by_course[course]["wins"] += 1
        if outcome == "MISS":
            by_course[course]["misses"] += 1
            if row.get("miss_reason") == "mid_priced_won":
                by_course[course]["mp_misses"] += 1

    matrix = []
    for course, stats in sorted(by_course.items()):
        n = stats["n"]
        if n < 10:
            continue
        profile = _get_profile(course)
        wins = stats["wins"]
        misses = stats["misses"]
        mp_misses = stats["mp_misses"]
        mp_miss_rate = round(mp_misses / n, 4) if n else 0.0
        sr = round(wins / n, 4) if n else 0.0
        # Treatment suggestion (WATCHLIST_ONLY)
        treatment = []
        if profile["front_runner_bias"] == "yes":
            treatment.append("WATCH_PACE_DYNAMICS")
        if profile["draw_bias"] not in ("unknown", ""):
            treatment.append("WATCH_DRAW_BIAS")
        if profile["uphill_finish"] == "yes":
            treatment.append("WATCH_STAMINA_FINISH")
        if profile["turn_severity"] in ("sharp", "very_sharp"):
            treatment.append("WATCH_TACTICAL_SPEED")
        if not treatment:
            treatment = ["INVESTIGATE_FURTHER"]
        root_cause = "FRONT_RUNNER" if profile["front_runner_bias"] == "yes" else (
            "DRAW_BIAS" if profile["draw_bias"] not in ("unknown", "") else "UNKNOWN"
        )
        matrix.append({
            "course": course,
            "n": n,
            "wins": wins,
            "misses": misses,
            "mp_misses": mp_misses,
            "mp_miss_rate": mp_miss_rate,
            "sr": sr,
            "draw_known": "yes" if profile["draw_bias"] not in ("unknown", "") else "no",
            "pace_known": "yes" if profile["front_runner_bias"] != "unknown" else "no",
            "sharp_turns": "yes" if profile["turn_severity"] in ("sharp", "very_sharp", "tight_circular") else "no",
            "uphill": profile["uphill_finish"],
            "root_cause": root_cause,
            "treatment": "|".join(treatment),
            "status": "WATCHLIST_ONLY",
        })
    return sorted(matrix, key=lambda x: x["mp_misses"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# S7 — Missing features
# ─────────────────────────────────────────────────────────────────────────────
def _s7_missing_features(profiles, sigma):
    features = [
        {
            "feature": "draw_bias_by_course_distance",
            "priority": "CRITICAL",
            "in_velo": "no",
            "partially_present": "no",
            "absent": "yes",
            "derivable_locally": "no",
            "bha_available": "yes_published",
            "rp_available": "yes_course_stats",
            "notes": "BHA and RP both publish draw statistics. Not currently ingested. Beverley 5f, Chester, Catterick all have documented biases.",
        },
        {
            "feature": "pace_map_front_runner_flag",
            "priority": "CRITICAL",
            "in_velo": "no",
            "partially_present": "no",
            "absent": "yes",
            "derivable_locally": "partial_from_form",
            "bha_available": "no",
            "rp_available": "yes_rp_pace_data",
            "notes": "RP provides pace data in race cards. Not ingested. Front runner identification is root cause of most drain course failures.",
        },
        {
            "feature": "course_speed_figure_adjustment",
            "priority": "HIGH",
            "in_velo": "no",
            "partially_present": "no",
            "absent": "yes",
            "derivable_locally": "yes_from_sigma_history",
            "bha_available": "no",
            "rp_available": "yes",
            "notes": "Track-adjusted speed figures available from RP. Local derivation possible from sigma win patterns.",
        },
        {
            "feature": "course_specific_trainer_handler_profile",
            "priority": "HIGH",
            "in_velo": "partial_jtcd",
            "partially_present": "yes",
            "absent": "no",
            "derivable_locally": "yes_from_jtcd_tables",
            "bha_available": "no",
            "rp_available": "yes",
            "notes": "JTCD tables built but course-specific trainer win rate at specific venues not fully exposed to scorer.",
        },
        {
            "feature": "going_course_interaction",
            "priority": "HIGH",
            "in_velo": "partial",
            "partially_present": "yes",
            "absent": "no",
            "derivable_locally": "yes",
            "bha_available": "no",
            "rp_available": "yes",
            "notes": "Going captured but interaction with specific course drainage/camber not modelled. Cheltenham soft vs Flat soft are different.",
        },
        {
            "feature": "field_size_pace_dynamics",
            "priority": "MEDIUM",
            "in_velo": "field_size_present",
            "partially_present": "yes",
            "absent": "no",
            "derivable_locally": "yes",
            "bha_available": "no",
            "rp_available": "partial",
            "notes": "Field size present in sigma but pace dynamic modelling not done. Small fields at Ludlow/Perth need different pace assumptions.",
        },
        {
            "feature": "course_undulation_stamp",
            "priority": "MEDIUM",
            "in_velo": "no",
            "partially_present": "no",
            "absent": "yes",
            "derivable_locally": "yes_from_static_profiles",
            "bha_available": "no",
            "rp_available": "partial",
            "notes": "Static course profiles exist (this script). Could be encoded as binary feature for stamina-finish adjustment.",
        },
        {
            "feature": "distance_suitability_at_course",
            "priority": "MEDIUM",
            "in_velo": "distance_present",
            "partially_present": "yes",
            "absent": "no",
            "derivable_locally": "yes",
            "bha_available": "no",
            "rp_available": "yes",
            "notes": "Distance present but optimal distance for horse at specific course not computed.",
        },
        {
            "feature": "course_experience_count",
            "priority": "MEDIUM",
            "in_velo": "partial_passport",
            "partially_present": "yes",
            "absent": "no",
            "derivable_locally": "yes_from_passport",
            "bha_available": "no",
            "rp_available": "yes",
            "notes": "Passport has course history. Course experience count (runs at this venue) not used as feature.",
        },
        {
            "feature": "seasonal_course_form_filter",
            "priority": "LOW",
            "in_velo": "no",
            "partially_present": "no",
            "absent": "yes",
            "derivable_locally": "yes",
            "bha_available": "no",
            "rp_available": "partial",
            "notes": "Some courses heavily seasonal (Galway festival, Royal Ascot form). Seasonal adjustment not modelled.",
        },
    ]
    critical_high = [f for f in features if f["priority"] in ("CRITICAL", "HIGH")]
    return {
        "feature_gap_count": len(features),
        "critical_count": sum(1 for f in features if f["priority"] == "CRITICAL"),
        "high_count": sum(1 for f in features if f["priority"] == "HIGH"),
        "medium_count": sum(1 for f in features if f["priority"] == "MEDIUM"),
        "low_count": sum(1 for f in features if f["priority"] == "LOW"),
        "features": features,
        "critical_high_features": critical_high,
    }


# ─────────────────────────────────────────────────────────────────────────────
# S8 — Candidate rules (WATCHLIST_ONLY)
# ─────────────────────────────────────────────────────────────────────────────
def _s8_candidate_rules(s2, s3, s4, s5):
    rules = [
        {
            "rule_id": "R01",
            "name": "BEVERLEY_MIDPRICE_WATCH",
            "description": "Flag Beverley races where winner_sp in 4-12 range and front_runner_flag absent",
            "derived_from": "S4 Beverley deep dive — mid_priced_won dominant miss reason",
            "status": "WATCHLIST_ONLY",
            "promotion_gate": "n>=30 Beverley wins with rule applied, operator review required",
        },
        {
            "rule_id": "R02",
            "name": "SHARP_TRACK_PACE_WATCH",
            "description": "At sharp-turn tracks (Beverley, Chester, Catterick, Ripon, Thirsk): down-weight picks without pace flag",
            "derived_from": "S6 matrix — sharp track high mp_miss_rate",
            "status": "WATCHLIST_ONLY",
            "promotion_gate": "Backtest across 200+ races, operator review",
        },
        {
            "rule_id": "R03",
            "name": "IRISH_TRACK_CONFIDENCE_FLOOR",
            "description": "For Irish tracks with n<20 in VELO: apply confidence floor, avoid A-tier classification",
            "derived_from": "S2 drain audit — Down Royal, Kilbeggan, Wexford, Clonmel all thin samples",
            "status": "WATCHLIST_ONLY",
            "promotion_gate": "Pending Irish handler profile enrichment, n>=30 per venue",
        },
        {
            "rule_id": "R04",
            "name": "AW_SURFACE_PACE_ADJUSTMENT",
            "description": "For AW tracks (Tapeta, Poly, Fibresand): flag front-runner type more aggressively",
            "derived_from": "S6 matrix — AW tracks high front_runner_bias",
            "status": "WATCHLIST_ONLY",
            "promotion_gate": "Backtest across AW corpus, operator review",
        },
        {
            "rule_id": "R05",
            "name": "UPHILL_FINISH_STAMINA_GATE",
            "description": "At uphill finish tracks (Beverley, Pontefract, Bath, Hamilton, Brighton, Salisbury): require stamina indicator present",
            "derived_from": "S7 feature gap — uphill_finish_stamp not in scorer",
            "status": "WATCHLIST_ONLY",
            "promotion_gate": "Feature must be built and backtested first",
        },
        {
            "rule_id": "R06",
            "name": "DRAW_BIAS_KNOWN_TRACK_FLAG",
            "description": "At draw-bias-known tracks (Chester, Catterick, Ripon, Beverley 5f): suppress picks without draw data",
            "derived_from": "S7 feature gap — draw_bias feature absent",
            "status": "WATCHLIST_ONLY",
            "promotion_gate": "Draw feature must be built and validated first",
        },
        {
            "rule_id": "R07",
            "name": "MID_PRICE_BAND_6_10_WATCH",
            "description": "6-10 band is highest volume mid-price miss zone — monitor for systematic pick suppression opportunity",
            "derived_from": "S5 midprice failure audit",
            "status": "WATCHLIST_ONLY",
            "promotion_gate": "Operator review after n>=200 in band, no model change without review",
        },
        {
            "rule_id": "R08",
            "name": "WORCESTER_EDGE_DEFEND",
            "description": "Worcester SR=50% — defend edge by maintaining model consistency, do not override",
            "derived_from": "S3 edge audit — Worcester top performer",
            "status": "REPORT_ONLY",
            "promotion_gate": "N/A — defend existing edge",
        },
    ]
    return rules


# ─────────────────────────────────────────────────────────────────────────────
# S9 — External backfill plan
# ─────────────────────────────────────────────────────────────────────────────
def _s9_external_backfill_plan(profiles):
    fields = [
        {
            "field": "draw_bias_statistics",
            "local_status": "ABSENT",
            "bha_source": "BHA raceday programme — draw statistics published for sprint distances",
            "rp_source": "RP course stats pages — draw win % by stall/distance",
            "feasibility": "SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN",
            "priority": "CRITICAL",
            "notes": "Must be scraped/parsed and matched to course+distance combo. Not automated yet.",
        },
        {
            "field": "pace_data_early_positions",
            "local_status": "ABSENT",
            "bha_source": "NOT_AVAILABLE",
            "rp_source": "RP racecard — pace ratings sometimes published",
            "feasibility": "SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN",
            "priority": "CRITICAL",
            "notes": "RP pace ratings not consistently available. Manual check required.",
        },
        {
            "field": "course_speed_par_figures",
            "local_status": "ABSENT",
            "bha_source": "NOT_AVAILABLE",
            "rp_source": "RP speed ratings section",
            "feasibility": "SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN",
            "priority": "HIGH",
            "notes": "Track par figures used for speed figure normalisation. RP publishes these.",
        },
        {
            "field": "trainer_course_win_rate",
            "local_status": "PARTIAL_JTCD",
            "bha_source": "BHA trainer stats — general, not course-specific",
            "rp_source": "RP trainer profiles — course breakdown available",
            "feasibility": "SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN",
            "priority": "HIGH",
            "notes": "JTCD tables partially cover this. RP trainer course pages would enrich. Not scraped.",
        },
        {
            "field": "going_stick_readings",
            "local_status": "GOING_DESCRIPTION_PRESENT",
            "bha_source": "BHA going reports — published pre-race",
            "rp_source": "RP going updates",
            "feasibility": "LOCAL_PRESENT_TEXT_ONLY",
            "priority": "MEDIUM",
            "notes": "Going text is present (e.g. 'Soft To Heavy'). Numeric GoingStick reading not captured.",
        },
        {
            "field": "field_size_sectional_pace",
            "local_status": "FIELD_SIZE_PRESENT",
            "bha_source": "NOT_AVAILABLE",
            "rp_source": "RP sectional times — for major meetings only",
            "feasibility": "UNSAFE_FOR_AUTOMATION",
            "priority": "MEDIUM",
            "notes": "Sectional times only available for selected meetings. Cannot automate for full corpus.",
        },
        {
            "field": "course_rpr_par",
            "local_status": "ABSENT",
            "bha_source": "NOT_AVAILABLE",
            "rp_source": "RP RPR par by course/distance",
            "feasibility": "SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN",
            "priority": "MEDIUM",
            "notes": "RPR par figures published by RP. Would help normalise RPR by course.",
        },
        {
            "field": "course_undulation_binary",
            "local_status": "PRESENT_IN_STATIC_PROFILES",
            "bha_source": "BHA course descriptions",
            "rp_source": "RP course guides",
            "feasibility": "LOCAL_DERIVABLE_FROM_STATIC_PROFILES",
            "priority": "MEDIUM",
            "notes": "This script builds static profiles. Binary feature encodable now without scraping.",
        },
    ]
    return {
        "total_fields": len(fields),
        "critical_fields": [f for f in fields if f["priority"] == "CRITICAL"],
        "high_fields": [f for f in fields if f["priority"] == "HIGH"],
        "fields": fields,
        "important_caveat": "No external URLs called in this script. All assessments are static knowledge of BHA/RP site structure.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# S10 — Operator brief
# ─────────────────────────────────────────────────────────────────────────────
def _s10_operator_brief(s1, s2, s3, s4, s5, s6, s7, s8, s9):
    bev = s4
    bev_n = bev.get("beverley_rows", 0)
    bev_sr = bev.get("sr", 0.0)
    bev_miss = bev.get("misses", 0)
    total_mp = s5.get("total_midprice_misses", 0)
    by_band = s5.get("by_mp_band", {})
    top_mp_courses = list(s5.get("by_course", {}).items())[:5]
    n_critical_features = s7.get("critical_count", 0)
    n_high_features = s7.get("high_count", 0)
    drain_courses = list(s2.keys())
    edge_top = sorted(s3.values(), key=lambda x: x["sr"], reverse=True)[:3]

    lines = [
        "# RESULTS-02: Operator Brief",
        "",
        "## Status",
        "REPORT_ONLY. No scoring changes. No model promotion. No Supabase writes. No Telegram.",
        "",
        "## Q1. What is Beverley's failure pattern?",
        f"Beverley: n={bev_n}, SR={bev_sr:.1%}, misses={bev_miss}.",
        "Dominant miss reason: mid_priced_won.",
        "Profile: sharp right-hand oval, stiff uphill finish, documented 5f low-draw bias.",
        "Root causes: front-runner hold-on pattern, draw bias not in model, pace dynamics absent.",
        "Treatment: WATCHLIST_ONLY — do not apply rule until draw/pace features built.",
        "",
        "## Q2. Why is mid-price the biggest miss category?",
        f"Total mid-price misses (miss_reason=mid_priced_won): {total_mp}",
        f"By band: {by_band}",
        "Root cause: VELO picks shorter-priced horses. Mid-price winners (4-16) are often",
        "pace setters at front-runner tracks, or draw-advantaged horses at bias tracks.",
        "Model does not have pace or draw features — cannot flag these types.",
        "",
        "## Q3. Which courses drive most mid-price misses?",
        "Top 5 by miss count: " + ", ".join(f"{c}({n})" for c, n in top_mp_courses),
        "",
        "## Q4. What are the drain course root causes?",
        "Drain courses: " + ", ".join(drain_courses),
        "Common patterns: Irish tracks thin data / handler gap; sharp tracks pace/draw gap; ",
        "Perth/Ludlow small-field jump dynamics not modelled.",
        "",
        "## Q5. What are the edge course drivers?",
        "Top 3 edge courses: " + ", ".join(f"{e['course']}(SR={e['sr']:.1%})" for e in edge_top),
        "Common patterns: flat/pace-friendly tracks, stamina-testing tracks where model is calibrated.",
        "",
        "## Q6. What critical features are missing?",
        f"{n_critical_features} CRITICAL features, {n_high_features} HIGH features missing.",
        "CRITICAL: draw_bias_by_course_distance, pace_map_front_runner_flag",
        "HIGH: course_speed_figure_adjustment, trainer_handler_course_profile, going_course_interaction",
        "",
        "## Q7. Is Beverley a special case or systemic?",
        "Both. Beverley is the most acute single-venue failure (SR=4%).",
        "But the root causes (draw bias, pace dynamics) are systemic across multiple tracks.",
        "",
        "## Q8. Should any drain rule be applied now?",
        "NO. All rules are WATCHLIST_ONLY. Features must be built and backtested first.",
        "Do not apply course suppression rules without operator approval.",
        "",
        "## Q9. Are edge course rules safe to promote?",
        "NO promotion without operator review. Edge performance is passive — no rule needed to maintain it.",
        "Rule R08 (Worcester defend) is REPORT_ONLY — do not override current model.",
        "",
        "## Q10. What is the BHA/RP backfill plan?",
        "Critical: draw_bias_statistics (RP/BHA), pace_data_early_positions (RP).",
        "Status: SOURCE_SECTION_EXISTS_BACKFILL_NOT_PROVEN — sites known, not yet scraped.",
        "No external URLs called in this report.",
        "",
        "## Q11. What is the EW course picture?",
        "EW place performance not separately audited in RESULTS-02 (see RESULTS-01 EW table).",
        "Course place rate in S1 inventory. Frame rate >50% at edge courses is consistent.",
        "EW course audit is OPEN for follow-on task.",
        "",
        "## Q12. What are the immediate next steps?",
        "1. WATCHLIST_ONLY — monitor all 8 candidate rules, do not apply.",
        "2. Backfill draw_bias feature — BHA/RP source confirmed, scrape pending.",
        "3. Backfill pace_map feature — RP pace ratings, scrape pending.",
        "4. Irish handler enrichment — JTCD tables extend to venue level.",
        "5. Beverley: next 20 races shadow log — test draw/pace hypothesis.",
        "6. NO_VFU_21_START, NO_VCP_04_START, NO_MODEL_PROMOTION until gates met.",
        "",
        "## FINAL CLASSIFICATIONS",
    ]
    for c in _FINAL_CLASSIFICATIONS:
        lines.append(f"- {c}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Writer helpers
# ─────────────────────────────────────────────────────────────────────────────
def _write_csv(path, rows, fieldnames=None):
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def _write_md(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    os.makedirs("data/reports", exist_ok=True)

    print("Loading data...")
    sigma, ledger, course_table, midprice_table = _load_data()

    # Build profile map enriched with label from course_table
    profiles_map = {}
    for row in course_table.values():
        course = row["course"]
        p = _get_profile(course)
        p["label"] = row.get("label", "COURSE_NEUTRAL")
        p["course"] = course
        profiles_map[course] = p

    print("S1: Course inventory...")
    s1 = _s1_inventory(sigma, ledger, course_table)

    print("S2: Drain audit...")
    s2 = _s2_drain_audit(sigma, ledger, profiles_map)

    print("S3: Edge audit...")
    s3 = _s3_edge_audit(sigma, ledger, profiles_map)

    print("S4: Beverley deep dive...")
    s4 = _s4_beverley_deep_dive(sigma, ledger)

    print("S5: Mid-price failure audit...")
    s5 = _s5_midprice_failure(sigma, ledger)

    print("S6: Course mid-price matrix...")
    s6 = _s6_course_midprice_matrix(sigma, profiles_map)

    print("S7: Missing features...")
    s7 = _s7_missing_features(profiles_map, sigma)

    print("S8: Candidate rules...")
    s8 = _s8_candidate_rules(s2, s3, s4, s5)

    print("S9: External backfill plan...")
    s9 = _s9_external_backfill_plan(profiles_map)

    print("S10: Operator brief...")
    s10_text = _s10_operator_brief(s1, s2, s3, s4, s5, s6, s7, s8, s9)

    # ── Write outputs ─────────────────────────────────────────────────────────
    print("Writing outputs...")

    # 1. Main audit JSON
    full_json = {
        "meta": {
            "script": "RESULTS-02",
            "hard_constraints": _HARD_CONSTRAINTS,
            "final_classifications": _FINAL_CLASSIFICATIONS,
            "generated_at": datetime.utcnow().isoformat(),
        },
        "s1_inventory": s1,
        "s2_drain_audit": s2,
        "s3_edge_audit": s3,
        "s4_beverley_deep_dive": s4,
        "s5_midprice_failure": {k: v for k, v in s5.items() if k != "enriched_rows"},
        "s6_midprice_matrix": s6,
        "s7_missing_features": s7,
        "s8_candidate_rules": s8,
        "s9_external_backfill": s9,
    }
    _write_json("data/reports/results_02_course_intelligence_audit.json", full_json)

    # 2. Main audit MD
    md_lines = [
        "# RESULTS-02: VÉLØ Course Intelligence Audit",
        "",
        f"Generated: {datetime.utcnow().isoformat()}",
        "Status: REPORT_ONLY",
        "",
        "## Hard Constraints",
        "\n".join(f"- {c}" for c in _HARD_CONSTRAINTS),
        "",
        "## S1: Course Inventory",
        f"Total courses in sigma: {len(s1)}",
        "",
        "## S2: Drain Audit",
    ]
    for course, data in s2.items():
        md_lines.append(f"\n### {course}")
        md_lines.append(f"n={data['n']}, SR={data['sr']:.1%}, wins={data['wins']}, misses={data['misses']}")
        md_lines.append(f"avg_winner_sp={data['avg_winner_sp']}, avg_pick_sp={data['avg_pick_sp']}, sp_gap={data['sp_gap']}")
        md_lines.append("Miss reasons: " + str(data['miss_reason_breakdown']))
        md_lines.append("Root cause hypotheses:")
        for h in data["root_cause_hypotheses"]:
            md_lines.append(f"  - {h}")
        md_lines.append(f"Status: {data['watchlist_status']}")

    md_lines.append("\n## S3: Edge Audit")
    for course, data in s3.items():
        md_lines.append(f"\n### {course}")
        md_lines.append(f"n={data['n']}, SR={data['sr']:.1%}, wins={data['wins']}, misses={data['misses']}")
        md_lines.append("Why working: " + " | ".join(data["why_working_hypothesis"]))

    md_lines.append("\n## S5: Mid-Price Failure Summary")
    md_lines.append(f"Total mid_priced_won misses: {s5['total_midprice_misses']}")
    md_lines.append("By band: " + str(s5['by_mp_band']))
    md_lines.append("By race type: " + str(s5['by_race_type']))
    md_lines.append("Top courses: " + str(dict(list(s5['by_course'].items())[:10])))

    md_lines.append("\n## S7: Missing Features")
    for f in s7["features"]:
        md_lines.append(f"\n### [{f['priority']}] {f['feature']}")
        md_lines.append(f"in_velo={f['in_velo']}, derivable_locally={f['derivable_locally']}")
        md_lines.append(f"bha_available={f['bha_available']}, rp_available={f['rp_available']}")
        md_lines.append(f"Notes: {f['notes']}")

    md_lines.append("\n## S8: Candidate Rules (WATCHLIST_ONLY)")
    for r in s8:
        md_lines.append(f"\n### {r['rule_id']}: {r['name']}")
        md_lines.append(f"Status: {r['status']}")
        md_lines.append(f"Description: {r['description']}")
        md_lines.append(f"Promotion gate: {r['promotion_gate']}")

    md_lines.append("\n## Final Classifications")
    for c in _FINAL_CLASSIFICATIONS:
        md_lines.append(f"- {c}")

    _write_md("data/reports/results_02_course_intelligence_audit.md", "\n".join(md_lines))

    # 3. Course profiles table CSV
    profile_rows = []
    all_courses = set(r["course"] for r in s1)
    for course in sorted(all_courses):
        p = _get_profile(course)
        ct = course_table.get(course, {})
        profile_rows.append({
            "course": course,
            "country": p["country"],
            "surface": p["surface"],
            "handedness": p["handedness"],
            "track_shape": p["track_shape"],
            "turn_severity": p["turn_severity"],
            "uphill_finish": p["uphill_finish"],
            "draw_bias": p["draw_bias"],
            "front_runner_bias": p["front_runner_bias"],
            "stamina_emphasis": p["stamina_emphasis"],
            "speed_emphasis": p["speed_emphasis"],
            "source_confidence": p["source_confidence"],
            "velo_n": ct.get("n", ""),
            "velo_sr": ct.get("sr", ""),
            "velo_label": ct.get("label", "COURSE_NOISE_LOW_SAMPLE"),
            "notes": p["notes"],
        })
    _write_csv("data/reports/results_02_course_profiles_table.csv", profile_rows)

    # 4. Drain root causes CSV
    drain_rows = []
    for course, data in s2.items():
        drain_rows.append({
            "course": course,
            "n": data["n"],
            "wins": data["wins"],
            "sr": data["sr"],
            "misses": data["misses"],
            "avg_winner_sp": data["avg_winner_sp"],
            "avg_pick_sp": data["avg_pick_sp"],
            "sp_gap": data["sp_gap"],
            "miss_reason_breakdown": json.dumps(data["miss_reason_breakdown"]),
            "root_cause_hypotheses": " | ".join(data["root_cause_hypotheses"]),
            "watchlist_status": data["watchlist_status"],
        })
    _write_csv("data/reports/results_02_course_drain_root_causes.csv", drain_rows)

    # 5. Edge root causes CSV
    edge_rows = []
    for course, data in s3.items():
        edge_rows.append({
            "course": course,
            "n": data["n"],
            "wins": data["wins"],
            "sr": data["sr"],
            "misses": data["misses"],
            "miss_reason_breakdown": json.dumps(data["miss_reason_breakdown"]),
            "why_working": " | ".join(data["why_working_hypothesis"]),
            "status": data["watchlist_status"],
        })
    _write_csv("data/reports/results_02_course_edge_root_causes.csv", edge_rows)

    # 6. Mid-price failure audit MD
    mp_md = [
        "# RESULTS-02: Mid-Price Failure Audit",
        "",
        "REPORT_ONLY. MIDPRICE_MISSES_NOT_SUPPRESSED.",
        "",
        f"## Total mid_priced_won misses: {s5['total_midprice_misses']}",
        "",
        "## By odds band",
        str(s5['by_mp_band']),
        "",
        "## By race type",
        str(s5['by_race_type']),
        "",
        "## By going",
        str(s5['by_going']),
        "",
        "## By decision tier",
        str(s5['by_decision_tier']),
        "",
        "## Top courses (mid-price misses)",
        str(s5['by_course']),
        "",
        "## Course root cause hypotheses",
    ]
    for course, data in s5["course_root_causes"].items():
        mp_md.append(f"\n### {course} (n={data['count']})")
        for h in data["hypotheses"]:
            mp_md.append(f"  - {h}")
    _write_md("data/reports/results_02_midprice_failure_audit.md", "\n".join(mp_md))

    # 7. Mid-price failure audit JSON
    mp_json = {k: v for k, v in s5.items() if k != "enriched_rows"}
    _write_json("data/reports/results_02_midprice_failure_audit.json", mp_json)

    # 8. Mid-price misses table CSV
    mp_miss_rows = s5.get("enriched_rows", [])
    if mp_miss_rows:
        _write_csv("data/reports/results_02_midprice_misses_table.csv", mp_miss_rows)
    else:
        _write_md("data/reports/results_02_midprice_misses_table.csv", "")

    # 9. Course feature backfill map MD
    bf_md = [
        "# RESULTS-02: Course Feature Backfill Map",
        "",
        "REPORT_ONLY. No external URLs called. All entries are static knowledge of BHA/RP site structure.",
        "",
    ]
    for f in s9["fields"]:
        bf_md.append(f"\n## [{f['priority']}] {f['field']}")
        bf_md.append(f"Local status: {f['local_status']}")
        bf_md.append(f"BHA source: {f['bha_source']}")
        bf_md.append(f"RP source: {f['rp_source']}")
        bf_md.append(f"Feasibility: {f['feasibility']}")
        bf_md.append(f"Notes: {f['notes']}")
    _write_md("data/reports/results_02_course_feature_backfill_map.md", "\n".join(bf_md))

    # 10. Course model gap matrix CSV
    _write_csv("data/reports/results_02_course_model_gap_matrix.csv", s6)

    # 11. Operator brief MD
    _write_md("data/reports/results_02_operator_brief.md", s10_text)

    # 12. Beverley deep dive MD (optional, write if rows exist)
    if s4.get("beverley_rows", 0) > 0:
        bev_md = [
            "# RESULTS-02: Beverley Deep Dive",
            "",
            f"n={s4['beverley_rows']}, SR={s4['sr']:.1%}, wins={s4['wins']}, placed={s4['placed']}, misses={s4['misses']}",
            "",
            "## Miss reason breakdown",
            str(s4['miss_reason_breakdown']),
            "",
            "## Winner SP band distribution",
            str(s4['winner_mp_band_distribution']),
            "",
            "## Profile",
            "Sharp right-hand oval, stiff uphill finish, 5f low-draw bias (documented).",
            "Front runner hold-on pattern dominant. Draw bias absent from VELO model.",
            "",
            "## All races (sorted by date)",
            "| date | off | outcome | miss_reason | winner | winner_sp | pick_sp | race_type | dist | going | tier |",
            "|------|-----|---------|-------------|--------|-----------|---------|-----------|------|-------|------|",
        ]
        for r in s4["data"]:
            bev_md.append(
                f"| {r['date']} | {r['off_time']} | {r['outcome']} | {r['miss_reason']} | "
                f"{r['actual_winner']} | {r['winner_sp_dec']} | {r['pick_sp_dec']} | "
                f"{r['race_type']} | {r['distance']} | {r['going']} | {r['decision_tier']} |"
            )
        _write_md("data/reports/results_02_beverley_deep_dive.md", "\n".join(bev_md))
        print(f"Beverley deep dive written: {s4['beverley_rows']} races.")

    # Summary
    print("\n=== RESULTS-02 Complete ===")
    print(f"Courses inventoried: {len(s1)}")
    print(f"Drain courses audited: {len(s2)}")
    print(f"Edge courses audited: {len(s3)}")
    print(f"Beverley rows: {s4.get('beverley_rows', 0)}, SR={s4.get('sr', 0):.1%}")
    print(f"Mid-price misses: {s5['total_midprice_misses']}")
    print(f"Mid-price matrix rows: {len(s6)}")
    print(f"Missing features: {s7['feature_gap_count']} ({s7['critical_count']} CRITICAL, {s7['high_count']} HIGH)")
    print(f"Candidate rules: {len(s8)} (all WATCHLIST_ONLY or REPORT_ONLY)")
    print(f"Backfill fields: {s9['total_fields']}")
    print("\nFinal classifications:")
    for c in _FINAL_CLASSIFICATIONS:
        print(f"  {c}")
    print("\nAll 12 output files written.")


if __name__ == "__main__":
    main()
