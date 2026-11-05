from __future__ import annotations

from src.velo.formfav_card_adapter import PROVIDER_OPINION_FIELDS, fetch_formfav_racecards


class DataOnlyClient:
    def meetings(self, date, timezone="UTC"):
        return {"meetings": [{
            "country": "us", "track": "Test Park", "slug": "test-park",
            "races": [{"raceNumber": 1, "startTime": f"{date}T18:00:00Z"}],
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
