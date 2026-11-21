from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.ops import formfav_readiness as fr

NOW = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
FRESH = (NOW - timedelta(minutes=30)).isoformat()


def _stats(**kw):
    s = {"date": "2026-10-15", "races": 40, "races_with_form": 40, "races_with_predictions": 40,
         "runners": 351, "scratched": 5, "runners_with_stats": 320, "runners_with_speedmap": 259,
         "runners_with_class": 304, "newest_form_update": FRESH}
    s.update(kw)
    return s


def test_ready_when_stored_complete_and_fresh() -> None:
    assert fr.evaluate(_stats(), now=NOW) == []


def test_default_gate_requires_every_published_race() -> None:
    assert any("form stored" in f for f in fr.evaluate(_stats(races_with_form=39), now=NOW))
    assert any("predictions" in f for f in fr.evaluate(_stats(races_with_predictions=39), now=NOW))


def test_each_gap_is_reported() -> None:
    assert "only 0" in fr.evaluate(_stats(races=0), now=NOW)[0]
    assert any("form stored" in f for f in fr.evaluate(_stats(races_with_form=30), now=NOW))
    assert any("predictions" in f for f in fr.evaluate(_stats(races_with_predictions=20), now=NOW))
    assert any("runner stats" in f for f in fr.evaluate(_stats(runners_with_stats=100), now=NOW))
    stale = (NOW - timedelta(hours=9)).isoformat()
    assert any("refresh cycle has been missed" in f for f in fr.evaluate(_stats(newest_form_update=stale), now=NOW))
    assert any("refresh cycle has been missed" in f for f in fr.evaluate(_stats(newest_form_update=None), now=NOW))


def test_form_read_one_refresh_cycle_ago_passes_when_the_worker_is_alive() -> None:
    """2026-11-15: form re-read at 01:09, gate at 07:00, worker running. That day was refused."""
    now = datetime(2026, 11, 15, 7, 0, 8, tzinfo=UTC)
    stats = _stats(newest_form_update="2026-11-15T01:09:23.896449+00:00", worker_heartbeat="2026-11-15T06:59:10+00:00")
    assert fr.evaluate(stats, now=now, require_predictions=False) == []


def test_a_dead_worker_fails_even_with_recent_form() -> None:
    now = datetime(2026, 11, 15, 7, 0, tzinfo=UTC)
    stats = _stats(newest_form_update="2026-11-15T05:30:00+00:00", worker_heartbeat="2026-11-15T05:31:00+00:00")
    fails = fr.evaluate(stats, now=now)
    assert len(fails) == 1 and "worker may be down" in fails[0]
    assert any("worker may be down" in f for f in fr.evaluate(_stats(worker_heartbeat=None), now=NOW))


def test_form_older_than_a_refresh_cycle_fails_even_when_the_worker_is_alive() -> None:
    now = datetime(2026, 11, 15, 7, 0, tzinfo=UTC)
    stats = _stats(newest_form_update="2026-11-14T22:00:00+00:00", worker_heartbeat="2026-11-15T06:59:00+00:00")
    fails = fr.evaluate(stats, now=now)
    assert len(fails) == 1 and "refresh cycle has been missed" in fails[0]


def test_the_form_age_limit_covers_the_six_hour_refresh_and_can_be_set(monkeypatch) -> None:
    assert fr.DEFAULT_MAX_FORM_AGE > timedelta(hours=6)
    monkeypatch.setenv("FORMFAV_READY_MAX_FORM_AGE_HOURS", "2.5")
    assert fr._hours_from_env("FORMFAV_READY_MAX_FORM_AGE_HOURS", fr.DEFAULT_MAX_FORM_AGE) == timedelta(hours=2.5)
    for bad in ("", "abc", "0", "-1"):
        monkeypatch.setenv("FORMFAV_READY_MAX_FORM_AGE_HOURS", bad)
        assert fr._hours_from_env("FORMFAV_READY_MAX_FORM_AGE_HOURS", fr.DEFAULT_MAX_FORM_AGE) == fr.DEFAULT_MAX_FORM_AGE


def test_collect_reports_the_worker_heartbeat_from_the_race_rows() -> None:
    def fetch(path: str):
        if path.startswith("formfav_races?"):
            return [{"provider_race_key": "a", "updated_at": "2026-11-15T06:58:00+00:00"},
                    {"provider_race_key": "b", "updated_at": "2026-11-15T06:59:30+00:00"}]
        return []

    stats = fr.collect("2026-11-15", {"gb", "ie"}, fetch=fetch)
    assert stats["worker_heartbeat"] == "2026-11-15T06:59:30+00:00"


def test_prediction_coverage_never_gates_factual_readiness() -> None:
    assert fr.evaluate(
        _stats(races_with_predictions=0),
        now=NOW,
        min_form=0.8,
        require_predictions=False,
    ) == []


def test_prediction_endpoint_failure_does_not_break_factual_collection() -> None:
    def fetch(path: str):
        if path.startswith("formfav_races"):
            return [{"provider_race_key": "a", "updated_at": FRESH}]
        if path.startswith("formfav_runner_form"):
            return [{
                "provider_race_key": "a",
                "scratched": False,
                "updated_at": FRESH,
                "form_payload": {"stats": {"x": 1}},
            }]
        if path.startswith("formfav_predictions"):
            raise RuntimeError("benchmark offline")
        raise AssertionError(path)

    stats = fr.collect("2026-10-15", {"gb", "ie"}, fetch=fetch)

    assert stats["races_with_form"] == 1
    assert stats["races_with_predictions"] == 0
    assert stats["prediction_benchmark_errors"] == ["RuntimeError: benchmark offline"]
    assert fr.evaluate(stats, now=NOW, min_form=0.8, require_predictions=False) == []


def test_collect_counts_from_rest_rows() -> None:
    def fetch(path: str):
        if path.startswith("formfav_races"):
            return [{"provider_race_key": "a"}, {"provider_race_key": "b"}]
        if path.startswith("formfav_runner_form"):
            return [
                {"provider_race_key": "a", "scratched": False, "updated_at": FRESH,
                 "form_payload": {"stats": {"x": 1}, "speedMap": {"s": 1}, "classProfile": {"c": 1}}},
                {"provider_race_key": "a", "scratched": True, "updated_at": FRESH, "form_payload": {}},
            ]
        if path.startswith("formfav_predictions"):
            return [{"provider_race_key": "a"}]
        raise AssertionError(path)

    s = fr.collect("2026-10-15", {"gb", "ie"}, fetch=fetch)
    assert s["races"] == 2 and s["races_with_form"] == 1 and s["races_with_predictions"] == 1
    assert s["runners"] == 2 and s["scratched"] == 1 and s["runners_with_stats"] == 1
    assert s["newest_form_update"] == FRESH
