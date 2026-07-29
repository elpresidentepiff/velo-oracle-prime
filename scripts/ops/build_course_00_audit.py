"""
COURSE-00 — VÉLØ Course Eyes Completion Pack
REPORT_ONLY — No live features, no scoring change, no model promotion.

Hard constraints enforced at runtime via _HARD_CONSTRAINTS list.
All outputs go to data/reports/course_00_*.
"""

import csv
import json
import os
import sys
from collections import Counter, defaultdict
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
    "COURSE_RULES_WATCHLIST_ONLY",
    "DO_NOT_SUPPRESS_CONTRADICTIONS",
    "MISSING_ARTIFACTS_RESOLVE_UNKNOWN_NOT_CLEAN",
]

_FINAL_CLASSIFICATIONS = [
    "COURSE_00_COURSE_EYES_COMPLETION_COMPLETE",
    "COURSE_REGISTRY_WRITTEN",
    "DRAW_BIAS_PRIORITY_TABLE_WRITTEN",
    "PACE_BIAS_PRIORITY_TABLE_WRITTEN",
    "AW_CLUSTER_DEEP_DIVE_WRITTEN",
    "BEVERLEY_WAR_BOOK_WRITTEN",
    "MIDPRICE_6_10_WOUND_TABLE_WRITTEN",
    "FEATURE_READINESS_MATRIX_WRITTEN",
    "EXTERNAL_SOURCE_FIELD_MAP_WRITTEN",
    "COURSE_WATCHLIST_WRITTEN",
    "COURSE_01_DESIGN_SPEC_WRITTEN_NOT_IMPLEMENTED",
    "DRAW_EYES_IDENTIFIED_CRITICAL",
    "PACE_EYES_IDENTIFIED_CRITICAL",
    "BEVERLEY_WATCHLIST_ONLY",
    "AW_CLUSTER_WATCHLIST_ONLY",
    "COURSE_RULES_WATCHLIST_ONLY",
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

containment_is_not_profit = True

# ---------------------------------------------------------------------------
# COURSE EYES REGISTRY
# ---------------------------------------------------------------------------
_COURSE_EYES = {
    "Beverley": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "3f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Sharp uphill finish. Low-draw bias in 5f/6f. Front-runners hold on. Tight oval penalises wide draws.",
    },
    "Southwell (AW)": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "fibresand",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED", "AW_PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Fibresand surface. Strong front-runner bias. Low draw in sprints. Pace angle critical.",
    },
    "Kempton (AW)": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "flat_straight",
        "run_in": "2.5f",
        "sprint_chute": "yes",
        "aw_surface_subtype": "polytrack",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED", "AW_PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Triangular polytrack. Sprint chute exists. Low draw favoured in sprints. Front-runners very competitive.",
    },
    "Wolverhampton (AW)": {
        "draw_bias_known": "yes",
        "draw_bias_side": "high_at_5f_low_at_6f",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "tapeta",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED", "AW_PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tapeta. High draw at 5f, low draw at 6f. Front-runner hold-on common. Bias direction distance-dependent.",
    },
    "Lingfield (AW)": {
        "draw_bias_known": "yes",
        "draw_bias_side": "high",
        "draw_bias_distances": ["5f", "6f", "7f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "polytrack",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED", "AW_PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Polytrack. High draw bias in sprints. Left-hand sharp. Front-runners hold well.",
    },
    "Newcastle (Aw)": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "galloping",
        "run_in": "3f",
        "sprint_chute": "no",
        "aw_surface_subtype": "tapeta",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tapeta. Galloping track despite AW surface. Low draw in sprints. Longer run-in than most AW tracks.",
    },
    "Chelmsford (Aw)": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "polytrack",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Polytrack. Sharp oval. Low draw bias in sprints.",
    },
    "Thirsk": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2.5f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Flat oval. Low draw bias in sprints. Tight turns favour low-drawn front-runners.",
    },
    "Bath": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "no",
        "front_runner_advantage": "no",
        "circuit_type": "undulating",
        "run_in": "3f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["COURSE_SHAPE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating one-turn track. Uphill finish. Stayers/tough travellers favoured. No strong draw bias.",
    },
    "Chester": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f", "7f", "1m"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "1.5f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Tightest track in Britain. Extreme low-draw bias at all distances. Front-runners hold on in almost every race.",
    },
    "Brighton": {
        "draw_bias_known": "yes",
        "draw_bias_side": "high",
        "draw_bias_distances": ["5f", "5.5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "undulating",
        "run_in": "3.5f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating. Runs downhill then up. High draw bias in sprints. Firm going suits.",
    },
    "Catterick": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "1.5f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Sharp left-hand. Very short run-in. Low draw bias in sprints. Front-runners hugely advantaged.",
    },
    "Ripon": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2f",
        "sprint_chute": "yes",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Sprint chute. Low draw bias 5f/6f. Right-hand track. Front-runners hold on.",
    },
    "Pontefract": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2.5f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating. Uphill finish. Low draw favoured in sprints. Left-hand oval.",
    },
    "Newmarket": {
        "draw_bias_known": "yes",
        "draw_bias_side": "high",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "galloping",
        "run_in": "4f",
        "sprint_chute": "yes",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Rowley Mile: high draw (stands side) in large fields. July Course is a separate track. Very long run-in.",
    },
    "Newmarket (July)": {
        "draw_bias_known": "yes",
        "draw_bias_side": "high",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "galloping",
        "run_in": "3.5f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "July Course (separate from Rowley Mile). High draw in sprints. Long straight.",
    },
    "Musselburgh": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Flat sharp oval. Low draw at 5f. Speed/pace model appears well-calibrated here.",
    },
    "Ayr": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "no",
        "circuit_type": "galloping",
        "run_in": "4f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED", "HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Galloping flat track. Long run-in. Closers competitive. Scottish handler patterns may differ.",
    },
    "Doncaster": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "galloping",
        "run_in": "4f",
        "sprint_chute": "yes",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Wide galloping track. Very long run-in. Low draw bias in sprint chute races.",
    },
    "Windsor": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Figure-eight track. Right-hand oval. Front-runners hold on in sprint races.",
    },
    "Haydock": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "no",
        "front_runner_advantage": "no",
        "circuit_type": "galloping",
        "run_in": "4f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Galloping left-hand. Long straight. No strong draw bias known. Stamina tests common.",
    },
    "Sandown": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "no",
        "front_runner_advantage": "no",
        "circuit_type": "galloping",
        "run_in": "4f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand galloping. Eclipse course. Uphill finish. Stayers favoured.",
    },
    "Ascot": {
        "draw_bias_known": "yes",
        "draw_bias_side": "high",
        "draw_bias_distances": ["5f"],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "galloping",
        "run_in": "2.5f",
        "sprint_chute": "yes",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand galloping. Sprint chute. High draw in 5f sprints (stands side in big fields).",
    },
    "York": {
        "draw_bias_known": "yes",
        "draw_bias_side": "high",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "galloping",
        "run_in": "5f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Flat galloping. Very long run-in. High draw bias in large-field sprints. Knavesmire.",
    },
    "Goodwood": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "undulating",
        "run_in": "3f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "COURSE_SHAPE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating. Right-hand. Low draw in 5f/6f sprints. Unique camber challenges off-side bias.",
    },
    "Leicester": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "galloping",
        "run_in": "3f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand galloping. Stiff uphill finish. Front-runners do hold on at sprint trips.",
    },
    "Carlisle": {
        "draw_bias_known": "yes",
        "draw_bias_side": "high",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "undulating",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Undulating right-hand. High draw bias in sprints. Uphill finish.",
    },
    "Nottingham": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "galloping",
        "run_in": "3f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Flat galloping left-hand. No strong known bias. Model appears adequately calibrated.",
    },
    "Salisbury": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "undulating",
        "run_in": "3f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Right-hand undulating. Uphill finish. Front-runners advantaged late in summer.",
    },
    "Yarmouth": {
        "draw_bias_known": "yes",
        "draw_bias_side": "low",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "flat_straight",
        "run_in": "5f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Very flat left-hand. Straight track component. Low draw in sprints. Front-runners competitive.",
    },
    "Epsom": {
        "draw_bias_known": "yes",
        "draw_bias_side": "high",
        "draw_bias_distances": ["5f", "6f"],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "undulating",
        "run_in": "4f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["DRAW_EYES_REQUIRED", "COURSE_SHAPE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Unique severe camber. Downhill then uphill finish. High draw bias in sprints. Very unusual track.",
    },
    "Kempton": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "unknown",
        "run_in": "unknown",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "UNKNOWN",
        "notes": "Turf track — separate from Kempton (AW). Not commonly run on turf. Treat as unknown.",
    },
    "Ludlow": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED", "HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Jump track. Sharp. Front-runners hold on. Pace dynamics different from flat model baseline.",
    },
    "Perth": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED", "HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Scottish jump track. Sharp. Irish/Scottish handler patterns poorly modelled. Low sample risk.",
    },
    "Kilbeggan": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "unknown",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED", "HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "UNKNOWN",
        "notes": "Irish jump track. Very low sample. Handler patterns unknown.",
    },
    "Clonmel": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "unknown",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED", "HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "UNKNOWN",
        "notes": "Irish jump track. Sharp. Low sample. Handler patterns unknown.",
    },
    "Down Royal": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "galloping",
        "run_in": "unknown",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["HANDLER_PROFILE_REQUIRED", "LOW_SAMPLE_WATCH"],
        "source_confidence": "UNKNOWN",
        "notes": "Northern Irish track. Very low sample. Full unknown profile.",
    },
    "Wexford": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "unknown",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED", "HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Irish jump track. Sharp. Front-runners hold on. Low sample risk.",
    },
    "Hexham": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "undulating",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Jump track. Stiff undulating. Stamina emphasis matches jump model output.",
    },
    "Ffos Las": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "2f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED", "HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Welsh track. Both flat and jump. Sharp. Front-runners do well.",
    },
    "Ballinrobe": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "yes",
        "front_runner_advantage": "yes",
        "circuit_type": "sharp",
        "run_in": "unknown",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["PACE_EYES_REQUIRED", "HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "UNKNOWN",
        "notes": "Irish track. Low sample. Handler patterns unknown.",
    },
    "Chepstow": {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "undulating",
        "run_in": "3f",
        "sprint_chute": "no",
        "aw_surface_subtype": "n/a",
        "course_00_required_features": ["COURSE_SHAPE_REQUIRED"],
        "source_confidence": "PUBLIC_GUIDE_SECONDARY",
        "notes": "Left-hand undulating. Long straight. No strong known bias.",
    },
}

_AW_CLUSTER_TRACKS = [
    "Southwell (AW)", "Kempton (AW)", "Wolverhampton (AW)",
    "Lingfield (AW)", "Newcastle (Aw)", "Chelmsford (Aw)",
]

# ---------------------------------------------------------------------------
# FEATURE READINESS MATRIX
# ---------------------------------------------------------------------------
_FEATURE_MATRIX = [
    {
        "feature": "draw_bias_by_course_distance",
        "in_velo": "no",
        "existing_local_source": "no",
        "external_source_candidate": "RP course stats / BHA raceday programme",
        "backfill_possible": "yes_with_scrape",
        "prospective_capture": "yes_via_rp_racecard",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "yes",
        "complexity": "MEDIUM",
        "risk": "LOW",
        "priority": "CRITICAL",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "pace_map_front_runner_flag",
        "in_velo": "no",
        "existing_local_source": "no",
        "external_source_candidate": "RP pace ratings (inconsistent)",
        "backfill_possible": "partial",
        "prospective_capture": "partial_via_rp",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "yes",
        "complexity": "HIGH",
        "risk": "MEDIUM",
        "priority": "CRITICAL",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "course_speed_figure_adjustment",
        "in_velo": "no",
        "existing_local_source": "no",
        "external_source_candidate": "Timeform / Raceform speed figures",
        "backfill_possible": "no",
        "prospective_capture": "no_paywall",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "yes",
        "complexity": "HIGH",
        "risk": "MEDIUM",
        "priority": "HIGH",
        "recommended_phase": "COURSE-02",
    },
    {
        "feature": "trainer_handler_course_profile",
        "in_velo": "partial_jtcd",
        "existing_local_source": "yes_jtcd_tables",
        "external_source_candidate": "JTC-D local profile bank",
        "backfill_possible": "yes_local",
        "prospective_capture": "yes_local",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "no",
        "complexity": "LOW",
        "risk": "LOW",
        "priority": "HIGH",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "going_course_interaction",
        "in_velo": "partial",
        "existing_local_source": "yes_sigma_going_field",
        "external_source_candidate": "RP racecard going string",
        "backfill_possible": "yes_local",
        "prospective_capture": "yes_local",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "no",
        "complexity": "LOW",
        "risk": "LOW",
        "priority": "HIGH",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "field_size_course_interaction",
        "in_velo": "no",
        "existing_local_source": "yes_sigma_field_size",
        "external_source_candidate": "sigma local",
        "backfill_possible": "yes_local",
        "prospective_capture": "yes_local",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "no",
        "needed_for_aw_cluster": "yes",
        "complexity": "LOW",
        "risk": "LOW",
        "priority": "MEDIUM",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "aw_surface_type_flag",
        "in_velo": "no",
        "existing_local_source": "yes_course_eyes_registry",
        "external_source_candidate": "_COURSE_EYES.aw_surface_subtype",
        "backfill_possible": "yes_static",
        "prospective_capture": "yes_static",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "no",
        "needed_for_aw_cluster": "yes",
        "complexity": "LOW",
        "risk": "LOW",
        "priority": "MEDIUM",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "circuit_type_flag",
        "in_velo": "no",
        "existing_local_source": "yes_course_eyes_registry",
        "external_source_candidate": "_COURSE_EYES.circuit_type",
        "backfill_possible": "yes_static",
        "prospective_capture": "yes_static",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "yes",
        "complexity": "LOW",
        "risk": "LOW",
        "priority": "MEDIUM",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "run_in_distance",
        "in_velo": "no",
        "existing_local_source": "yes_course_eyes_registry",
        "external_source_candidate": "_COURSE_EYES.run_in",
        "backfill_possible": "yes_static",
        "prospective_capture": "yes_static",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "yes",
        "complexity": "LOW",
        "risk": "LOW",
        "priority": "MEDIUM",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "uphill_finish_flag",
        "in_velo": "partial_via_mp_misses_csv",
        "existing_local_source": "partial",
        "external_source_candidate": "Course profiles / racing almanac",
        "backfill_possible": "yes_static",
        "prospective_capture": "yes_static",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "no",
        "complexity": "LOW",
        "risk": "LOW",
        "priority": "MEDIUM",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "sprint_chute_flag",
        "in_velo": "no",
        "existing_local_source": "yes_course_eyes_registry",
        "external_source_candidate": "_COURSE_EYES.sprint_chute",
        "backfill_possible": "yes_static",
        "prospective_capture": "yes_static",
        "needed_for_midprice": "no",
        "needed_for_beverley": "no",
        "needed_for_aw_cluster": "no",
        "complexity": "LOW",
        "risk": "LOW",
        "priority": "LOW",
        "recommended_phase": "COURSE-02",
    },
    {
        "feature": "draw_bias_direction_by_distance",
        "in_velo": "no",
        "existing_local_source": "yes_course_eyes_registry",
        "external_source_candidate": "_COURSE_EYES.draw_bias_side + draw_bias_distances",
        "backfill_possible": "yes_static",
        "prospective_capture": "yes_via_rp_racecard",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "yes",
        "complexity": "MEDIUM",
        "risk": "LOW",
        "priority": "CRITICAL",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "race_type_course_interaction",
        "in_velo": "no",
        "existing_local_source": "yes_sigma_race_type",
        "external_source_candidate": "sigma local",
        "backfill_possible": "yes_local",
        "prospective_capture": "yes_local",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "no",
        "needed_for_aw_cluster": "no",
        "complexity": "LOW",
        "risk": "LOW",
        "priority": "MEDIUM",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "pace_proxy_from_rp_comment",
        "in_velo": "no",
        "existing_local_source": "no",
        "external_source_candidate": "RP in-running comments (post-race)",
        "backfill_possible": "partial_with_scrape",
        "prospective_capture": "no_post_race_only",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "yes",
        "complexity": "HIGH",
        "risk": "HIGH",
        "priority": "HIGH",
        "recommended_phase": "COURSE-02",
    },
    {
        "feature": "draw_bias_empirical_by_course_distance_sample",
        "in_velo": "no",
        "existing_local_source": "partial_via_sigma_positions",
        "external_source_candidate": "sigma + RP historic results",
        "backfill_possible": "yes_with_n_gate",
        "prospective_capture": "yes_accumulation",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "yes",
        "complexity": "MEDIUM",
        "risk": "MEDIUM",
        "priority": "HIGH",
        "recommended_phase": "COURSE-01",
    },
    {
        "feature": "course_ground_preference_match",
        "in_velo": "partial_going_field",
        "existing_local_source": "yes_going_in_sigma",
        "external_source_candidate": "RP racecard going + RPDC going_preference",
        "backfill_possible": "yes_local",
        "prospective_capture": "yes_local",
        "needed_for_midprice": "yes",
        "needed_for_beverley": "yes",
        "needed_for_aw_cluster": "no",
        "complexity": "LOW",
        "risk": "LOW",
        "priority": "HIGH",
        "recommended_phase": "COURSE-01",
    },
]

# ---------------------------------------------------------------------------
# EXTERNAL SOURCE FIELD MAP
# ---------------------------------------------------------------------------
_EXTERNAL_SOURCE_MAP = [
    {
        "field": "draw",
        "local_status": "LOCAL_MISSING",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "SECTION_EXISTS_NOT_PROVEN",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "RP racecard shows draw by runner. Already captured via rp_account_collector when full racecard parsed.",
    },
    {
        "field": "course_draw_bias_direction",
        "local_status": "STATIC_IN_COURSE_EYES",
        "bha_status": "NOT_NEEDED",
        "rp_status": "NOT_NEEDED",
        "login_required": "no",
        "paywall_risk": "no",
        "automation_safe": "yes_static_lookup",
        "notes": "Available in _COURSE_EYES registry. Shadow field only. No live scoring.",
    },
    {
        "field": "pace_rating_front_runner",
        "local_status": "LOCAL_MISSING",
        "bha_status": "NOT_AVAILABLE",
        "rp_status": "PARTIAL_INCONSISTENT",
        "login_required": "yes_rp",
        "paywall_risk": "medium",
        "automation_safe": "no_inconsistent_coverage",
        "notes": "RP pace ratings exist but coverage is inconsistent. Consider proxy from in-running comment post-race.",
    },
    {
        "field": "course_speed_figure",
        "local_status": "LOCAL_MISSING",
        "bha_status": "NOT_AVAILABLE",
        "rp_status": "YES_BEHIND_PAYWALL",
        "login_required": "yes_rp_premium",
        "paywall_risk": "high",
        "automation_safe": "no",
        "notes": "Timeform/Raceform speed figures behind paywall. Not automatable without subscription.",
    },
    {
        "field": "trainer_course_win_rate",
        "local_status": "PARTIAL_JTCD",
        "bha_status": "SECTION_EXISTS_NOT_PROVEN",
        "rp_status": "SECTION_EXISTS_NOT_PROVEN",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "JTC-D tables already built locally. RP trainer course stats exist as supplement.",
    },
    {
        "field": "jockey_course_win_rate",
        "local_status": "PARTIAL_JTCD",
        "bha_status": "NOT_AVAILABLE",
        "rp_status": "SECTION_EXISTS_NOT_PROVEN",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "yes_with_rp_account",
        "notes": "JTC-D tables partially built. Supplement with RP jockey course stats.",
    },
    {
        "field": "going",
        "local_status": "PARTIAL_IN_SIGMA",
        "bha_status": "YES_OFFICIAL_GOING",
        "rp_status": "YES_IN_RACECARD",
        "login_required": "no_public",
        "paywall_risk": "no",
        "automation_safe": "yes",
        "notes": "Going string available in sigma.going where populated. Also in RP racecard without login.",
    },
    {
        "field": "distance_furlongs",
        "local_status": "PARTIAL_IN_SIGMA",
        "bha_status": "YES",
        "rp_status": "YES_IN_RACECARD",
        "login_required": "no_public",
        "paywall_risk": "no",
        "automation_safe": "yes",
        "notes": "sigma.distance field. Parse to furlongs float for distance bucket comparison.",
    },
    {
        "field": "field_size",
        "local_status": "PARTIAL_IN_SIGMA",
        "bha_status": "NOT_NEEDED",
        "rp_status": "YES_IN_RACECARD",
        "login_required": "no_public",
        "paywall_risk": "no",
        "automation_safe": "yes",
        "notes": "sigma.field_size where populated. RP racecard runner count as fallback.",
    },
    {
        "field": "aw_surface_subtype",
        "local_status": "STATIC_IN_COURSE_EYES",
        "bha_status": "YES_OFFICIAL",
        "rp_status": "YES_IN_COURSE_PROFILE",
        "login_required": "no",
        "paywall_risk": "no",
        "automation_safe": "yes_static_lookup",
        "notes": "Static knowledge in _COURSE_EYES. Rarely changes. Fibresand/Polytrack/Tapeta.",
    },
    {
        "field": "race_type",
        "local_status": "PARTIAL_IN_SIGMA",
        "bha_status": "YES",
        "rp_status": "YES_IN_RACECARD",
        "login_required": "no_public",
        "paywall_risk": "no",
        "automation_safe": "yes",
        "notes": "sigma.race_type where populated. Flat/Hurdle/Chase distinction important for model baseline.",
    },
    {
        "field": "in_running_position",
        "local_status": "LOCAL_MISSING",
        "bha_status": "NOT_AVAILABLE",
        "rp_status": "PARTIAL_POST_RACE",
        "login_required": "yes_rp",
        "paywall_risk": "no",
        "automation_safe": "partial_post_race_only",
        "notes": "Only available post-race from RP result comments. Not prospective. Shadow backfill only.",
    },
]

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
_REPORTS_DIR = os.path.join("data", "reports")


def _sp_to_dec(sp_str):
    """Convert SP string to decimal float. Returns None on failure."""
    if sp_str is None:
        return None
    if isinstance(sp_str, (int, float)):
        try:
            v = float(sp_str)
            return v if v > 0 else None
        except (TypeError, ValueError):
            return None
    s = str(sp_str).strip().replace(",", ".")
    # Strip favourite/joint markers e.g. "7/4F", "7/4JF", "11/10f"
    s = s.rstrip("FfJj")
    # Handle fractional e.g. "7/2"
    if "/" in s:
        parts = s.split("/")
        try:
            return round(float(parts[0]) / float(parts[1]) + 1.0, 4)
        except (ValueError, ZeroDivisionError):
            return None
    # Handle "7-2" style
    if "-" in s:
        parts = s.split("-")
        try:
            return round(float(parts[0]) / float(parts[1]) + 1.0, 4)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(s)
    except ValueError:
        return None


def _mp_band(sp_dec):
    """Assign SP decimal to mid-price band string."""
    if sp_dec is None:
        return "unknown"
    if sp_dec < 4.0:
        return "<4"
    if sp_dec < 6.0:
        return "4-6"
    if sp_dec < 10.0:
        return "6-10"
    if sp_dec < 17.0:
        return "10-16"
    return "16+"


def _extract_date(row):
    d = row.get("date")
    if d:
        return str(d)[:10]
    ca = row.get("created_at", "")
    return str(ca)[:10] if ca else "UNKNOWN"


def _safe_float(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _pct(num, den):
    if not den:
        return 0.0
    return round(100.0 * num / den, 1)


def _default_course_eye_entry(course_name):
    """Return a fully-unknown entry for any course not in _COURSE_EYES."""
    return {
        "draw_bias_known": "unknown",
        "draw_bias_side": "unknown",
        "draw_bias_distances": [],
        "pace_bias_known": "unknown",
        "front_runner_advantage": "unknown",
        "circuit_type": "unknown",
        "run_in": "unknown",
        "sprint_chute": "unknown",
        "aw_surface_subtype": "unknown",
        "course_00_required_features": ["HANDLER_PROFILE_REQUIRED"],
        "source_confidence": "UNKNOWN",
        "notes": f"No course eye data for {course_name}. Auto-generated unknown entry.",
    }


def _ensure_reports_dir():
    os.makedirs(_REPORTS_DIR, exist_ok=True)


def _write_csv(path, rows, fieldnames=None):
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_text(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------------------
def _load_sigma(path="data/sigma_audits_dump.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_csv_dict(path, key_col):
    result = {}
    try:
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                result[row[key_col]] = row
    except FileNotFoundError:
        print(f"  WARN: {path} not found — returning empty dict")
    return result


def _load_csv_list(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"  WARN: {path} not found — returning empty list")
    return rows


# ---------------------------------------------------------------------------
# SECTION 1 — COURSE REGISTRY
# ---------------------------------------------------------------------------
def _s1_course_registry(sigma, course_table, drain_roots, edge_roots):
    """
    Build unified course registry combining sigma aggregate, course tables,
    and _COURSE_EYES data. Returns list of dicts, one per course.
    """
    # Collect all known courses from sigma (track field) + CSVs
    all_courses = set()
    for row in sigma:
        t = row.get("track")
        if t:
            all_courses.add(str(t).strip())
    all_courses.update(course_table.keys())
    all_courses.update(drain_roots.keys())
    all_courses.update(edge_roots.keys())
    all_courses.discard("UNKNOWN")
    all_courses.discard("")

    registry = []
    for course in sorted(all_courses):
        eye = _COURSE_EYES.get(course, _default_course_eye_entry(course))
        ct = course_table.get(course, {})
        dr = drain_roots.get(course, {})
        er = edge_roots.get(course, {})

        n = _safe_int(ct.get("n", 0))
        wins = _safe_int(ct.get("wins", 0))
        sr = _safe_float(ct.get("sr", 0))
        label = ct.get("label", "UNKNOWN")
        avg_winner_sp = _safe_float(ct.get("avg_winner_sp"), None)
        watchlist_status = dr.get("watchlist_status", er.get("status", "UNKNOWN"))
        root_cause = dr.get("root_cause_hypotheses", "unknown")
        why_working = er.get("why_working", "unknown")

        required = eye.get("course_00_required_features", [])
        has_draw = "DRAW_EYES_REQUIRED" in required
        has_pace = "PACE_EYES_REQUIRED" in required

        registry.append({
            "course": course,
            "n": n,
            "wins": wins,
            "sr": sr,
            "label": label,
            "avg_winner_sp": avg_winner_sp if avg_winner_sp else "unknown",
            "watchlist_status": watchlist_status,
            "draw_bias_known": eye["draw_bias_known"],
            "draw_bias_side": eye["draw_bias_side"],
            "draw_bias_distances": ",".join(eye["draw_bias_distances"]),
            "pace_bias_known": eye["pace_bias_known"],
            "front_runner_advantage": eye["front_runner_advantage"],
            "circuit_type": eye["circuit_type"],
            "run_in": eye["run_in"],
            "sprint_chute": eye["sprint_chute"],
            "aw_surface_subtype": eye["aw_surface_subtype"],
            "required_features": "|".join(required),
            "draw_eyes_required": "yes" if has_draw else "no",
            "pace_eyes_required": "yes" if has_pace else "no",
            "source_confidence": eye["source_confidence"],
            "root_cause": root_cause,
            "why_working": why_working,
            "notes": eye.get("notes", ""),
        })
    return registry


# ---------------------------------------------------------------------------
# SECTION 2 — DRAW PRIORITY TABLE
# ---------------------------------------------------------------------------
def _s2_draw_priority(sigma, course_table):
    """
    For each course with draw_bias_known='yes', build per-distance priority rows.
    """
    rows = []
    for course, eye in sorted(_COURSE_EYES.items()):
        if eye["draw_bias_known"] != "yes":
            continue
        ct = course_table.get(course, {})
        n = _safe_int(ct.get("n", 0))
        sr = _safe_float(ct.get("sr", 0))

        distances = eye["draw_bias_distances"] if eye["draw_bias_distances"] else ["all"]
        for dist in distances:
            rows.append({
                "course": course,
                "distance": dist,
                "draw_bias_known": "yes",
                "draw_bias_side": eye["draw_bias_side"],
                "front_runner_advantage": eye["front_runner_advantage"],
                "circuit_type": eye["circuit_type"],
                "course_n": n,
                "course_sr": sr,
                "aw_surface_subtype": eye["aw_surface_subtype"],
                "source_confidence": eye["source_confidence"],
                "priority": "CRITICAL" if n >= 20 else "WATCH_LOW_SAMPLE",
                "status": "WATCHLIST_ONLY",
                "required_feature": "draw_bias_by_course_distance",
                "recommended_phase": "COURSE-01",
            })
    # Also add rows for courses where draw_bias_known='unknown' and n >= 20
    for course, eye in sorted(_COURSE_EYES.items()):
        if eye["draw_bias_known"] != "unknown":
            continue
        ct = course_table.get(course, {})
        n = _safe_int(ct.get("n", 0))
        if n < 20:
            continue
        rows.append({
            "course": course,
            "distance": "unknown",
            "draw_bias_known": "unknown",
            "draw_bias_side": "unknown",
            "front_runner_advantage": eye["front_runner_advantage"],
            "circuit_type": eye["circuit_type"],
            "course_n": n,
            "course_sr": _safe_float(ct.get("sr", 0)),
            "aw_surface_subtype": eye["aw_surface_subtype"],
            "source_confidence": "UNKNOWN",
            "priority": "INVESTIGATE",
            "status": "WATCHLIST_ONLY",
            "required_feature": "draw_bias_by_course_distance",
            "recommended_phase": "COURSE-01",
        })
    return rows


# ---------------------------------------------------------------------------
# SECTION 3 — PACE PRIORITY TABLE
# ---------------------------------------------------------------------------
def _s3_pace_priority(sigma, course_table):
    """
    For each course with front_runner_advantage='yes', build priority row.
    """
    rows = []
    for course, eye in sorted(_COURSE_EYES.items()):
        ct = course_table.get(course, {})
        n = _safe_int(ct.get("n", 0))
        sr = _safe_float(ct.get("sr", 0))
        avg_sp = _safe_float(ct.get("avg_winner_sp"), None)

        if eye["front_runner_advantage"] == "yes":
            pace_priority = "CRITICAL" if n >= 20 else "WATCH_LOW_SAMPLE"
        elif eye["pace_bias_known"] == "unknown":
            pace_priority = "INVESTIGATE" if n >= 20 else "LOW_SAMPLE"
        else:
            pace_priority = "MONITOR"

        rows.append({
            "course": course,
            "front_runner_advantage": eye["front_runner_advantage"],
            "pace_bias_known": eye["pace_bias_known"],
            "circuit_type": eye["circuit_type"],
            "run_in": eye["run_in"],
            "aw_surface_subtype": eye["aw_surface_subtype"],
            "course_n": n,
            "course_sr": sr,
            "avg_winner_sp": avg_sp if avg_sp else "unknown",
            "pace_priority": pace_priority,
            "status": "WATCHLIST_ONLY",
            "required_feature": "pace_map_front_runner_flag",
            "recommended_phase": "COURSE-01",
            "source_confidence": eye["source_confidence"],
        })
    return sorted(rows, key=lambda r: (r["pace_priority"] != "CRITICAL", r["course_n"] == 0, r["course"]))


# ---------------------------------------------------------------------------
# SECTION 4 — AW CLUSTER DEEP DIVE
# ---------------------------------------------------------------------------
def _s4_aw_cluster(sigma, course_table, drain_roots, mp_misses):
    """
    Deep dive on 6 AW tracks. Return structured dict for MD output.
    """
    aw_tracks = _AW_CLUSTER_TRACKS

    # Build per-track stats from source tables
    track_stats = {}
    for t in aw_tracks:
        eye = _COURSE_EYES.get(t, _default_course_eye_entry(t))
        ct = course_table.get(t, {})
        dr = drain_roots.get(t, {})

        n = _safe_int(ct.get("n", 0))
        wins = _safe_int(ct.get("wins", 0))
        sr = _safe_float(ct.get("sr"), None)
        avg_winner_sp = _safe_float(ct.get("avg_winner_sp"), None)
        avg_pick_sp = _safe_float(dr.get("avg_pick_sp"), None)
        sp_gap = _safe_float(dr.get("sp_gap"), None)
        misses = _safe_int(dr.get("misses", 0))
        root_cause = dr.get("root_cause_hypotheses", "unknown")
        watchlist = dr.get("watchlist_status", "WATCHLIST_ONLY")

        # Mid-price misses for this track from mp_misses CSV
        track_mp = [r for r in mp_misses if r.get("course", "").strip() == t]
        mp_6_10 = [r for r in track_mp if r.get("mp_band", "") == "6-10"]
        mp_4_6 = [r for r in track_mp if r.get("mp_band", "") == "4-6"]

        track_stats[t] = {
            "course": t,
            "surface": eye["aw_surface_subtype"],
            "circuit_type": eye["circuit_type"],
            "draw_bias_known": eye["draw_bias_known"],
            "draw_bias_side": eye["draw_bias_side"],
            "draw_bias_distances": eye["draw_bias_distances"],
            "front_runner_advantage": eye["front_runner_advantage"],
            "run_in": eye["run_in"],
            "sprint_chute": eye["sprint_chute"],
            "n": n,
            "wins": wins,
            "sr": sr,
            "avg_winner_sp": avg_winner_sp,
            "avg_pick_sp": avg_pick_sp,
            "sp_gap": sp_gap,
            "misses": misses,
            "mp_misses_total": len(track_mp),
            "mp_misses_6_10": len(mp_6_10),
            "mp_misses_4_6": len(mp_4_6),
            "root_cause": root_cause,
            "watchlist_status": watchlist,
            "required_features": eye["course_00_required_features"],
            "notes": eye.get("notes", ""),
        }

    # Overall AW cluster totals
    total_n = sum(track_stats[t]["n"] for t in aw_tracks)
    total_wins = sum(track_stats[t]["wins"] for t in aw_tracks)
    total_mp = sum(track_stats[t]["mp_misses_total"] for t in aw_tracks)
    total_mp_6_10 = sum(track_stats[t]["mp_misses_6_10"] for t in aw_tracks)
    cluster_sr = _pct(total_wins, total_n)

    return {
        "aw_cluster_tracks": aw_tracks,
        "total_n": total_n,
        "total_wins": total_wins,
        "cluster_sr_pct": cluster_sr,
        "total_mp_misses": total_mp,
        "total_mp_misses_6_10": total_mp_6_10,
        "track_stats": track_stats,
        "status": "WATCHLIST_ONLY",
        "constraint": "NO_COURSE_01_IMPLEMENTATION",
        "containment_is_not_profit": True,
    }


# ---------------------------------------------------------------------------
# SECTION 5 — BEVERLEY WAR BOOK
# ---------------------------------------------------------------------------
def _s5_beverley_war_book(sigma, mp_misses, drain_roots):
    """
    Full Beverley-specific breakdown from sigma (track=Beverley)
    supplemented by mp_misses CSV and drain_roots.
    """
    eye = _COURSE_EYES.get("Beverley", _default_course_eye_entry("Beverley"))
    dr = drain_roots.get("Beverley", {})

    # sigma rows where track='Beverley'
    bev_sigma = [r for r in sigma if str(r.get("track", "")).strip() == "Beverley"]

    # mp_misses rows
    bev_mp = [r for r in mp_misses if r.get("course", "").strip() == "Beverley"]

    # Outcome breakdown from sigma
    outcomes = Counter(r.get("outcome") for r in bev_sigma)
    miss_reasons = Counter(r.get("miss_reason") for r in bev_sigma)

    # MP miss band breakdown
    band_counts = Counter(r.get("mp_band", "unknown") for r in bev_mp)

    # Winner SP distribution from mp_misses
    winner_sps = [_safe_float(r.get("winner_sp_dec")) for r in bev_mp if r.get("winner_sp_dec")]
    avg_winner_sp_mp = round(sum(winner_sps) / len(winner_sps), 2) if winner_sps else None

    # Full row list from mp_misses for the war book table
    war_rows = []
    for r in bev_mp:
        war_rows.append({
            "date": r.get("date", "unknown"),
            "off_time": r.get("off_time", "unknown"),
            "race_type": r.get("race_type", "unknown"),
            "distance": r.get("distance", "unknown"),
            "going": r.get("going", "unknown"),
            "actual_winner": r.get("actual_winner", "unknown"),
            "winner_sp_dec": r.get("winner_sp_dec", "unknown"),
            "mp_band": r.get("mp_band", "unknown"),
            "decision_tier": r.get("decision_tier", "unknown"),
            "pick_sp_dec": r.get("pick_sp_dec", "unknown"),
            "front_runner_bias": r.get("front_runner_bias", "unknown"),
            "uphill_finish": r.get("uphill_finish", "unknown"),
            "turn_severity": r.get("turn_severity", "unknown"),
        })

    return {
        "course": "Beverley",
        "circuit_type": eye["circuit_type"],
        "draw_bias_known": eye["draw_bias_known"],
        "draw_bias_side": eye["draw_bias_side"],
        "draw_bias_distances": eye["draw_bias_distances"],
        "front_runner_advantage": eye["front_runner_advantage"],
        "run_in": eye["run_in"],
        "notes": eye.get("notes", ""),
        "sigma_n": len(bev_sigma),
        "sigma_outcomes": dict(outcomes),
        "sigma_miss_reasons": dict(miss_reasons),
        "mp_misses_total": len(bev_mp),
        "mp_band_counts": dict(band_counts),
        "avg_winner_sp_in_mp_misses": avg_winner_sp_mp,
        "drain_n": _safe_int(dr.get("n", 0)),
        "drain_sr": _safe_float(dr.get("sr"), None),
        "drain_avg_winner_sp": _safe_float(dr.get("avg_winner_sp"), None),
        "drain_avg_pick_sp": _safe_float(dr.get("avg_pick_sp"), None),
        "drain_sp_gap": _safe_float(dr.get("sp_gap"), None),
        "root_cause_hypotheses": dr.get("root_cause_hypotheses", "unknown"),
        "watchlist_status": "WATCHLIST_ONLY",
        "war_rows": war_rows,
        "required_features": eye["course_00_required_features"],
        "status": "BEVERLEY_WATCHLIST_ONLY",
        "constraint": "NO_COURSE_01_IMPLEMENTATION",
    }


# ---------------------------------------------------------------------------
# SECTION 6 — MID-PRICE 6-10 WOUND TABLE
# ---------------------------------------------------------------------------
def _s6_midprice_6_10(sigma, mp_misses):
    """
    All 6-10 band misses from mp_misses CSV (mp_band=='6-10').
    Also cross-check from sigma miss_reason=='mid_priced_won' and SP in 6-10 range.
    """
    # Primary: from pre-built csv
    from_csv = [r for r in mp_misses if r.get("mp_band", "").strip() == "6-10"]

    # Secondary: from sigma direct (where actual_winner_sp available)
    seen_from_sigma = []
    for r in sigma:
        if r.get("miss_reason") != "mid_priced_won":
            continue
        sp = _safe_float(r.get("actual_winner_sp"))
        if sp is None:
            continue
        if 6.0 <= sp < 10.0:
            seen_from_sigma.append({
                "date": _extract_date(r),
                "course": r.get("track", "unknown") or "unknown",
                "off_time": r.get("off_time", "unknown") or "unknown",
                "race_type": r.get("race_type", "unknown") or "unknown",
                "distance": r.get("distance", "unknown") or "unknown",
                "going": r.get("going", "unknown") or "unknown",
                "actual_winner": r.get("actual_winner_name", "unknown") or "unknown",
                "winner_sp_dec": sp,
                "mp_band": "6-10",
                "decision_tier": r.get("decision_tier", "unknown") or "unknown",
                "pick_sp_dec": _safe_float(r.get("pick_sp")) or "unknown",
                "source": "sigma_direct",
            })

    # Annotate CSV rows
    output_rows = []
    for r in from_csv:
        output_rows.append({
            "date": r.get("date", "unknown"),
            "course": r.get("course", "unknown"),
            "off_time": r.get("off_time", "unknown"),
            "race_type": r.get("race_type", "unknown"),
            "distance": r.get("distance", "unknown"),
            "going": r.get("going", "unknown"),
            "actual_winner": r.get("actual_winner", "unknown"),
            "winner_sp_dec": r.get("winner_sp_dec", "unknown"),
            "mp_band": "6-10",
            "decision_tier": r.get("decision_tier", "unknown"),
            "pick_sp_dec": r.get("pick_sp_dec", "unknown"),
            "front_runner_bias": r.get("front_runner_bias", "unknown"),
            "uphill_finish": r.get("uphill_finish", "unknown"),
            "turn_severity": r.get("turn_severity", "unknown"),
            "source": "midprice_misses_csv",
        })

    # Sort by date desc
    output_rows.sort(key=lambda x: str(x.get("date", "")), reverse=True)

    # Summary by course
    course_counts = Counter(r["course"] for r in output_rows)
    top_courses = course_counts.most_common(10)

    return {
        "rows": output_rows,
        "n_total": len(output_rows),
        "n_from_csv": len(from_csv),
        "n_from_sigma": len(seen_from_sigma),
        "top_courses": top_courses,
        "status": "WOUND_TABLE_COMPLETE",
    }


# ---------------------------------------------------------------------------
# SECTION 7 — FEATURE READINESS
# ---------------------------------------------------------------------------
def _s7_feature_readiness():
    return _FEATURE_MATRIX


# ---------------------------------------------------------------------------
# SECTION 8 — EXTERNAL SOURCE MAP
# ---------------------------------------------------------------------------
def _s8_external_source_map():
    return _EXTERNAL_SOURCE_MAP


# ---------------------------------------------------------------------------
# SECTION 9 — COURSE WATCHLIST
# ---------------------------------------------------------------------------
def _s9_course_watchlist(drain_roots, edge_roots, course_table):
    """
    Categorise all courses into: DRAIN / EDGE / NEUTRAL / UNKNOWN.
    Within each, tag with required eyes.
    """
    drain_courses = list(drain_roots.keys())
    edge_courses = list(edge_roots.keys())

    # All courses from course_table
    all_courses = set(course_table.keys())
    all_courses.update(drain_courses)
    all_courses.update(edge_courses)
    all_courses.discard("UNKNOWN")
    all_courses.discard("")

    watchlist = {"DRAIN": [], "EDGE": [], "NEUTRAL": [], "UNKNOWN_STATUS": []}

    for course in sorted(all_courses):
        eye = _COURSE_EYES.get(course, _default_course_eye_entry(course))
        ct = course_table.get(course, {})
        dr = drain_roots.get(course, {})
        er = edge_roots.get(course, {})

        n = _safe_int(ct.get("n", 0))
        sr = _safe_float(ct.get("sr"), None)
        label = ct.get("label", "UNKNOWN")

        required = eye.get("course_00_required_features", [])
        eyes_flags = "|".join(required) if required else "NONE"

        entry = {
            "course": course,
            "n": n,
            "sr": sr,
            "label": label,
            "eyes_required": eyes_flags,
            "draw_bias_known": eye["draw_bias_known"],
            "pace_bias_known": eye["pace_bias_known"],
            "circuit_type": eye["circuit_type"],
            "watchlist_only": "yes",
            "notes": eye.get("notes", ""),
        }

        if course in drain_courses:
            entry["root_cause"] = dr.get("root_cause_hypotheses", "unknown")
            watchlist["DRAIN"].append(entry)
        elif course in edge_courses:
            entry["why_working"] = er.get("why_working", "unknown")
            watchlist["EDGE"].append(entry)
        elif label in ("COURSE_DOING_WELL",):
            watchlist["EDGE"].append(entry)
        elif n == 0:
            watchlist["UNKNOWN_STATUS"].append(entry)
        else:
            watchlist["NEUTRAL"].append(entry)

    return watchlist


# ---------------------------------------------------------------------------
# SECTION 10 — COURSE-01 DESIGN SPEC
# ---------------------------------------------------------------------------
def _s10_course01_spec():
    return """# COURSE-01 Design Spec

## Mission: Draw and Pace Shadow Feature Registry

REPORT_ONLY design spec. NOT IMPLEMENTED.
Status: DESIGN_SPEC_ONLY — COURSE-01 implementation pending VCP-03 completion.

---

## Objective

Create shadow-only draw/pace/course-position features that can explain
mid-price misses without affecting live scoring. All fields are shadow-only
until promotion gates are met.

---

## Shadow fields to add

- `shadow_draw_pos` — runner's stall draw (integer, from RP racecard)
- `shadow_draw_bias_flag` — 1 if draw matches bias direction for this course+distance, else 0
- `shadow_draw_bias_side` — "favoured" / "unfavoured" / "neutral" / "unknown"
- `shadow_front_runner_flag` — 1 if runner is classified as front-runner pace type
- `shadow_pace_map_position` — "lead" / "prominent" / "hold-up" / "unknown"
- `shadow_aw_surface` — fibresand / polytrack / tapeta / n/a (from static registry)
- `shadow_circuit_type` — sharp / galloping / undulating / flat_straight / unknown
- `shadow_run_in_f` — run-in furlongs float (from static registry)
- `shadow_uphill_finish` — yes / no / unknown (from static registry)
- `shadow_sprint_chute` — yes / no / unknown (from static registry)

---

## Data ingestion plan

- Source 1: draw available in RP racecard (runner.draw) — already parsed via rp_account_collector
- Source 2: course static profiles — _COURSE_EYES registry (this script)
- Source 3: draw bias lookup table by course+distance — built from _COURSE_EYES
- Source 4: pace proxy — derive from in-running comments post-race (partial coverage only)

---

## Promotion requirements

- n >= 300 prospective shadow race validation
- Course-specific sample gates (n >= 50 per course before course-level inference)
- False-green guard: no silent improvement (shadow correlation must be audited against control)
- No direct score change without VCP-03 completion and VFU review
- Operator decision required at each promotion gate

---

## What this does NOT do

- Does not change sqpe_v17_prob
- Does not change vp score
- Does not affect sigma output
- Does not affect live model weights
- Does not affect Supabase tables
- Does not trigger VFU-21 or VCP-04

---

## Build order (when authorised)

1. Draw ingestion from RP racecard parser (shadow field only)
2. Static course registry join (course+distance -> draw_bias_side)
3. Shadow draw_bias_flag computation
4. Pace proxy from post-race comment parser (shadow only)
5. Shadow feature validation table (n >= 300 before review)
6. Operator review gate
7. If approved: promote to scoring with VFU-21 protocol

---

## Status

DESIGN_SPEC_ONLY — COURSE-01 implementation pending VCP-03 completion.
NO_COURSE_01_IMPLEMENTATION constraint active.
"""


# ---------------------------------------------------------------------------
# SECTION 11 — OPERATOR BRIEF
# ---------------------------------------------------------------------------
def _s11_operator_brief(s1, s2, s3, s4, s5, s6, s7, s8, s9):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    drain_n = len(s9.get("DRAIN", []))
    edge_n = len(s9.get("EDGE", []))
    aw_n = s4.get("total_n", 0)
    aw_sr = s4.get("cluster_sr_pct", 0)
    bev_mp = s5.get("mp_misses_total", 0)
    wound_n = s6.get("n_total", 0)
    top_wound = s6.get("top_courses", [])[:5]
    draw_critical = len([r for r in s2 if r.get("priority") == "CRITICAL"])
    pace_critical = len([r for r in s3 if r.get("pace_priority") == "CRITICAL"])
    critical_features = [f["feature"] for f in s7 if f["priority"] == "CRITICAL"]

    top_wound_str = "\n".join(f"  - {c}: {n} misses" for c, n in top_wound)

    return f"""# COURSE-00 Operator Brief
## VÉLØ Course Eyes Completion Pack
Generated: {now}
Status: REPORT_ONLY

---

## Q1. What is COURSE-00?

COURSE-00 is a pure analytical audit of course-level intelligence gaps in the VÉLØ system.
It produces a static course eye registry, draw/pace priority tables, deep dives on AW tracks
and Beverley, a mid-price 6-10 wound table, a feature readiness matrix, and a COURSE-01 design
spec. No live changes are made. All course rules are WATCHLIST_ONLY.

---

## Q2. What is the AW cluster situation?

{len(_AW_CLUSTER_TRACKS)} AW tracks audited: {", ".join(_AW_CLUSTER_TRACKS)}.
Combined n={aw_n}, SR={aw_sr}%.
All have draw_bias_known='yes' and front_runner_advantage='yes'.
Required features: DRAW_EYES_REQUIRED + PACE_EYES_REQUIRED + AW_PACE_EYES_REQUIRED.
Status: WATCHLIST_ONLY. No scoring change.

---

## Q3. What is the Beverley situation?

Beverley: sharp track, uphill finish, low draw bias at 5f/6f, front-runner hold-on pattern.
Mid-price misses from mp_misses CSV: {bev_mp} rows.
Root cause: draw bias + pace dynamics + uphill finish not captured in VÉLØ.
Status: BEVERLEY_WATCHLIST_ONLY. Required: DRAW_EYES_REQUIRED + PACE_EYES_REQUIRED.

---

## Q4. How many drain courses vs edge courses?

DRAIN courses identified: {drain_n}
EDGE courses identified: {edge_n}
Full breakdown in: course_00_course_watchlist.md

---

## Q5. What are the top 6-10 wound courses?

Total 6-10 band mid-price misses: {wound_n}
Top courses by count:
{top_wound_str}

---

## Q6. What are the 2 CRITICAL missing features?

1. draw_bias_by_course_distance — CRITICAL, COURSE-01
2. pace_map_front_runner_flag — CRITICAL, COURSE-01

Additional CRITICAL: draw_bias_direction_by_distance.

---

## Q7. What is the feature readiness status?

Total features audited: {len(s7)}
CRITICAL: {len([f for f in s7 if f["priority"] == "CRITICAL"])}
HIGH: {len([f for f in s7 if f["priority"] == "HIGH"])}
MEDIUM: {len([f for f in s7 if f["priority"] == "MEDIUM"])}
LOW: {len([f for f in s7 if f["priority"] == "LOW"])}
Critical feature list: {", ".join(critical_features)}

---

## Q8. How many courses have draw_bias_known='yes'?

{draw_critical} course/distance combinations at CRITICAL priority (n>=20).
Full draw priority table: course_00_draw_bias_priority_table.csv

---

## Q9. How many courses have front_runner_advantage='yes'?

{pace_critical} courses at CRITICAL pace priority.
Full pace priority table: course_00_pace_bias_priority_table.csv

---

## Q10. What does COURSE-01 do and is it implemented?

COURSE-01 creates shadow-only draw/pace/course-position features.
It is NOT implemented. This is a design spec only.
Constraint: NO_COURSE_01_IMPLEMENTATION active.
Implementation requires VCP-03 completion and operator gate.

---

## Q11. What are the active hard constraints?

{chr(10).join("- " + c for c in _HARD_CONSTRAINTS)}

---

## FINAL CLASSIFICATIONS

{chr(10).join("- " + c for c in _FINAL_CLASSIFICATIONS)}
"""


# ---------------------------------------------------------------------------
# MARKDOWN GENERATORS
# ---------------------------------------------------------------------------

def _md_course_eyes_pack(s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11):
    bev = s5
    aw = s4

    lines = [
        "# COURSE-00 — VÉLØ Course Eyes Completion Pack",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "Status: REPORT_ONLY | All course rules: WATCHLIST_ONLY",
        "",
        "---",
        "",
        "## Hard Constraints",
        "",
    ]
    for c in _HARD_CONSTRAINTS:
        lines.append(f"- {c}")
    lines += [
        "",
        "---",
        "",
        "## Section 1 — Course Registry Summary",
        "",
        f"Total courses in registry: {len(s1)}",
        "",
        "| Course | N | SR | Label | Draw Known | Pace Known | Required Eyes |",
        "|--------|---|----|----|----|----|---|",
    ]
    for r in s1[:40]:
        lines.append(
            f"| {r['course']} | {r['n']} | {r['sr']:.3f} | {r['label']} "
            f"| {r['draw_bias_known']} | {r['pace_bias_known']} | {r['required_features'][:40]} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Section 2 — Draw Bias Priority",
        "",
        f"Draw bias priority rows (CRITICAL + INVESTIGATE): {len(s2)}",
        "",
        "| Course | Distance | Bias Side | Circuit | N | Priority |",
        "|--------|----------|-----------|---------|---|----------|",
    ]
    for r in s2[:20]:
        lines.append(
            f"| {r['course']} | {r['distance']} | {r['draw_bias_side']} "
            f"| {r['circuit_type']} | {r['course_n']} | {r['priority']} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Section 3 — Pace Bias Priority",
        "",
        f"Pace priority rows: {len(s3)}",
        "",
        "| Course | Front Runner | Pace Known | Circuit | N | Priority |",
        "|--------|-------------|------------|---------|---|----------|",
    ]
    for r in s3[:20]:
        lines.append(
            f"| {r['course']} | {r['front_runner_advantage']} | {r['pace_bias_known']} "
            f"| {r['circuit_type']} | {r['course_n']} | {r['pace_priority']} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Section 4 — AW Cluster Summary",
        "",
        f"Tracks: {', '.join(aw['aw_cluster_tracks'])}",
        f"Total N: {aw['total_n']} | Wins: {aw['total_wins']} | SR: {aw['cluster_sr_pct']}%",
        f"Total MP misses: {aw['total_mp_misses']} | 6-10 band: {aw['total_mp_misses_6_10']}",
        "Status: WATCHLIST_ONLY | NO_COURSE_01_IMPLEMENTATION",
        "",
        "| Track | Surface | Draw Known | FR Adv | N | SR | MP Misses |",
        "|-------|---------|-----------|--------|---|----|----|",
    ]
    for t in aw["aw_cluster_tracks"]:
        ts = aw["track_stats"].get(t, {})
        sr_val = f"{ts.get('sr', 0):.3f}" if ts.get("sr") is not None else "unknown"
        lines.append(
            f"| {t} | {ts.get('surface','?')} | {ts.get('draw_bias_known','?')} "
            f"| {ts.get('front_runner_advantage','?')} | {ts.get('n',0)} "
            f"| {sr_val} | {ts.get('mp_misses_total',0)} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Section 5 — Beverley War Book Summary",
        "",
        f"Circuit: {bev['circuit_type']} | Draw bias: {bev['draw_bias_side']} "
        f"at {', '.join(bev['draw_bias_distances'])}",
        f"Front runner advantage: {bev['front_runner_advantage']} | Run-in: {bev['run_in']}",
        f"Sigma rows: {bev['sigma_n']} | MP misses: {bev['mp_misses_total']}",
        f"Drain SR: {bev.get('drain_sr', 'unknown')} | Avg winner SP: {bev.get('drain_avg_winner_sp','unknown')}",
        f"Avg pick SP: {bev.get('drain_avg_pick_sp','unknown')} | SP gap: {bev.get('drain_sp_gap','unknown')}",
        "",
        f"Root cause: {bev['root_cause_hypotheses']}",
        "",
        "Status: BEVERLEY_WATCHLIST_ONLY",
        "",
        "---",
        "",
        "## Section 6 — Mid-Price 6-10 Wound Table",
        "",
        f"Total 6-10 band misses: {s6['n_total']}",
        "",
        "Top 10 courses:",
    ]
    for course, count in s6.get("top_courses", [])[:10]:
        lines.append(f"- {course}: {count}")
    lines += [
        "",
        "---",
        "",
        "## Section 7 — Feature Readiness Matrix",
        "",
        "| Feature | In VELO | Priority | Phase | Complexity | Risk |",
        "|---------|---------|----------|-------|-----------|------|",
    ]
    for f in s7:
        lines.append(
            f"| {f['feature']} | {f['in_velo']} | {f['priority']} "
            f"| {f['recommended_phase']} | {f['complexity']} | {f['risk']} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Section 8 — External Source Field Map",
        "",
        "| Field | Local Status | RP Status | Login Required | Automation Safe |",
        "|-------|-------------|-----------|---------------|-----------------|",
    ]
    for f in s8:
        lines.append(
            f"| {f['field']} | {f['local_status']} | {f['rp_status']} "
            f"| {f['login_required']} | {f['automation_safe']} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Section 9 — Course Watchlist",
        "",
        f"DRAIN: {len(s9.get('DRAIN',[]))} | EDGE: {len(s9.get('EDGE',[]))} "
        f"| NEUTRAL: {len(s9.get('NEUTRAL',[]))} | UNKNOWN: {len(s9.get('UNKNOWN_STATUS',[]))}",
        "",
        "### DRAIN Courses",
    ]
    for r in s9.get("DRAIN", []):
        lines.append(f"- **{r['course']}** (n={r['n']}, SR={r['sr']}) — {r.get('root_cause','unknown')[:80]}")
    lines += ["", "### EDGE Courses"]
    for r in s9.get("EDGE", []):
        lines.append(f"- **{r['course']}** (n={r['n']}, SR={r['sr']})")
    lines += [
        "",
        "---",
        "",
        "## Section 10 — COURSE-01 Design Spec",
        "",
        s10,
        "",
        "---",
        "",
        "## Final Classifications",
        "",
    ]
    for c in _FINAL_CLASSIFICATIONS:
        lines.append(f"- {c}")

    return "\n".join(lines)


def _md_aw_cluster(s4):
    aw = s4
    lines = [
        "# COURSE-00 — AW Cluster Deep Dive",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "Status: WATCHLIST_ONLY | NO_COURSE_01_IMPLEMENTATION",
        "",
        f"**Tracks audited:** {', '.join(aw['aw_cluster_tracks'])}",
        f"**Combined N:** {aw['total_n']} | **Wins:** {aw['total_wins']} | **SR:** {aw['cluster_sr_pct']}%",
        f"**Total MP misses:** {aw['total_mp_misses']} | **6-10 band:** {aw['total_mp_misses_6_10']}",
        "",
        "---",
    ]
    for t in aw["aw_cluster_tracks"]:
        ts = aw["track_stats"].get(t, {})
        eye = _COURSE_EYES.get(t, {})
        lines += [
            "",
            f"## {t}",
            "",
            f"- **Surface:** {ts.get('surface','unknown')}",
            f"- **Circuit:** {ts.get('circuit_type','unknown')}",
            f"- **Draw bias:** {ts.get('draw_bias_known','unknown')} — side: {ts.get('draw_bias_side','unknown')} at {', '.join(ts.get('draw_bias_distances',[]))}",
            f"- **Front runner advantage:** {ts.get('front_runner_advantage','unknown')}",
            f"- **Run-in:** {ts.get('run_in','unknown')} | Sprint chute: {ts.get('sprint_chute','unknown')}",
            f"- **N:** {ts.get('n',0)} | **Wins:** {ts.get('wins',0)} | **SR:** {ts.get('sr','unknown')}",
            f"- **Avg winner SP:** {ts.get('avg_winner_sp','unknown')} | **Avg pick SP:** {ts.get('avg_pick_sp','unknown')}",
            f"- **SP gap:** {ts.get('sp_gap','unknown')}",
            f"- **MP misses total:** {ts.get('mp_misses_total',0)} | **6-10 band:** {ts.get('mp_misses_6_10',0)} | **4-6 band:** {ts.get('mp_misses_4_6',0)}",
            f"- **Root cause:** {ts.get('root_cause','unknown')}",
            f"- **Watchlist status:** {ts.get('watchlist_status','WATCHLIST_ONLY')}",
            f"- **Required features:** {', '.join(ts.get('required_features',[]))}",
            f"- **Notes:** {eye.get('notes','')}",
        ]
    lines += [
        "",
        "---",
        "",
        "## AW Cluster — Key Findings",
        "",
        "1. All 6 AW tracks have confirmed draw bias (known=yes).",
        "2. All 6 have front_runner_advantage=yes.",
        "3. DRAW_EYES_REQUIRED + PACE_EYES_REQUIRED + AW_PACE_EYES_REQUIRED flagged for AW tracks.",
        "4. Mid-price 6-10 misses concentrated in Southwell, Kempton, Wolverhampton.",
        "5. Surface type (fibresand vs polytrack vs tapeta) adds additional model gap.",
        "6. containment_is_not_profit = True — identifying these tracks is not the same as fixing SR.",
        "7. All rules WATCHLIST_ONLY. No implementation without COURSE-01 authorisation.",
    ]
    return "\n".join(lines)


def _md_beverley_war_book(s5):
    bev = s5
    lines = [
        "# COURSE-00 — Beverley War Book",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "Status: BEVERLEY_WATCHLIST_ONLY | NO_COURSE_01_IMPLEMENTATION",
        "",
        "---",
        "",
        "## Track Profile",
        "",
        f"- **Circuit type:** {bev['circuit_type']}",
        f"- **Draw bias:** {bev['draw_bias_known']} — side: {bev['draw_bias_side']} at {', '.join(bev['draw_bias_distances'])}",
        f"- **Front runner advantage:** {bev['front_runner_advantage']}",
        f"- **Run-in:** {bev['run_in']}",
        f"- **Notes:** {bev['notes']}",
        "",
        "---",
        "",
        "## Performance Summary",
        "",
        f"- **Sigma rows (track=Beverley):** {bev['sigma_n']}",
        f"- **Sigma outcomes:** {bev['sigma_outcomes']}",
        f"- **Sigma miss reasons:** {bev['sigma_miss_reasons']}",
        f"- **Drain table N:** {bev['drain_n']} | **SR:** {bev['drain_sr']}",
        f"- **Avg winner SP:** {bev['drain_avg_winner_sp']} | **Avg pick SP:** {bev['drain_avg_pick_sp']}",
        f"- **SP gap (pick - winner):** {bev['drain_sp_gap']} (negative = backing too-short prices)",
        "",
        "---",
        "",
        "## Mid-Price Miss Breakdown",
        "",
        f"**Total MP misses from CSV:** {bev['mp_misses_total']}",
        f"**Avg winner SP in MP misses:** {bev['avg_winner_sp_in_mp_misses']}",
        "",
        "Band counts:",
    ]
    for band, count in sorted(bev["mp_band_counts"].items()):
        lines.append(f"- {band}: {count}")
    lines += [
        "",
        "---",
        "",
        "## Root Cause",
        "",
        f"{bev['root_cause_hypotheses']}",
        "",
        "---",
        "",
        "## Required Features",
        "",
    ]
    for f in bev["required_features"]:
        lines.append(f"- {f}")
    lines += [
        "",
        "---",
        "",
        "## War Book — All Mid-Price Miss Rows",
        "",
        "| Date | Off | Type | Dist | Going | Winner | SP | Band | Tier | Pick SP | FR Bias |",
        "|------|-----|------|------|-------|--------|-----|------|------|---------|---------|",
    ]
    for r in bev["war_rows"]:
        lines.append(
            f"| {r['date']} | {r['off_time']} | {r['race_type']} | {r['distance']} "
            f"| {r['going']} | {r['actual_winner']} | {r['winner_sp_dec']} "
            f"| {r['mp_band']} | {r['decision_tier']} | {r['pick_sp_dec']} "
            f"| {r['front_runner_bias']} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Constraints",
        "",
        "- BEVERLEY_WATCHLIST_ONLY",
        "- NO_COURSE_01_IMPLEMENTATION",
        "- containment_is_not_profit = True",
        "- DO_NOT_SUPPRESS_CONTRADICTIONS",
    ]
    return "\n".join(lines)


def _md_external_source_map(s8):
    lines = [
        "# COURSE-00 — External Source Field Map",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "Status: REPORT_ONLY",
        "",
        "No external URL calls made in this audit. All source assessments are static knowledge.",
        "",
        "---",
        "",
    ]
    for f in s8:
        lines += [
            f"## {f['field']}",
            "",
            f"- **Local status:** {f['local_status']}",
            f"- **BHA status:** {f['bha_status']}",
            f"- **RP status:** {f['rp_status']}",
            f"- **Login required:** {f['login_required']}",
            f"- **Paywall risk:** {f['paywall_risk']}",
            f"- **Automation safe:** {f['automation_safe']}",
            f"- **Notes:** {f['notes']}",
            "",
        ]
    return "\n".join(lines)


def _md_course_watchlist(s9):
    lines = [
        "# COURSE-00 — Course Watchlist",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "Status: WATCHLIST_ONLY for all courses",
        "",
        "---",
        "",
        "## DRAIN Courses",
        "",
        f"*{len(s9.get('DRAIN',[]))} courses where SR is below expectation.*",
        "",
        "| Course | N | SR | Eyes Required | Root Cause |",
        "|--------|---|----|----|---|",
    ]
    for r in s9.get("DRAIN", []):
        lines.append(
            f"| {r['course']} | {r['n']} | {r['sr']} | {r['eyes_required'][:40]} "
            f"| {str(r.get('root_cause','unknown'))[:60]} |"
        )
    lines += [
        "",
        "---",
        "",
        "## EDGE Courses",
        "",
        f"*{len(s9.get('EDGE',[]))} courses where model is performing well.*",
        "",
        "| Course | N | SR | Eyes Required |",
        "|--------|---|---|---|",
    ]
    for r in s9.get("EDGE", []):
        lines.append(
            f"| {r['course']} | {r['n']} | {r['sr']} | {r['eyes_required'][:40]} |"
        )
    lines += [
        "",
        "---",
        "",
        "## NEUTRAL Courses",
        "",
        "| Course | N | SR | Eyes Required |",
        "|--------|---|---|---|",
    ]
    for r in s9.get("NEUTRAL", []):
        lines.append(
            f"| {r['course']} | {r['n']} | {r['sr']} | {r['eyes_required'][:40]} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Unknown Status Courses",
        "",
        "| Course | N | Eyes Required |",
        "|--------|---|---|",
    ]
    for r in s9.get("UNKNOWN_STATUS", []):
        lines.append(f"| {r['course']} | {r['n']} | {r['eyes_required'][:40]} |")
    lines += [
        "",
        "---",
        "",
        "## Constraints",
        "",
        "- All courses: WATCHLIST_ONLY",
        "- NO_COURSE_01_IMPLEMENTATION",
        "- COURSE_RULES_WATCHLIST_ONLY",
        "- MISSING_ARTIFACTS_RESOLVE_UNKNOWN_NOT_CLEAN",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("COURSE-00 — VÉLØ Course Eyes Completion Pack")
    print("REPORT_ONLY — No scoring change. No model promotion.")
    print("=" * 60)
    print()

    _ensure_reports_dir()

    # --- Load data ---
    print("Loading sigma_audits_dump.json ...")
    sigma = _load_sigma()
    print(f"  Loaded {len(sigma)} sigma rows")

    print("Loading RESULTS-01 course performance table ...")
    course_table = _load_csv_dict(
        "data/reports/results_01_course_performance_table.csv", "course"
    )
    print(f"  Loaded {len(course_table)} course rows")

    print("Loading RESULTS-02 drain root causes ...")
    drain_roots = _load_csv_dict(
        "data/reports/results_02_course_drain_root_causes.csv", "course"
    )
    print(f"  Loaded {len(drain_roots)} drain courses")

    print("Loading RESULTS-02 edge root causes ...")
    edge_roots = _load_csv_dict(
        "data/reports/results_02_course_edge_root_causes.csv", "course"
    )
    print(f"  Loaded {len(edge_roots)} edge courses")

    print("Loading RESULTS-02 midprice misses table ...")
    mp_misses = _load_csv_list("data/reports/results_02_midprice_misses_table.csv")
    print(f"  Loaded {len(mp_misses)} mid-price miss rows")

    print("Loading RESULTS-02 course model gap matrix ...")
    gap_matrix = _load_csv_dict(
        "data/reports/results_02_course_model_gap_matrix.csv", "course"
    )
    print(f"  Loaded {len(gap_matrix)} gap matrix rows")

    # Import base profiles from build_results_02_audit if available
    sys.path.insert(0, "scripts/ops")
    try:
        from build_results_02_audit import _COURSE_PROFILES as _BASE_PROFILES
        print(f"  Imported {len(_BASE_PROFILES)} base course profiles")
    except ImportError:
        _BASE_PROFILES = {}
        print("  WARN: build_results_02_audit import failed — using empty base profiles")

    print()
    print("Running sections ...")

    # --- Run sections ---
    print("  S1: Course registry ...")
    s1 = _s1_course_registry(sigma, course_table, drain_roots, edge_roots)

    print("  S2: Draw priority table ...")
    s2 = _s2_draw_priority(sigma, course_table)

    print("  S3: Pace priority table ...")
    s3 = _s3_pace_priority(sigma, course_table)

    print("  S4: AW cluster deep dive ...")
    s4 = _s4_aw_cluster(sigma, course_table, drain_roots, mp_misses)

    print("  S5: Beverley war book ...")
    s5 = _s5_beverley_war_book(sigma, mp_misses, drain_roots)

    print("  S6: Mid-price 6-10 wound table ...")
    s6 = _s6_midprice_6_10(sigma, mp_misses)

    print("  S7: Feature readiness ...")
    s7 = _s7_feature_readiness()

    print("  S8: External source map ...")
    s8 = _s8_external_source_map()

    print("  S9: Course watchlist ...")
    s9 = _s9_course_watchlist(drain_roots, edge_roots, course_table)

    print("  S10: COURSE-01 design spec ...")
    s10 = _s10_course01_spec()

    print("  S11: Operator brief ...")
    s11 = _s11_operator_brief(s1, s2, s3, s4, s5, s6, s7, s8, s9)

    print()
    print("Writing output files ...")

    # File 1 — Full narrative MD
    p = os.path.join(_REPORTS_DIR, "course_00_course_eyes_completion_pack.md")
    _write_text(p, _md_course_eyes_pack(s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11))
    print(f"  [1/12] {p}")

    # File 2 — Structured JSON
    p = os.path.join(_REPORTS_DIR, "course_00_course_eyes_completion_pack.json")
    _write_json(p, {
        "meta": {
            "script": "build_course_00_audit.py",
            "generated": datetime.utcnow().isoformat(),
            "constraints": _HARD_CONSTRAINTS,
            "final_classifications": _FINAL_CLASSIFICATIONS,
            "status": "REPORT_ONLY",
        },
        "s1_course_registry": s1,
        "s2_draw_priority": s2,
        "s3_pace_priority": s3,
        "s4_aw_cluster": {
            k: v for k, v in s4.items() if k != "track_stats"
        },
        "s4_aw_track_stats": s4.get("track_stats", {}),
        "s5_beverley": {
            k: v for k, v in s5.items() if k != "war_rows"
        },
        "s5_beverley_war_rows": s5.get("war_rows", []),
        "s6_midprice_6_10_summary": {
            "n_total": s6["n_total"],
            "n_from_csv": s6["n_from_csv"],
            "top_courses": s6["top_courses"],
            "status": s6["status"],
        },
        "s6_midprice_6_10_rows": s6["rows"],
        "s7_feature_matrix": s7,
        "s8_external_source_map": s8,
        "s9_watchlist": s9,
        "s10_course01_spec": s10,
        "s11_operator_brief": s11,
    })
    print(f"  [2/12] {p}")

    # File 3 — Draw bias priority CSV
    p = os.path.join(_REPORTS_DIR, "course_00_draw_bias_priority_table.csv")
    _write_csv(p, s2)
    print(f"  [3/12] {p}")

    # File 4 — Pace bias priority CSV
    p = os.path.join(_REPORTS_DIR, "course_00_pace_bias_priority_table.csv")
    _write_csv(p, s3)
    print(f"  [4/12] {p}")

    # File 5 — AW cluster deep dive MD
    p = os.path.join(_REPORTS_DIR, "course_00_aw_cluster_deep_dive.md")
    _write_text(p, _md_aw_cluster(s4))
    print(f"  [5/12] {p}")

    # File 6 — Beverley war book MD
    p = os.path.join(_REPORTS_DIR, "course_00_beverley_war_book.md")
    _write_text(p, _md_beverley_war_book(s5))
    print(f"  [6/12] {p}")

    # File 7 — Mid-price 6-10 wound table CSV
    p = os.path.join(_REPORTS_DIR, "course_00_midprice_6_10_wound_table.csv")
    _write_csv(p, s6["rows"])
    print(f"  [7/12] {p}")

    # File 8 — Feature readiness matrix CSV
    p = os.path.join(_REPORTS_DIR, "course_00_feature_readiness_matrix.csv")
    _write_csv(p, s7)
    print(f"  [8/12] {p}")

    # File 9 — External source field map MD
    p = os.path.join(_REPORTS_DIR, "course_00_external_source_field_map.md")
    _write_text(p, _md_external_source_map(s8))
    print(f"  [9/12] {p}")

    # File 10 — Course watchlist MD
    p = os.path.join(_REPORTS_DIR, "course_00_course_watchlist.md")
    _write_text(p, _md_course_watchlist(s9))
    print(f"  [10/12] {p}")

    # File 11 — COURSE-01 design spec MD
    p = os.path.join(_REPORTS_DIR, "course_00_course_01_design_spec.md")
    _write_text(p, s10)
    print(f"  [11/12] {p}")

    # File 12 — Operator brief MD
    p = os.path.join(_REPORTS_DIR, "course_00_operator_brief.md")
    _write_text(p, s11)
    print(f"  [12/12] {p}")

    print()
    print("=" * 60)
    print("FINAL CLASSIFICATIONS:")
    print("=" * 60)
    for c in _FINAL_CLASSIFICATIONS:
        print(f"  {c}")
    print()
    print("COURSE-00 COMPLETE. REPORT_ONLY. No live changes.")
    print(f"containment_is_not_profit = {containment_is_not_profit}")
    print("=" * 60)


if __name__ == "__main__":
    main()
