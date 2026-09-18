import json
from unittest.mock import Mock

import pytest

from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
from scripts.playbook_g_shadow_adapter import PlaybookGShadowAdapter


def _complete_event():
    return {
        "race_id": "race_1",
        "idempotency_key": "race_1:2026-09-19",
        "learning_allowed": True,
        "prediction_result": "WIN",
        "prediction_snapshot": {
            "horse_id": "h1",
            "horse": "Winner",
            "velo_prime_prob": 0.4,
            "doctrines_fired": ["LAY_THE_STORY"],
        },
        "result_snapshot": {
            "winner_id": "h1",
            "winner_name": "Winner",
            "winner_sp": 4.5,
            "favourite_won": True,
            "winner_profile": {"draw": 3},
            "outcome_known": True,
        },
    }


def test_shadow_adapter_forwards_settled_price_identity_and_profile():
    adapter = object.__new__(PlaybookGShadowAdapter)

    race_data, prediction, actual_result = adapter._prepare_engine_inputs(_complete_event())

    assert race_data["power_anchor"] == "h1"
    assert prediction["power_anchor"] == "h1"
    assert prediction["doctrines_fired"] == ["LAY_THE_STORY"]
    assert actual_result == {
        "winner": "h1",
        "sp": 4.5,
        "favourite_won": True,
        "winner_profile": {"draw": 3},
    }


def test_shadow_adapter_rejects_claimed_learnable_event_without_settled_price(tmp_path):
    event = _complete_event()
    event["result_snapshot"]["winner_sp"] = None
    events_path = tmp_path / "events.jsonl"
    state_path = tmp_path / "sentient_state_shadow_test.json"
    audit_path = tmp_path / "audit.json"
    events_path.write_text(json.dumps(event) + "\n")

    adapter = PlaybookGShadowAdapter(str(events_path), str(state_path), str(audit_path))
    adapter.engine.observe_race_outcome = Mock()
    adapter.run()

    audit = json.loads(audit_path.read_text())
    assert audit["events_skipped_incomplete_outcome"] == 1
    assert audit["engine_updates_applied"] == 0
    assert audit["verdict"] == "FAIL_INCOMPLETE_OUTCOME"
    adapter.engine.observe_race_outcome.assert_not_called()


def test_sentient_error_vector_refuses_false_loss_for_correct_pick_without_sp():
    engine = object.__new__(SentientLoopbackEngine)

    with pytest.raises(ValueError, match="no valid settled decimal SP"):
        engine._compute_error_vector(
            {"power_anchor": "h1", "confidence": 0.4},
            {"winner": "h1", "sp": None},
        )


def test_sentient_error_vector_uses_real_settled_profit():
    engine = object.__new__(SentientLoopbackEngine)

    error = engine._compute_error_vector(
        {"power_anchor": "h1", "confidence": 0.4},
        {"winner": "h1", "sp": 4.5},
    )

    assert error["prediction_correct"] == 1.0
    assert error["profit"] == 3.5
