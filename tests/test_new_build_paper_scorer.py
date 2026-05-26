from __future__ import annotations

from new_build_velo.paper_scorer import _bad_keys, _feature_row


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
