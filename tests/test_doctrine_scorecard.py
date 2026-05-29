import pandas as pd

from src.monitoring.doctrine_scorecard import build_scorecard


def test_build_scorecard_gate_and_edge_metrics():
    df = pd.DataFrame(
        [
            {
                "race_id": "r1",
                "decision_tier": "A",
                "outcome": "WIN",
                "cash_run_flag": True,
                "setup_run_flag": False,
                "decoy_support_flag": True,
                "market_deception_score": 0.72,
                "confidence_level": "HIGH",
                "market_top_pick_won": False,
            },
            {
                "race_id": "r2",
                "decision_tier": "A-STRIKE",
                "outcome": "MISS",
                "cash_run_flag": False,
                "setup_run_flag": True,
                "decoy_support_flag": False,
                "market_deception_score": 0.66,
                "confidence_level": "LOW",
                "market_top_pick_won": True,
            },
            {
                "race_id": "r3",
                "decision_tier": "B",
                "outcome": "PLACED",
                "cash_run_flag": False,
                "setup_run_flag": False,
                "decoy_support_flag": False,
                "market_deception_score": 0.2,
                "confidence_level": "MEDIUM",
                "market_top_pick_won": False,
            },
        ]
    )

    scorecard = build_scorecard(df, gate_target=100, mds_threshold=0.5)

    assert scorecard["gate_progress"]["flagged_races"] == 2
    assert scorecard["gate_progress"]["remaining"] == 98
    assert scorecard["tier_a"]["sample_size"] == 2
    assert scorecard["tier_a"]["wins"] == 1
    assert scorecard["decoy_interception"]["sample_size"] == 2
    assert scorecard["decoy_interception"]["interceptions"] == 1
    assert scorecard["doctrine_vs_market"]["edge_pct_points"] == 0.0


def test_build_scorecard_without_market_columns_sets_note():
    df = pd.DataFrame(
        [
            {"decision_tier": "A", "outcome": "WIN", "confidence_level": "HIGH"},
            {"decision_tier": "B", "outcome": "MISS", "confidence_level": "LOW"},
        ]
    )
    scorecard = build_scorecard(df)
    assert scorecard["doctrine_vs_market"]["market_win_rate_pct"] is None
    assert "note" in scorecard["doctrine_vs_market"]
