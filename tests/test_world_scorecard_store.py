from __future__ import annotations

from src.velo.world_scorecard_store import build_rows


def test_build_rows_is_world_only_data_only_and_pre_off() -> None:
    payload = {
        "date": "2026-11-05",
        "generated_at": "2026-11-05T10:00:00+00:00",
        "scoring_engine": "existing_velo_prime_stack",
        "races": [{
            "provider_race_key": "formfav:ca:2026-11-05:woodbine:r1",
            "scheduled_off": "2026-11-05T18:00:00+00:00",
            "country": "ca", "course": "Woodbine", "race_number": 1,
            "scorecard": [{
                "rank": 1, "horse": "North Star", "horse_id": "ff_ca_1",
                "velo_prime_prob": 0.24, "place_prob": 0.61,
                "longshot_prob": 0.05, "sp_dec": 5.0,
                "improvement_score": 0.2, "market_deception_score": 0.1,
                "confidence_level": "medium",
            }],
        }],
    }
    rows = build_rows(payload)
    assert len(rows) == 1
    assert rows[0]["provider_predictions_consumed"] is False
    assert rows[0]["generated_pre_off"] is True
    assert rows[0]["country"] == "ca"


def test_build_rows_excludes_uk_and_ire() -> None:
    payload = {
        "date": "2026-11-05", "generated_at": "2026-11-05T10:00:00+00:00",
        "races": [{
            "provider_race_key": "formfav:gb:x", "scheduled_off": "2026-11-05T12:00:00Z",
            "country": "gb", "scorecard": [{"horse": "A", "horse_id": "a", "rank": 1}],
        }],
    }
    assert build_rows(payload) == []


def test_build_rows_rejects_post_off_scoring() -> None:
    payload = {
        "date": "2026-11-05", "generated_at": "2026-11-05T13:00:00+00:00",
        "races": [{
            "provider_race_key": "formfav:ca:x", "scheduled_off": "2026-11-05T12:00:00Z",
            "country": "ca", "race_number": 1,
            "scorecard": [{"horse": "A", "horse_id": "a", "rank": 1}],
        }],
    }
    assert build_rows(payload) == []
