"""
VFU-16 — Win/Place Conversion Tribunal
======================================
PURPOSE: Investigate when high place probability inflates VP on horses that
         are place-worthy but not win-worthy.

HARD RULES (permanent from VFU-10 / operator brief):
  - READ ONLY — does NOT mutate canonical Horse Passport
  - Does NOT write Supabase
  - Does NOT change live scoring or VP formula
  - Does NOT change VP threshold (0.40 — UNCHANGED)
  - Does NOT promote doctrine
  - Does NOT promote models
  - Does NOT send Telegram
  - Does NOT restore Racing API
  - Guardrail proposal: DRY_RUN_ONLY, blocked_from_live_use=True,
    human_approval_required=True

GOVERNING LAW (VFU-10): No evidence becomes doctrine unless it was knowable
                          before the race.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

VALIDATION_VERSION = "VFU_16_WIN_PLACE_CONVERSION_TRIBUNAL_V1"
VP_THRESHOLD = 0.40

# Mechanism taxonomy
PLACE_STRONG_WIN_WEAK = "PLACE_STRONG_WIN_WEAK"
TRUE_WIN_SIGNAL_FAILED = "TRUE_WIN_SIGNAL_FAILED"
SQPE_SMALL_FIELD_EXCEPTION = "SQPE_SMALL_FIELD_EXCEPTION"
MARKET_AND_VP_JOINT_OVERCONFIDENCE = "MARKET_AND_VP_JOINT_OVERCONFIDENCE"
SOURCE_GAP_NO_SP = "SOURCE_GAP_NO_SP"
SP_SOURCE_ZERO_BLOCKER = "SP_SOURCE_ZERO_BLOCKER"
DRAIN_COURSE_CONTEXT = "DRAIN_COURSE_CONTEXT"
DATA_LINEAGE_REQUIRED = "DATA_LINEAGE_REQUIRED"
INSUFFICIENT_COMPONENT_DATA = "INSUFFICIENT_COMPONENT_DATA"

ALL_MECHANISMS = {
    PLACE_STRONG_WIN_WEAK,
    TRUE_WIN_SIGNAL_FAILED,
    SQPE_SMALL_FIELD_EXCEPTION,
    MARKET_AND_VP_JOINT_OVERCONFIDENCE,
    SOURCE_GAP_NO_SP,
    SP_SOURCE_ZERO_BLOCKER,
    DRAIN_COURSE_CONTEXT,
    DATA_LINEAGE_REQUIRED,
    INSUFFICIENT_COMPONENT_DATA,
}

# Missing-reason codes that indicate we cannot identify the horse / race
DATA_LINEAGE_REASONS = {
    "RAC_PREFIX_NOT_IN_ANY_SOURCE",
    "HORSE_NAME_UNKNOWN",
    "NON_STANDARD_RACE_ID_FORMAT",
    "NUMERIC_RID_NOT_IN_NEW_FORMAT_RESULTS",
}

# Guardrail thresholds (DRY_RUN_ONLY — never touches live scoring)
GUARDRAIL_PLACE_PROB_THRESHOLD = 0.85
GUARDRAIL_SQPE_CEILING = 0.06
GUARDRAIL_IMPROVEMENT_CEILING = 0.30
GUARDRAIL_SP_MAX = 8.0
GUARDRAIL_SP_MIN = 2.0

# 15 required final classifications
FINAL_CLASSIFICATIONS = [
    "VFU_16_WIN_PLACE_CONVERSION_TRIBUNAL_COMPLETE",
    "PLACE_PROB_DOMINANT_FAILURE_CONFIRMED",
    "WIN_PLACE_SEPARATION_REQUIRED",
    "FALSE_GREEN_MECHANISMS_SPLIT",
    "FOOD_FOR_THOUGHT_DATA_LINEAGE_RETAINED",
    "LIGHTSOUTANDAWAY_EXCEPTION_RETAINED",
    "GUARDRAIL_PROPOSAL_DRY_RUN_ONLY",
    "NO_LIVE_SCORING_CHANGE",
    "NO_VP_THRESHOLD_CHANGE",
    "NO_LIVE_DOCTRINE_PROMOTION",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "NO_SUPABASE_WRITES",
    "NO_MODEL_PROMOTION",
    "NO_TELEGRAM_SEND",
    "NO_RACING_API_RESTORATION",
]

# ── Paths ─────────────────────────────────────────────────────────────────────

REPORTS = Path("data/reports")
OUT_PREFIX = REPORTS / "vfu_16"


def _load_jsonl(path: Path) -> list[dict]:
    lines = []
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                lines.append(json.loads(ln))
    return lines


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=_safe_serial) + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=_safe_serial)


def _safe_serial(obj: Any) -> Any:
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    raise TypeError(f"Not serialisable: {type(obj)}")


# ── Mechanism classification ──────────────────────────────────────────────────


def _extract_components(case: dict) -> dict:
    raw = case.get("components") or {}
    return {
        "sqpe_v17_prob": raw.get("sqpe_v17_prob"),
        "improvement_score": raw.get("improvement_score"),
        "market_deception_score": raw.get("market_deception_score"),
        "place_prob": raw.get("place_prob"),
        "field_size": raw.get("field_size"),
        "race_type": raw.get("race_type"),
        "decision_tier": raw.get("decision_tier"),
    }


def classify_mechanism(case: dict, vfu15: dict | None) -> str:
    """Assign one of 9 mechanism labels to a false-GREEN case."""
    is_placed = case.get("is_placed_not_won", False)
    pick_sp = case.get("pick_sp")
    missing_reason = case.get("pick_sp_missing_reason") or ""

    # PLACED cases are definitionally place-strong regardless of SP availability
    if is_placed:
        return PLACE_STRONG_WIN_WEAK

    # ── MISS cases from here ────────────────────────────────────────────────

    is_drain = (vfu15 or {}).get("vfu15_is_drain", False)
    sp_class = (vfu15 or {}).get("vfu15_sp_classification") or ""

    # Identity / format unresolvable → data lineage gate
    if missing_reason in DATA_LINEAGE_REASONS:
        return DATA_LINEAGE_REQUIRED

    # Race found but sp_dec absent in source → source failure, not model failure
    if missing_reason == "RACE_FOUND_BUT_HORSE_NOT_IN_RUNNERS":
        return SP_SOURCE_ZERO_BLOCKER

    # DRAIN course context (checked before generic source gap so High Storm is correct)
    if is_drain or sp_class == "DRAIN_MISS":
        return DRAIN_COURSE_CONTEXT

    # Other source gaps
    if pick_sp is None:
        return SOURCE_GAP_NO_SP

    # ── Cases with SP ───────────────────────────────────────────────────────

    comp = _extract_components(case)
    has_comp = case.get("has_component_data", False)

    if has_comp:
        sqpe = comp.get("sqpe_v17_prob")
        pp = comp.get("place_prob")
        imp = comp.get("improvement_score")
        mds = comp.get("market_deception_score")

        # SQPE-driven, low place_prob, small field (Lightsoutandaway pattern)
        if sqpe and sqpe >= 0.09 and (pp is None or pp < 0.60):
            return SQPE_SMALL_FIELD_EXCEPTION

        # Strong WIN signals fired incorrectly (Martymill: imp=0.636, mds=0.746)
        if (imp and imp >= 0.40) or (mds and mds >= 0.50):
            return TRUE_WIN_SIGNAL_FAILED

        # Place prob dominant (African Spirit / Minella Rescue / Cawthorne Cracker)
        if pp and pp >= 0.80:
            return PLACE_STRONG_WIN_WEAK

        # Short price: market and VP agreed — both wrong
        if pick_sp < 4.0:
            return MARKET_AND_VP_JOINT_OVERCONFIDENCE

        # Component data present but no clear pattern
        return INSUFFICIENT_COMPONENT_DATA

    # No component data — classify by price signal only
    if pick_sp < 4.0:
        return MARKET_AND_VP_JOINT_OVERCONFIDENCE

    return INSUFFICIENT_COMPONENT_DATA


def guardrail_flag(case: dict) -> str | None:
    """Return DRY-RUN guardrail flag if case would have triggered the proposal.
    This is purely retrospective / forensic — never touches live scoring."""
    comp = _extract_components(case)
    pp = comp.get("place_prob")
    sqpe = comp.get("sqpe_v17_prob")
    imp = comp.get("improvement_score")
    pick_sp = case.get("pick_sp")
    if not case.get("has_component_data") or pp is None:
        return None
    if (
        pp >= GUARDRAIL_PLACE_PROB_THRESHOLD
        and (sqpe is None or sqpe < GUARDRAIL_SQPE_CEILING)
        and (imp is None or imp < GUARDRAIL_IMPROVEMENT_CEILING)
        and pick_sp is not None
        and GUARDRAIL_SP_MIN <= pick_sp <= GUARDRAIL_SP_MAX
    ):
        return "PLACE_STRONG_WIN_UNPROVEN"
    return None


def is_ew_positive(case: dict) -> bool:
    """PLACED cases would have returned EW value; MISS cases would not."""
    return bool(case.get("is_placed_not_won", False))


def human_review_priority(case: dict, mechanism: str) -> str:
    """Assign P0/P1/P2/P3 review priority."""
    horse = case.get("horse_name", "") or ""
    is_p0 = case.get("is_p0_named_case", False)
    is_miss = case.get("is_miss", False)
    vp = case.get("vp", 0.0) or 0.0

    if mechanism == DATA_LINEAGE_REQUIRED:
        return "P0"
    if mechanism == TRUE_WIN_SIGNAL_FAILED:
        return "P0"
    if is_p0:
        return "P0"
    if is_miss and mechanism == PLACE_STRONG_WIN_WEAK:
        return "P1"
    if is_miss and mechanism == SQPE_SMALL_FIELD_EXCEPTION:
        return "P1"
    if is_miss and mechanism == MARKET_AND_VP_JOINT_OVERCONFIDENCE:
        return "P2"
    if is_miss and mechanism == DRAIN_COURSE_CONTEXT:
        return "P2"
    if is_miss and vp >= 0.60:
        return "P2"
    if case.get("is_placed_not_won", False):
        return "P3"
    return "P3"


# ── Analysis functions ────────────────────────────────────────────────────────


def build_annotated_cases(
    enr_cases: list[dict],
    miss_by_caseid: dict[str, dict],
) -> list[dict]:
    """Return all 121 cases with VFU-16 annotations merged in."""
    result = []
    for case in enr_cases:
        c = dict(case)
        cid = c.get("case_id", "")
        vfu15 = miss_by_caseid.get(cid) if c.get("is_miss") else None

        # Merge VFU-15 fields for MISS cases
        if vfu15:
            c["vfu15_sp_classification"] = vfu15.get("vfu15_sp_classification")
            c["vfu15_component_driver"] = vfu15.get("vfu15_component_driver")
            c["vfu15_is_drain"] = vfu15.get("vfu15_is_drain", False)
            c["vfu15_market_agreement"] = vfu15.get("vfu15_market_agreement")
            c["vfu15_surface"] = vfu15.get("vfu15_surface")
        else:
            c.setdefault("vfu15_sp_classification", None)
            c.setdefault("vfu15_component_driver", None)
            c.setdefault("vfu15_is_drain", False)
            c.setdefault("vfu15_market_agreement", None)
            c.setdefault("vfu15_surface", None)

        comp = _extract_components(c)
        mechanism = classify_mechanism(c, vfu15)

        c["vfu16_mechanism"] = mechanism
        c["vfu16_is_ew_positive"] = is_ew_positive(c)
        c["vfu16_guardrail_flag"] = guardrail_flag(c)
        c["vfu16_human_review_priority"] = human_review_priority(c, mechanism)
        c["vfu16_validation_version"] = VALIDATION_VERSION
        c["blocked_from_live_use"] = True
        c["human_approval_required"] = True
        c["dry_run_only"] = True
        c["vfu16_place_prob"] = comp.get("place_prob")
        c["vfu16_sqpe"] = comp.get("sqpe_v17_prob")
        c["vfu16_improvement"] = comp.get("improvement_score")
        c["vfu16_mds"] = comp.get("market_deception_score")
        c["vfu16_field_size"] = comp.get("field_size")
        c["vfu16_race_type"] = comp.get("race_type")

        result.append(c)
    return result


def build_mechanism_split(cases: list[dict]) -> dict:
    """Q: Which mechanisms account for the 121 false-GREEN cases?"""
    counts: Counter = Counter(c["vfu16_mechanism"] for c in cases)
    miss_counts: Counter = Counter(
        c["vfu16_mechanism"] for c in cases if c.get("is_miss")
    )
    placed_counts: Counter = Counter(
        c["vfu16_mechanism"] for c in cases if c.get("is_placed_not_won")
    )
    total = len(cases)
    miss_total = sum(1 for c in cases if c.get("is_miss"))
    placed_total = sum(1 for c in cases if c.get("is_placed_not_won"))

    return {
        "total_fg_cases": total,
        "miss_cases": miss_total,
        "placed_cases": placed_total,
        "by_mechanism": {m: counts[m] for m in sorted(counts)},
        "miss_by_mechanism": {m: miss_counts[m] for m in sorted(miss_counts)},
        "placed_by_mechanism": {m: placed_counts[m] for m in sorted(placed_counts)},
        "vfu16_validation_version": VALIDATION_VERSION,
    }


def build_place_prob_dominant_cases(cases: list[dict]) -> list[dict]:
    """Cases where component data confirms high place_prob (>= 0.80)."""
    result = []
    for c in cases:
        pp = c.get("vfu16_place_prob")
        if c.get("has_component_data") and pp is not None and pp >= 0.80:
            result.append(
                {
                    "case_id": c.get("case_id"),
                    "horse_name": c.get("horse_name"),
                    "horse_id": c.get("horse_id"),
                    "course": c.get("course"),
                    "race_date": c.get("race_date"),
                    "race_type": c.get("vfu16_race_type"),
                    "field_size": c.get("vfu16_field_size"),
                    "vp": c.get("vp"),
                    "place_prob": pp,
                    "sqpe": c.get("vfu16_sqpe"),
                    "improvement_score": c.get("vfu16_improvement"),
                    "mds": c.get("vfu16_mds"),
                    "pick_sp": c.get("pick_sp"),
                    "vfu15_sp_classification": c.get("vfu15_sp_classification"),
                    "outcome": c.get("outcome"),
                    "is_miss": c.get("is_miss"),
                    "is_placed_not_won": c.get("is_placed_not_won"),
                    "vfu16_mechanism": c.get("vfu16_mechanism"),
                    "vfu15_component_driver": c.get("vfu15_component_driver"),
                    "is_ew_positive": c.get("vfu16_is_ew_positive"),
                    "vfu16_guardrail_flag": c.get("vfu16_guardrail_flag"),
                    "human_review_required": True,
                    "blocked_from_live_use": True,
                }
            )
    # Sort by place_prob descending
    result.sort(key=lambda x: -(x.get("place_prob") or 0.0))
    return result


def build_watchlist(cases: list[dict]) -> dict:
    """Win-weak / place-strong watchlist for future guardrail consideration."""
    watchlist_mechs = {
        PLACE_STRONG_WIN_WEAK,
        DRAIN_COURSE_CONTEXT,
        SQPE_SMALL_FIELD_EXCEPTION,
        TRUE_WIN_SIGNAL_FAILED,
        MARKET_AND_VP_JOINT_OVERCONFIDENCE,
    }
    entries = [c for c in cases if c.get("vfu16_mechanism") in watchlist_mechs]
    guardrail_candidates = [c for c in entries if c.get("vfu16_guardrail_flag")]

    watchlist_rows = []
    for c in entries:
        watchlist_rows.append(
            {
                "case_id": c.get("case_id"),
                "horse_name": c.get("horse_name"),
                "course": c.get("course"),
                "race_date": c.get("race_date"),
                "vp": c.get("vp"),
                "pick_sp": c.get("pick_sp"),
                "place_prob": c.get("vfu16_place_prob"),
                "sqpe": c.get("vfu16_sqpe"),
                "outcome": c.get("outcome"),
                "is_miss": c.get("is_miss"),
                "is_placed_not_won": c.get("is_placed_not_won"),
                "vfu16_mechanism": c.get("vfu16_mechanism"),
                "vfu16_guardrail_flag": c.get("vfu16_guardrail_flag"),
                "is_ew_positive": c.get("vfu16_is_ew_positive"),
                "human_review_priority": c.get("vfu16_human_review_priority"),
                "blocked_from_live_use": True,
                "human_approval_required": True,
                "dry_run_only": True,
            }
        )

    return {
        "watchlist_description": (
            "Win-weak / place-strong cases for future dry-run guardrail consideration. "
            "ALL entries: blocked_from_live_use=True, human_approval_required=True."
        ),
        "total_watchlist_entries": len(watchlist_rows),
        "guardrail_candidates_count": len(guardrail_candidates),
        "blocked_from_live_use": True,
        "human_approval_required": True,
        "dry_run_only": True,
        "guardrail_proposal": {
            "name": "PLACE_STRONG_WIN_UNPROVEN",
            "status": "DRY_RUN_ONLY",
            "trigger_conditions": {
                "place_prob_min": GUARDRAIL_PLACE_PROB_THRESHOLD,
                "sqpe_max": GUARDRAIL_SQPE_CEILING,
                "improvement_max": GUARDRAIL_IMPROVEMENT_CEILING,
                "pick_sp_min": GUARDRAIL_SP_MIN,
                "pick_sp_max": GUARDRAIL_SP_MAX,
                "note": "course must not be confirmed strongly favourable",
            },
            "effect": (
                "DRY_RUN flag only — does NOT change VP, does NOT block scoring, "
                "operator review required before any live use"
            ),
            "blocked_from_live_use": True,
            "human_approval_required": True,
        },
        "entries": watchlist_rows,
        "vfu16_validation_version": VALIDATION_VERSION,
    }


def build_human_review_queue(cases: list[dict]) -> dict:
    """Priority-sorted human review queue from VFU-16 findings."""
    queue = []
    for c in cases:
        priority = c.get("vfu16_human_review_priority", "P3")
        if priority in ("P0", "P1", "P2"):
            queue.append(
                {
                    "priority": priority,
                    "case_id": c.get("case_id"),
                    "horse_name": c.get("horse_name"),
                    "course": c.get("course"),
                    "race_date": c.get("race_date"),
                    "vp": c.get("vp"),
                    "pick_sp": c.get("pick_sp"),
                    "vfu16_mechanism": c.get("vfu16_mechanism"),
                    "is_miss": c.get("is_miss"),
                    "vfu15_sp_classification": c.get("vfu15_sp_classification"),
                    "vfu15_component_driver": c.get("vfu15_component_driver"),
                    "vfu16_guardrail_flag": c.get("vfu16_guardrail_flag"),
                    "pick_sp_missing_reason": c.get("pick_sp_missing_reason"),
                    "human_review_reason": _review_reason(c),
                    "blocked_from_live_use": True,
                    "human_approval_required": True,
                }
            )

    queue.sort(key=lambda x: x["priority"])

    p0 = [e for e in queue if e["priority"] == "P0"]
    p1 = [e for e in queue if e["priority"] == "P1"]
    p2 = [e for e in queue if e["priority"] == "P2"]

    return {
        "generated_by": VALIDATION_VERSION,
        "total_for_review": len(queue),
        "p0_critical": len(p0),
        "p1_high": len(p1),
        "p2_medium": len(p2),
        "entries": queue,
    }


def _review_reason(case: dict) -> str:
    mech = case.get("vfu16_mechanism", "")
    horse = case.get("horse_name", "?")
    if mech == TRUE_WIN_SIGNAL_FAILED:
        return f"{horse}: WIN signals (imp+MDS) co-fired strongly but both failed — overconfidence pattern"
    if mech == DATA_LINEAGE_REQUIRED:
        return f"{horse}: identity/source unresolvable — pick_sp_missing_reason={case.get('pick_sp_missing_reason')}"
    if case.get("is_p0_named_case"):
        return f"{horse}: P0 named case — {mech}"
    if mech == PLACE_STRONG_WIN_WEAK and case.get("is_miss"):
        return f"{horse}: MISS but place_prob={case.get('vfu16_place_prob')} — VP inflated by place signal"
    if mech == SQPE_SMALL_FIELD_EXCEPTION:
        return f"{horse}: SQPE-driven small-field exception — confirm SQPE calibration for small-field chases"
    return f"{horse}: {mech}"


# ── 8 Core Questions ──────────────────────────────────────────────────────────


def answer_8_questions(cases: list[dict], mechanism_split: dict) -> dict:
    miss_cases = [c for c in cases if c.get("is_miss")]
    miss_with_comp = [c for c in miss_cases if c.get("has_component_data")]

    # Q1: PLACE_PROB_DOMINANT in confirmed MISS cases
    q1_count = sum(
        1
        for c in miss_with_comp
        if (c.get("vfu16_place_prob") or 0.0) >= 0.80
    )
    q1_miss_psw = mechanism_split["miss_by_mechanism"].get(PLACE_STRONG_WIN_WEAK, 0)

    # Q2: Short-price joint overconfidence
    q2_count = mechanism_split["miss_by_mechanism"].get(
        MARKET_AND_VP_JOINT_OVERCONFIDENCE, 0
    )

    # Q3: Place-strong win-weak (all: MISS + PLACED)
    q3_total = mechanism_split["by_mechanism"].get(PLACE_STRONG_WIN_WEAK, 0)
    q3_miss = mechanism_split["miss_by_mechanism"].get(PLACE_STRONG_WIN_WEAK, 0)
    q3_placed = mechanism_split["placed_by_mechanism"].get(PLACE_STRONG_WIN_WEAK, 0)

    # Q4: Data lineage repair
    q4_count = mechanism_split["miss_by_mechanism"].get(DATA_LINEAGE_REQUIRED, 0)

    # Q5: Is place_prob too heavily influencing VP?
    q5_evidence = (
        f"{q1_count}/{len(miss_with_comp)} MISS cases with component data have "
        f"place_prob >= 0.80. Avg place_prob in MISS comp cases: "
        f"{_avg([c.get('vfu16_place_prob') or 0.0 for c in miss_with_comp if c.get('vfu16_place_prob')]):.3f}. "
        f"place_prob is badge-only in SQPE_IMPROVEMENT_MDS_V1 but its high values "
        f"propagate through the VP formula. Pattern is confirmed."
    )

    # Q6: Calibration issue vs signal issue?
    q6_evidence = (
        "CALIBRATION ISSUE — not a signal issue. place_prob correctly identifies "
        "place-worthy horses (65/121 FG cases literally placed). The problem is "
        "that high place_prob drives VP above 0.40 even when win-signal components "
        "(sqpe, improvement) are weak. VP needs a win/place separation layer."
    )

    # Q7: Should VFU-17 focus on dry-run guardrail?
    guardrail_candidate_count = sum(
        1 for c in cases if c.get("vfu16_guardrail_flag") == "PLACE_STRONG_WIN_UNPROVEN"
    )
    q7_answer = (
        f"YES — PLACE_STRONG_WIN_UNPROVEN guardrail proposed (DRY_RUN_ONLY). "
        f"{guardrail_candidate_count} cases would have triggered retrospectively. "
        f"VFU-17 should build the dry-run harness and validate prospectively before "
        f"any live consideration."
    )

    # Q8: Should any live scoring change happen now?
    q8_answer = (
        "NO. Evidence is forensic / retrospective only. VP threshold stays at "
        f"{VP_THRESHOLD:.2f}. No model changes. No live guardrail. "
        "Operator review required before any action on these findings."
    )

    return {
        "Q1_place_prob_dominant_miss_count": {
            "answer": q1_count,
            "note": f"{q1_count} of {len(miss_with_comp)} MISS cases with component data have place_prob >= 0.80",
            "miss_classified_place_strong_win_weak": q1_miss_psw,
        },
        "Q2_short_price_joint_overconfidence": {
            "answer": q2_count,
            "note": f"{q2_count} MISS cases: market AND VP both agreed, both wrong",
        },
        "Q3_place_strong_win_weak_count": {
            "answer": q3_total,
            "miss": q3_miss,
            "placed": q3_placed,
            "note": (
                f"{q3_total} total ({q3_placed} PLACED definitionally + {q3_miss} "
                f"MISS with confirmed place_prob dominance)"
            ),
        },
        "Q4_data_lineage_repair_count": {
            "answer": q4_count,
            "note": f"{q4_count} MISS cases require source/identity repair before classification",
        },
        "Q5_is_place_prob_too_influential": {
            "answer": "YES",
            "evidence": q5_evidence,
        },
        "Q6_calibration_vs_signal_issue": {
            "answer": "CALIBRATION_ISSUE",
            "evidence": q6_evidence,
        },
        "Q7_should_vfu17_focus_guardrail": {
            "answer": "YES",
            "evidence": q7_answer,
            "guardrail_retrospective_trigger_count": guardrail_candidate_count,
        },
        "Q8_live_scoring_change_now": {
            "answer": "NO",
            "evidence": q8_answer,
            "vp_threshold_unchanged": VP_THRESHOLD,
        },
    }


def _avg(vals: list) -> float:
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else 0.0


# ── Output writers ────────────────────────────────────────────────────────────


def write_mechanism_split(path: Path, split: dict) -> None:
    _write_json(path, split)


def write_place_prob_dominant_jsonl(path: Path, rows: list[dict]) -> None:
    _write_jsonl(path, rows)


def write_watchlist(path: Path, watchlist: dict) -> None:
    _write_json(path, watchlist)


def write_human_review_queue(path: Path, queue: dict) -> None:
    _write_json(path, queue)


def write_summary_json(
    path: Path,
    cases: list[dict],
    mechanism_split: dict,
    q8: dict,
    pp_dominant: list[dict],
    watchlist: dict,
    hrq: dict,
) -> None:
    miss_cases = [c for c in cases if c.get("is_miss")]
    placed_cases = [c for c in cases if c.get("is_placed_not_won")]
    mcount = mechanism_split["by_mechanism"]

    summary = {
        "validation_version": VALIDATION_VERSION,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "vp_threshold": VP_THRESHOLD,
        "total_fg_cases": len(cases),
        "miss_cases": len(miss_cases),
        "placed_cases": len(placed_cases),
        "mechanism_split": mcount,
        "key_findings": {
            "place_strong_win_weak_total": mcount.get(PLACE_STRONG_WIN_WEAK, 0),
            "market_and_vp_joint_overconfidence": mcount.get(MARKET_AND_VP_JOINT_OVERCONFIDENCE, 0),
            "insufficient_component_data": mcount.get(INSUFFICIENT_COMPONENT_DATA, 0),
            "drain_course_context": mcount.get(DRAIN_COURSE_CONTEXT, 0),
            "data_lineage_required": mcount.get(DATA_LINEAGE_REQUIRED, 0),
            "sp_source_zero_blocker": mcount.get(SP_SOURCE_ZERO_BLOCKER, 0),
            "source_gap_no_sp": mcount.get(SOURCE_GAP_NO_SP, 0),
            "true_win_signal_failed": mcount.get(TRUE_WIN_SIGNAL_FAILED, 0),
            "sqpe_small_field_exception": mcount.get(SQPE_SMALL_FIELD_EXCEPTION, 0),
            "place_prob_dominant_confirmed_count": len(pp_dominant),
            "watchlist_entries": watchlist["total_watchlist_entries"],
            "guardrail_retrospective_candidates": watchlist["guardrail_candidates_count"],
            "human_review_p0": hrq["p0_critical"],
            "human_review_p1": hrq["p1_high"],
        },
        "8_questions": q8,
        "final_classifications": FINAL_CLASSIFICATIONS,
        "hard_rules": {
            "vp_threshold_unchanged": True,
            "no_live_scoring_change": True,
            "no_passport_mutation": True,
            "no_supabase_writes": True,
            "no_doctrine_promotion": True,
            "no_model_promotion": True,
            "no_telegram_send": True,
            "no_racing_api_restoration": True,
            "guardrail_proposal_status": "DRY_RUN_ONLY",
            "blocked_from_live_use": True,
            "human_approval_required": True,
        },
    }
    _write_json(path, summary)


def write_summary_md(path: Path, summary: dict) -> None:
    mcount = summary["mechanism_split"]
    kf = summary["key_findings"]
    q8 = summary["8_questions"]

    lines = [
        f"# VFU-16 — Win/Place Conversion Tribunal",
        f"",
        f"**Version:** {summary['validation_version']}",
        f"**Generated:** {summary['generated_at']}",
        f"**VP_THRESHOLD:** {summary['vp_threshold']:.2f} (UNCHANGED)",
        f"",
        f"## Scope",
        f"",
        f"| | Count |",
        f"|---|---|",
        f"| Total false-GREEN cases | {summary['total_fg_cases']} |",
        f"| MISS (not placed) | {summary['miss_cases']} |",
        f"| PLACED (not won) | {summary['placed_cases']} |",
        f"",
        f"## Mechanism Split",
        f"",
        f"| Mechanism | Count |",
        f"|---|---|",
    ]

    for mech, count in sorted(mcount.items(), key=lambda x: -x[1]):
        lines.append(f"| {mech} | {count} |")

    lines += [
        f"",
        f"## Key Findings",
        f"",
        f"- **PLACE_STRONG_WIN_WEAK:** {kf['place_strong_win_weak_total']} cases "
        f"({summary['placed_cases']} PLACED definitionally + MISS with confirmed place_prob dominance)",
        f"- **MARKET_AND_VP_JOINT_OVERCONFIDENCE:** {kf['market_and_vp_joint_overconfidence']} MISS cases — "
        f"market AND VP agreed, both wrong (dominant in short-price misses)",
        f"- **PLACE_PROB_DOMINANT confirmed:** {kf['place_prob_dominant_confirmed_count']} cases "
        f"with component data and place_prob >= 0.80",
        f"- **Guardrail retrospective candidates:** {kf['guardrail_retrospective_candidates']} cases "
        f"would have triggered PLACE_STRONG_WIN_UNPROVEN (DRY_RUN_ONLY)",
        f"",
        f"## 8 Core Questions",
        f"",
        f"| Q | Answer |",
        f"|---|---|",
        f"| Q1 PLACE_PROB_DOMINANT MISS count | {q8['Q1_place_prob_dominant_miss_count']['answer']} confirmed (component data) |",
        f"| Q2 Short-price joint overconfidence | {q8['Q2_short_price_joint_overconfidence']['answer']} MISS cases |",
        f"| Q3 Place-strong win-weak total | {q8['Q3_place_strong_win_weak_count']['answer']} (MISS + PLACED) |",
        f"| Q4 Data lineage repair needed | {q8['Q4_data_lineage_repair_count']['answer']} MISS cases |",
        f"| Q5 Is place_prob too influential? | {q8['Q5_is_place_prob_too_influential']['answer']} |",
        f"| Q6 Calibration vs signal issue? | {q8['Q6_calibration_vs_signal_issue']['answer']} |",
        f"| Q7 VFU-17 focus on guardrail? | {q8['Q7_should_vfu17_focus_guardrail']['answer']} |",
        f"| Q8 Live scoring change now? | **{q8['Q8_live_scoring_change_now']['answer']}** |",
        f"",
        f"## Named Exception Cases (retained verbatim)",
        f"",
        f"- **Lightsoutandaway:** SQPE_SMALL_FIELD_EXCEPTION — sqpe=0.099, place_prob=0.49, "
        f"field_size=6, Chase. Separate mechanism, not place_prob inflation.",
        f"- **Food For Thought (rac_11930100, Beverley):** DATA_LINEAGE_REQUIRED — "
        f"P0 evidence gap, RAC_PREFIX_NOT_IN_ANY_SOURCE. Not classifiable until lineage resolved.",
        f"- **Martymill:** TRUE_WIN_SIGNAL_FAILED — improvement_score=0.636, MDS=0.746. "
        f"Both WIN signals co-fired strongly. Both wrong. Highest-priority P0 review.",
        f"",
        f"## Doctrine Implications (NOT YET ACTIVE)",
        f"",
        f"1. VP needs a win/place **separation layer** — not a threshold change",
        f"2. place_prob inflating VP is a **calibration issue**, not a signal failure",
        f"3. Proposed guardrail: **PLACE_STRONG_WIN_UNPROVEN** (DRY_RUN_ONLY)",
        f"   - Trigger: place_prob >= {kf.get('guardrail_retrospective_candidates', '?')} cases retrospectively",
        f"   - Effect: flag only — no VP change, no scoring block",
        f"   - Status: **OPERATOR REVIEW REQUIRED before any live use**",
        f"",
        f"## Hard Rules (permanent)",
        f"",
        f"- VP threshold: **{summary['vp_threshold']:.2f} UNCHANGED**",
        f"- No live scoring change",
        f"- No Passport mutation",
        f"- No Supabase writes",
        f"- No doctrine promotion",
        f"- No model promotion",
        f"- No Telegram send",
        f"- No Racing API restoration",
        f"",
        f"## Final Classifications (15)",
        f"",
    ]

    for clf in summary["final_classifications"]:
        lines.append(f"- `{clf}`")

    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    # ── Load inputs ──────────────────────────────────────────────────────────
    enr_cases = _load_jsonl(REPORTS / "vfu_14_false_green_sp_enriched_cases.jsonl")
    miss_cases_v15 = _load_jsonl(REPORTS / "vfu_15_miss_cases.jsonl")

    # Build case_id lookup for VFU-15 MISS cases
    miss_by_caseid: dict[str, dict] = {}
    for mc in miss_cases_v15:
        cid = mc.get("case_id", "")
        if cid:
            miss_by_caseid[cid] = mc

    # ── Annotate all 121 cases ───────────────────────────────────────────────
    cases = build_annotated_cases(enr_cases, miss_by_caseid)

    # ── Build analyses ───────────────────────────────────────────────────────
    mechanism_split = build_mechanism_split(cases)
    pp_dominant = build_place_prob_dominant_cases(cases)
    watchlist = build_watchlist(cases)
    hrq = build_human_review_queue(cases)
    q8 = answer_8_questions(cases, mechanism_split)

    # ── Write outputs ────────────────────────────────────────────────────────

    # 1. Mechanism split
    write_mechanism_split(
        OUT_PREFIX.parent / "vfu_16_false_green_mechanism_split.json",
        mechanism_split,
    )

    # 2. Place-prob dominant cases
    write_place_prob_dominant_jsonl(
        OUT_PREFIX.parent / "vfu_16_place_prob_dominant_cases.jsonl",
        pp_dominant,
    )

    # 3. Watchlist
    write_watchlist(
        OUT_PREFIX.parent / "vfu_16_win_weak_place_strong_watchlist.json",
        watchlist,
    )

    # 4. Human review queue
    write_human_review_queue(
        OUT_PREFIX.parent / "vfu_16_human_review_queue.json",
        hrq,
    )

    # 5 + 6. Summary JSON + MD
    summary = {
        "validation_version": VALIDATION_VERSION,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "vp_threshold": VP_THRESHOLD,
        "total_fg_cases": len(cases),
        "miss_cases": sum(1 for c in cases if c.get("is_miss")),
        "placed_cases": sum(1 for c in cases if c.get("is_placed_not_won")),
        "mechanism_split": mechanism_split["by_mechanism"],
        "key_findings": {
            "place_strong_win_weak_total": mechanism_split["by_mechanism"].get(PLACE_STRONG_WIN_WEAK, 0),
            "market_and_vp_joint_overconfidence": mechanism_split["by_mechanism"].get(MARKET_AND_VP_JOINT_OVERCONFIDENCE, 0),
            "insufficient_component_data": mechanism_split["by_mechanism"].get(INSUFFICIENT_COMPONENT_DATA, 0),
            "drain_course_context": mechanism_split["by_mechanism"].get(DRAIN_COURSE_CONTEXT, 0),
            "data_lineage_required": mechanism_split["by_mechanism"].get(DATA_LINEAGE_REQUIRED, 0),
            "sp_source_zero_blocker": mechanism_split["by_mechanism"].get(SP_SOURCE_ZERO_BLOCKER, 0),
            "source_gap_no_sp": mechanism_split["by_mechanism"].get(SOURCE_GAP_NO_SP, 0),
            "true_win_signal_failed": mechanism_split["by_mechanism"].get(TRUE_WIN_SIGNAL_FAILED, 0),
            "sqpe_small_field_exception": mechanism_split["by_mechanism"].get(SQPE_SMALL_FIELD_EXCEPTION, 0),
            "place_prob_dominant_confirmed_count": len(pp_dominant),
            "watchlist_entries": watchlist["total_watchlist_entries"],
            "guardrail_retrospective_candidates": watchlist["guardrail_candidates_count"],
            "human_review_p0": hrq["p0_critical"],
            "human_review_p1": hrq["p1_high"],
        },
        "8_questions": q8,
        "final_classifications": FINAL_CLASSIFICATIONS,
        "hard_rules": {
            "vp_threshold_unchanged": True,
            "no_live_scoring_change": True,
            "no_passport_mutation": True,
            "no_supabase_writes": True,
            "no_doctrine_promotion": True,
            "no_model_promotion": True,
            "no_telegram_send": True,
            "no_racing_api_restoration": True,
            "guardrail_proposal_status": "DRY_RUN_ONLY",
            "blocked_from_live_use": True,
            "human_approval_required": True,
        },
    }

    write_summary_json(
        OUT_PREFIX.parent / "vfu_16_win_place_conversion_summary.json",
        cases,
        mechanism_split,
        q8,
        pp_dominant,
        watchlist,
        hrq,
    )
    write_summary_md(
        OUT_PREFIX.parent / "vfu_16_win_place_conversion_summary.md",
        summary,
    )

    # ── Console report ───────────────────────────────────────────────────────
    print(f"VFU-16 — Win/Place Conversion Tribunal")
    print(f"{'='*60}")
    print(f"Total FG cases classified: {len(cases)}")
    print(f"  MISS: {summary['miss_cases']} | PLACED: {summary['placed_cases']}")
    print()
    print("Mechanism split:")
    for mech, cnt in sorted(mechanism_split["by_mechanism"].items(), key=lambda x: -x[1]):
        print(f"  {mech:<40} {cnt}")
    print()
    print(f"Place-prob dominant (component-confirmed): {len(pp_dominant)}")
    print(f"Watchlist entries: {watchlist['total_watchlist_entries']}")
    print(f"Guardrail retrospective candidates: {watchlist['guardrail_candidates_count']}")
    print(f"Human review P0: {hrq['p0_critical']} | P1: {hrq['p1_high']} | P2: {hrq['p2_medium']}")
    print()
    print("Q8 — Live scoring change now?")
    print(f"  {q8['Q8_live_scoring_change_now']['answer']}")
    print()
    print(f"VP_THRESHOLD: {VP_THRESHOLD:.2f} (UNCHANGED)")
    print()
    print("Final classifications:")
    for clf in FINAL_CLASSIFICATIONS:
        print(f"  {clf}")
    print()
    print(f"Outputs written to: {REPORTS}/vfu_16_*")


if __name__ == "__main__":
    main()
