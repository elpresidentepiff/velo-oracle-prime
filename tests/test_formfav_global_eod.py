from __future__ import annotations

from datetime import UTC, datetime

from scripts.ops import formfav_global_eod as eod
from scripts.ops import formfav_live_worker as worker

RACE = {
    "provider_race_key": "formfav:us:2026-10-13:x:r1",
    "race_date": "2026-10-13",
    "country": "us",
    "track": "X",
    "race_number": 1,
    "start_time": "2026-10-13T18:00:00+00:00",
}


def _pred(order):
    return {
        "model_version": "v",
        "confidence": "low",
        "predictions_payload": {
            "predictions": [
                {"name": f"H{n}", "number": n, "modelRank": i + 1, "winProb": 0.3 - i * 0.05}
                for i, n in enumerate(order)
            ]
        },
    }


def _res(positions, interim, scratched=()):
    return {
        "result_stage": "interim" if interim else "final",
        "interim": interim,
        "results_payload": {
            "placings": [
                {"name": f"H{n}", "number": n, "position": pos, "scratched": n in scratched,
                 "resultStage": "correct_weight"}
                for n, pos in positions.items()
            ]
        },
    }


def test_final_top_pick_win() -> None:
    row = eod.reconcile_race(RACE, _pred([1, 2, 3, 4]), _res({1: 1, 2: 2, 3: 3, 4: 4}, False))
    assert row["basis"] == "final"
    assert row["top1_hit"] is True and row["winner_in_top3"] is True
    assert row["winner_model_rank"] == 1 and row["top1_finish_position"] == 1


def test_provisional_when_provider_still_interim() -> None:
    row = eod.reconcile_race(RACE, _pred([1, 2, 3, 4]), _res({3: 1, 1: 2, 2: 3, 4: 4}, True))
    assert row["basis"] == "provisional"
    assert row["top1_hit"] is False and row["winner_in_top3"] is True
    assert row["winner_model_rank"] == 3 and row["top1_finish_position"] == 2
    assert row["details"]["all_correct_weight"] is True


def test_winner_outside_top3() -> None:
    row = eod.reconcile_race(RACE, _pred([1, 2, 3, 4]), _res({4: 1, 1: 2, 2: 3, 3: 4}, False))
    assert row["winner_in_top3"] is False and row["winner_model_rank"] == 4


def test_dead_heat_counts_either_winner() -> None:
    row = eod.reconcile_race(RACE, _pred([1, 2, 3]), _res({2: 1, 3: 1, 1: 3}, False))
    assert row["dead_heat"] is True and row["winner_numbers"] == [2, 3]
    assert row["winner_in_top3"] is True and row["winner_model_rank"] == 2


def test_scratched_top_pick_is_flagged() -> None:
    row = eod.reconcile_race(RACE, _pred([1, 2, 3]), _res({1: None, 2: 1, 3: 2}, False, scratched=(1,)))
    assert row["top1_scratched"] is True and row["top1_hit"] is False


def test_pending_or_missing_result_is_no_result() -> None:
    assert eod.reconcile_race(RACE, _pred([1, 2]), None)["basis"] == "no_result"
    pending = {"result_stage": "pending", "interim": True, "results_payload": {"resultStatus": "pending"}}
    assert eod.reconcile_race(RACE, _pred([1, 2]), pending)["basis"] == "no_result"


def test_no_prediction_means_no_row() -> None:
    assert eod.reconcile_race(RACE, None, _res({1: 1}, False)) is None


def test_summary_keeps_final_and_provisional_apart() -> None:
    rows = [
        eod.reconcile_race(RACE, _pred([1, 2, 3]), _res({1: 1, 2: 2, 3: 3}, False)),
        eod.reconcile_race(RACE, _pred([1, 2, 3]), _res({2: 1, 1: 2, 3: 3}, True)),
    ]
    s = eod.summarise(rows)["us"]
    assert s["final"]["top1_wins"] == 1 and s["provisional"]["top1_wins"] == 0


def test_settle_stops_on_rate_limit_and_skips_final(monkeypatch) -> None:
    races = [dict(RACE, provider_race_key=f"k{i}", race_number=i) for i in range(3)]
    preds = {r["provider_race_key"]: _pred([1, 2]) for r in races}
    results = {"k0": {"interim": False}}
    calls: list[str] = []

    def fetch(r):
        calls.append(r["provider_race_key"])
        raise RuntimeError("FormFav rate limit exceeded (HTTP 429)")

    report = eod.settle_day(
        "2026-10-13", races=races, results=results, preds=preds, fetch_result=fetch,
        persist_result=lambda *_: None, is_final=lambda p: True,
        on_error=lambda e: "429" in str(e), attempts={},
        started_before=datetime(2026, 10, 14, tzinfo=UTC), sleep=lambda _s: None,
    )
    assert calls == ["k1"] and report["stopped_rate_limited"] is True


def test_settle_upgrades_and_caps_attempts() -> None:
    races = [dict(RACE, provider_race_key="k1")]
    preds = {"k1": _pred([1, 2])}
    persisted: list[str] = []
    attempts: dict[str, int] = {}
    kwargs = {
        "races": races, "results": {}, "preds": preds,
        "fetch_result": lambda r: {"placings": [{"number": 1, "position": 1}], "resultStatus": "final"},
        "persist_result": lambda k, p: persisted.append(k), "is_final": lambda p: True,
        "on_error": lambda e: False, "attempts": attempts, "max_attempts": 1,
        "started_before": datetime(2026, 10, 14, tzinfo=UTC), "sleep": lambda _s: None,
    }
    first = eod.settle_day("2026-10-13", **kwargs)
    second = eod.settle_day("2026-10-13", **kwargs)
    assert first["upgraded_to_final"] == 1 and persisted == ["k1"]
    assert second["candidates"] == 0


def test_settle_skips_races_not_yet_off() -> None:
    races = [dict(RACE, provider_race_key="k1", start_time="2026-10-14T20:00:00+00:00")]
    report = eod.settle_day(
        "2026-10-14", races=races, results={}, preds={"k1": _pred([1])},
        fetch_result=lambda r: {}, persist_result=lambda *_: None, is_final=lambda p: False,
        on_error=lambda e: False, attempts={},
        started_before=datetime(2026, 10, 14, 19, tzinfo=UTC), sleep=lambda _s: None,
    )
    assert report["candidates"] == 0


def test_run_day_dry_run_writes_nothing() -> None:
    import json

    store = {
        "formfav_races": [RACE],
        "formfav_predictions": [dict(_pred([1, 2]), provider_race_key=RACE["provider_race_key"])],
        "formfav_results": [dict(_res({1: 1, 2: 2}, False), provider_race_key=RACE["provider_race_key"])],
    }

    def sb(method, path, data=None, prefer=None):
        return json.dumps(store[path.split("?")[0]]).encode()

    written: list = []
    report = eod.run_day(
        "2026-10-13", sb_request=sb, upsert=lambda *a: written.append(a), settle=None, dry_run=True,
    )
    assert written == [] and report["by_country"]["us"]["final"]["top1_wins"] == 1

    report = eod.run_day(
        "2026-10-13", sb_request=sb, upsert=lambda *a: written.append(a), settle=None, write_artifact=False,
    )
    assert written[0][0] == "formfav_sigma_audits" and written[0][2] == "provider_race_key"
    assert report["rows_written"] == 1


def test_meetings_refresh_prioritises_today_over_yesterday() -> None:
    dates = worker._meeting_dates(datetime(2026, 10, 14, 12, tzinfo=UTC))
    assert dates == ["2026-10-14", "2026-10-15", "2026-10-13"]
