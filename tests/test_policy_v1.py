"""
Direct tests for Decision Policy V1 lanes.
"""
import pytest
from new_build_velo.policy_v1 import apply_policy_v1

def test_win_trust():
    row = {
        "lane_b_prob": 0.35,
        "lane_b_rank": 1,
        "passport_found": True,
        "passport_strength_score": 1.5,
        "passport_summary": {"career_runs": 10},
        "passport_live_features": {"pp_place_rate_last3": 0.33}
    }
    res = apply_policy_v1(row)
    assert res["nb_decision_lane"] == "WIN_TRUST"
    assert "HIGH_VP_PROVEN_HISTORY" in res["nb_policy_reasons"]

def test_frame_trust():
    row = {
        "lane_b_prob": 0.18,
        "lane_b_rank": 1,
        "passport_found": True,
        "passport_summary": {"career_runs": 4},
        "passport_live_features": {"pp_place_rate_last3": 0.67}
    }
    res = apply_policy_v1(row)
    assert res["nb_decision_lane"] == "FRAME_TRUST"
    assert "STRONG_RECENCY_VELOCITY" in res["nb_policy_reasons"]

def test_suppress():
    row = {
        "lane_b_prob": 0.08,
        "lane_b_rank": 1,
        "passport_found": True,
        "passport_strength_score": 1.0,
        "passport_summary": {"career_runs": 2}
    }
    res = apply_policy_v1(row)
    assert res["nb_decision_lane"] == "SUPPRESS"
    assert "LOW_PROBABILITY_FADE" in res["nb_policy_reasons"]

def test_low_data():
    row = {
        "lane_b_prob": 0.28,
        "lane_b_rank": 1,
        "passport_found": False
    }
    res = apply_policy_v1(row)
    assert res["nb_decision_lane"] == "LOW_DATA"
    assert "INSUFFICIENT_PASSPORT_DATA" in res["nb_policy_reasons"]

def test_no_edge_rank_1():
    # Scored, but between thresholds
    row = {
        "lane_b_prob": 0.15,
        "lane_b_rank": 1,
        "passport_found": True,
        "passport_strength_score": 1.0,
        "passport_summary": {"career_runs": 10}
    }
    res = apply_policy_v1(row)
    assert res["nb_decision_lane"] == "NO_EDGE"

if __name__ == "__main__":
    pytest.main([__file__])
