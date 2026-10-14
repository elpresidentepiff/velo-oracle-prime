from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.velo import formfav_cache_client as cc
from src.velo.formfav_client import FormFavError

NOW = datetime(2026, 10, 14, 20, 0, tzinfo=UTC)
FRESH = (NOW - timedelta(minutes=20)).isoformat()
STALE = (NOW - timedelta(hours=30)).isoformat()


def _fetch_factory(updated=FRESH):
    def fetch(path: str):
        if path.startswith("formfav_races?race_date"):
            return [
                {"country": "gb", "track": "Kempton Park", "meeting_slug": "kempton-park", "updated_at": updated,
                 "metadata": {"raceNumber": 1, "startTime": "2026-10-14T15:25:00Z"}},
                {"country": "gb", "track": "Kempton Park", "meeting_slug": "kempton-park", "updated_at": updated,
                 "metadata": {"meeting_race": {"raceNumber": 2, "startTime": "2026-10-14T16:00:00Z"}}},  # legacy nested row
            ]
        if path.startswith("formfav_races?provider_race_key"):
            return [{"updated_at": updated, "metadata": {"raceNumber": 1, "distance": "2200m", "weather": "Overcast"},
                     "form_meta": {"raceClass": "Class 4", "distance": "2212m"}}]
        if path.startswith("formfav_runner_form"):
            return [{"updated_at": updated, "form_payload": {"number": 1, "name": "A"}},
                    {"updated_at": updated, "form_payload": {"number": 2, "name": "B"}}]
        if path.startswith("formfav_predictions"):
            return [{"updated_at": updated, "predictions_payload": {"predictions": [{"name": "A", "modelRank": 1}]}}]
        raise AssertionError(path)
    return fetch


class _Live:
    def __init__(self):
        self.calls = []

    def meetings(self, date, race_code="gallops", timezone="Europe/London"):
        self.calls.append("meetings")
        return {"meetings": [], "_source": "live"}

    def race_form(self, **kw):
        self.calls.append("race_form")
        return {"runners": [], "_source": "live"}

    def prices(self, **kw):
        self.calls.append("prices")
        return {}

    def track_bias(self, *a, **kw):
        self.calls.append("track_bias")
        return {}


def test_race_key_matches_worker() -> None:
    from scripts.ops import formfav_live_worker as w
    assert cc.race_key("2026-10-14", "gb", "Kempton Park", 3) == w._race_key("2026-10-14", "gb", "Kempton Park", 3)


def test_meetings_served_from_cache_without_live_call() -> None:
    live = _Live()
    c = cc.CachedFormFavClient(live, fetch=_fetch_factory(), now=lambda: NOW)
    out = c.meetings("2026-10-14")
    assert live.calls == [] and out["_source"] == "formfav_cache"
    m = out["meetings"][0]
    assert m["slug"] == "kempton-park" and [r["raceNumber"] for r in m["races"]] == [1, 2]


def test_race_form_rebuilt_from_cache() -> None:
    live = _Live()
    c = cc.CachedFormFavClient(live, fetch=_fetch_factory(), now=lambda: NOW)
    form = c.race_form(date="2026-10-14", track="kempton-park", race=1, country="gb")
    assert live.calls == [] and form["raceClass"] == "Class 4"
    assert form["distance"] == "2212m" and form["weather"] == "Overcast"  # form_meta wins, meeting race fills gaps
    assert [r["name"] for r in form["runners"]] == ["A", "B"]


def test_stale_rows_fall_back_to_live() -> None:
    live = _Live()
    c = cc.CachedFormFavClient(live, fetch=_fetch_factory(STALE), now=lambda: NOW)
    assert c.meetings("2026-10-14")["_source"] == "live"
    assert c.race_form(date="2026-10-14", track="kempton-park", race=1, country="gb")["_source"] == "live"
    assert live.calls == ["meetings", "race_form"] and c.stats["live_fallbacks"] == 2


def test_miss_without_live_client_raises_clear_error() -> None:
    c = cc.CachedFormFavClient(None, fetch=_fetch_factory(STALE), now=lambda: NOW)
    with pytest.raises(FormFavError, match="cache miss"):
        c.meetings("2026-10-14")
    with pytest.raises(FormFavError):
        c.track_bias("Kempton", 2000)


def test_predictions_from_cache_and_prices_go_live() -> None:
    live = _Live()
    c = cc.CachedFormFavClient(live, fetch=_fetch_factory(), now=lambda: NOW)
    assert c.predictions(date="2026-10-14", track="kempton-park", race=1, country="gb")["predictions"][0]["name"] == "A"
    c.prices(date="2026-10-14", track="kempton-park", race=1, country="gb")
    assert live.calls == ["prices"]


def test_build_client_respects_switch_and_missing_env(monkeypatch) -> None:
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", "FORMFAV_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert cc.build_enrichment_client() is None
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    assert isinstance(cc.build_enrichment_client(), cc.CachedFormFavClient)
    monkeypatch.setenv("FORMFAV_ENRICH_FROM_CACHE", "0")
    assert cc.build_enrichment_client() is None


def test_real_enrichment_runs_end_to_end_on_cached_data_with_no_live_client() -> None:
    """The failure mode we are fixing: no live API (429) but the worker's rows exist."""
    from copy import deepcopy

    from src.velo.formfav_enrichment import enrich_existing_racecards
    from src.velo.formfav_uk_features import build_race_shadow_packet

    runner_form = {
        "number": 3, "name": "Café Royal", "barrier": 4, "form": "32121", "last20Starts": "5432132121",
        "speedMap": {"runningStyle": "P", "earlySpeedIndex": 8.1, "settlingPosition": 2},
        "classProfile": {"currentRating": 85, "peakRating": 89, "highestClassWon": 3,
                         "optimalRangeMin": 82, "optimalRangeMax": 90, "trend": "rising"},
        "raceClassFit": {"raceClassRating": 86, "classDifference": -1, "withinOptimalRange": True,
                         "assessment": "comfort_zone"},
        "stats": {"overall": {"starts": 20, "wins": 4, "places": 10},
                  "track": {"starts": 6, "wins": 2, "places": 4},
                  "distance": {"starts": 8, "wins": 2, "places": 5},
                  "trackDistance": {"starts": 4, "wins": 1, "places": 3},
                  "conditions": {"synthetic": {"starts": 9, "wins": 3, "places": 6}}},
    }

    def fetch(path: str):
        if path.startswith("formfav_races?race_date"):
            return [{"country": "gb", "track": "Kempton Park", "meeting_slug": "kempton-park", "updated_at": FRESH,
                     "metadata": {"raceNumber": 1, "startTime": "2026-10-12T15:12:00Z", "timezone": "Europe/London",
                                  "distance": "1600m", "condition": "Standard", "paceScenario": "FAST"}}]
        if path.startswith("formfav_races?provider_race_key"):
            return [{"updated_at": FRESH, "metadata": {"raceNumber": 1, "paceScenario": "FAST", "distance": "1600m"},
                     "form_meta": {"track": "Kempton Park", "condition": "Standard"}}]
        if path.startswith("formfav_runner_form"):
            return [{"updated_at": FRESH, "form_payload": runner_form}]
        raise AssertionError(path)

    client = cc.CachedFormFavClient(None, fetch=fetch, now=lambda: NOW)
    prime = [{"race_id": "kempton-1612", "date": "2026-10-12", "course": "Kempton (AW)", "off_time": "4.12",
              "country": "GB", "going": "Standard",
              "runners": [{"horse": "Cafe Royal", "start_number": 3, "draw": 4, "odds": 7.0}]}]
    before = deepcopy(prime)
    shadow, audit = enrich_existing_racecards(
        date_str="2026-10-12", races=prime, countries={"gb"}, include_prices=False,
        include_track_bias=False, client=client,
    )
    f = build_race_shadow_packet(shadow[0])["runners"][0]
    assert prime == before and audit["errors"] == []
    assert audit["races_matched"] == 1 and audit["runners_matched"] == 1 and audit["form_calls_ok"] == 1
    assert f["ff_speedmap_present"] == 1.0 and f["ff_class_fit_present"] == 1.0
    assert f["ff_pace_scenario_present"] == 1.0 and f["ff_form_present"] == 1.0
    assert client.stats["cache_hits"] >= 2 and client.stats["live_fallbacks"] == 0
