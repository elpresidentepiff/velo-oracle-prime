from __future__ import annotations

from pathlib import Path

import pytest

from new_build_velo.database import build_database_spine, build_learning_eligibility_report, build_spine_status_report
from new_build_velo.spine import NEW_BUILD_ROOT, write_json


def test_database_spine_dry_run_has_required_tables() -> None:
    report = build_database_spine(execute=False)

    assert report["classification"] == "NEW_BUILD_NORMALIZED_DATABASE_SPINE_READY"
    assert report["rpr_boundary_status"] == "PASS_RPR_ARCHIVE_ONLY"
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False
    assert "runners" in report["tables"]
    assert "identity_bridge" in report["tables"]
    assert "outcome_bridge" in report["tables"]


def test_spine_status_report_is_read_only_summary() -> None:
    report = build_spine_status_report(execute=False)

    assert report["classification"] == "NEW_BUILD_SPINE_STATUS_READY"
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False
    assert report["rpr_boundary_status"] == "PASS_RPR_ARCHIVE_ONLY"


def test_learning_eligibility_keeps_rpr_excluded() -> None:
    report = build_learning_eligibility_report(execute=False)

    assert report["classification"] == "NEW_BUILD_SANDBOX_LEARNING_ELIGIBILITY_READY"
    assert report["banned_feature_violations"] == 0
    assert report["rpr_excluded"] is True
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False


def test_new_build_write_guard_rejects_old_velo_paths() -> None:
    with pytest.raises(ValueError):
        write_json(Path("data/sentient_state.json"), {"bad": True})


def test_new_build_write_guard_allows_new_build_paths() -> None:
    target = NEW_BUILD_ROOT / "_test_write_guard.json"
    write_json(target, {"ok": True})
    try:
        assert target.exists()
    finally:
        target.unlink(missing_ok=True)
