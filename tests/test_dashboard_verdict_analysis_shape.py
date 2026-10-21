"""Regression tests for the dashboard's persisted verdict-shape adapter."""

from app.main import _prediction_rows_from_analysis


def test_prediction_rows_accept_legacy_list_shape() -> None:
    rows = [{"horse": "Legacy Runner", "velo_prime_prob": 0.31}, {"horse": "Other"}]

    assert _prediction_rows_from_analysis(rows) == rows


def test_prediction_rows_accept_current_envelope_shape() -> None:
    rows = [{"horse": "Current Runner", "velo_prime_prob": 0.42}]

    assert _prediction_rows_from_analysis(
        {"predictions": rows, "governance": {"assigned_product": "WIN_ONLY"}}
    ) == rows


def test_prediction_rows_reject_malformed_shape_without_fabrication() -> None:
    assert _prediction_rows_from_analysis({"governance": {}}) == []
    assert _prediction_rows_from_analysis(None) == []
