import json

from scripts.ops import nightly_eod_learning_runner as module
from scripts.ops.nightly_eod_learning_runner import _selected_outcome, NightlyEODRunner


def test_outcome_requires_known_unique_subject_and_winner():
    result = {"runners": [{"horse_id": "1", "horse": "Winner", "position": "1"},
                          {"horse_id": "2", "horse": "Runner", "position": "PU"},
                          {"horse_id": "3", "horse": "Withdrawn", "position": "NR"}]}
    assert _selected_outcome({"horse_id": "1"}, result)[0] == "WIN"
    assert _selected_outcome({"horse_id": "2"}, result)[0] == "LOSS"
    assert _selected_outcome({"horse_id": "3"}, result)[0] == "VOID"
    assert _selected_outcome({"horse_id": "4"}, result)[0] == "UNKNOWN"
    assert _selected_outcome({"horse_id": "4", "horse": "Runner"}, result)[0] == "UNKNOWN"
    assert _selected_outcome({"horse_id": "2"}, {"runners": result["runners"][1:]})[0] == "UNKNOWN"
    assert _selected_outcome({"horse": "Runner"}, {"runners": result["runners"] + [result["runners"][1]]})[0] == "UNKNOWN"


def test_unresolved_or_void_is_not_classified_as_loss(tmp_path):
    runner = NightlyEODRunner("2026-11-25", str(tmp_path / "shadow.json"), dry_run=True)
    result = {"runners": [{"horse_id": "1", "horse": "Winner", "position": "1"},
                          {"horse_id": "3", "horse": "Withdrawn", "position": "NR"}]}
    assert runner._classify_loss({"top": {"horse_id": "missing"}}, result) == "DATA_ERROR"
    assert runner._classify_loss({"top": {"horse_id": "3"}}, result) == "DATA_ERROR"


def test_real_runner_quarantines_unknown_and_void_events(monkeypatch, tmp_path):
    import src.velo.council.agents as agents

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(agents, "learning_disposition", lambda responses: {
        "allowed": True, "disposition": "CLEAN", "integrity_reasons": [], "performance_reasons": []
    })
    data = tmp_path / "data"
    for directory in (data / "sigma_results", data / "council_runs", data / "mission_control"):
        directory.mkdir(parents=True)
    (data / "sigma_results/sigma_results_2026_11_25.json").write_text('{"sigma_status":"PASS"}')
    (data / "council_runs/council_run_2026-11-25.json").write_text('{"council_verdict":"PASS_TO_LEARNING","agent_responses":[]}')
    (data / "mission_control/2026-11-25_mission_control.json").write_text('{"learning_gate_status":"OPEN"}')
    preds = [{"race_id": str(i), "top": {"horse_id": ident}} for i, ident in enumerate(("1", "2", "3", "4"))]
    result = {"runners": [{"horse_id": "1", "horse": "Winner", "position": "1"},
                          {"horse_id": "2", "horse": "Starter", "position": "PU"},
                          {"horse_id": "3", "horse": "Withdrawn", "position": "NR"}]}
    pred_file, result_file = tmp_path / "pred.json", tmp_path / "results.json"
    pred_file.write_text(json.dumps(preds))
    result_file.write_text(json.dumps([{**result, "race_id": str(i)} for i in range(4)]))
    runner = NightlyEODRunner("2026-11-25", str(tmp_path / "shadow.json"), dry_run=True,
                              data_error_threshold=1.0, pred_file=str(pred_file), result_file=str(result_file))
    runner.run()
    events = [json.loads(line) for line in runner.events_path.read_text().splitlines()]
    assert [(e["prediction_result"], e["learning_allowed"]) for e in events] == [
        ("WIN", True), ("LOSS", True), ("VOID", False), ("UNKNOWN", False)
    ]
    assert events[2]["confidence_error"] is None and events[3]["confidence_error"] is None


def test_shadow_adapter_records_only_successfully_applied_keys(monkeypatch, tmp_path):
    from scripts import playbook_g_shadow_adapter as adapter_module

    class Engine:
        def __init__(self, **kwargs): pass
        def observe_race_outcome(self, race, prediction, result):
            if race["race_id"] == "failed":
                raise ValueError("test failure")

    monkeypatch.setattr(adapter_module, "SentientLoopbackEngine", Engine)
    events = [{"race_id": key, "idempotency_key": key, "learning_allowed": allowed,
               "prediction_snapshot": {}, "result_snapshot": {}}
              for key, allowed in [("applied", True), ("failed", True), ("denied", False)]]
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events))
    audit_path = tmp_path / "audit.json"
    adapter = adapter_module.PlaybookGShadowAdapter(str(path), str(tmp_path / "sentient_state_shadow.json"), str(audit_path))
    adapter.run()
    audit = json.loads(audit_path.read_text())
    assert audit["applied_keys"] == ["applied"]
    assert set(audit["processed_keys"]) == {"applied", "denied"}
    adapter.run()
    assert json.loads(audit_path.read_text())["applied_keys"] == ["applied"]
