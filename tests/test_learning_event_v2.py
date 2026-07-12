"""Tests for src/velo/learning/learning_event_v2.py (LEARNING-LOOP-01A Phase 3,
corrected per PR #147 REQUEST CHANGES: P0-4, P0-5, P0-6)."""

import dataclasses

import pytest

from src.velo.learning.learning_event_v2 import (
    TIME_SAFETY_COUNTERFACTUAL_REPLAY,
    TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS,
    TIME_SAFETY_SAFE_PROSPECTIVE,
    LearningEventValidationError,
    OutcomeTruth,
    PredictionTruth,
    RaceContext,
    SafetyProvenance,
    build_learning_event,
    compute_consumption_id,
    compute_input_card_hash,
)


def _card_hash(**overrides):
    base = {
        "race_id": "rp_LIN_20260601_2.07",
        "subject_horse_id": "rp_LIN_volto_di_medusa",
        "prediction_run_id": "run_1",
        "runner_universe": ({"horse_id": "rp_LIN_volto_di_medusa", "horse_name": "Volto Di Medusa"},),
        "model_scores": {"velo_prime_prob": 0.42},
        "rank_order": ("rp_LIN_volto_di_medusa",),
        "top_three": ("rp_LIN_volto_di_medusa",),
        "model_versions": {"velo_prime": "v17"},
        "active_components": ("velo_prime",),
        "excluded_components": (),
    }
    base.update(overrides)
    return compute_input_card_hash(**base)


def _prediction(**overrides):
    base = {
        "race_date": "2026-06-01",
        "race_id": "rp_LIN_20260601_2.07",
        "course": "Lingfield",
        "off_time": "2.07",
        "subject_horse_id": "rp_LIN_volto_di_medusa",
        "prediction_run_id": "run_1",
        "runner_universe": ({"horse_id": "rp_LIN_volto_di_medusa", "horse_name": "Volto Di Medusa"},),
        "model_scores": {"velo_prime_prob": 0.42},
        "rank_order": ("rp_LIN_volto_di_medusa",),
        "top_three": ("rp_LIN_volto_di_medusa",),
        "odds_value": 6.0,
        "odds_capture_ts": "2026-06-01T13:50:00Z",
        "prediction_timestamp": "2026-06-01T13:00:00Z",
        "source_commit": "abc123",
        "input_card_hash": _card_hash(),
        "model_versions": {"velo_prime": "v17"},
        "active_components": ("velo_prime",),
        "excluded_components": (),
    }
    base.update(overrides)
    return PredictionTruth(**base)


def _outcome(**overrides):
    base = {
        "result_race_id": "rp_LIN_20260601_2.07",
        "runner_positions": {"rp_LIN_volto_di_medusa": "1"},
        "non_runners": (),
        "sp_by_horse": {"rp_LIN_volto_di_medusa": 6.0},
        "bsp_by_horse": {},
        "winner_horse_id": "rp_LIN_volto_di_medusa",
        "frame_horse_ids": ("rp_LIN_volto_di_medusa",),
        "result_source_hash": "resulthash1",
        "result_universe_complete": True,
        "resolved_result_horse_id": "rp_LIN_volto_di_medusa",
        "horse_resolution_method": "EXACT_HORSE_ID",
        "subject_outcome_status": "FINISHED",
        "subject_finish_position": "1",
        "subject_sp": 6.0,
        "subject_bsp": None,
        "subject_is_winner": True,
        "subject_is_frame": True,
        "subject_is_non_runner": False,
    }
    base.update(overrides)
    return OutcomeTruth(**base)


def _context(**overrides):
    base = {
        "race_class": "6",
        "race_type": "Flat",
        "field_size": 8,
        "going": "Good",
        "distance_f": 9.0,
        "surface": "Turf",
    }
    base.update(overrides)
    return RaceContext(**base)


def _safety(**overrides):
    base = {
        "race_resolution_method": "EXACT_RACE_ID",
        "horse_resolution_methods": {"rp_LIN_volto_di_medusa": "EXACT_HORSE_ID"},
        "ambiguous_join_blocked": False,
        "time_safety": TIME_SAFETY_SAFE_PROSPECTIVE,
        "leakage_status": "CLEAN",
        "result_source": "RP_LOCAL_JSON",
        "result_source_classification": "RESULT_SOURCE_RP_LOCAL_PRIMARY",
        "result_source_complete": True,
        "prediction_timestamp_present": True,
        "prediction_timestamp_before_off": True,
        "odds_timestamp_present": True,
        "odds_timestamp_before_off": True,
        "source_commit_present": True,
        "model_versions_present": True,
        "input_card_hash_verified": True,
        "analysis_allowed": True,
        "shadow_evaluation_allowed": True,
        "state_learning_allowed": True,
        "model_training_allowed": True,
        "promotion_eligible": False,
    }
    base.update(overrides)
    return SafetyProvenance(**base)


def _event(**safety_overrides):
    return build_learning_event(
        prediction=_prediction(),
        outcome=_outcome(),
        context=_context(),
        safety=_safety(**safety_overrides),
    )


# ---------------------------------------------------------------------------
# no default-safe classifications
# ---------------------------------------------------------------------------


def test_time_safety_is_a_required_constructor_argument():
    import inspect

    sig = inspect.signature(SafetyProvenance)
    assert sig.parameters["time_safety"].default is inspect.Parameter.empty
    assert sig.parameters["leakage_status"].default is inspect.Parameter.empty


def test_unknown_time_safety_classification_rejected():
    with pytest.raises(LearningEventValidationError):
        _safety(time_safety="MADE_UP_CLASSIFICATION")


def test_unknown_leakage_status_rejected():
    with pytest.raises(LearningEventValidationError):
        _safety(leakage_status="MADE_UP")


def test_ambiguous_blocked_event_cannot_have_any_allow_flag():
    with pytest.raises(LearningEventValidationError):
        _safety(
            ambiguous_join_blocked=True,
            analysis_allowed=True,
            time_safety=TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS,
        )


def test_counterfactual_replay_cannot_be_state_learning_allowed():
    with pytest.raises(LearningEventValidationError):
        _safety(time_safety=TIME_SAFETY_COUNTERFACTUAL_REPLAY, state_learning_allowed=True, analysis_allowed=True)


def test_counterfactual_replay_can_still_be_analysis_allowed():
    s = _safety(
        time_safety=TIME_SAFETY_COUNTERFACTUAL_REPLAY,
        analysis_allowed=True,
        shadow_evaluation_allowed=True,
        state_learning_allowed=False,
        model_training_allowed=False,
        promotion_eligible=False,
    )
    assert s.analysis_allowed is True
    assert s.state_learning_allowed is False


def test_promotion_eligible_requires_safe_time_safety():
    with pytest.raises(LearningEventValidationError):
        _safety(time_safety=TIME_SAFETY_COUNTERFACTUAL_REPLAY, promotion_eligible=True)


def test_promotion_eligible_requires_all_gates_not_just_safe_label():
    """A SAFE_* label alone must not be enough -- every promotion gate
    (leakage clean, complete result, real card hash, timestamps proven
    pre-race, commit + model versions present) must also hold."""
    with pytest.raises(LearningEventValidationError):
        _safety(
            time_safety=TIME_SAFETY_SAFE_PROSPECTIVE,
            promotion_eligible=True,
            leakage_status="UNKNOWN",  # not CLEAN -- must block promotion
        )


def test_promotion_eligible_blocked_when_odds_not_proven_before_off():
    with pytest.raises(LearningEventValidationError):
        _safety(
            time_safety=TIME_SAFETY_SAFE_PROSPECTIVE,
            promotion_eligible=True,
            odds_timestamp_before_off=False,
        )


def test_promotion_eligible_blocked_when_result_source_incomplete():
    with pytest.raises(LearningEventValidationError):
        _safety(
            time_safety=TIME_SAFETY_SAFE_PROSPECTIVE,
            promotion_eligible=True,
            result_source_complete=False,
        )


def test_promotion_eligible_allowed_when_every_gate_holds():
    s = _safety(time_safety=TIME_SAFETY_SAFE_PROSPECTIVE, promotion_eligible=True)
    assert s.promotion_eligible is True


# ---------------------------------------------------------------------------
# input_card_hash is a real hash, not a bare identifier string
# ---------------------------------------------------------------------------


def test_input_card_hash_is_a_real_sha256_not_an_identifier_string():
    h = _card_hash()
    assert h != "rp_LIN_20260601_2.07:rp_LIN_volto_di_medusa"
    assert len(h) == 64  # sha256 hex digest length
    int(h, 16)  # must be valid hex


def test_input_card_hash_changes_when_model_scores_change():
    h1 = _card_hash()
    h2 = _card_hash(model_scores={"velo_prime_prob": 0.99})
    assert h1 != h2


def test_input_card_hash_changes_when_rank_order_changes():
    h1 = _card_hash()
    h2 = _card_hash(rank_order=("some_other_horse",))
    assert h1 != h2


def test_input_card_hash_stable_for_identical_content():
    assert _card_hash() == _card_hash()


# ---------------------------------------------------------------------------
# event_key (stable) vs event_content_hash (changes with any content) vs event_id
# ---------------------------------------------------------------------------


def test_event_key_stable_across_identical_events():
    e1 = _event()
    e2 = _event()
    assert e1.event_key == e2.event_key


def test_event_key_unchanged_when_only_result_content_changes():
    """A corrected result must not mint a new logical slot -- event_key
    stays the same; only event_content_hash / event_id change."""
    e1 = _event()
    e2 = build_learning_event(
        prediction=_prediction(),
        outcome=_outcome(winner_horse_id="a_different_horse"),
        context=_context(),
        safety=_safety(),
    )
    assert e1.event_key == e2.event_key
    assert e1.event_content_hash != e2.event_content_hash
    assert e1.event_id != e2.event_id


def test_event_key_changes_with_subject_horse():
    e1 = _event()
    e2 = build_learning_event(
        prediction=_prediction(subject_horse_id="a_different_horse"),
        outcome=_outcome(),
        context=_context(),
        safety=_safety(),
    )
    assert e1.event_key != e2.event_key


def test_event_key_changes_with_prediction_run_id():
    e1 = _event()
    e2 = build_learning_event(
        prediction=_prediction(prediction_run_id="run_2"),
        outcome=_outcome(),
        context=_context(),
        safety=_safety(),
    )
    assert e1.event_key != e2.event_key


def test_event_content_hash_changes_when_model_score_changes():
    e1 = _event()
    e2 = build_learning_event(
        prediction=_prediction(model_scores={"velo_prime_prob": 0.99}),
        outcome=_outcome(),
        context=_context(),
        safety=_safety(),
    )
    assert e1.event_content_hash != e2.event_content_hash


def test_event_content_hash_changes_when_safety_classification_changes():
    e1 = _event()
    e2 = build_learning_event(
        prediction=_prediction(),
        outcome=_outcome(),
        context=_context(),
        safety=_safety(
            time_safety=TIME_SAFETY_COUNTERFACTUAL_REPLAY,
            analysis_allowed=True,
            state_learning_allowed=False,
            model_training_allowed=False,
            promotion_eligible=False,
        ),
    )
    assert e1.event_content_hash != e2.event_content_hash


def test_event_id_repeatable_for_identical_content():
    e1 = _event()
    e2 = _event()
    assert e1.event_id == e2.event_id


def test_event_id_changes_when_result_content_changes():
    e1 = _event()
    e2 = build_learning_event(
        prediction=_prediction(),
        outcome=_outcome(result_source_hash="different_hash"),
        context=_context(),
        safety=_safety(),
    )
    assert e1.event_id != e2.event_id


# ---------------------------------------------------------------------------
# consumption_id requires an explicit (event, consumer, version, state)
# ---------------------------------------------------------------------------


def test_consumption_id_requires_consumer_identity():
    e = _event()
    with pytest.raises(TypeError):
        e.consumption_id()  # no consumer args -- must not silently default


def test_consumption_id_differs_by_consumer_name():
    e = _event()
    a = e.consumption_id(consumer_name="playbook_g_v2", consumer_version="1.0", target_state="shadow")
    b = e.consumption_id(consumer_name="sigma_memory", consumer_version="1.0", target_state="shadow")
    assert a != b


def test_consumption_id_differs_by_consumer_version():
    e = _event()
    a = e.consumption_id(consumer_name="playbook_g_v2", consumer_version="1.0", target_state="shadow")
    b = e.consumption_id(consumer_name="playbook_g_v2", consumer_version="2.0", target_state="shadow")
    assert a != b


def test_consumption_id_differs_by_target_state():
    e = _event()
    a = e.consumption_id(consumer_name="playbook_g_v2", consumer_version="1.0", target_state="shadow")
    b = e.consumption_id(consumer_name="playbook_g_v2", consumer_version="1.0", target_state="live")
    assert a != b


def test_consumption_id_same_for_same_event_and_consumer_identity():
    e1 = _event()
    e2 = _event()
    a = e1.consumption_id(consumer_name="playbook_g_v2", consumer_version="1.0", target_state="shadow")
    b = e2.consumption_id(consumer_name="playbook_g_v2", consumer_version="1.0", target_state="shadow")
    assert a == b


def test_consumption_id_changes_when_underlying_event_content_changes():
    e1 = _event()
    e2 = build_learning_event(
        prediction=_prediction(),
        outcome=_outcome(result_source_hash="different_hash"),
        context=_context(),
        safety=_safety(),
    )
    a = e1.consumption_id(consumer_name="playbook_g_v2", consumer_version="1.0", target_state="shadow")
    b = e2.consumption_id(consumer_name="playbook_g_v2", consumer_version="1.0", target_state="shadow")
    assert a != b


def test_compute_consumption_id_matches_method_form():
    e = _event()
    direct = compute_consumption_id(event_id=e.event_id, consumer_name="x", consumer_version="1", target_state="shadow")
    via_method = e.consumption_id(consumer_name="x", consumer_version="1", target_state="shadow")
    assert direct == via_method


# ---------------------------------------------------------------------------
# immutability / dict export
# ---------------------------------------------------------------------------


def test_event_is_frozen_immutable():
    e = _event()
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.prediction.race_id = "mutated"


def test_to_dict_includes_all_three_ids():
    e = _event()
    d = e.to_dict()
    assert d["event_key"] == e.event_key
    assert d["event_content_hash"] == e.event_content_hash
    assert d["event_id"] == e.event_id
