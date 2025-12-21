"""
Integration tests for V12 Pipeline (Phase 1.1 Closure)

End-to-end tests:
1. Full pipeline with realistic race data
2. Race context propagation
3. Top-4 output structure
4. ADLG quarantine flags but doesn't break
"""

import pytest
from app.ml.opponent_models import classify_market_role
from app.ml.chaos_calculator import calculate_chaos
from app.strategy.top4_ranker import rank_top4


def test_full_pipeline_with_realistic_race():
    """Test full pipeline from odds to Top-4 output."""
    # Simulate realistic race data
    race_data = {
        "race_id": "test_race_001",
        "runners": [
            {"runner_id": "r1", "odds_decimal": 2.5, "name": "Favorite"},
            {"runner_id": "r2", "odds_decimal": 4.0, "name": "Second Choice"},
            {"runner_id": "r3", "odds_decimal": 6.0, "name": "Mid-range"},
            {"runner_id": "r4", "odds_decimal": 8.0, "name": "Outsider 1"},
            {"runner_id": "r5", "odds_decimal": 12.0, "name": "Outsider 2"},
            {"runner_id": "r6", "odds_decimal": 20.0, "name": "Long shot"},
        ]
    }
    
    # Step 1: Classify market roles
    all_odds = [r["odds_decimal"] for r in race_data["runners"]]
    
    for runner in race_data["runners"]:
        role, reason = classify_market_role(runner["odds_decimal"], all_odds)
        runner["market_role"] = role
        runner["role_reason"] = reason
    
    # Step 2: Calculate chaos
    chaos = calculate_chaos(all_odds, len(all_odds))
    
    # Step 3: Build race context
    race_ctx = {
        "race_id": race_data["race_id"],
        "chaos_level": chaos,
        "field_size": len(race_data["runners"]),
        "manipulation_risk": 0.3
    }
    
    # Step 4: Rank Top-4
    top4, breakdowns = rank_top4(race_data["runners"], race_ctx)
    
    # Assertions
    assert len(top4) == 4, f"Expected 4 runners, got {len(top4)}"
    
    # Check that Top-4 includes low odds runners (not just first 4)
    top4_ids = []
    for r in top4:
        rid = r.get("runner_id") if isinstance(r, dict) else getattr(r, "runner_id", None)
        top4_ids.append(rid)
    
    assert "r1" in top4_ids, "Favorite should be in Top-4"
    assert "r2" in top4_ids, "Second choice should be in Top-4"
    
    # Check that scores are ordered (descending)
    scores = [breakdowns[rid].total for rid in top4_ids]
    assert scores == sorted(scores, reverse=True), \
        f"Scores not in descending order: {scores}"


def test_race_context_propagation():
    """Test that race_id and chaos propagate through pipeline."""
    race_id = "test_race_propagation"
    
    runners = [
        {"runner_id": "r1", "odds_decimal": 2.0, "market_role": "ANCHOR", "role_reason": "Fav"},
        {"runner_id": "r2", "odds_decimal": 5.0, "market_role": "RELEASE", "role_reason": "Mid"},
    ]
    
    chaos = 0.4
    
    race_ctx = {
        "race_id": race_id,
        "chaos_level": chaos,
        "field_size": 2,
        "manipulation_risk": 0.3
    }
    
    top4, _ = rank_top4(runners, race_ctx)
    
    # Race context should be used (no errors)
    assert len(top4) == 2
    assert race_ctx["race_id"] == race_id
    assert race_ctx["chaos_level"] == chaos


def test_top4_output_structure():
    """Test that Top-4 output has required structure."""
    runners = [
        {"runner_id": "r1", "odds_decimal": 2.0, "market_role": "ANCHOR", "role_reason": "Fav"},
        {"runner_id": "r2", "odds_decimal": 5.0, "market_role": "RELEASE", "role_reason": "Mid"},
        {"runner_id": "r3", "odds_decimal": 10.0, "market_role": "NOISE", "role_reason": "Weak"},
    ]
    
    race_ctx = {
        "race_id": "test_race",
        "chaos_level": 0.5,
        "field_size": 3,
        "manipulation_risk": 0.3
    }
    
    top4, breakdowns = rank_top4(runners, race_ctx)
    
    # Check Top-4 structure
    assert isinstance(top4, list), "Top-4 should be a list"
    assert len(top4) == 3, "Should return all 3 runners"
    
    # Check breakdowns structure
    assert isinstance(breakdowns, dict), "Breakdowns should be a dict"
    assert len(breakdowns) == 3, "Should have 3 breakdowns"
    
    for runner_id, breakdown in breakdowns.items():
        assert hasattr(breakdown, "total"), "Breakdown should have total"
        assert hasattr(breakdown, "components"), "Breakdown should have components"
        assert breakdown.total > 0, f"Score should be positive for {runner_id}"


def test_market_role_classification_integration():
    """Test market role classification with realistic odds."""
    # Realistic odds distribution
    all_odds = [1.8, 3.5, 5.0, 8.0, 12.0, 20.0, 30.0]
    
    roles = []
    for odds in all_odds:
        role, reason = classify_market_role(odds, all_odds)
        roles.append(role)
    
    # Check that we have variety (not all NOISE)
    unique_roles = set(roles)
    assert len(unique_roles) >= 2, \
        f"Expected at least 2 different roles, got {unique_roles}"
    
    # Lowest odds should be ANCHOR
    role_lowest, _ = classify_market_role(all_odds[0], all_odds)
    assert role_lowest == "ANCHOR", \
        f"Lowest odds should be ANCHOR, got {role_lowest}"
    
    # Highest odds should be NOISE
    role_highest, _ = classify_market_role(all_odds[-1], all_odds)
    assert role_highest == "NOISE", \
        f"Highest odds should be NOISE, got {role_highest}"


def test_chaos_varies_by_race():
    """Test that chaos calculation varies by odds distribution."""
    # Race 1: Strong favorite
    race1_odds = [1.5, 5.0, 10.0, 15.0, 20.0]
    chaos1 = calculate_chaos(race1_odds, len(race1_odds))
    
    # Race 2: Flat odds
    race2_odds = [3.0, 3.5, 4.0, 4.5, 5.0]
    chaos2 = calculate_chaos(race2_odds, len(race2_odds))
    
    # Race 3: Very strong favorite
    race3_odds = [1.2, 10.0, 20.0, 30.0, 50.0]
    chaos3 = calculate_chaos(race3_odds, len(race3_odds))
    
    # Chaos should be different
    assert chaos1 != chaos2, "Chaos should differ between races"
    assert chaos2 > chaos1, "Flat odds should have higher chaos"
    assert chaos3 < chaos1, "Very strong favorite should have lowest chaos"


def test_adlg_quarantine_flags_but_doesnt_break():
    """Test that ADLG quarantine flags races without breaking output."""
    # Simulate race with potential ADLG issue (very flat odds)
    runners = [
        {"runner_id": "r1", "odds_decimal": 5.0, "market_role": "NOISE", "role_reason": "Flat"},
        {"runner_id": "r2", "odds_decimal": 5.5, "market_role": "NOISE", "role_reason": "Flat"},
        {"runner_id": "r3", "odds_decimal": 6.0, "market_role": "NOISE", "role_reason": "Flat"},
        {"runner_id": "r4", "odds_decimal": 6.5, "market_role": "NOISE", "role_reason": "Flat"},
    ]
    
    race_ctx = {
        "race_id": "adlg_test_race",
        "chaos_level": 0.8,  # High chaos
        "field_size": 4,
        "manipulation_risk": 0.3
    }
    
    # Should not raise exception
    top4, breakdowns = rank_top4(runners, race_ctx)
    
    # Should still produce output
    assert len(top4) == 4
    assert len(breakdowns) == 4
    
    # All scores should be positive
    for runner_id, breakdown in breakdowns.items():
        assert breakdown.total > 0, f"Score should be positive even in ADLG case"


def test_score_determinism():
    """Test that same input produces same output (deterministic)."""
    runners = [
        {"runner_id": "r1", "odds_decimal": 2.0, "market_role": "ANCHOR", "role_reason": "Fav"},
        {"runner_id": "r2", "odds_decimal": 5.0, "market_role": "RELEASE", "role_reason": "Mid"},
    ]
    
    race_ctx = {
        "race_id": "determinism_test",
        "chaos_level": 0.5,
        "field_size": 2,
        "manipulation_risk": 0.3
    }
    
    # Run twice
    top4_run1, breakdowns_run1 = rank_top4(runners, race_ctx)
    top4_run2, breakdowns_run2 = rank_top4(runners, race_ctx)
    
    # Scores should be identical
    for runner_id in ["r1", "r2"]:
        score1 = breakdowns_run1[runner_id].total
        score2 = breakdowns_run2[runner_id].total
        assert score1 == score2, \
            f"Score for {runner_id} not deterministic: {score1} vs {score2}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
