from __future__ import annotations

from new_build_velo.outcomes import build_outcome_bridge_v2


def test_outcome_bridge_v2_is_strict_and_archive_only() -> None:
    report = build_outcome_bridge_v2(execute=False)

    assert report["classification"] == "NEW_BUILD_OUTCOME_BRIDGE_V2_READY"
    assert report["banned_feature_violations"] == 0
    assert report["rpr_boundary_status"] == "PASS_RPR_ARCHIVE_ONLY"
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False
    assert report["source_rows"] >= 0
