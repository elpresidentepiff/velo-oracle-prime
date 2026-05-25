from __future__ import annotations

from new_build_velo.outcome_diagnostics import build_outcome_match_diagnostics


def test_outcome_diagnostics_explains_bridge_state() -> None:
    report = build_outcome_match_diagnostics(execute=False)

    assert report["classification"] == "NEW_BUILD_OUTCOME_DIAGNOSTICS_READY"
    assert report["banned_feature_violations"] == 0
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False
    assert "reason_counts" in report
