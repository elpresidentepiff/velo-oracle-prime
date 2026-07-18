"""Deep Race Agent verdict logic reads PDF postdata_score/plot_conviction (2026-07-18 wiring)."""
from scripts.ops.build_deep_race_agent_v1 import _agent_judgement


def _base_card(**overrides):
    card = {
        "support": [],
        "risk": [],
        "agent_questions": [],
        "core_numbers": {"vp": 0.2, "mds": 0.1, "frame_gate_probability": 0.5, "win_gate_probability": 0.5, "passport_strength_score": 0.2},
        "new_build": {"old_in_lane_a_top3": True},
        "shadow": {},
        "horse_state": {},
        "tri_action": "TRI_PASS",
    }
    card.update(overrides)
    return card


def _base_evidence(live_identity=None):
    return {
        "rating": {"available": False},
        "performance": {"available": False},
        "history": {"available": False},
        "identity": {},
        "live_identity": live_identity or {"available": False},
    }


def test_no_pdf_signal_is_neutral():
    result = _agent_judgement(_base_card(), _base_evidence())
    assert not any("PDF_" in s for s in result["support"] + result["risk"])


def test_strong_postdata_score_adds_support():
    evidence = _base_evidence({"available": True, "postdata_score": 0.6})
    result = _agent_judgement(_base_card(), evidence)
    assert any(s.startswith("PDF_POSTDATA_POSITIVE") for s in result["support"])
    assert result["support_score"] == 1


def test_negative_postdata_score_adds_risk():
    evidence = _base_evidence({"available": True, "postdata_score": -0.5})
    result = _agent_judgement(_base_card(), evidence)
    assert any(s.startswith("PDF_POSTDATA_NEGATIVE") for s in result["risk"])
    assert result["risk_score"] == 1


def test_high_plot_conviction_adds_support():
    evidence = _base_evidence({"available": True, "plot_conviction": 0.85})
    result = _agent_judgement(_base_card(), evidence)
    assert any(s.startswith("PDF_PLOT_CONVICTION_HIGH") for s in result["support"])
    assert result["support_score"] == 1


def test_weak_signals_below_threshold_are_neutral():
    evidence = _base_evidence({"available": True, "postdata_score": 0.1, "plot_conviction": 0.3})
    result = _agent_judgement(_base_card(), evidence)
    assert not any("PDF_" in s for s in result["support"] + result["risk"])


def test_missing_signal_fields_do_not_crash():
    evidence = _base_evidence({"available": True})  # no postdata_score/plot_conviction keys at all
    result = _agent_judgement(_base_card(), evidence)
    assert not any("PDF_" in s for s in result["support"] + result["risk"])


def test_both_signals_can_stack_support():
    evidence = _base_evidence({"available": True, "postdata_score": 0.5, "plot_conviction": 0.9})
    result = _agent_judgement(_base_card(), evidence)
    assert result["support_score"] == 2
    assert any(s.startswith("PDF_POSTDATA_POSITIVE") for s in result["support"])
    assert any(s.startswith("PDF_PLOT_CONVICTION_HIGH") for s in result["support"])
