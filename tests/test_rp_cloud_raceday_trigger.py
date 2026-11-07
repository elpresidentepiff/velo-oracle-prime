from __future__ import annotations

from pathlib import Path

import scripts.ops.rp_cloud_raceday as raceday


def test_scheduled_run_is_recorded_as_railway_cron_not_manual() -> None:
    assert raceday._trigger_source(None, {}) == "railway_cron"
    assert raceday._trigger_source("", {"TRIGGER_SOURCE": "  "}) == "railway_cron"


def test_authorised_rescore_is_not_recorded_as_the_schedule() -> None:
    assert raceday._trigger_source("WAKE-VELO-OFFTIME-FIX-20261107", {}) == "railway_manual"


def test_an_explicit_trigger_source_wins() -> None:
    assert raceday._trigger_source(None, {"TRIGGER_SOURCE": "github_actions_manual"}) == "github_actions_manual"
    assert raceday._trigger_source("why", {"TRIGGER_SOURCE": "api_manual"}) == "api_manual"


def test_run_forwards_env_on_top_of_the_process_environment(monkeypatch) -> None:
    seen = {}

    def fake_run(command, cwd=None, check=None, env=None):
        seen["env"] = env

        class Done:
            returncode = 0

        return Done()

    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setattr(raceday.subprocess, "run", fake_run)
    raceday._run("x", ["true"], env={"TRIGGER_SOURCE": "railway_cron"})
    assert seen["env"]["TRIGGER_SOURCE"] == "railway_cron"
    assert seen["env"]["SUPABASE_URL"] == "https://example.invalid"  # the child keeps its credentials
    raceday._run("y", ["true"])
    assert seen["env"] is None  # untouched steps inherit exactly as before


def test_only_the_score_step_gets_the_trigger_source() -> None:
    src = (Path(__file__).parents[1] / "scripts" / "ops" / "rp_cloud_raceday.py").read_text(encoding="utf-8")
    score_at = src.index('"canonical FormFav-first parse/score/persist"')
    assert "_trigger_source(args.authorised_rescore_reason)" in src[score_at:score_at + 200]
    assert src.count('"TRIGGER_SOURCE": _trigger_source(') == 1  # no other step is relabelled
