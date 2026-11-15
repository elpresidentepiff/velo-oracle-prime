"""Regression tests for the 2026-11-14 morning incident.

Two Railway services ran the same 07:00 pipeline. Both were killed by a 15-minute limit meant for
one capture step but applied to the whole race-day runner; one died 20 seconds before the canonical
scorecards were persisted, so eight of ten model lanes never reached Supabase.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

import scripts.ops.rp_cloud_eod as eod
import scripts.ops.rp_cloud_raceday as raceday
import scripts.ops.run_full_raceday as full
from scripts.ops.bounded_subprocess import StepTimeout, run_bounded, timeout_from_env


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


# ── a timeout stops the step and everything it started ───────────────────────


@pytest.mark.skipif(os.name == "nt", reason="process-group check is POSIX; Windows uses taskkill /T")
def test_timeout_stops_the_grandchild_too(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    parent = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(120)\n"
    )
    with pytest.raises(StepTimeout) as caught:
        run_bounded("orchestrator", [sys.executable, "-c", parent], cwd=tmp_path, timeout=3)
    assert caught.value.label == "orchestrator"

    grandchild = int(pid_file.read_text())
    deadline = time.monotonic() + 10
    while _alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not _alive(grandchild), "the scorer must not keep running after its run was reported failed"


def test_run_bounded_returns_the_exit_code(tmp_path: Path) -> None:
    assert run_bounded("ok", [sys.executable, "-c", "raise SystemExit(0)"], cwd=tmp_path, timeout=60) == 0
    assert run_bounded("bad", [sys.executable, "-c", "raise SystemExit(7)"], cwd=tmp_path, timeout=60) == 7


def test_timeout_from_env_ignores_bad_values(monkeypatch) -> None:
    monkeypatch.delenv("X_TIMEOUT", raising=False)
    assert timeout_from_env("X_TIMEOUT", 900) == 900
    for bad in ("", "abc", "0", "-5"):
        monkeypatch.setenv("X_TIMEOUT", bad)
        assert timeout_from_env("X_TIMEOUT", 900) == 900
    monkeypatch.setenv("X_TIMEOUT", "120")
    assert timeout_from_env("X_TIMEOUT", 900) == 120


# ── the race-day runner is not given a single-step limit ─────────────────────


def _stub_capture_path(monkeypatch, tmp_path: Path) -> list[dict]:
    """Run raceday.main() with every step recorded instead of executed."""
    calls: list[dict] = []

    def fake_run(label, command, env=None, timeout=None):
        calls.append({"label": label, "command": command, "env": env, "timeout": timeout})

    url_dir = tmp_path / "data" / "racing_post_url_lists"
    url_dir.mkdir(parents=True)
    (url_dir / "rp_racecards_2026-11-14.txt").write_text("https://example.invalid/1\n", encoding="utf-8")
    monkeypatch.setattr(raceday, "ROOT", tmp_path)
    monkeypatch.setattr(raceday, "_run", fake_run)
    monkeypatch.setattr(raceday, "_capture_index_and_tomorrow", lambda date_str: None)
    monkeypatch.setattr(sys, "argv", ["rp_cloud_raceday.py", "--date", "2026-11-14"])
    return calls


def test_the_runner_gets_its_own_budget_not_the_capture_limit(monkeypatch, tmp_path: Path) -> None:
    for name in ("RAILWAY_SERVICE_NAME", "VELO_AUTHORISED_RESCORE_REASON", "RP_CLOUD_ORCHESTRATOR_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    calls = _stub_capture_path(monkeypatch, tmp_path)

    assert raceday.main() == 0

    runner = [c for c in calls if "scripts/ops/run_full_raceday.py" in c["command"]]
    assert len(runner) == 1
    assert runner[0]["timeout"] == raceday._ORCHESTRATOR_TIMEOUT_SECONDS
    # The 2026-11-14 run needed more than 17 minutes; the budget must clear the runner's own
    # longest steps (passport capture, then scoring) with room for the thirty others.
    assert raceday._ORCHESTRATOR_TIMEOUT_SECONDS >= (
        full.PASSPORT_CAPTURE_TIMEOUT_SECONDS + full.SCORING_TIMEOUT_SECONDS + full.DEFAULT_STEP_TIMEOUT_SECONDS
    )
    assert raceday._ORCHESTRATOR_TIMEOUT_SECONDS > raceday._DEFAULT_STEP_TIMEOUT_SECONDS
    # Capture steps keep the short default.
    assert all(c["timeout"] is None for c in calls if c not in runner)


def test_the_runner_budget_can_be_changed_without_a_deploy(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("RAILWAY_SERVICE_NAME", raising=False)
    monkeypatch.delenv("VELO_AUTHORISED_RESCORE_REASON", raising=False)
    monkeypatch.setenv("RP_CLOUD_ORCHESTRATOR_TIMEOUT_SECONDS", "7200")
    calls = _stub_capture_path(monkeypatch, tmp_path)
    assert raceday.main() == 0
    assert calls[-1]["timeout"] == 7200


# ── inside the runner, a stalled step costs only itself unless the day depends on it ──


def _timing_out(label, cmd, *, cwd, timeout, env=None):
    raise StepTimeout(label, timeout)


def test_a_stalled_non_critical_step_is_recorded_and_the_day_continues(monkeypatch) -> None:
    monkeypatch.setattr(full, "run_bounded", _timing_out)
    results: list[dict] = []
    assert full.run("Passport top-up: capture horse form", ["x"], critical=False, results=results, timeout=5) is False
    assert results == [
        {
            "step": "Passport top-up: capture horse form",
            "cmd": ["x"],
            "returncode": None,
            "ok": False,
            "critical": False,
            "timed_out": True,
        }
    ]


def test_runner_steps_use_the_default_limit_unless_given_one(monkeypatch) -> None:
    seen: list[float] = []

    def fake(label, cmd, *, cwd, timeout, env=None):
        seen.append(timeout)
        assert env["PYTHONPATH"] == "."
        return 0

    monkeypatch.delenv("VELO_STEP_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(full, "run_bounded", fake)
    results: list[dict] = []
    assert full.run("a", ["x"], critical=False, results=results) is True
    assert full.run("b", ["x"], critical=True, results=results, timeout=full.SCORING_TIMEOUT_SECONDS) is True
    assert seen == [full.DEFAULT_STEP_TIMEOUT_SECONDS, full.SCORING_TIMEOUT_SECONDS]
    assert [r["timed_out"] for r in results] == [False, False]


def test_scoring_and_passport_capture_have_their_own_limits() -> None:
    src = (Path(__file__).parents[1] / "scripts" / "ops" / "run_full_raceday.py").read_text(encoding="utf-8")
    scoring = src.index('"Step 9: Live scoring (run_prime_today.py)"')
    assert "timeout=SCORING_TIMEOUT_SECONDS" in src[scoring : scoring + 500]
    passport = src.index('"Passport top-up: capture horse form (RP JSON API)"')
    assert "timeout=PASSPORT_CAPTURE_TIMEOUT_SECONDS" in src[passport : passport + 500]


# ── only one Railway service runs the scheduled morning ──────────────────────


def test_the_duplicate_service_stands_down_on_the_schedule() -> None:
    reason = raceday._not_the_morning_owner(None, {"RAILWAY_SERVICE_NAME": "velo-prime-scoring"})
    assert reason and "velo-prime-scoring" in reason and "velo-rp-capture" in reason


def test_the_owner_the_laptop_and_an_authorised_rescore_all_proceed() -> None:
    assert raceday._not_the_morning_owner(None, {"RAILWAY_SERVICE_NAME": "velo-rp-capture"}) is None
    assert raceday._not_the_morning_owner(None, {}) is None  # laptop / CI: no Railway service name
    assert (
        raceday._not_the_morning_owner("WAKE-VELO-OFFTIME-FIX-20261107", {"RAILWAY_SERVICE_NAME": "velo-prime-scoring"})
        is None
    )


def test_ownership_can_be_moved_by_variable() -> None:
    env = {"RAILWAY_SERVICE_NAME": "velo-prime-scoring", "VELO_MORNING_OWNER_SERVICE": "velo-prime-scoring"}
    assert raceday._not_the_morning_owner(None, env) is None
    env = {"RAILWAY_SERVICE_NAME": "velo-rp-capture", "VELO_MORNING_OWNER_SERVICE": "velo-prime-scoring"}
    assert raceday._not_the_morning_owner(None, env) is not None


def test_a_standing_down_service_runs_nothing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "velo-prime-scoring")
    monkeypatch.delenv("VELO_MORNING_OWNER_SERVICE", raising=False)
    monkeypatch.delenv("VELO_AUTHORISED_RESCORE_REASON", raising=False)
    calls = _stub_capture_path(monkeypatch, tmp_path)
    monkeypatch.setattr(
        raceday, "_capture_index_and_tomorrow", lambda date_str: pytest.fail("must not touch Racing Post")
    )
    assert raceday.main() == 0
    assert calls == []


# ── the evening run cannot hang and block the following nights ───────────────


def test_every_eod_step_is_bounded(monkeypatch) -> None:
    def hang(label, command, *, cwd, timeout, env=None):
        raise StepTimeout(label, timeout)

    monkeypatch.setattr(eod, "run_bounded", hang)
    with pytest.raises(RuntimeError, match="capture RP results pages exceeded 1800s"):
        eod._run("capture RP results pages", ["x"], timeout=eod._CAPTURE_TIMEOUT_SECONDS)

    src = (Path(__file__).parents[1] / "scripts" / "ops" / "rp_cloud_eod.py").read_text(encoding="utf-8")
    body = src[src.index("def _settle_day(") : src.index("def main()")]
    assert body.count("\n    _run(") == 3
    assert body.count("timeout=timeout_from_env(") == 3
