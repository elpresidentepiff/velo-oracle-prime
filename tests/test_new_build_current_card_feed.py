from __future__ import annotations

from new_build_velo.current_card_feed import _missing_reason, _reason_codes


def test_missing_passport_reason_is_non_failure_class() -> None:
    reason = _missing_reason(
        passport_found=False,
        champion_features_available=False,
        intent_features_available=False,
        runner={},
    )

    assert reason == "UNRACED_OR_NO_FORM_HISTORY_OR_NOT_IN_PASSPORT_BANK"


def test_reason_codes_do_not_emit_rpr_and_mark_passport_strength() -> None:
    codes = _reason_codes(
        passport={
            "career_runs": 12,
            "place_rate": 0.66,
            "avg_sp_last5": 3.5,
            "jockey_continuity": True,
            "or_change_last3": 5,
            "cash_run_candidate": False,
            "setup_run_candidate": True,
        },
        feature={"pp_course_seen": None},
        runner={"headgear_first_time": True, "wind_surgery": False},
        intent_features_available=False,
    )

    assert "STRONG_PLACE_PROFILE" in codes
    assert "HISTORICAL_MARKET_RESPECT" in codes
    assert "JOCKEY_CONTINUITY" in codes
    assert "OR_RISING" in codes
    assert "FIRST_TIME_HEADGEAR" in codes
    assert not any("RPR" in code for code in codes)
