from __future__ import annotations

from new_build_velo.evaluator import evaluate_predictions


def test_evaluator_waits_for_outcome_linked_rows() -> None:
    report = evaluate_predictions(execute=False)

    assert report["classification"] in {"NEW_BUILD_EVALUATION_READY", "OUTCOME_LINKED_ROWS_REQUIRED"}
    assert report["banned_feature_violations"] == 0
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False
