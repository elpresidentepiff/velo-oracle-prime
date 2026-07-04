from __future__ import annotations

import sys
from pathlib import Path

from new_build_velo.paper_scorer import _bad_keys, _feature_row, _going_code as _going_code_scorer

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "ops"))
from new_build_two_lane_score import _going_code as _going_code_lane  # type: ignore[import]

_TRAINED_MIN = -1.0
_TRAINED_MAX = 2.0

_ALL_GOING_LABELS = [
    "heavy", "soft", "good to soft", "good", "good to firm", "firm",
    "standard", "standard to slow", "slow",
]


def test_paper_feature_row_fills_missing_with_medians_without_rpr() -> None:
    row = {
        "field_size": 10,
        "draw": 5,
        "age": 4,
        "passport_summary": {
            "career_runs": 7,
            "win_rate": 0.1,
            "place_rate": 0.4,
            "layoff_flag": "ACTIVE",
        },
    }
    medians = {
        "field_size": 11.0,
        "draw_num": 6.0,
        "draw_pct": 0.5,
        "age_num": 4.0,
        "wgt_lbs": 127.0,
        "pp_layoff": 0.0,
        "pp_avg_sp_last5": 13.9,
    }

    features, missing = _feature_row(row, ["field_size", "draw_num", "draw_pct", "wgt_lbs", "pp_layoff", "pp_avg_sp_last5"], medians)

    assert features["field_size"] == 10.0
    assert features["draw_num"] == 5.0
    assert features["draw_pct"] == 0.5
    assert features["wgt_lbs"] == 127.0
    assert features["pp_layoff"] == 0.0
    assert features["pp_avg_sp_last5"] == 13.9
    assert missing == ["wgt_lbs", "pp_avg_sp_last5"]


def test_paper_scorer_rpr_guard_allows_policy_only() -> None:
    assert _bad_keys({"rpr_policy": "RPR_ARCHIVE_ONLY", "rpr_feature_allowed": False}) == []
    assert _bad_keys({"rp_rpr_archive_only": 100}) == ["rp_rpr_archive_only"]


# A-3 regression: going_code values must stay inside raceform_v17 trained range (-1 to 2)
def test_going_code_scorer_all_labels_within_trained_range() -> None:
    for label in _ALL_GOING_LABELS:
        v = _going_code_scorer(label, default=1.0)
        assert _TRAINED_MIN <= v <= _TRAINED_MAX, f"paper_scorer _going_code({label!r})={v} outside [-1, 2]"


def test_going_code_scorer_default_within_trained_range() -> None:
    v = _going_code_scorer(None, default=1.0)
    assert _TRAINED_MIN <= v <= _TRAINED_MAX, f"paper_scorer _going_code default={v} outside [-1, 2]"
    v2 = _going_code_scorer("", default=0.0)
    assert _TRAINED_MIN <= v2 <= _TRAINED_MAX, f"paper_scorer _going_code empty default={v2} outside [-1, 2]"


def test_going_code_lane_all_labels_within_trained_range() -> None:
    for label in _ALL_GOING_LABELS:
        v = _going_code_lane(label)
        assert _TRAINED_MIN <= v <= _TRAINED_MAX, f"two_lane_score _going_code({label!r})={v} outside [-1, 2]"


def test_going_code_lane_default_within_trained_range() -> None:
    # default=1.0 and median fallback 1.0 must both be in range
    v = _going_code_lane(None)
    assert _TRAINED_MIN <= v <= _TRAINED_MAX, f"two_lane_score _going_code None default={v} outside [-1, 2]"
    v2 = _going_code_lane("")
    assert _TRAINED_MIN <= v2 <= _TRAINED_MAX, f"two_lane_score _going_code empty default={v2} outside [-1, 2]"
    assert v == 1.0, "two_lane_score _going_code default must be 1.0 (Good on trained scale)"
