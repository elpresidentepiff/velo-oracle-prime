import json

import scripts.ops.run_full_raceday_eod as eod


def _step(name: str, *, ok: bool, critical: bool) -> dict:
    return {
        "step": name,
        "cmd": ["test"],
        "returncode": 0 if ok else 1,
        "ok": ok,
        "critical": critical,
    }


def test_completion_allows_optional_failure_but_names_warning() -> None:
    summary = eod._completion_summary(
        [
            _step("required", ok=True, critical=True),
            _step("optional research", ok=False, critical=False),
        ]
    )

    assert summary["status"] == "PASS_WITH_WARNINGS"
    assert summary["required_failures"] == []
    assert summary["optional_failures"] == ["optional research"]


def test_completion_fails_when_required_close_step_fails() -> None:
    summary = eod._completion_summary(
        [
            _step("sigma", ok=True, critical=True),
            _step("learning persistence", ok=False, critical=True),
        ]
    )

    assert summary["status"] == "FAIL"
    assert summary["required_failures"] == ["learning persistence"]
    assert summary["required_steps_passed"] == 1
    assert summary["required_steps_total"] == 2


def test_finalize_persists_failed_and_blocked_terminal_states(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(eod, "ROOT", tmp_path)

    failed_exit = eod._finalize_run(
        "2026-07-30",
        "2026_07_30",
        [_step("council", ok=False, critical=True)],
    )
    failed_report = json.loads(
        (tmp_path / "data/reports/run_full_raceday_eod_2026_07_30.json").read_text()
    )
    assert failed_exit == 1
    assert failed_report["status"] == "FAIL"
    assert failed_report["completion"]["required_failures"] == ["council"]

    blocked_exit = eod._finalize_run(
        "2026-07-31",
        "2026_07_31",
        [],
        blocked_reason="RP_SESSION_UNAVAILABLE",
    )
    blocked_report = json.loads(
        (tmp_path / "data/reports/run_full_raceday_eod_2026_07_31.json").read_text()
    )
    assert blocked_exit == 1
    assert blocked_report["status"] == "BLOCKED"
    assert blocked_report["completion"]["blocked_reason"] == "RP_SESSION_UNAVAILABLE"
