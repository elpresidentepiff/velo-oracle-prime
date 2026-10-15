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


def test_each_gap_is_reported() -> None:
    assert "only 0" in fr.evaluate(_stats(races=0), now=NOW)[0]
    assert any("form stored" in f for f in fr.evaluate(_stats(races_with_form=30), now=NOW))
    assert any("predictions" in f for f in fr.evaluate(_stats(races_with_predictions=20), now=NOW))
    assert any("runner stats" in f for f in fr.evaluate(_stats(runners_with_stats=100), now=NOW))
    stale = (NOW - timedelta(hours=9)).isoformat()
    assert any("worker may be down" in f for f in fr.evaluate(_stats(newest_form_update=stale), now=NOW))
    assert any("worker may be down" in f for f in fr.evaluate(_stats(newest_form_update=None), now=NOW))


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
