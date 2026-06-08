from __future__ import annotations

from new_build_velo.features import build_features


def test_feature_assembler_excludes_banned_fields() -> None:
    report = build_features(execute=False)

    assert report["classification"] == "NEW_BUILD_FEATURES_READY"
    assert report["banned_feature_violations"] == 0
    assert report["rpr_excluded"] is True
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False
