from datetime import UTC, datetime

from scripts.ops import formfav_live_worker as worker


def test_main_orders_live_capture_before_global_eod(monkeypatch):
    calls: list[str] = []

    class StopLoop(Exception):
        pass

    monkeypatch.setattr(worker, "FormFavClient", lambda: object())
    monkeypatch.setattr(worker, "_sb_env", lambda: ("url", "key"))
    monkeypatch.setattr(worker, "_run_live_cycle", lambda client, now: calls.append("live"))

    def eod(client, now):
        calls.append("eod")
        raise StopLoop

    monkeypatch.setattr(worker, "_maybe_run_global_eod", eod)
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: (_ for _ in ()).throw(StopLoop()))

    try:
        worker.main()
    except StopLoop:
        pass

    assert calls == ["live", "eod"]


def test_live_cycle_refreshes_and_processes_current_card(monkeypatch):
    calls: list[str] = []
    now = datetime(2026, 11, 7, 9, 0, tzinfo=UTC)
    monkeypatch.setattr(worker, "_provider_backoff_remaining", lambda: 0)

    def refresh(client, captured_now):
        calls.append("refresh")
        worker._meeting_cache = {
            "2026-11-07": [
                {"races": [{"raceNumber": 1}, {"raceNumber": 2, "abandoned": True}]}
            ]
        }

    monkeypatch.setattr(worker, "_refresh_meetings", refresh)
    monkeypatch.setattr(
        worker,
        "_process_race",
        lambda client, date_str, meeting, race, captured_now: calls.append("race"),
    )

    assert worker._run_live_cycle(object(), now) == 1
    assert calls == ["refresh", "race"]
