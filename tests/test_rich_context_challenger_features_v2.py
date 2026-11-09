from __future__ import annotations

import pytest

from src.velo.rich_context_challenger_features_v2 import (
    APPROVED_FAMILIES,
    FEATURE_NAMES,
    build_enriched_vector,
)


def _families() -> dict:
    return {
        "prime_baseline_snapshot": {"velo_prime_prob": 0.2, "place_prob": 0.5, "sp_dec": 6},
        "market_facts": {"sp_dec": 6, "is_fav": False},
        "canonical_history": {"win_rate": 0.1, "current_jockey_pair_win_rate": 0.2},
        "formfav_raw_facts": {
            "weightKg": 58,
            "barrier": 3,
            "trainer": "T",
            "stats": {"overall": {"starts": 20, "wins": 4, "places": 10}},
        },
        "formfav_pace_context": {"speedMap": {"earlySpeedIndex": 8}},
        "formfav_class_context": {"classProfile": {"currentRating": 82}},
        "formfav_track_bias_context": {"trackBias": {"sampleSize": 14}},
        "rp_spotlight_facts": {"family_counts": {"pace_and_running_style": 2}},
        "connections_passports": {"pp_career_runs": 12, "pp_jockey_continuity": 1},
    }


def test_every_approved_family_is_vectorised_with_coverage() -> None:
    result = build_enriched_vector(_families())
    assert result["fully_enriched"] is True
    assert result["covered_family_count"] == len(APPROVED_FAMILIES)
    assert len(result["vector"]) == len(FEATURE_NAMES)
    assert result["missing_families"] == []
    by_name = dict(zip(FEATURE_NAMES, result["vector"], strict=True))
    assert by_name["formfav_pace_context__speedMap__earlySpeedIndex"] == 8.0
    assert by_name["formfav_class_context__classProfile__currentRating"] == 82.0
    assert by_name["formfav_track_bias_context__trackBias__sampleSize"] == 14.0
    assert by_name["formfav_raw_facts__stats__overall__wins"] == 4.0


def test_missingness_is_explicit_and_never_a_favourable_guess() -> None:
    result = build_enriched_vector({"prime_baseline_snapshot": {"velo_prime_prob": 0.2}})
    by_name = dict(zip(FEATURE_NAMES, result["vector"], strict=True))
    assert by_name["formfav_raw_facts__weightKg"] == 0.0
    assert by_name["formfav_raw_facts__weightKg__missing"] == 1.0
    assert "formfav_raw_facts" in result["missing_families"]


def test_provider_prediction_leakage_fails_closed_recursively() -> None:
    families = _families()
    families["formfav_pace_context"]["speedMap"]["winProbability"] = 0.9
    with pytest.raises(ValueError, match="leakage"):
        build_enriched_vector(families)


def test_unknown_provider_fields_cannot_change_fixed_schema() -> None:
    before = build_enriched_vector(_families())
    families = _families()
    families["formfav_raw_facts"]["unknownProviderFact"] = "x"
    after = build_enriched_vector(families)
    assert before["feature_names"] == after["feature_names"]
    assert len(before["vector"]) == len(after["vector"])
