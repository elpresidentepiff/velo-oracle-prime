from app.world_dashboard import model_performance_summary


def test_model_performance_uses_only_settled_top_pick_rows_and_never_promotes():
    result = model_performance_summary(
        [
            {"model_name": "MAIN_VELO_PRIME", "lane_name": "main", "run_date": "2026-11-01", "result_position": 1, "settlement_status": "SETTLED", "win": True, "frame": True},
            {"model_name": "NEW_BUILD_LANE_C_MODEL", "lane_name": "lane_c", "run_date": "2026-11-01", "result_position": 2, "settlement_status": "SETTLED", "win": False, "frame": True},
            {"model_name": "NEW_BUILD_LANE_C_MODEL", "lane_name": "lane_c", "run_date": "2026-11-02", "result_position": None, "settlement_status": "UNSETTLED", "win": False, "frame": False},
        ],
        365,
    )

    assert result["coverage"] == {"captured_scoring_dates": 2, "first_date": "2026-11-01", "last_date": "2026-11-02"}
    prime, lane_c = result["models"]
    assert prime["settled_top_picks"] == 1
    assert prime["win_sr_pct"] == 100.0
    assert prime["promotion_status"] == "FROZEN_PRODUCTION_BASELINE"
    assert lane_c["top_picks"] == 2
    assert lane_c["settled_top_picks"] == 1
    assert lane_c["win_sr_pct"] == 0.0
    assert lane_c["promotion_status"] == "SHADOW_ONLY_LANE_C_GATE_REVIEW_REQUIRED"
    assert lane_c["stake_authorised"] is False


def test_void_and_non_runner_rows_excluded_from_denominator():
    """VOID (NR) rows must not inflate settled_top_picks."""
    result = model_performance_summary(
        [
            {"model_name": "MAIN_VELO_PRIME", "lane_name": "main", "run_date": "2026-11-01", "result_position": "NR", "settlement_status": "VOID", "win": False, "frame": False},
            {"model_name": "MAIN_VELO_PRIME", "lane_name": "main", "run_date": "2026-11-01", "result_position": 1, "settlement_status": "SETTLED", "win": True, "frame": True},
        ],
        365,
    )
    (prime,) = result["models"]
    assert prime["top_picks"] == 2
    assert prime["settled_top_picks"] == 1
    assert prime["win_sr_pct"] == 100.0
