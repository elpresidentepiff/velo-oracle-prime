"""
tests/test_sigma_26_writer_enrichment.py
==========================================
Focused tests for SIGMA-26 dry-run enrichment: pick_sp, field_size, race_type
extraction from a verdict row, and non-blocking sigma_row construction.

Scope: this mission does NOT write verdict_id — see test_no_verdict_id_write_in_sigma_26.
No Supabase writes are performed by these tests (pure functions only).
"""

from __future__ import annotations

from app.services.velo_prime_service import _build_race_type_fields
from scripts.ops.run_results_sigma import (
    SIGMA_VERDICT_SELECT_COLUMNS,
    _build_sigma_row,
    _extract_field_size_from_prediction,
    _extract_pick_sp_from_prediction,
    _extract_race_type_from_prediction,
)


def _base_sigma_row_kwargs(prediction=None):
    return {
        "race_id": "922170_20260630",
        "race_date": "2026-06-30",
        "course": "Brighton",
        "off_time": "14:43",
        "outcome": "MISS",
        "decision_tier": "B",
        "miss_reason": "favourite_won",
        "top_pick_position": 3,
        "actual_winner_id": "h9",
        "actual_winner_name": "Some Winner",
        "actual_winner_sp": 4.5,
        "notes": "{}",
        "prediction": prediction,
    }


def test_extract_pick_sp_from_full_analysis_top_horse():
    prediction = {
        "top_rank_horse_id": "h1",
        "full_analysis": {
            "predictions": [
                {"horse_id": "h1", "sp_dec": 7.5},
                {"horse_id": "h2", "sp_dec": 3.0},
            ]
        },
    }
    assert _extract_pick_sp_from_prediction(prediction) == 7.5


def test_extract_pick_sp_missing_returns_none():
    # No matching horse_id
    prediction = {
        "top_rank_horse_id": "h1",
        "full_analysis": {"predictions": [{"horse_id": "h2", "sp_dec": 3.0}]},
    }
    assert _extract_pick_sp_from_prediction(prediction) is None

    # Matching horse but no sp_dec
    prediction2 = {
        "top_rank_horse_id": "h1",
        "full_analysis": {"predictions": [{"horse_id": "h1"}]},
    }
    assert _extract_pick_sp_from_prediction(prediction2) is None

    # No prediction at all
    assert _extract_pick_sp_from_prediction(None) is None
    assert _extract_pick_sp_from_prediction({}) is None


def test_extract_field_size_from_predicted_field_size():
    prediction = {"predicted_field_size": 8}
    assert _extract_field_size_from_prediction(prediction) == 8

    assert _extract_field_size_from_prediction({}) is None
    assert _extract_field_size_from_prediction(None) is None


def test_extract_race_type_from_persisted_prediction():
    prediction = {"race_type": "hurdle"}
    assert _extract_race_type_from_prediction(prediction) == "hurdle"

    assert _extract_race_type_from_prediction({"race_type": None}) is None
    assert _extract_race_type_from_prediction({}) is None
    assert _extract_race_type_from_prediction(None) is None


def test_sigma_row_enrichment_does_not_break_winner_sp():
    row = _build_sigma_row(**_base_sigma_row_kwargs(prediction=None))
    assert row["actual_winner_sp"] == 4.5
    assert row["actual_winner_id"] == "h9"
    assert row["actual_winner_name"] == "Some Winner"


def test_sigma_row_includes_three_enrichment_fields_when_present():
    prediction = {
        "top_rank_horse_id": "h1",
        "predicted_field_size": 12,
        "race_type": "chase",
        "full_analysis": {"predictions": [{"horse_id": "h1", "sp_dec": 6.0}]},
    }
    row = _build_sigma_row(**_base_sigma_row_kwargs(prediction=prediction))
    assert row["pick_sp"] == 6.0
    assert row["field_size"] == 12
    assert row["race_type"] == "chase"


def test_missing_enrichment_fields_do_not_block_sigma_row():
    row = _build_sigma_row(**_base_sigma_row_kwargs(prediction=None))
    assert "pick_sp" not in row
    assert "field_size" not in row
    assert "race_type" not in row
    # Core fields still present — row construction was not blocked.
    assert row["race_id"] == "922170_20260630"
    assert row["outcome"] == "MISS"
    assert row["decision_tier"] == "B"


def test_missing_enrichment_fields_are_omitted_to_prevent_null_overwrite():
    # prediction missing all three enrichment sources (no full_analysis,
    # no predicted_field_size, no race_type). _build_sigma_row must omit the
    # keys rather than writing None, because run_results_sigma.py upserts
    # this row into sigma_audits — an explicit null would overwrite any good
    # value already written by a prior run for this race_id.
    prediction = {"top_rank_horse_id": "h1"}
    row = _build_sigma_row(**_base_sigma_row_kwargs(prediction=prediction))
    assert "pick_sp" not in row
    assert "field_size" not in row
    assert "race_type" not in row


def test_verdict_persistence_payload_accepts_race_type_fields():
    race_with_type = {"race_id": "r1", "type": "Hurdle"}
    fields = _build_race_type_fields(race_with_type)
    assert fields["race_type"] == "hurdle"
    assert fields["race_type_raw"] == "Hurdle"
    assert fields["race_type_source"] == "scoring_race_dict"
    assert fields["race_type_recorded_at"] is not None

    race_without_type = {"race_id": "r2"}
    fields2 = _build_race_type_fields(race_without_type)
    assert fields2["race_type"] is None
    assert fields2["race_type_raw"] is None
    assert fields2["race_type_source"] is None
    assert fields2["race_type_recorded_at"] is None


def test_sigma_26_does_not_add_verdict_id_even_when_prediction_has_id():
    prediction = {
        "top_rank_horse_id": "h1",
        "predicted_field_size": 12,
        "race_type": "chase",
        "id": "some-verdict-uuid",
        "full_analysis": {"predictions": [{"horse_id": "h1", "sp_dec": 6.0}]},
    }
    row = _build_sigma_row(**_base_sigma_row_kwargs(prediction=prediction))
    assert "verdict_id" not in row


def test_sigma_verdict_select_columns_include_field_size_and_race_type():
    assert "predicted_field_size" in SIGMA_VERDICT_SELECT_COLUMNS
    assert "race_type" in SIGMA_VERDICT_SELECT_COLUMNS
    # verdict_id is intentionally excluded from this mission's scope.
    assert "verdict_id" not in SIGMA_VERDICT_SELECT_COLUMNS
