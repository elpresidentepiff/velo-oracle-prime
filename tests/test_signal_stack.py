"""
Tests for Issue #84 — VÉLØ Signal Stack payload.

Validates:
  - Kenobi regression: VP30_TIER_A badge, effective_confidence=high, stale detected
  - UNAUTHORISED_SELECTION → SP_MISSING, SOURCE_RP_MERGED, CONFIDENCE_STALE_LOW, ROUTER_FALLBACK
  - All sidecar values present (mds, improvement, place_prob)
  - No scoring mutation: build_signal_stack_payload never modifies top dict
  - Badge logic: MDS_HIGH, IMPROVE_HIGH, PLACE_PROB_HIGH, B_LOW_VP_SUPPRESS
  - Execution blockers empty when execution_allowed=True
  - SP present → no SP_MISSING
  - api source → no SOURCE_RP_MERGED
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.velo.signal_stack import (  # noqa: E402
    build_execution_blockers,
    build_signal_stack_payload,
    effective_confidence,
)

_KENOBI_TOP = {
    "horse": "Kenobi",
    "decision_tier": "A",
    "velo_prime_prob": 0.5479,
    "confidence_level": "low",
    "market_deception_score": 0.016,
    "improvement_score": 0.1,
    "place_prob": 0.6,
    "assigned_product": "VISION_ONLY",
    "execution_allowed": False,
    "router_reasons": ["UNAUTHORISED_SELECTION"],
    "sp_dec": None,
}
_KENOBI_RACE = {"race_id": "rp_FFO_20260520_15_20", "course": "FFO", "off_time": "15:20"}
_KENOBI_ROUTE = {"actual_winner_sp": 0.0, "prob_gap": 0.4}


# ── effective_confidence ──────────────────────────────────────────────────────


def test_effective_conf_high():
    assert effective_confidence(0.5479) == "high"


def test_effective_conf_at_boundary():
    assert effective_confidence(0.45) == "high"
    assert effective_confidence(0.44) == "normal"


def test_effective_conf_normal():
    assert effective_confidence(0.30) == "normal"
    assert effective_confidence(0.15) == "normal"


def test_effective_conf_low():
    assert effective_confidence(0.14) == "low"
    assert effective_confidence(0.0) == "low"


# ── Kenobi regression ─────────────────────────────────────────────────────────


def _kenobi_payload():
    return build_signal_stack_payload(
        _KENOBI_RACE, _KENOBI_TOP, tier="A",
        sec_prob=0.15, racecard_source="rp_merged",
        route_data=_KENOBI_ROUTE,
    )


def test_kenobi_vp30_tier_a_badge():
    assert "VP30_TIER_A" in _kenobi_payload()["badges"]


def test_kenobi_effective_confidence_is_high():
    assert _kenobi_payload()["effective_confidence"] == "high"


def test_kenobi_ensemble_confidence_preserved():
    assert _kenobi_payload()["ensemble_confidence"] == "low"


def test_kenobi_confidence_stale_detected():
    assert "CONFIDENCE_STALE_LOW" in _kenobi_payload()["execution_blockers"]


def test_kenobi_sp_missing_blocker():
    assert "SP_MISSING" in _kenobi_payload()["execution_blockers"]


def test_kenobi_source_rp_merged_blocker():
    assert "SOURCE_RP_MERGED" in _kenobi_payload()["execution_blockers"]


def test_kenobi_router_fallback_blocker():
    assert "ROUTER_FALLBACK" in _kenobi_payload()["execution_blockers"]


def test_kenobi_mds_value_correct():
    p = _kenobi_payload()
    assert abs(p["mds"] - 0.016) < 1e-4


def test_kenobi_improvement_present():
    p = _kenobi_payload()
    assert "improvement" in p
    assert isinstance(p["improvement"], float)


def test_kenobi_place_prob_present():
    p = _kenobi_payload()
    assert "place_prob" in p
    assert isinstance(p["place_prob"], float)


def test_kenobi_all_required_fields_present():
    p = _kenobi_payload()
    required = (
        "vp", "tier", "ensemble_confidence", "effective_confidence",
        "prob_gap", "mds", "improvement", "place_prob",
        "badges", "risks", "assigned_product",
        "execution_allowed", "router_reasons", "execution_blockers", "source",
    )
    for field in required:
        assert field in p, f"Missing field: {field}"


def test_kenobi_no_scoring_mutation():
    top_before = dict(_KENOBI_TOP)
    build_signal_stack_payload(
        _KENOBI_RACE, _KENOBI_TOP, tier="A",
        sec_prob=0.15, racecard_source="rp_merged",
        route_data=_KENOBI_ROUTE,
    )
    for k, v in top_before.items():
        assert _KENOBI_TOP[k] == v, f"top[{k!r}] was mutated: {v!r} → {_KENOBI_TOP[k]!r}"


def test_kenobi_signal_stack_not_attached_to_top():
    top_copy = dict(_KENOBI_TOP)
    build_signal_stack_payload(_KENOBI_RACE, top_copy, tier="A")
    assert "signal_stack" not in top_copy


# ── Badge logic ───────────────────────────────────────────────────────────────


def test_mds_high_badge():
    top = {**_KENOBI_TOP, "market_deception_score": 0.6, "execution_allowed": True}
    p = build_signal_stack_payload({}, top, tier="A", sec_prob=0.1)
    assert "MDS_HIGH" in p["badges"]


def test_mds_below_threshold_no_badge():
    top = {**_KENOBI_TOP, "market_deception_score": 0.49, "execution_allowed": True}
    p = build_signal_stack_payload({}, top, tier="A", sec_prob=0.1)
    assert "MDS_HIGH" not in p["badges"]


def test_improve_high_badge():
    top = {**_KENOBI_TOP, "improvement_score": 0.41, "execution_allowed": True}
    p = build_signal_stack_payload({}, top, tier="A", sec_prob=0.1)
    assert "IMPROVE_HIGH" in p["badges"]


def test_place_prob_high_badge():
    top = {**_KENOBI_TOP, "place_prob": 0.81, "execution_allowed": True}
    p = build_signal_stack_payload({}, top, tier="A", sec_prob=0.1)
    assert "PLACE_PROB_HIGH" in p["badges"]


def test_b_low_vp_suppress_badge():
    top = {**_KENOBI_TOP, "velo_prime_prob": 0.22}
    p = build_signal_stack_payload({}, top, tier="B", sec_prob=0.1)
    assert "B_LOW_VP_SUPPRESS" in p["badges"]


def test_no_vp30_tier_a_when_tier_b():
    top = {**_KENOBI_TOP, "velo_prime_prob": 0.40}
    p = build_signal_stack_payload({}, top, tier="B", sec_prob=0.1)
    assert "VP30_TIER_A" not in p["badges"]


# ── Execution blockers ────────────────────────────────────────────────────────


def test_no_blockers_when_execution_allowed():
    top = {**_KENOBI_TOP, "execution_allowed": True, "router_reasons": ["GOLD_STANDARD_ALIGNMENT"]}
    assert build_execution_blockers(top, {}, "") == []


def test_non_unauthorised_reasons_preserved_as_blockers():
    top = {**_KENOBI_TOP, "router_reasons": ["WEAK_MARGIN"]}
    blockers = build_execution_blockers(top, {}, "")
    assert "WEAK_MARGIN" in blockers


def test_sp_present_no_sp_missing():
    top = {**_KENOBI_TOP, "sp_dec": 4.5}
    blockers = build_execution_blockers(top, {"actual_winner_sp": 4.5}, "rp_merged")
    assert "SP_MISSING" not in blockers


def test_api_source_no_rp_merged_blocker():
    blockers = build_execution_blockers(_KENOBI_TOP, {}, racecard_source="api")
    assert "SOURCE_RP_MERGED" not in blockers


def test_normal_effective_conf_no_stale_flag():
    top = {**_KENOBI_TOP, "velo_prime_prob": 0.30}
    blockers = build_execution_blockers(top, {}, "rp_merged")
    assert "CONFIDENCE_STALE_LOW" not in blockers
    assert "LOW_DISPLAY_CONFIDENCE" in blockers


def test_weak_margin_blocker_fires():
    top = {**_KENOBI_TOP}
    blockers = build_execution_blockers(top, {"prob_gap": 0.01}, "")
    assert "WEAK_MARGIN" in blockers


def test_strong_margin_no_weak_blocker():
    top = {**_KENOBI_TOP}
    blockers = build_execution_blockers(top, {"prob_gap": 0.15}, "")
    assert "WEAK_MARGIN" not in blockers
