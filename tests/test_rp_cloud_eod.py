"""Pure tests for Railway cloud EOD preparation and postconditions."""

from __future__ import annotations

import json

import pytest

from scripts.ops import rp_cloud_eod as eod
from scripts.ops import run_full_raceday_eod as full_eod


def _race(race_id: str, source_url: str) -> dict:
    return {
        "race_id": race_id,
        "course": "Test Course",
        "date": "2026-11-02",
        "time": f"1{race_id[-1]}:00:00",
        "raw": {
            "race_id": int(race_id),
            "course": "Test Course",
            "off_time": "1.00",
            "source_url": source_url,
        },
    }


def _verdict(race_id: str, horse_id: str, horse: str) -> dict:
    return {
        "race_id": race_id,
        "top_rank_horse_id": horse_id,
        "velo_prime_prob": 0.41,
        "decision_tier": "A",
        "confidence_level": "HIGH",
        "generated_at": "2026-11-02T07:00:00Z",
        "assigned_product": "WIN_ONLY",
        "full_analysis": {
            "predictions": [{"horse_id": horse_id, "horse": horse}]
        },
    }


def test_results_url_requires_rp_racecard_path_and_matching_identity():
    url = "https://www.racingpost.com/racecards/1/test/2026-11-02/100"
    assert eod._results_url(url, "100") == (
        "https://www.racingpost.com/results/1/test/2026-11-02/100"
    )
    assert eod._results_url(url, "999") is None
    assert eod._results_url("https://example.com/100", "100") is None


def test_safe_artifact_path_rejects_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(eod, "ROOT", tmp_path)
    assert eod._safe_artifact_path("../../.env") is None
    assert eod._safe_artifact_path("not-approved/file.json") is None
    assert eod._safe_artifact_path("data/reports/packet.json") == (
        tmp_path / "data" / "reports" / "packet.json"
    )


def test_prepare_cloud_eod_uses_only_scored_races(tmp_path, monkeypatch):
    races = [
        _race("100", "https://www.racingpost.com/racecards/1/test/2026-11-02/100"),
        _race("101", "https://www.racingpost.com/racecards/1/test/2026-11-02/101"),
        _race("999", "https://www.racingpost.com/racecards/9/other/2026-11-02/999"),
    ]
    verdicts = [_verdict("100", "h1", "Alpha"), _verdict("101", "h2", "Beta")]
    artifacts = [
        {
            "artifact_type": "old_velo_three_option_card",
            "source_path": "data/reports/old_velo_three_option_card_2026_11_02.json",
            "payload": {"date": "2026-11-02", "races": []},
        }
    ]

    def fake_get(table, _params):
        return {"races": races, "velo_verdicts": verdicts, "velo_report_artifacts": artifacts}[table]

    monkeypatch.setattr(eod, "ROOT", tmp_path)
    monkeypatch.setattr(eod, "URL_LIST_ROOT", tmp_path / "data" / "racing_post_url_lists")
    monkeypatch.setattr(eod, "_get", fake_get)

    summary = eod.prepare_cloud_eod_inputs("2026-11-02")

    assert summary["races_available"] == 3
    assert summary["scored_races"] == 2
    assert summary["results_urls"] == 2
    urls = (tmp_path / summary["url_list"]).read_text(encoding="utf-8").splitlines()
    assert urls == [
        "https://www.racingpost.com/results/1/test/2026-11-02/100",
        "https://www.racingpost.com/results/1/test/2026-11-02/101",
    ]
    cards = json.loads(
        (tmp_path / "data" / "racecards_2026_11_02_standard.json").read_text(encoding="utf-8")
    )
    assert [str(card["race_id"]) for card in cards] == ["100", "101"]
    backup = json.loads(
        (tmp_path / "data" / "velo_prime_verdicts_2026_11_02.json").read_text(encoding="utf-8")
    )
    assert [row["top"]["horse"] for row in backup] == ["Alpha", "Beta"]


def test_prepare_cloud_eod_blocks_missing_rp_url(tmp_path, monkeypatch):
    races = [_race("100", "")]
    verdicts = [_verdict("100", "h1", "Alpha")]

    def fake_get(table, _params):
        return {"races": races, "velo_verdicts": verdicts, "velo_report_artifacts": []}[table]

    monkeypatch.setattr(eod, "ROOT", tmp_path)
    monkeypatch.setattr(eod, "URL_LIST_ROOT", tmp_path / "data" / "racing_post_url_lists")
    monkeypatch.setattr(eod, "_get", fake_get)

    with pytest.raises(RuntimeError, match="race-universe gate failed"):
        eod.prepare_cloud_eod_inputs("2026-11-02")


def test_prepare_cloud_eod_blocks_unresolved_top_pick(tmp_path, monkeypatch):
    races = [_race("100", "https://www.racingpost.com/racecards/1/test/2026-11-02/100")]
    verdicts = [_verdict("100", "h1", "Alpha")]
    verdicts[0]["full_analysis"] = {"predictions": []}

    def fake_get(table, _params):
        return {"races": races, "velo_verdicts": verdicts, "velo_report_artifacts": []}[table]

    monkeypatch.setattr(eod, "ROOT", tmp_path)
    monkeypatch.setattr(eod, "URL_LIST_ROOT", tmp_path / "data" / "racing_post_url_lists")
    monkeypatch.setattr(eod, "_get", fake_get)

    with pytest.raises(RuntimeError, match="TOP_PICK_NAME_MISSING"):
        eod.prepare_cloud_eod_inputs("2026-11-02")


def test_hydration_does_not_replace_fresh_verdict_backup(tmp_path, monkeypatch):
    target = tmp_path / "data" / "velo_prime_verdicts_2026_11_02.json"
    target.parent.mkdir(parents=True)
    target.write_text('[{"fresh": true}]', encoding="utf-8")
    monkeypatch.setattr(eod, "ROOT", tmp_path)
    monkeypatch.setattr(
        eod,
        "_get",
        lambda *_args, **_kwargs: [
            {
                "artifact_type": "velo_prime_verdicts",
                "source_path": "data/velo_prime_verdicts_2026_11_02.json",
                "payload": [{"fresh": False}],
            }
        ],
    )

    assert eod._hydrate_report_artifacts("2026-11-02") == 0
    assert json.loads(target.read_text(encoding="utf-8")) == [{"fresh": True}]


def test_verify_eod_report_requires_every_mandatory_step(tmp_path, monkeypatch):
    monkeypatch.setattr(eod, "ROOT", tmp_path)
    report_path = tmp_path / "data" / "reports" / "run_full_raceday_eod_2026_11_02.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "results": [
                    {"step": step, "ok": True}
                    for step in sorted(eod.MANDATORY_EOD_STEPS)
                ]
            }
        ),
        encoding="utf-8",
    )
    assert eod._verify_eod_report("2026-11-02")["mandatory_steps_passed"] == len(
        eod.MANDATORY_EOD_STEPS
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["results"][0]["ok"] = False
    report_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="postcondition failed"):
        eod._verify_eod_report("2026-11-02")


def test_cloud_persistence_command_excludes_unrefreshed_passports():
    command = full_eod._daily_artifact_persist_command(
        "2026-11-02", include_passports=False
    )
    assert "passports" not in command
    assert command[-3:] == ["--date", "2026-11-02", "--execute"]
    for kind in ("council", "mission", "ledger", "reports"):
        assert kind in command

    refreshed = full_eod._daily_artifact_persist_command(
        "2026-11-02", include_passports=True
    )
    assert "passports" in refreshed



# --- EOD-CATCHUP-01: a missed night is settled by the next run, oldest first -------------------------


def test_catch_up_picks_only_whole_day_misses_in_the_window_and_never_today():
    rows = [
        {"day": "2026-10-18", "uk_verdict_races": 21, "uk_sigma_rows": 0},  # outside a 14-day window
        {"day": "2026-10-29", "uk_verdict_races": 38, "uk_sigma_rows": 0},
        {"day": "2026-11-07", "uk_verdict_races": 46, "uk_sigma_rows": 45},  # partial: a void race, left alone
        {"day": "2026-11-08", "uk_verdict_races": 22, "uk_sigma_rows": 0},
        {"day": "2026-11-02", "uk_verdict_races": 0, "uk_sigma_rows": 0},  # nothing scored, nothing to settle
        {"day": "2026-11-10", "uk_verdict_races": 20, "uk_sigma_rows": 0},
        {"day": "2026-11-11", "uk_verdict_races": 27, "uk_sigma_rows": 0},  # today: the normal run settles it
    ]
    assert eod.select_catch_up_days(rows, "2026-11-11", 14) == ["2026-10-29", "2026-11-08", "2026-11-10"]
    assert eod.select_catch_up_days(rows, "2026-11-11", 30)[0] == "2026-10-18"
    assert eod.select_catch_up_days(rows, "2026-11-11", 0) == []


def _main_with(monkeypatch, argv, missing):
    settled: list[str] = []
    monkeypatch.setattr(eod, "_missing_settlement_days", lambda today, n: missing)
    monkeypatch.setattr(eod, "_login", lambda: None)

    def settle(day, args):
        settled.append(day)
        if day == "2026-11-08":
            raise RuntimeError("results page not ready")
        return {"date": day, "status": "PASS"}

    monkeypatch.setattr(eod, "_settle_day", settle)
    monkeypatch.setattr("sys.argv", ["rp_cloud_eod.py", *argv])
    return eod.main(), settled


def test_nightly_run_settles_the_backlog_first_and_one_failure_does_not_stop_the_rest(monkeypatch):
    code, settled = _main_with(monkeypatch, ["--execute"], ["2026-11-08", "2026-11-10"])
    assert settled[:2] == ["2026-11-08", "2026-11-10"] and len(settled) == 3  # then today
    assert code == 1  # a failed day is reported, not hidden


def test_backfill_only_never_settles_today(monkeypatch):
    code, settled = _main_with(monkeypatch, ["--execute", "--backfill-only"], ["2026-11-10"])
    assert settled == ["2026-11-10"] and code == 0


def test_an_explicit_date_settles_only_that_date(monkeypatch):
    code, settled = _main_with(monkeypatch, ["--execute", "--date", "2026-11-10"], ["2026-11-08"])
    assert settled == ["2026-11-10"] and code == 0


def test_daily_run_truth_is_rebuilt_from_supabase_for_mission_control(monkeypatch):
    """GATE_PIPELINE_TRUTH_MISSING: the EOD container must rebuild the morning's run-truth packet."""
    import sys
    import types

    calls = []
    fake = types.ModuleType("velo_daily_run_truth_watchdog")

    def write_report(date_str):
        calls.append(date_str)
        return {"status": "AUTOMATED_RUN_OK", "issues": []}

    fake.write_report = write_report
    monkeypatch.setitem(sys.modules, "velo_daily_run_truth_watchdog", fake)
    out = eod._rebuild_daily_run_truth("2026-11-12")
    assert calls == ["2026-11-12"]
    assert out["status"] == "AUTOMATED_RUN_OK"


def test_daily_run_truth_rebuild_failure_is_not_fatal_and_invents_nothing(monkeypatch):
    import sys
    import types

    fake = types.ModuleType("velo_daily_run_truth_watchdog")

    def write_report(date_str):
        raise RuntimeError("supabase down")

    fake.write_report = write_report
    monkeypatch.setitem(sys.modules, "velo_daily_run_truth_watchdog", fake)
    out = eod._rebuild_daily_run_truth("2026-11-12")
    assert out["status"] == "RUN_TRUTH_REBUILD_ERROR"
    assert "supabase down" in out["error"]


def test_settle_day_rebuilds_run_truth_before_the_eod_sequence(monkeypatch):
    order = []
    monkeypatch.setattr(eod, "prepare_cloud_eod_inputs", lambda d: order.append("prepare") or {})
    monkeypatch.setattr(eod, "_hydrate_runner_snapshots", lambda d: order.append("snapshots") or {})
    monkeypatch.setattr(
        eod, "_rebuild_daily_run_truth", lambda d: order.append("run_truth") or {"status": "AUTOMATED_RUN_OK"}
    )

    class Args:
        execute = False

    out = eod._settle_day("2026-11-12", Args())
    assert out["status"] == "PLAN_ONLY"
    assert order == ["prepare", "snapshots", "run_truth"]
