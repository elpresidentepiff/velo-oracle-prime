from __future__ import annotations

from src.velo.formfav_card_adapter import PROVIDER_OPINION_FIELDS, fetch_formfav_racecards


class DataOnlyClient:
    def meetings(self, date, race_code="gallops", timezone="UTC"):
        if race_code != "gallops":
            return {"meetings": []}
        return {"meetings": [{
            "country": "us", "track": "Test Park", "slug": "test-park",
            "races": [{"raceNumber": 1, "startTime": f"{date}T18:00:00Z", "timezone": "America/New_York"}],
        }]}

    def race_form(self, **kwargs):
        return {
            "track": "Test Park", "startTime": "2026-11-05T18:00:00Z",
            "runners": [{
                "number": 1, "name": "Evidence Only", "stats": {"overall": {"starts": 4, "wins": 1}},
                "speedMap": {"runningStyle": "P"}, "classProfile": {"currentRating": 72},
            }],
        }

    def prices(self, **kwargs):
        return {"runners": []}


def test_global_adapter_never_exposes_formfav_prediction_opinion() -> None:
    races, report = fetch_formfav_racecards(
        date_str="2026-11-05", countries={"us"}, include_prices=False, client=DataOnlyClient()
    )
    assert report["races_loaded"] == 1
    race = races[0]
    assert race["_formfav"]["data_only"] is True
    assert race["_formfav"]["provider_predictions_consumed"] is False
    assert not PROVIDER_OPINION_FIELDS.intersection(race["runners"][0]["_formfav"])


class HarnessClient(DataOnlyClient):
    def meetings(self, date, race_code="gallops", timezone="UTC"):
        if race_code != "harness":
            return {"meetings": []}
        return {"meetings": [{
            "country": "au", "track": "Pinjarra", "slug": "pinjarra",
            "races": [{"raceNumber": 7, "startTime": f"{date}T08:40:00Z", "timezone": "Australia/Perth"}],
        }]}

    def race_form(self, **kwargs):
        assert kwargs["race_code"] == "harness"
        return {
            "track": "Pinjarra", "startTime": "2026-11-16T08:40:00Z", "timezone": "Australia/Perth",
            "runners": [{"number": 1, "name": "Harness Evidence", "stats": {}}],
        }


def test_global_adapter_loads_harness_and_reports_complete_provider_universe() -> None:
    races, report = fetch_formfav_racecards(
        date_str="2026-11-16", countries={"au"}, include_prices=False, client=HarnessClient(),
    )
    assert len(races) == 1
    assert races[0]["_formfav"]["race_code"] == "harness"
    assert report["race_codes"] == ["gallops", "harness"]
    assert report["expected_races"] == report["races_loaded"] == 1
    assert report["missing_races"] == 0 and report["coverage_status"] == "COMPLETE"
