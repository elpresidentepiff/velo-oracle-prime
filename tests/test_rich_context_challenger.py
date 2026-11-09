from copy import deepcopy

import pytest

from src.velo.rich_context_challenger import (
    MODEL_STATUS,
    assert_prime_invariant,
    build_runner_shadow_packet,
    score_with_frozen_artifact,
)


def _inputs():
    return {
        "race_id": "rp_123",
        "horse_id": "456",
        "race_date": "2026-11-07",
        "prime_snapshot": {"horse_id": "456", "velo_prime_prob": 0.21, "place_prob": 0.52},
        "formfav_manifest": {
            "training_eligible": True,
            "derived_vector_hash": "f" * 64,
            "families": {
                "raw_facts": {"barrier": 4, "trainer": "T"},
                "provider_derived_context": {"speedMap": {"style": "leader"}, "trackBias": {"draw": "low"}},
            },
        },
        "history_packet": {
            "eligible": True,
            "source_row_ids": ["1", "2"],
            "features": {"win_rate": 0.2, "course_runs": 3},
        },
        "comment_packet": {
            "training_eligible": True,
            "feature_families": ["pace_and_running_style"],
            "family_counts": {"pace_and_running_style": 1},
            "raw_text_sha256": "a" * 64,
            "normalized_text_sha256": "b" * 64,
        },
        "connections_passport": {
            "current_jockey_pair_runs": 3,
            "current_jockey_pair_win_rate": 0.33,
        },
    }


def test_packet_combines_only_separate_eligible_families_without_scoring():
    packet = build_runner_shadow_packet(**_inputs())
    assert packet["eligible_for_future_fit"] is True
    assert packet["model_status"] == MODEL_STATUS
    assert packet["challenger_probability"] is None
    assert packet["challenger_rank"] is None
    assert packet["production_influence"] is False
    assert packet["provider_predictions_consumed"] is False
    assert packet["family_coverage"]["canonical_history"] is True
    assert packet["families"]["formfav_pace_context"] == {"speedMap": {"style": "leader"}}
    assert packet["families"]["connections_passports"]["current_jockey_pair_runs"] == 3
    assert packet["enriched_feature_contract"]["feature_schema_hash"]
    assert packet["enriched_feature_contract"]["scoring_status"] == "AWAITING_CHRONOLOGICAL_V2_FIT"


def test_provider_prediction_leakage_fails_closed():
    inputs = _inputs()
    inputs["formfav_manifest"]["families"]["raw_facts"]["winProbability"] = 0.9
    with pytest.raises(ValueError, match="leakage"):
        build_runner_shadow_packet(**inputs)


def test_missing_history_is_ineligible_not_neutral_default():
    inputs = _inputs()
    inputs["history_packet"] = {"eligible": False, "features": {"win_rate": 0.99}}
    packet = build_runner_shadow_packet(**inputs)
    assert packet["eligible_for_future_fit"] is False
    assert "canonical_history" not in packet["families"]
    assert "MISSING_REQUIRED_FAMILY:canonical_history" in packet["ineligibility_reasons"]


def test_packet_hash_is_deterministic():
    assert build_runner_shadow_packet(**_inputs())["input_hash"] == build_runner_shadow_packet(**_inputs())["input_hash"]


def test_prime_invariant_checks_only_canonical_prime_fields():
    before = [{"horse_id": "456", "horse": "A", "velo_prime_prob": 0.4, "place_prob": 0.6, "longshot_prob": 0.1}]
    after = deepcopy(before)
    after[0]["rich_context_shadow"] = {"status": MODEL_STATUS}
    assert_prime_invariant(before, after)
    after[0]["velo_prime_prob"] = 0.41
    with pytest.raises(AssertionError):
        assert_prime_invariant(before, after)


def test_unfitted_model_never_emits_a_probability():
    packet = build_runner_shadow_packet(**_inputs())
    scored = score_with_frozen_artifact(packet, None)
    assert scored["challenger_probability"] is None
    assert scored["model_status"] == MODEL_STATUS
