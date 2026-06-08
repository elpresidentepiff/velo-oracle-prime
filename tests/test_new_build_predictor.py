from __future__ import annotations

from new_build_velo.predictor import build_predictions


def test_sandbox_predictor_builds_without_banned_features() -> None:
    report = build_predictions(execute=False)

    assert report["classification"] == "NEW_BUILD_SANDBOX_PREDICTIONS_READY"
    assert report["banned_feature_violations"] == 0
    assert report["rpr_excluded"] is True
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False
