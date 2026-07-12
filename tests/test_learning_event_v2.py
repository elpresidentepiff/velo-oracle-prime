"""Tests for src/velo/learning/learning_event_v2.py (LEARNING-LOOP-01A Phase 3)."""

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
)


def _prediction(**overrides):
    base = {
        "race_date": "2026-06-01",
        "race_id": "rp_LIN_20260601_2.07",
        "course": "Lingfield",
        "off_time": "2.07",
        "runner_universe": ({"horse_id": "rp_LIN_volto_di_medusa", "horse_name": "Volto Di Medusa"},),
        "model_scores": {"velo_prime_prob": 0.42},
        "rank_order": ("rp_LIN_volto_di_medusa",),
        "top_three": ("rp_LIN_volto_di_medusa",),
        "odds_value": 6.0,
        "odds_capture_ts": "2026-06-01T13:50:00Z",
        "source_commit": "abc123",
        "input_card_hash": "cardhash1",
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
        "learning_allowed": True,
        "promotion_eligible": False,
        "result_source": "RP_LOCAL_JSON",
        "result_source_classification": "RESULT_SOURCE_RP_LOCAL_PRIMARY",
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


def test_ambiguous_blocked_event_cannot_be_learning_allowed():
    with pytest.raises(LearningEventValidationError):
        _safety(
            ambiguous_join_blocked=True,
            learning_allowed=True,
            time_safety=TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS,
        )


def test_promotion_eligible_requires_safe_time_safety():
    with pytest.raises(LearningEventValidationError):
        _safety(time_safety=TIME_SAFETY_COUNTERFACTUAL_REPLAY, promotion_eligible=True)


def test_promotion_eligible_allowed_with_safe_classification():
    s = _safety(time_safety=TIME_SAFETY_SAFE_PROSPECTIVE, promotion_eligible=True)
    assert s.promotion_eligible is True


# ---------------------------------------------------------------------------
# deterministic, idempotent event ids
# ---------------------------------------------------------------------------


def test_event_id_repeatable_for_identical_content():
    e1 = _event()
    e2 = _event()
    assert e1.event_id == e2.event_id


def test_event_id_changes_when_result_hash_changes():
    e1 = _event()
    e2 = build_learning_event(
        prediction=_prediction(),
        outcome=_outcome(result_source_hash="different_hash"),
        context=_context(),
        safety=_safety(),
    )
    assert e1.event_id != e2.event_id


def test_consumption_id_derived_from_event_id():
    e = _event()
    assert e.consumption_id != e.event_id
    e2 = _event()
    assert e.consumption_id == e2.consumption_id


def test_content_hash_changes_with_any_field_change():
    e1 = _event()
    e2 = build_learning_event(
        prediction=_prediction(odds_value=7.0),
        outcome=_outcome(),
        context=_context(),
        safety=_safety(),
    )
    assert e1.content_hash() != e2.content_hash()


def test_event_is_frozen_immutable():
    import dataclasses

    e = _event()
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.prediction.race_id = "mutated"


def test_to_dict_includes_ids():
    e = _event()
    d = e.to_dict()
    assert d["event_id"] == e.event_id
    assert d["consumption_id"] == e.consumption_id
