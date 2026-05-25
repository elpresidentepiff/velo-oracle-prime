from __future__ import annotations

from new_build_velo.result_gaps import plan_result_gaps


def test_result_gap_plan_is_new_build_only() -> None:
    report = plan_result_gaps(execute=False)

    assert report["classification"] == "NEW_BUILD_RESULT_GAP_PLAN_READY"
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False
    assert "missing_result_dates" in report
