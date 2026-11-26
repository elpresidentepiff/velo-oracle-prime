from __future__ import annotations

import pytest

from src.velo.rich_context_challenger_features_v3 import (
    FEATURE_NAMES,
    REQUIRED_FAMILIES,
    missing_required_families,
    vector_from_packet_families,
)


def _families() -> dict:
    return {
        "prime_baseline_snapshot": {"velo_prime_prob": 0.25, "sp_dec": 4.0},
        "canonical_history": {
            "win_rate": 0.2,
            "place_rate": 0.5,
            "days_since_last_run": 21,
            "course_win_rate": 0.1,
            "distance_win_rate": 0.15,
        },
        "market_facts": {"decimal_price": 4.0},
        "formfav_raw_facts": {"barrier": 4, "age": 5, "weight": 130, "last20StartsCount": 12},
        "formfav_pace_context": {"speedMap": {"runningStyle": "L", "earlySpeedIndex": 8, "settlingPosition": 2}, "paceScenario": "FAST"},
        "formfav_class_context": {"classProfile": {"currentRating": 70}, "raceClassFit": {"classDifference": -1, "withinOptimalRange": True}},
        "formfav_track_bias_context": {"trackBias": {"biasStrengthScore": 0.5, "barrierAdvantage": 0.1}},
        "rp_spotlight_facts": {"feature_families": ["pace_and_running_style"], "family_counts": {"pace_and_running_style": 2}},
        "connections_passports": {"career_runs": 20, "wins": 4, "places": 9},
    }


def test_v3_refuses_partial_context_instead_of_fabricating_a_full_score() -> None:
    families = _families()
    families.pop("formfav_track_bias_context")
    assert missing_required_families(families) == ["formfav_track_bias_context"]
    assert vector_from_packet_families(families) is None


def test_v3_vector_is_complete_and_fixed_width_for_full_factual_packet() -> None:
    vector = vector_from_packet_families(_families())
    assert vector is not None
    assert len(vector) == len(FEATURE_NAMES)
    by_name = dict(zip(FEATURE_NAMES, vector, strict=True))
    assert by_name["velo_prime_prob"] == 0.25
    assert by_name["formfav_style_leader"] == 1.0
    assert by_name["spotlight_has_pace_fact"] == 1.0
    assert by_name["connections_win_rate"] == 0.2


def test_v3_refuses_provider_prediction_leakage_at_final_feature_boundary() -> None:
    families = _families()
    families["formfav_raw_facts"]["winProbability"] = 0.99
    with pytest.raises(ValueError, match="leakage"):
        vector_from_packet_families(families)


def test_v3_contract_declares_every_required_family() -> None:
    assert len(REQUIRED_FAMILIES) == 9
    assert "rp_spotlight_facts" in REQUIRED_FAMILIES
    assert "connections_passports" in REQUIRED_FAMILIES
