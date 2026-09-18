import json

from scripts.ops import nightly_eod_learning_runner as nightly
from scripts.ops.nightly_eod_learning_runner import (
    NightlyEODRunner,
    _exit_code_for_verdict,
    _settled_result_facts,
)


def test_nightly_runner_exit_code_reflects_domain_verdict():
    assert _exit_code_for_verdict("PASS") == 0
    assert _exit_code_for_verdict("FAIL") == 1
    assert _exit_code_for_verdict("FAIL_GATE_BLOCKED") == 1


def test_settled_result_facts_require_actual_winner_and_capture_price_profile():
    facts = _settled_result_facts({
        "runners": [
            {"horse_id": "h2", "horse": "Second", "position": "2", "sp": "2/1"},
            {
                "horse_id": "h1",
                "horse": "Winner",
                "position": "1",
                "sp": "5/2F",
                "draw": "7",
                "running_style": "off_pace",
            },
        ]
    })

    assert facts == {
        "winner_id": "h1",
        "winner_name": "Winner",
        "winner_sp": 3.5,
        "favourite_won": False,
        "winner_profile": {"running_style": "off_pace", "draw": 7},
        "winner_identity_known": True,
    }


def test_settled_result_facts_do_not_promote_second_place_when_winner_missing():
    facts = _settled_result_facts({
        "runners": [{"horse_id": "h2", "horse": "Second", "position": "2", "sp_dec": 3.0}]
    })

    assert facts["winner_identity_known"] is False
    assert facts["winner_sp"] is None


def _write_gate_artifacts(root, date_str):
    date_tag = date_str.replace("-", "_")
    (root / "data" / "sigma_results").mkdir(parents=True)
    (root / "data" / "council_runs").mkdir(parents=True)
    (root / "data" / "mission_control").mkdir(parents=True)
    (root / "data" / "sigma_results" / f"sigma_results_{date_tag}.json").write_text(
        json.dumps({"sigma_status": "PASS"})
    )
    (root / "data" / "council_runs" / f"council_run_{date_str}.json").write_text(
        json.dumps({
            "council_verdict": "PASS_TO_LEARNING",
            "agent_responses": [{"agent": "test", "labels": []}],
        })
    )
    (root / "data" / "mission_control" / f"{date_str}_mission_control.json").write_text(
        json.dumps({"learning_gate_status": "OPEN"})
    )


def _run_dry_nightly(monkeypatch, tmp_path, result_runner):
    date_str = "2026-09-19"
    _write_gate_artifacts(tmp_path, date_str)
    monkeypatch.setattr(nightly, "ROOT", tmp_path)

    race_id = "rp_ASC_20260919_2.00"
    pred_path = tmp_path / "predictions.json"
    result_path = tmp_path / "results.json"
    pred_path.write_text(json.dumps([{
        "race_id": race_id,
        "course": "Ascot",
        "off_time": "2.00",
        "top": {
            "horse_id": "h1",
            "horse": "Winner",
            "velo_prime_prob": 0.4,
            "doctrines_fired": ["LAY_THE_STORY"],
        },
    }]))
    result_path.write_text(json.dumps({"results": [{
        "race_id": race_id,
        "venue": "ASC",
        "off": "2.00",
        "runners": [result_runner],
    }]}))

    runner = NightlyEODRunner(
        date_str,
        str(tmp_path / "data" / "sentient_state_shadow.json"),
        dry_run=True,
        pred_file=str(pred_path),
        result_file=str(result_path),
    )
    verdict = runner.run()
    event = json.loads(runner.events_path.read_text().strip())
    status = json.loads(runner.status_path.read_text())
    return verdict, event, status


def test_nightly_event_carries_settled_truth_into_learning_ledger(monkeypatch, tmp_path):
    verdict, event, status = _run_dry_nightly(monkeypatch, tmp_path, {
        "horse_id": "h1",
        "horse": "Winner",
        "position": "1",
        "sp_dec": 4.5,
        "draw": "3",
    })

    assert verdict == "PASS"
    assert event["learning_allowed"] is True
    assert event["prediction_result"] == "WIN"
    assert event["result_snapshot"] == {
        "winner_id": "h1",
        "winner_name": "Winner",
        "winner_sp": 4.5,
        "favourite_won": True,
        "winner_profile": {"draw": 3},
        "outcome_known": True,
    }
    assert status["learning_blocked"] == 0


def test_nightly_event_blocks_learning_and_fails_data_gate_without_settled_sp(monkeypatch, tmp_path):
    verdict, event, status = _run_dry_nightly(monkeypatch, tmp_path, {
        "horse_id": "h1",
        "horse": "Winner",
        "position": "1",
        "sp_dec": 0.0,
    })

    assert verdict == "FAIL"
    assert event["learning_allowed"] is False
    assert event["learning_permission_reason"] == "BLOCKED_SETTLED_SP_MISSING"
    assert event["result_snapshot"]["winner_sp"] is None
    assert status["learning_blocked"] == 1
    assert status["data_error_count"] == 1
