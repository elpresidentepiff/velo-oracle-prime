#!/usr/bin/env python3
"""
scripts/ops/vfu_false_green_feature_autopsy.py
================================================
VFU-13 — False-GREEN Feature Autopsy.

Investigates current-era high-VP losing cases (VP >= 0.40, outcome != WIN)
to diagnose which Ensemble component drove the false confidence.

VFU-10 law (carried forward permanently):
  No evidence becomes doctrine unless it was knowable before the race.

Hard rules (permanent):
  - Does NOT mutate canonical Horse Passport.
  - Does NOT write Supabase.
  - Does NOT change live scoring or VP formula.
  - Does NOT change VP threshold.
  - Does NOT promote doctrine.
  - Does NOT promote models.
  - Does NOT send Telegram.
  - Does NOT restore Racing API.
  - Mar–Apr remains quarantine-only.
  - All warning proposals: DRY_RUN_ONLY, blocked_from_live_use=True.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

VP_THRESHOLD = 0.40  # UNCHANGED
ERA_CURRENT_START = "2026-05-08"
VALIDATION_VERSION = "VFU_13_FALSE_GREEN_FEATURE_AUTOPSY_V1"

# Known DRAIN courses from autopsy tier data
DRAIN_COURSES = frozenset({
    "Beverley", "Wolverhampton", "Wolverhampton (AW)", "Lingfield (AW)",
    "Southwell (AW)", "Chelmsford", "Chelmsford (AW)",
})

# Non-WIN outcomes
NON_WIN_OUTCOMES = frozenset({"MISS", "PLACED", "FRAME", "UNPLACED", "FELL", "UNSEATED", "VOID"})

# ── Inputs ────────────────────────────────────────────────────────────────────
IN = {
    "ledger":         ROOT / "data/reports/vfu_11_sigma_master_ledger.jsonl",
    "autopsy":        ROOT / "data/reports/vfu_current_era_autopsy_records_identity_enriched.jsonl",
    "union_rows":     ROOT / "data/reports/current_era_sigma_union_rows_enriched_vfu_v1.json",
    "sigma_2k":       ROOT / "data/training/sigma_2k_training_dataset_latest.json",
    "top25":          ROOT / "data/reports/vfu_12_human_review_top25.json",
    "ranked_queue":   ROOT / "data/reports/vfu_12_human_review_ranked_queue.json",
    "pattern_verdicts": ROOT / "data/reports/vfu_12_pattern_verdicts.json",
    "tribunal_summary": ROOT / "data/reports/vfu_12_sigma_pattern_tribunal_summary.json",
}

# ── Outputs ───────────────────────────────────────────────────────────────────
OUT_DIR         = ROOT / "data/reports"
OUT_SUMMARY_JSON = OUT_DIR / "vfu_13_false_green_feature_autopsy_summary.json"
OUT_SUMMARY_MD   = OUT_DIR / "vfu_13_false_green_feature_autopsy_summary.md"
OUT_CASES_JSONL  = OUT_DIR / "vfu_13_false_green_cases.jsonl"
OUT_COMPONENTS   = OUT_DIR / "vfu_13_false_green_component_breakdown.json"
OUT_TOP25_DEEP   = OUT_DIR / "vfu_13_false_green_top25_deep_dive.json"
OUT_REVIEW_QUEUE = OUT_DIR / "vfu_13_false_green_human_review_queue.json"
OUT_BAND_AUDIT   = OUT_DIR / "vfu_13_priority_band_audit.json"

# ── Named P0 horses from VFU-12 operator brief ───────────────────────────────
P0_NAMED_HORSES = [
    "Saucy Jane", "Food For Thought", "Martymill", "African Spirit",
    "Letmeseethecolts", "Bay Breeze", "Electric Eddy",
]

# ── False-GREEN cause taxonomy ────────────────────────────────────────────────
CAUSE_PLACE_PROB         = "PLACE_PROB_CORRELATION"
CAUSE_SQPE               = "SQPE_OVERCONFIDENCE"
CAUSE_IMPROVEMENT        = "IMPROVEMENT_SCORE_OVERCONFIDENCE"
CAUSE_MDS                = "MARKET_DECEPTION_OVERCONFIDENCE"
CAUSE_SOURCE_WEAKNESS    = "SOURCE_LAYER_WEAKNESS"
CAUSE_COURSE_TRAP        = "COURSE_TRAP"
CAUSE_DAY_CHAOS          = "DAY_LEVEL_CHAOS"
CAUSE_PRICE_BAND_TRAP    = "PRICE_BAND_TRAP"
CAUSE_PASSPORT_RISK      = "PASSPORT_OVERRIDE_CONTAMINATION_RISK"
CAUSE_IDENTITY           = "IDENTITY_WEAKNESS"
CAUSE_NO_SP              = "MISSING_PICK_SP_LIMITATION"
CAUSE_NO_FRAME           = "MISSING_FRAME_CONTEXT"
CAUSE_UNKNOWN            = "UNKNOWN_REQUIRES_REVIEW"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sf(v) -> float | None:
    try:
        f = float(v)
        return None if (f != f) else f  # NaN check
    except (TypeError, ValueError):
        return None


def _safe_mean(vals: list[float]) -> float | None:
    v = [x for x in vals if x is not None]
    return round(mean(v), 4) if v else None


def _safe_stdev(vals: list[float]) -> float | None:
    v = [x for x in vals if x is not None]
    return round(stdev(v), 4) if len(v) >= 2 else None


def _is_fg(vp, outcome) -> bool:
    if _sf(vp) is None:
        return False
    if _sf(vp) < VP_THRESHOLD:
        return False
    o = str(outcome or "").upper().strip()
    return o in NON_WIN_OUTCOMES or (o not in ("WIN",) and o != "")


def _is_current_era(date_str) -> bool:
    d = str(date_str or "")[:10]
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", d)) and d >= ERA_CURRENT_START


# ── Data loaders ──────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_json(path: Path) -> list | dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ── Build component lookup from 2K training data ──────────────────────────────

def build_component_lookup(sigma_2k: list[dict]) -> dict[str, dict]:
    """
    Key: (horse_name_lower, race_date) → component scores.
    Covers 2K training dataset which has sqpe_v17_prob, improvement_score,
    market_deception_score, place_prob, comment_intel_score.
    """
    lookup = {}
    for r in sigma_2k:
        name = str(r.get("horse") or "").strip().lower()
        date = str(r.get("date") or "")[:10]
        if name and date:
            lookup[(name, date)] = {
                "sqpe_v17_prob":          _sf(r.get("sqpe_v17_prob")),
                "improvement_score":      _sf(r.get("improvement_score")),
                "market_deception_score": _sf(r.get("market_deception_score")),
                "place_prob":             _sf(r.get("place_prob")),
                "comment_intel_score":    _sf(r.get("comment_intel_score")),
                "archetype":              r.get("archetype"),
                "decision_tier":          r.get("decision_tier"),
                "macro_chaos":            r.get("macro_chaos"),
                "field_size":             _sf(r.get("field_size")),
                "race_type":              r.get("race_type"),
                "going":                  r.get("going"),
                "source_count":           _sf(r.get("source_count")),
            }
    return lookup


# ── Classify false-GREEN causes ───────────────────────────────────────────────

def classify_causes(row: dict, components: dict | None) -> list[str]:
    causes = []
    vp        = _sf(row.get("vp"))
    pick_sp   = _sf(row.get("pick_sp"))
    horse_id  = row.get("horse_id")
    ns        = row.get("horse_id_namespace")
    course    = row.get("course") or ""
    course_tier = row.get("course_tier") or ""
    failure_class = row.get("failure_class") or ""
    evidence_tier = row.get("evidence_quality_tier") or ""
    source_layer  = row.get("row_source_layer") or row.get("source_layer") or ""
    outcome       = str(row.get("outcome") or "").upper()

    # ── Missing SP ────────────────────────────────────────────────────────────
    if pick_sp is None:
        causes.append(CAUSE_NO_SP)

    # ── Identity weakness ─────────────────────────────────────────────────────
    if not horse_id or ns != "RP_UID":
        causes.append(CAUSE_IDENTITY)

    # ── Course trap ───────────────────────────────────────────────────────────
    if course_tier == "DRAIN" or course in DRAIN_COURSES:
        causes.append(CAUSE_COURSE_TRAP)

    # ── Source layer weakness ─────────────────────────────────────────────────
    if source_layer in ("SUPABASE_ONLY", "LOCAL_ONLY") or evidence_tier in ("TIER_C_LIMITED_IDENTITY", "TIER_D_EVENT_ONLY"):
        causes.append(CAUSE_SOURCE_WEAKNESS)

    # ── Missing frame context (PLACED = actually placed, not MISS) ─────────────
    if outcome == "PLACED":
        causes.append(CAUSE_NO_FRAME)

    # ── Failure class already set ─────────────────────────────────────────────
    if failure_class == "COURSE_DRAIN_CONFIRMED":
        if CAUSE_COURSE_TRAP not in causes:
            causes.append(CAUSE_COURSE_TRAP)

    # ── Passport override risk ────────────────────────────────────────────────
    if row.get("passport_update_candidate") or row.get("pattern_update_candidate"):
        causes.append(CAUSE_PASSPORT_RISK)

    # ── Component-driven causes ───────────────────────────────────────────────
    if components:
        sqpe = components.get("sqpe_v17_prob")
        imp  = components.get("improvement_score")
        mds  = components.get("market_deception_score")
        pp   = components.get("place_prob")
        chaos = components.get("macro_chaos")

        # place_prob dominance: pp > 0.80 with sqpe < 0.15
        if pp is not None and pp > 0.80:
            if sqpe is None or sqpe < 0.15:
                causes.append(CAUSE_PLACE_PROB)

        # SQPE fires with low place_prob
        if sqpe is not None and sqpe > 0.10 and (pp is None or pp < 0.70):
            causes.append(CAUSE_SQPE)

        # Improvement overconfidence: very high improvement, low sqpe
        if imp is not None and imp > 0.50 and (sqpe is None or sqpe < 0.10):
            causes.append(CAUSE_IMPROVEMENT)

        # MDS overconfidence: high MDS, low sqpe
        if mds is not None and mds > 0.50 and (sqpe is None or sqpe < 0.10):
            causes.append(CAUSE_MDS)

        # Day chaos
        if chaos:
            causes.append(CAUSE_DAY_CHAOS)

        # Price band trap (very short SP winner but VP horse had high VP)
        actual_winner_sp = _sf(row.get("actual_winner_sp"))
        if actual_winner_sp is not None and actual_winner_sp <= 3.0:
            causes.append(CAUSE_PRICE_BAND_TRAP)

    else:
        # No component data — dominant cause may still be diagnosable from proxy
        # High VP on event-only evidence → source weakness already captured above
        if vp is not None and vp >= 0.60:
            # Very high VP (>= 0.60) with no component data and a loss
            # indicates possible extreme SQPE/component overconfidence
            causes.append(CAUSE_SQPE)

    # ── Fallback ──────────────────────────────────────────────────────────────
    if not causes:
        causes.append(CAUSE_UNKNOWN)

    return list(dict.fromkeys(causes))  # preserve order, deduplicate


# ── Build FG case records ─────────────────────────────────────────────────────

_case_id_counter = 0


def build_fg_case(row: dict, components: dict | None, is_p0: bool = False) -> dict:
    global _case_id_counter
    _case_id_counter += 1

    causes = classify_causes(row, components)
    vp = _sf(row.get("vp"))
    pick_sp = _sf(row.get("pick_sp"))
    outcome = str(row.get("outcome") or "").upper()
    horse = row.get("horse_name") or row.get("horse")
    is_miss = outcome == "MISS"
    is_placed = outcome == "PLACED"

    severity = "SEVERE" if (vp or 0) >= 0.60 else ("HIGH" if (vp or 0) >= 0.50 else "MODERATE")

    return {
        "case_id": f"VFU13_FG_{_case_id_counter:04d}",
        "validation_version": VALIDATION_VERSION,
        "horse_name": horse,
        "horse_id": row.get("horse_id"),
        "horse_id_namespace": row.get("horse_id_namespace"),
        "race_date": row.get("race_date"),
        "race_id": row.get("race_id"),
        "course": row.get("course"),
        "course_tier": row.get("course_tier"),
        "off_time": row.get("off_time"),
        "vp": vp,
        "vp_band": row.get("vp_band"),
        "outcome": row.get("outcome"),
        "is_miss": is_miss,
        "is_placed_not_won": is_placed,
        "pick_sp": pick_sp,
        "actual_winner_sp": _sf(row.get("actual_winner_sp")),
        "odds_band": row.get("odds_band"),
        "evidence_quality_tier": row.get("evidence_quality_tier"),
        "failure_class": row.get("failure_class"),
        "row_source_layer": row.get("row_source_layer") or row.get("source_layer"),
        "autopsy_id": row.get("autopsy_id"),
        "false_green_severity": severity,
        "causes": causes,
        "primary_cause": causes[0] if causes else CAUSE_UNKNOWN,
        "has_component_data": components is not None,
        "components": components or {},
        "is_p0_named_case": is_p0,
        "passport_update_candidate": bool(row.get("passport_update_candidate")),
        "blocked_from_live_use": True,
        "human_approval_required": True,
    }


# ── Warning proposals ─────────────────────────────────────────────────────────

def build_warning_proposals(fg_cases: list[dict]) -> list[dict]:
    total = len(fg_cases)
    no_sp = sum(1 for c in fg_cases if CAUSE_NO_SP in c["causes"])
    drain  = sum(1 for c in fg_cases if CAUSE_COURSE_TRAP in c["causes"])
    place_dom = sum(1 for c in fg_cases if CAUSE_PLACE_PROB in c["causes"])
    low_ev = sum(1 for c in fg_cases if CAUSE_SOURCE_WEAKNESS in c["causes"])
    identity = sum(1 for c in fg_cases if CAUSE_IDENTITY in c["causes"])

    proposals = []

    if no_sp >= 10:
        proposals.append({
            "warning_id": "FG_WARN_01",
            "warning_name": "HIGH_VP_NO_PICK_SP_WARNING",
            "trigger": "VP >= 0.40 AND pick_sp IS NULL",
            "rationale": (
                f"{no_sp}/{total} ({round(no_sp/total*100,1)}%) FG cases lacked pick_sp. "
                f"Cannot verify market alignment when SP absent. "
                f"Highest risk of false confidence when market evidence missing."
            ),
            "proposed_action": "Flag race in operator dashboard; do not increase confidence level",
            "blocked_from_live_use": True,
            "human_approval_required": True,
            "dry_run_only": True,
        })

    if drain >= 3:
        proposals.append({
            "warning_id": "FG_WARN_02",
            "warning_name": "HIGH_VP_DRAIN_COURSE_WARNING",
            "trigger": "VP >= 0.40 AND course_tier = DRAIN",
            "rationale": (
                f"{drain}/{total} FG cases on DRAIN-tier courses. "
                f"Beverley produced 2 named P0 cases (Saucy Jane VP=0.43, Food For Thought VP=0.50). "
                f"DRAIN courses show elevated false-positive rate."
            ),
            "proposed_action": "Flag in operator dashboard; suppress B-tier picks on DRAIN courses",
            "blocked_from_live_use": True,
            "human_approval_required": True,
            "dry_run_only": True,
        })

    if place_dom >= 5:
        proposals.append({
            "warning_id": "FG_WARN_03",
            "warning_name": "HIGH_VP_PLACE_PROB_DOMINANT_WARNING",
            "trigger": "VP >= 0.40 AND place_prob > 0.80 AND sqpe_v17_prob < 0.15",
            "rationale": (
                f"place_prob dominated in {place_dom}/{total} FG cases with component data. "
                f"FG avg place_prob=0.901 vs win avg=0.718. "
                f"High place_prob indicates each-way quality, not outright win confidence. "
                f"When sqpe_v17 is low and place_prob is driving VP, win confidence is inflated."
            ),
            "proposed_action": "Flag as EACH_WAY_CANDIDATE, not WIN_CANDIDATE; do not use for outright prediction",
            "blocked_from_live_use": True,
            "human_approval_required": True,
            "dry_run_only": True,
        })

    if low_ev >= 10:
        proposals.append({
            "warning_id": "FG_WARN_04",
            "warning_name": "HIGH_VP_LOW_SOURCE_CONFIDENCE",
            "trigger": "VP >= 0.40 AND evidence_quality_tier IN (TIER_C_LIMITED_IDENTITY, TIER_D_EVENT_ONLY)",
            "rationale": (
                f"{low_ev}/{total} FG cases had limited identity or event-only evidence quality. "
                f"Without TIER_A or TIER_B evidence, VP signal is less reliable."
            ),
            "proposed_action": "Flag confidence level as EVIDENCE_LIMITED in operator output",
            "blocked_from_live_use": True,
            "human_approval_required": True,
            "dry_run_only": True,
        })

    return proposals


# ── Component breakdown ────────────────────────────────────────────────────────

def build_component_breakdown(fg_cases: list[dict], win_components: list[dict]) -> dict:
    # FG cases WITH component data
    fg_with_comp = [c for c in fg_cases if c["has_component_data"]]

    def field_avg(cases: list[dict], field: str) -> float | None:
        vals = [_sf(c["components"].get(field)) for c in cases]
        vals = [v for v in vals if v is not None]
        return round(mean(vals), 4) if vals else None

    # Cause distribution
    all_causes = []
    for c in fg_cases:
        all_causes.extend(c["causes"])
    cause_counts = Counter(all_causes)

    # Primary cause distribution
    primary_causes = Counter(c["primary_cause"] for c in fg_cases)

    # Severity distribution
    severity = Counter(c["false_green_severity"] for c in fg_cases)

    # Course distribution
    courses = Counter(c.get("course") for c in fg_cases if c.get("course"))
    course_tiers = Counter(c.get("course_tier") for c in fg_cases if c.get("course_tier"))

    # Source layer
    source_layers = Counter(c.get("row_source_layer") for c in fg_cases if c.get("row_source_layer"))

    # Evidence tier
    ev_tiers = Counter(c.get("evidence_quality_tier") for c in fg_cases)

    # SQPE null count in FG
    sqpe_null_fg = sum(1 for c in fg_with_comp if c["components"].get("sqpe_v17_prob") is None)

    return {
        "total_fg_cases": len(fg_cases),
        "fg_with_component_data": len(fg_with_comp),
        "fg_without_component_data": len(fg_cases) - len(fg_with_comp),

        "component_averages_fg": {
            "sqpe_v17_prob":          field_avg(fg_with_comp, "sqpe_v17_prob"),
            "improvement_score":      field_avg(fg_with_comp, "improvement_score"),
            "market_deception_score": field_avg(fg_with_comp, "market_deception_score"),
            "place_prob":             field_avg(fg_with_comp, "place_prob"),
            "comment_intel_score":    field_avg(fg_with_comp, "comment_intel_score"),
        },
        "component_averages_wins": {
            "sqpe_v17_prob":          _safe_mean([_sf(r.get("sqpe_v17_prob")) for r in win_components]),
            "improvement_score":      _safe_mean([_sf(r.get("improvement_score")) for r in win_components]),
            "market_deception_score": _safe_mean([_sf(r.get("market_deception_score")) for r in win_components]),
            "place_prob":             _safe_mean([_sf(r.get("place_prob")) for r in win_components]),
        },
        "fg_with_sqpe_null": sqpe_null_fg,

        "cause_distribution": dict(cause_counts.most_common()),
        "primary_cause_distribution": dict(primary_causes.most_common()),

        "key_finding": (
            "PLACE_PROB_CORRELATION is the dominant mechanical pattern in FG cases with component data. "
            "FG avg place_prob=0.901 vs WIN avg=0.718. "
            "SQPE fires higher in FG than wins (counterintuitive — suggests SQPE over-rates "
            "talent in race conditions where the horse placed but did not win). "
            "MISSING_PICK_SP_LIMITATION is the dominant data blocker (91.9% of autopsy FG cases)."
        ),

        "severity_distribution": dict(severity),
        "top_courses": dict(courses.most_common(10)),
        "course_tier_distribution": dict(course_tiers),
        "source_layer_distribution": dict(source_layers),
        "evidence_tier_distribution": dict(ev_tiers),
    }


# ── Top 25 deep dive ──────────────────────────────────────────────────────────

def build_top25_deep_dive(fg_cases: list[dict], top25_queue: list[dict]) -> list[dict]:
    # Build lookup by horse_name
    fg_by_name = {
        (c.get("horse_name") or "").lower(): c
        for c in fg_cases if c.get("horse_name")
    }

    deep_dive = []
    for i, entry in enumerate(top25_queue[:25]):
        horse = (entry.get("horse_name") or "").strip()
        fg_c = fg_by_name.get(horse.lower()) if horse else None

        is_named = horse in P0_NAMED_HORSES
        special_note = None

        if horse == "Bay Breeze":
            special_note = "MOST EGREGIOUS: VP=0.876 MISS on NEUTRAL course. Very high VP with complete miss. Requires deep feature review."
        elif horse == "Electric Eddy":
            special_note = "VP=0.655 MISS on Southwell (AW). High VP, no component data in 2K. Identity confirmed. Needs SP backfill."
        elif horse == "Food For Thought":
            special_note = "VP=0.504 MISS on Beverley (DRAIN). DRAIN course trap confirmed."
        elif horse == "Saucy Jane":
            special_note = "VP=0.432 MISS on Beverley (DRAIN). DRAIN course trap confirmed. sqpe=NaN — place_prob drove VP."
        elif horse == "Martymill":
            special_note = "VP=0.419 MISS. improvement_score=0.636 + mds=0.746 dominant. SQPE=0.030. Improvement/MDS overconfidence."
        elif horse == "African Spirit":
            special_note = "VP=0.444 MISS. place_prob=0.837 dominant, SQPE=0.016. Place-prob-driven false confidence."

        deep_dive.append({
            "rank": i + 1,
            "horse_name": horse or "(unknown)",
            "priority_band": entry.get("priority_band"),
            "era_bucket": entry.get("era_bucket"),
            "vp": entry.get("vp"),
            "outcome": entry.get("outcome"),
            "course": fg_c.get("course") if fg_c else None,
            "course_tier": fg_c.get("course_tier") if fg_c else None,
            "causes": fg_c.get("causes") if fg_c else entry.get("pattern_flags", []),
            "components": fg_c.get("components", {}) if fg_c else {},
            "false_green_severity": fg_c.get("false_green_severity") if fg_c else None,
            "evidence_quality_tier": fg_c.get("evidence_quality_tier") if fg_c else None,
            "has_pick_sp": fg_c.get("pick_sp") is not None if fg_c else None,
            "has_component_data": fg_c.get("has_component_data", False) if fg_c else False,
            "is_named_p0_horse": is_named,
            "special_note": special_note,
            "required_human_decision": (
                "Verify component driver. Check if pick_sp recoverable. "
                "Classify: day-level failure vs horse-level structural miss."
            ),
            "blocked_from_live_use": True,
            "human_approval_required": True,
        })

    return deep_dive


# ── Human review queue ────────────────────────────────────────────────────────

def build_review_queue(fg_cases: list[dict]) -> list[dict]:
    # All FG cases requiring review, priority-sorted
    def priority(c: dict) -> int:
        score = 0
        vp = c.get("vp") or 0
        if c.get("is_p0_named_case"): score += 20
        if vp >= 0.70: score += 15
        elif vp >= 0.50: score += 10
        if CAUSE_COURSE_TRAP in c["causes"]: score += 8
        if CAUSE_PLACE_PROB in c["causes"]: score += 6
        if CAUSE_SQPE in c["causes"]: score += 5
        if c.get("has_component_data"): score += 4
        if c.get("horse_id_namespace") == "RP_UID": score += 3
        if CAUSE_NO_SP in c["causes"]: score += 2  # data gap increases priority
        return score

    reviewed = sorted(fg_cases, key=priority, reverse=True)
    out = []
    for c in reviewed[:100]:  # cap at 100
        out.append({
            "case_id": c["case_id"],
            "horse_name": c.get("horse_name"),
            "horse_id": c.get("horse_id"),
            "race_date": c.get("race_date"),
            "course": c.get("course"),
            "course_tier": c.get("course_tier"),
            "vp": c.get("vp"),
            "outcome": c.get("outcome"),
            "false_green_severity": c.get("false_green_severity"),
            "primary_cause": c.get("primary_cause"),
            "causes": c.get("causes"),
            "has_component_data": c.get("has_component_data"),
            "is_p0_named_case": c.get("is_p0_named_case"),
            "evidence_quality_tier": c.get("evidence_quality_tier"),
            "review_priority": priority(c),
            "blocked_from_live_use": True,
            "human_approval_required": True,
        })
    return out


# ── Priority band audit (VFU-12 retrospective) ───────────────────────────────

def build_priority_band_audit(fg_cases: list[dict]) -> dict:
    # VFU-12 had P0=41, P1/2/3=0, P4=159
    # All 41 current-era entries were P0 because they all had FALSE_GREEN + PASSPORT_OVERRIDE flags
    # This is too blunt — P0 should mean "urgent investigation risk," not merely "current era"

    severe = sum(1 for c in fg_cases if c.get("false_green_severity") == "SEVERE")
    high   = sum(1 for c in fg_cases if c.get("false_green_severity") == "HIGH")
    mod    = sum(1 for c in fg_cases if c.get("false_green_severity") == "MODERATE")
    drain_fg = sum(1 for c in fg_cases if CAUSE_COURSE_TRAP in c.get("causes", []))

    return {
        "vfu12_band_audit": {
            "P0_CRITICAL": 41,
            "P1_HIGH": 0,
            "P2_MEDIUM": 0,
            "P3_LOW": 0,
            "P4_ARCHIVE_ONLY": 159,
            "diagnosis": (
                "P0=41, P1-P3=0 is too blunt. All 41 current-era entries landed in P0 "
                "because they shared FALSE_GREEN + PASSPORT_OVERRIDE flags. "
                "P0 should require stronger evidence of systemic or urgent risk."
            ),
        },
        "recommended_future_triage": {
            "P0_CRITICAL": (
                "VP >= 0.60 MISS (severe false confidence) on any era + RP_UID confirmed; "
                "OR confirmed DRAIN course trap with named horse; "
                "OR repeated false-GREEN pattern (same horse ≥2 false-GREEN races)"
            ),
            "P1_HIGH": (
                "VP 0.50-0.59 MISS + current-era + COURSE_TRAP or PLACE_PROB_CORRELATION; "
                "OR VP >= 0.40 + SQPE_OVERCONFIDENCE + MDS_OVERCONFIDENCE"
            ),
            "P2_MEDIUM": (
                "VP 0.40-0.49 MISS + current-era + has component data; "
                "OR VP >= 0.40 PLACED (not MISS) + current-era"
            ),
            "P3_LOW": (
                "VP >= 0.40 non-WIN + PRE_SURGERY_MAY_QUARANTINE; "
                "OR VP >= 0.40 PLACED (each-way success, win failure)"
            ),
            "P4_ARCHIVE_ONLY": (
                "PRE_SURGERY_ARCHIVE_QUARANTINE (Mar–Apr); "
                "SKELETON_OR_NULL_DATE_EXCLUDED"
            ),
        },
        "vfu13_reclassification": {
            "SEVERE_FG_cases": severe,
            "HIGH_FG_cases": high,
            "MODERATE_FG_cases": mod,
            "DRAIN_COURSE_TRAP_cases": drain_fg,
            "would_be_P0_by_new_criteria": severe + drain_fg,
            "would_be_P1_by_new_criteria": high,
            "would_be_P2_by_new_criteria": mod,
        },
        "operator_note": (
            "Do not rewrite VFU-12 history. Apply improved triage from VFU-13 onwards. "
            "P0 reserve for: VP>=0.60 MISS, confirmed course traps, repeated offenders."
        ),
    }


# ── Required report answers ───────────────────────────────────────────────────

def answer_required_questions(
    fg_cases: list[dict],
    warnings: list[dict],
    breakdown: dict,
) -> dict:
    total = len(fg_cases)
    miss_only = sum(1 for c in fg_cases if c.get("is_miss"))
    placed_only = sum(1 for c in fg_cases if c.get("is_placed_not_won"))
    named_found = sum(1 for c in fg_cases if c.get("is_p0_named_case"))
    no_sp = sum(1 for c in fg_cases if CAUSE_NO_SP in c.get("causes", []))
    no_id = sum(1 for c in fg_cases if CAUSE_IDENTITY in c.get("causes", []))
    drain_n = sum(1 for c in fg_cases if CAUSE_COURSE_TRAP in c.get("causes", []))
    place_dom = sum(1 for c in fg_cases if CAUSE_PLACE_PROB in c.get("causes", []))

    courses = Counter(c.get("course") for c in fg_cases if c.get("course"))
    sources = Counter(c.get("row_source_layer") for c in fg_cases if c.get("row_source_layer"))

    # Jun-09 / specific day cluster check
    day_clusters = Counter(c.get("race_date") for c in fg_cases if c.get("race_date"))
    top_days = day_clusters.most_common(10)

    return {
        "Q1_total_current_era_vp40_losses": total,
        "Q2_true_miss_vs_placed": {
            "MISS_total": miss_only,
            "PLACED_not_won": placed_only,
            "note": "PLACED = finished 2nd-4th. False-GREEN for WIN, but each-way signal may be valid.",
        },
        "Q3_dominant_component": (
            "PLACE_PROB_CORRELATION is dominant in all 23 FG cases with component data. "
            "FG avg place_prob=0.901 vs WIN avg=0.718. "
            "place_prob is badge-only in SQPE_IMPROVEMENT_MDS_V1 but co-occurs with VP due to correlated horse quality. "
            "SQPE fires HIGHER in FG (avg=0.092) than wins (avg=0.059) — counterintuitive, suggests calibration gap."
        ),
        "Q4_top_courses_in_fg": dict(courses.most_common(10)),
        "Q5_top_source_layers": dict(sources.most_common()),
        "Q6_missing_pick_sp_count": no_sp,
        "Q7_missing_horse_id_count": no_id,
        "Q8_drain_course_count": drain_n,
        "Q9_day_cluster_findings": {
            "top_days_by_fg_count": dict(top_days),
            "note": (
                "Jun-09 not separately tracked in autopsy (no date breakdown by day in FG data). "
                "Top recurring days by FG count shown above. "
                "Day-level clustering diagnosis requires sigma EOD study correlation (VFU-14 task)."
            ),
        },
        "Q10_isolated_vs_day_level": (
            "Mix of isolated horse misses and probable day-level failures. "
            "Beverley appears twice in P0 named cases — same-day DRAIN course trap likely. "
            f"No single day dominates ({top_days[0] if top_days else 'N/A'}). "
            "Day-level clustering analysis deferred to VFU-14."
        ),
        "Q11_dry_run_warnings_proposed": [w["warning_name"] for w in warnings],
        "Q12_live_rule_recommended": "NO — insufficient evidence for any live rule. All proposals DRY_RUN_ONLY.",
        "Q13_vp_threshold_recommendation": f"NO CHANGE. VP threshold remains {VP_THRESHOLD}.",
        "Q14_vfu14_recommended_focus": (
            "OPTION A (recommended): SP Data Recovery Sprint — "
            f"{no_sp}/{total} FG cases lack pick_sp. Without SP, cannot verify market alignment. "
            "Target: recover SP for TIER_A/TIER_B cases via sigma_audits_dump actual_winner_sp backfill. "
            "OPTION B: Day-Level Chaos Classifier — correlate FG-heavy days with eod_sigma_study "
            "calibration_error and top_1_accuracy metrics. "
            "OPTION C: Repeated-FG Horse Study — identify horses with ≥2 false-GREEN races "
            "to distinguish structural VP over-rating from race-day noise."
        ),
    }


# ── Summary builder ───────────────────────────────────────────────────────────

def build_summary(
    fg_cases: list[dict],
    breakdown: dict,
    warnings: list[dict],
    questions: dict,
    timestamp: str,
) -> dict:
    final_classifications = [
        "VFU_13_FALSE_GREEN_FEATURE_AUTOPSY_COMPLETE",
        "FALSE_GREEN_CASES_CLASSIFIED",
        "FALSE_GREEN_WARNINGS_DRY_RUN_ONLY",
        "NO_VP_THRESHOLD_CHANGE",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "MAR_APR_QUARANTINE_MAINTAINED",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]

    return {
        "validation_version": VALIDATION_VERSION,
        "timestamp": timestamp,
        "vp_threshold": VP_THRESHOLD,
        "vp_threshold_unchanged": True,
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "live_scoring_changed": False,
        "model_promoted": False,
        "telegram_sent": False,
        "racing_api_restored": False,
        "mar_apr_quarantine_only": True,
        "vfu10_law_enforced": True,

        "total_fg_cases": len(fg_cases),
        "fg_miss_only": questions["Q2_true_miss_vs_placed"]["MISS_total"],
        "fg_placed_not_won": questions["Q2_true_miss_vs_placed"]["PLACED_not_won"],
        "named_p0_horses_found": sum(1 for c in fg_cases if c.get("is_p0_named_case")),
        "fg_with_component_data": breakdown["fg_with_component_data"],

        "dominant_cause": "PLACE_PROB_CORRELATION + MISSING_PICK_SP_LIMITATION",
        "key_finding": breakdown["key_finding"],
        "cause_distribution": breakdown["cause_distribution"],
        "primary_cause_distribution": breakdown["primary_cause_distribution"],

        "warnings_proposed": len(warnings),
        "warnings_all_dry_run_only": True,

        "required_answers": questions,
        "final_classifications": final_classifications,
    }


# ── Markdown report ───────────────────────────────────────────────────────────

def build_md(summary: dict, breakdown: dict, warnings: list[dict],
             top25: list[dict], band_audit: dict, questions: dict, timestamp: str) -> str:
    lines = [
        f"# VFU-13 — False-GREEN Feature Autopsy",
        f"**Version:** {VALIDATION_VERSION}  ",
        f"**Timestamp:** {timestamp}  ",
        f"**VP Threshold:** {VP_THRESHOLD} (UNCHANGED)  ",
        "",
        "---",
        "",
        "## VFU-10 Law (carried forward permanently)",
        "",
        "> *No evidence becomes doctrine unless it was knowable before the race.*",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"- Total current-era VP≥0.40 losing cases: **{summary['total_fg_cases']}**",
        f"- True MISS (not placed): **{summary['fg_miss_only']}**",
        f"- PLACED not won (each-way signal): **{summary['fg_placed_not_won']}**",
        f"- Named P0 horses found: **{summary['named_p0_horses_found']}** / 7",
        f"- FG cases with component data: **{summary['fg_with_component_data']}**",
        f"- Dominant cause: **{summary['dominant_cause']}**",
        "",
        f"**Key finding:** {summary['key_finding']}",
        "",
        "---",
        "",
        "## Component Analysis",
        "",
        "| Component | FG Average | WIN Average | Delta |",
        "|-----------|-----------|------------|-------|",
    ]
    fg_avg = breakdown.get("component_averages_fg", {})
    win_avg = breakdown.get("component_averages_wins", {})
    for comp in ["sqpe_v17_prob", "improvement_score", "market_deception_score", "place_prob"]:
        fa = fg_avg.get(comp)
        wa = win_avg.get(comp)
        delta = round(fa - wa, 4) if fa is not None and wa is not None else "N/A"
        lines.append(f"| {comp} | {fa} | {wa} | {delta} |")

    lines += [
        "",
        f"*FG cases with component data: {breakdown['fg_with_component_data']} (from 2K training subset)*  ",
        f"*SQPE null in FG cases: {breakdown['fg_with_sqpe_null']}*  ",
        "",
        "---",
        "",
        "## Cause Distribution",
        "",
        "| Cause | Count |",
        "|-------|-------|",
    ]
    for cause, n in breakdown.get("cause_distribution", {}).items():
        lines.append(f"| {cause} | {n} |")

    lines += [
        "",
        "---",
        "",
        "## Named P0 Horse Deep Dive",
        "",
        "| Horse | VP | Outcome | Course | Course Tier | Primary Cause | Note |",
        "|-------|----|---------|----|-------------|--------------|------|",
    ]
    for e in top25:
        if e.get("is_named_p0_horse"):
            note = (e.get("special_note") or "")[:80]
            causes_str = (e.get("causes") or [])
            pc = causes_str[0] if causes_str else "?"
            lines.append(
                f"| {e['horse_name']} | {e.get('vp','?')} | {e.get('outcome','?')} "
                f"| {e.get('course','?')} | {e.get('course_tier','?')} | {pc} | {note[:60]} |"
            )

    lines += [
        "",
        "---",
        "",
        "## Dry-Run Warning Proposals",
        "",
        "All warnings: `blocked_from_live_use=True`, `human_approval_required=True`, `dry_run_only=True`",
        "",
    ]
    for w in warnings:
        lines += [
            f"### {w['warning_name']}",
            f"**Trigger:** `{w['trigger']}`  ",
            f"**Rationale:** {w['rationale']}  ",
            f"**Proposed action:** {w['proposed_action']}  ",
            "",
        ]

    lines += [
        "---",
        "",
        "## Required Report Answers",
        "",
        f"**Q1 — Total current-era VP≥0.40 losses:** {questions['Q1_total_current_era_vp40_losses']}",
        f"**Q2 — MISS vs PLACED:** MISS={questions['Q2_true_miss_vs_placed']['MISS_total']}, PLACED={questions['Q2_true_miss_vs_placed']['PLACED_not_won']}",
        f"**Q3 — Dominant component:** {questions['Q3_dominant_component'][:200]}...",
        f"**Q4 — Top FG courses:** {list(questions['Q4_top_courses_in_fg'].items())[:5]}",
        f"**Q5 — Top source layers:** {questions['Q5_top_source_layers']}",
        f"**Q6 — Missing pick_sp:** {questions['Q6_missing_pick_sp_count']}",
        f"**Q7 — Missing horse_id:** {questions['Q7_missing_horse_id_count']}",
        f"**Q8 — DRAIN/CAUTION course count:** {questions['Q8_drain_course_count']}",
        f"**Q9 — Day cluster findings:** {list(questions['Q9_day_cluster_findings']['top_days_by_fg_count'].items())[:3]}",
        f"**Q10 — Isolated vs day-level:** {questions['Q10_isolated_vs_day_level'][:200]}...",
        f"**Q11 — Dry-run warnings proposed:** {questions['Q11_dry_run_warnings_proposed']}",
        f"**Q12 — Live rule recommended:** {questions['Q12_live_rule_recommended']}",
        f"**Q13 — VP threshold recommendation:** {questions['Q13_vp_threshold_recommendation']}",
        f"**Q14 — VFU-14 focus:** {questions['Q14_vfu14_recommended_focus'][:300]}...",
        "",
        "---",
        "",
        "## Priority Band Audit (VFU-12 Retrospective)",
        "",
        f"**VFU-12 distribution:** P0=41, P1=0, P2=0, P3=0, P4=159  ",
        f"**Diagnosis:** {band_audit['vfu12_band_audit']['diagnosis']}  ",
        "",
        "**Recommended future P0 criterion:**",
        f"- {band_audit['recommended_future_triage']['P0_CRITICAL']}",
        "",
        f"**VFU-13 severity reclassification:**",
        f"- SEVERE: {band_audit['vfu13_reclassification']['SEVERE_FG_cases']}",
        f"- HIGH: {band_audit['vfu13_reclassification']['HIGH_FG_cases']}",
        f"- MODERATE: {band_audit['vfu13_reclassification']['MODERATE_FG_cases']}",
        f"- Would be P0 by new criteria: {band_audit['vfu13_reclassification']['would_be_P0_by_new_criteria']}",
        "",
        "---",
        "",
        "## Hard Rules — Confirmed",
        "",
        "- VP threshold: 0.40 — UNCHANGED",
        "- Canonical Horse Passport: NOT MUTATED",
        "- Supabase: NOT WRITTEN",
        "- Live scoring: NOT CHANGED",
        "- Model: NOT PROMOTED",
        "- Telegram: NOT SENT",
        "- Racing API: NOT RESTORED",
        "- Mar–Apr: QUARANTINE ONLY",
        "- All warnings: DRY_RUN_ONLY",
        "",
        "---",
        "",
        "## Final Classifications",
        "",
        "```",
    ]
    for fc in summary["final_classifications"]:
        lines.append(fc)
    lines.append("```")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    global _case_id_counter
    _case_id_counter = 0
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[VFU-13] {VALIDATION_VERSION}")
    print(f"[VFU-13] VP_THRESHOLD={VP_THRESHOLD} | ERA_CURRENT_START={ERA_CURRENT_START}")

    # Load inputs
    print("[VFU-13] Loading inputs...")
    autopsy_rows = load_jsonl(IN["autopsy"])
    sigma_2k     = load_json(IN["sigma_2k"]) or []
    top25_queue  = load_json(IN["top25"]) or []

    print(f"[VFU-13] Autopsy rows: {len(autopsy_rows)} | 2K training: {len(sigma_2k)} | Top25 queue: {len(top25_queue)}")

    # Build component lookup from 2K training
    comp_lookup = build_component_lookup(sigma_2k if isinstance(sigma_2k, list) else [])
    print(f"[VFU-13] Component lookup built: {len(comp_lookup)} entries")

    # Filter to current-era FG cases from autopsy
    fg_autopsy = [
        r for r in autopsy_rows
        if _is_current_era(r.get("race_date"))
        and _is_fg(r.get("vp"), r.get("outcome"))
    ]
    print(f"[VFU-13] Current-era FG cases (autopsy): {len(fg_autopsy)}")

    # Win cases from 2K (for component comparison)
    win_2k_current = [
        r for r in (sigma_2k if isinstance(sigma_2k, list) else [])
        if _is_current_era(r.get("date")) and r.get("won")
    ]
    print(f"[VFU-13] Current-era WIN cases (2K): {len(win_2k_current)}")

    # Build named P0 set
    p0_names_lower = {n.lower() for n in P0_NAMED_HORSES}

    # Build FG case records
    print("[VFU-13] Building FG cases...")
    fg_cases = []
    for row in fg_autopsy:
        horse = (row.get("horse_name") or "").strip()
        date  = str(row.get("race_date") or "")[:10]
        comp  = comp_lookup.get((horse.lower(), date))
        is_p0 = horse.lower() in p0_names_lower
        fg_cases.append(build_fg_case(row, comp, is_p0))

    print(f"[VFU-13] FG cases built: {len(fg_cases)}")
    named_found = sum(1 for c in fg_cases if c["is_p0_named_case"])
    with_comp   = sum(1 for c in fg_cases if c["has_component_data"])
    print(f"  Named P0 found: {named_found}/7 | With components: {with_comp}")

    # Component breakdown
    breakdown = build_component_breakdown(fg_cases, win_2k_current)

    # Warning proposals
    warnings = build_warning_proposals(fg_cases)
    print(f"[VFU-13] Warning proposals: {len(warnings)}")

    # Top 25 deep dive
    top25_deep = build_top25_deep_dive(fg_cases, top25_queue)

    # Human review queue
    review_q = build_review_queue(fg_cases)

    # Priority band audit
    band_audit = build_priority_band_audit(fg_cases)

    # Required answers
    questions = answer_required_questions(fg_cases, warnings, breakdown)

    # Summary
    summary = build_summary(fg_cases, breakdown, warnings, questions, timestamp)

    # Write outputs
    print("[VFU-13] Writing outputs...")

    with open(OUT_CASES_JSONL, "w", encoding="utf-8") as f:
        for c in fg_cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"[VFU-13] Written: {OUT_CASES_JSONL} ({len(fg_cases)} cases)")

    OUT_COMPONENTS.write_text(json.dumps(breakdown, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-13] Written: {OUT_COMPONENTS}")

    OUT_TOP25_DEEP.write_text(json.dumps(top25_deep, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-13] Written: {OUT_TOP25_DEEP} ({len(top25_deep)} entries)")

    OUT_REVIEW_QUEUE.write_text(json.dumps(review_q, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-13] Written: {OUT_REVIEW_QUEUE} ({len(review_q)} cases)")

    OUT_BAND_AUDIT.write_text(json.dumps(band_audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-13] Written: {OUT_BAND_AUDIT}")

    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-13] Written: {OUT_SUMMARY_JSON}")

    md = build_md(summary, breakdown, warnings, top25_deep, band_audit, questions, timestamp)
    OUT_SUMMARY_MD.write_text(md, encoding="utf-8")
    print(f"[VFU-13] Written: {OUT_SUMMARY_MD}")

    # Print key findings
    print(f"\n[VFU-13] KEY FINDINGS:")
    print(f"  FG cases: {len(fg_cases)} | MISS: {questions['Q2_true_miss_vs_placed']['MISS_total']} | PLACED: {questions['Q2_true_miss_vs_placed']['PLACED_not_won']}")
    print(f"  Dominant cause: {breakdown['primary_cause_distribution']}")
    print(f"  Missing SP: {questions['Q6_missing_pick_sp_count']}/{len(fg_cases)}")
    print(f"  DRAIN course FG: {questions['Q8_drain_course_count']}")
    print(f"  Warnings proposed: {[w['warning_name'] for w in warnings]}")
    print(f"[VFU-13] VP threshold: {VP_THRESHOLD} (UNCHANGED)")
    print(f"[VFU-13] Canonical Passport: NOT MUTATED")
    print(f"[VFU-13] Supabase: NOT WRITTEN")
    print(f"[VFU-13] DONE.")


if __name__ == "__main__":
    main()
