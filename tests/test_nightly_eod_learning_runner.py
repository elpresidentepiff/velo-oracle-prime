import json
from unittest.mock import Mock

from scripts.ops import nightly_eod_learning_runner as nightly
from scripts.ops.nightly_eod_learning_runner import (
    NightlyEODRunner,
    _exit_code_for_verdict,
    _settled_result_facts,
)
from scripts.playbook_g_shadow_adapter import PlaybookGShadowAdapter


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


def _governed_abandoned_status(date_str, race_ids, *, source_url="https://www.irishracing.com/news"):
    return {
        "date": date_str,
        "contract": "GOVERNED_RACE_STATUS_V1",
        "races": [
            {
                "race_id": race_id,
                "course": "Cork",
                "off": "4.25",
                "race_status": "ABANDONED",
                "race_status_evidence": {
                    "source_name": "Irish Racing",
                    "source_url": source_url,
                    "observed_at": "2026-09-29T18:00:00+01:00",
                },
            }
            for race_id in race_ids
        ],
    }


def _run_nightly_universe(monkeypatch, tmp_path, *, status_payload=None, missing_ids=()):
    date_str = "2026-09-29"
    _write_gate_artifacts(tmp_path, date_str)
    monkeypatch.setattr(nightly, "ROOT", tmp_path)
    results_dir = tmp_path / "data" / "results"
    results_dir.mkdir(parents=True)

    race_ids = [str(929700 + i) for i in range(35)] + ["929766", "929767", "929768", "929769"]
    preds = [{
        "race_id": race_id,
        "course": "Test",
        "off_time": "2.00",
        "top": {"horse_id": f"h{race_id}", "horse": f"Horse {race_id}", "velo_prime_prob": 0.4},
    } for race_id in race_ids]
    missing = set(missing_ids)
    results = [{
        "race_id": race_id,
        "venue": "TST",
        "off": "2.00",
        "runners": [{
            "horse_id": f"h{race_id}", "horse": f"Horse {race_id}",
            "position": "1", "sp_dec": 3.0,
        }],
    } for race_id in race_ids if race_id not in missing]

    pred_path = tmp_path / "predictions.json"
    result_path = results_dir / "rp_results_2026_09_29.json"
    pred_path.write_text(json.dumps(preds))
    result_path.write_text(json.dumps({"results": results}))
    if status_payload is not None:
        (results_dir / "race_status_2026_09_29.json").write_text(json.dumps(status_payload))

    runner = NightlyEODRunner(
        date_str,
        str(tmp_path / "data" / "sentient_state_shadow.json"),
        dry_run=True,
        pred_file=str(pred_path),
        result_file=str(result_path),
    )
    verdict = runner.run()
    events = [json.loads(line) for line in runner.events_path.read_text().splitlines()] if runner.events_path.exists() else []
    return verdict, runner, events


def test_nightly_runner_accepts_35_results_plus_4_governed_abandoned_without_learning(monkeypatch, tmp_path):
    abandoned = ["929766", "929767", "929768", "929769"]
    status = _governed_abandoned_status("2026-09-29", abandoned)

    verdict, runner, events = _run_nightly_universe(
        monkeypatch, tmp_path, status_payload=status, missing_ids=abandoned,
    )

    void_events = [event for event in events if event["prediction_result"] == "VOID"]
    assert verdict == "PASS"
    assert runner.stats["matched_races"] == 39
    assert runner.stats["data_error_count"] == 0
    assert runner.stats["void_or_unknown"] == 4
    assert len(void_events) == 4
    assert all(event["learning_class"] == "RACE_ABANDONED_VOID" for event in void_events)
    assert all(event["learning_allowed"] is False for event in void_events)

    void_path = tmp_path / "void_events.jsonl"
    void_path.write_text("\n".join(json.dumps(event) for event in void_events) + "\n")
    audit_path = tmp_path / "void_adapter_audit.json"
    adapter = PlaybookGShadowAdapter(
        str(void_path), str(tmp_path / "sentient_state_shadow.json"), str(audit_path),
    )
    adapter.engine.observe_race_outcome = Mock()
    adapter.run()
    audit = json.loads(audit_path.read_text())
    assert audit["engine_updates_applied"] == 0
    adapter.engine.observe_race_outcome.assert_not_called()


def test_nightly_runner_rejects_unauthenticated_race_status(monkeypatch, tmp_path):
    abandoned = ["929769"]
    status = _governed_abandoned_status("2026-09-29", abandoned, source_url="/relative")

    verdict, runner, events = _run_nightly_universe(
        monkeypatch, tmp_path, status_payload=status, missing_ids=abandoned,
    )

    assert verdict == "FAIL"
    assert events == []
    assert runner.failures[0]["type"] == "INVALID_RACE_STATUS_EVIDENCE"


def test_nightly_runner_still_fails_genuine_missing_result(monkeypatch, tmp_path):
    missing = ["929766", "929767", "929768", "929769"]
    monkeypatch.setattr(nightly, "load_race_status_evidence", lambda *_args, **_kwargs: [])

    verdict, runner, _events = _run_nightly_universe(
        monkeypatch, tmp_path, missing_ids=missing,
    )

    assert verdict == "FAIL"
    assert runner.stats["data_error_count"] == 4
    assert {failure["type"] for failure in runner.failures} >= {
        "MISSING_RESULT", "DATA_ERROR_RATE_EXCEEDED",
    }
