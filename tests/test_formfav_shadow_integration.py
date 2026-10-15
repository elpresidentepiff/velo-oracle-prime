from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.ops.run_formfav_uk_enhanced_shadow import _default_date
from src.velo.formfav_enrichment import _closest_existing_race, enrich_existing_racecards
from src.velo.formfav_uk_features import build_race_shadow_packet
from src.velo.supabase_racecard_source import load_supabase_rp_racecards


def test_unattended_shadow_defaults_to_current_london_race_day() -> None:
    assert _default_date() == datetime.now(ZoneInfo("Europe/London")).date().isoformat()


def test_rp_dot_time_and_track_alias_match_formfav_utc() -> None:
    race = {
        "race_id": "kempton-1612",
        "date": "2026-10-12",
        "course": "Kempton (AW)",
        "off_time": "4.12",
        "country": "GB",
    }
    assert _closest_existing_race(
        [race],
        track="Kempton Park",
        start_time="2026-10-12T15:12:00Z",
        timezone="Europe/London",
        race_number=1,
        country="gb",
    ) is race


def test_nullable_formfav_start_time_uses_meeting_race_ordinal() -> None:
    races = [
        {"race_id": "r1", "course": "Roscommon", "off_time": "1.30", "country": "IRE"},
        {"race_id": "r2", "course": "Roscommon", "off_time": "2.00", "country": "IRE"},
    ]
    assert _closest_existing_race(
        races,
        track="Roscommon Racecourse",
        start_time=None,
        timezone="Europe/Dublin",
        race_number=2,
        country="ie",
    ) is races[1]


class _FakeFormFav:
    def meetings(self, date: str, timezone: str):
        return {
            "meetings": [{
                "country": "gb",
                "track": "Kempton Park",
                "slug": "kempton-park",
                "races": [{
                    "raceNumber": 1,
                    "startTime": "2026-10-12T15:12:00Z",
                    "timezone": "Europe/London",
                }],
            }]
        }

    def race_form(self, **kwargs):
        return {
            "track": "Kempton Park",
            "distance": "1600m",
            "condition": "Standard",
            "paceScenario": "FAST",
            "runners": [{
                "number": 3,
                "name": "Café Royal",
                "barrier": 4,
                "form": "32121",
                "last20Starts": "5432132121",
                "speedMap": {
                    "runningStyle": "P",
                    "earlySpeedIndex": 8.1,
                    "settlingPosition": 2,
                },
                "classProfile": {
                    "currentRating": 85,
                    "peakRating": 89,
                    "highestClassWon": 3,
                    "optimalRangeMin": 82,
                    "optimalRangeMax": 90,
                    "trend": "rising",
                },
                "raceClassFit": {
                    "raceClassRating": 86,
                    "classDifference": -1,
                    "withinOptimalRange": True,
                    "assessment": "comfort_zone",
                },
                "stats": {
                    "overall": {"starts": 20, "wins": 4, "places": 10},
                    "track": {"starts": 6, "wins": 2, "places": 4},
                    "distance": {"starts": 8, "wins": 2, "places": 5},
                    "trackDistance": {"starts": 4, "wins": 1, "places": 3},
                    "conditions": {
                        "synthetic": {"starts": 9, "wins": 3, "places": 6}
                    },
                },
            }],
        }

    def track_bias(self, **kwargs):
        return {
            "biasStrength": "moderate",
            "barrierStats": [{
                "barrierNumber": 4,
                "totalStarts": 40,
                "wins": 8,
                "places": 19,
                "advantage": 0.11,
            }],
        }


def test_shadow_enrichment_builds_pace_class_form_and_bias_without_mutating_prime() -> None:
    prime_races = [{
        "race_id": "kempton-1612",
        "date": "2026-10-12",
        "course": "Kempton (AW)",
        "off_time": "4.12",
        "country": "GB",
        "going": "Standard",
        "runners": [{
            "horse": "Cafe Royal",
            "start_number": 3,
            "draw": 4,
            "odds": 7.0,
        }],
    }]
    before = deepcopy(prime_races)

    shadow, audit = enrich_existing_racecards(
        date_str="2026-10-12",
        races=prime_races,
        countries={"gb"},
        include_prices=False,
        include_track_bias=True,
        client=_FakeFormFav(),
    )
    packet = build_race_shadow_packet(shadow[0])
    features = packet["runners"][0]

    assert prime_races == before
    assert "_formfav" not in prime_races[0]
    assert audit["races_matched"] == 1
    assert audit["runners_matched"] == 1
    assert audit["matching_methods"] == {"track_time": 1}
    assert features["ff_speedmap_present"] == 1.0
    assert features["ff_pace_scenario_present"] == 1.0
    assert features["ff_class_profile_present"] == 1.0
    assert features["ff_class_fit_present"] == 1.0
    assert features["ff_form_present"] == 1.0
    assert features["ff_track_bias_present"] == 1.0
    # 2026-10-15: sample size was silently 0 for every runner (key "totalStarts" vs "starts").
    assert features["ff_barrier_bias_starts"] == 40.0
    assert features["ff_barrier_bias_sample_ok"] == 1.0
    assert features["ff_barrier_bias_win_rate_raw"] == 8 / 40
    assert features["ff_barrier_bias_win_rate_smoothed"] is not None
    assert features["ff_training_eligible"] == 1.0


def test_supabase_loader_reconstructs_rp_card_and_marks_no_scoring(monkeypatch) -> None:
    payload = [{
        "race_id": "rac-1",
        "course": "Roscommon",
        "date": "2026-10-12",
        "time": "13:30:00",
        "race_type": "Hurdle",
        "distance_f": 16,
        "going": "Good",
        "class": "4",
        "race_name": "Test Hurdle",
        "raw": {
            "source": "racing_post_account_racecard_capture",
            "country": "IRE",
            "race_time": "1.30",
            "runners": [{
                "horse": "One Horse",
                "weight_lbs": 154,
                "form_figures": "12-3",
                "forecast_odds": 6.0,
            }],
        },
    }]

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-secret")
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Response())

    races = load_supabase_rp_racecards("2026-10-12")
    race = races[0]
    runner = race["runners"][0]
    assert race["country"] == "ie"
    assert race["off_time"] == "1.30"
    assert race["_source"]["velo_scoring_allowed"] is False
    assert race["_source"]["mode"] == "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
    assert runner["lbs"] == 154
    assert runner["form"] == "12-3"
    assert runner["odds"] == 6.0


def test_missing_provider_pace_scenario_is_transparently_derived_from_speed_maps() -> None:
    styles = (("L", 8.5), ("L", 7.8), ("P", 7.1), ("M", 5.0))
    race = {
        "race_id": "pace-1",
        "course": "Test Course",
        "_formfav": {"country": "gb", "paceScenario": None},
        "runners": [
            {
                "horse": f"Horse {index}",
                "_formfav": {
                    "name": f"Horse {index}",
                    "speedMap": {
                        "runningStyle": style,
                        "earlySpeedIndex": speed,
                        "settlingPosition": index,
                    },
                },
            }
            for index, (style, speed) in enumerate(styles, start=1)
        ],
    }

    packet = build_race_shadow_packet(race)

    assert packet["formfav_pace_scenario"] == "VERY_FAST"
    assert packet["pace_scenario_source"] == "speed_map_derived"
    assert packet["pace_pressure_score"] == 1.25
    assert all(row["ff_pace_scenario_present"] == 1.0 for row in packet["runners"])
    assert all(row["ff_pace_scenario_provider"] == 0.0 for row in packet["runners"])
    assert all(row["ff_pace_scenario_derived"] == 1.0 for row in packet["runners"])
    assert race["_formfav"].get("paceScenarioDerived") is None



def test_barrier_bias_without_a_sample_is_flagged_not_trusted() -> None:
    from src.velo.formfav_uk_features import _bias_for_barrier, _smoothed_stat

    row = _bias_for_barrier({"barrierStats": [{"barrierNumber": 3, "advantage": 0.2}]}, 3)
    stat = _smoothed_stat(row, "ff_barrier_bias")
    assert row is not None and stat["ff_barrier_bias_starts"] == 0.0
    assert stat["ff_barrier_bias_win_rate_smoothed"] is None
    # plain "starts" (the other stat blocks) still works
    assert _smoothed_stat({"starts": 10, "wins": 2, "places": 5}, "x")["x_starts"] == 10.0
