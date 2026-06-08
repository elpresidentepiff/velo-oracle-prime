from __future__ import annotations

from new_build_velo.passport_bank import _rpr_violations, passport_to_feature_row


def test_passport_feature_bridge_emits_model_schema_without_rpr() -> None:
    row = passport_to_feature_row(
        {
            "horse_name": "Clean Horse",
            "horse_rp_uid": 123,
            "career_runs": 5,
            "win_rate": 0.2,
            "place_rate": 0.6,
            "days_since_last_run": 21,
            "layoff_flag": "ACTIVE",
            "avg_sp_last5": 6.5,
            "jockey_continuity": True,
            "or_change_last3": 4,
            "class_movement": "UP",
        }
    )

    assert row["horse_rp_uid"] == "123"
    assert row["pp_career_runs"] == 5.0
    assert row["pp_layoff"] == 0.0
    assert row["pp_jockey_continuity"] == 1.0
    assert row["pp_class_moved_up"] == 1.0
    assert row["pp_class_moved_down"] == 0.0
    assert row["rpr_feature_allowed"] is False
    assert _rpr_violations([row]) == []


def test_passport_feature_bridge_keeps_profile_only_course_seen_blank() -> None:
    row = passport_to_feature_row({"horse_name": "Course Horse", "horse_rp_uid": 456})

    assert "pp_course_seen" in row
    assert row["pp_course_seen"] is None
