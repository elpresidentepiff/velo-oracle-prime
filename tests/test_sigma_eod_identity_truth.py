"""Regression tests for post-race top-pick identity reporting.

These tests are pure: they do not connect to Supabase, Railway, Telegram, or
any execution bridge.
"""

from scripts.ops.run_results_sigma import _extract_top_pick_name_from_prediction


def test_extracts_top_pick_name_from_production_full_analysis_dict():
    verdict = {
        "top_rank_horse_id": "horse-2",
        "full_analysis": {
            "predictions": [
                {"horse_id": "horse-1", "horse": "First Runner"},
                {"horse_id": "horse-2", "horse": "Declared Pick"},
            ]
        },
    }

    assert _extract_top_pick_name_from_prediction(verdict) == "Declared Pick"


def test_extracts_top_pick_name_from_serialized_production_shape():
    verdict = {
        "top_rank_horse_id": "horse-7",
        "full_analysis": (
            '{"predictions": [{"horse_id": "horse-7", '
            '"horse_name": "Serialized Pick"}]}'
        ),
    }

    assert _extract_top_pick_name_from_prediction(verdict) == "Serialized Pick"


def test_legacy_list_shape_and_first_row_fallback_remain_supported():
    verdict = {
        "top_rank_horse_id": "",
        "full_analysis": [{"id": "legacy-1", "name": "Legacy Pick"}],
    }

    assert _extract_top_pick_name_from_prediction(verdict) == "Legacy Pick"


def test_missing_or_malformed_analysis_never_invents_a_name():
    assert _extract_top_pick_name_from_prediction(None) is None
    assert _extract_top_pick_name_from_prediction({}) is None
    assert _extract_top_pick_name_from_prediction(
        {"top_rank_horse_id": "horse-1", "full_analysis": "not-json"}
    ) is None
