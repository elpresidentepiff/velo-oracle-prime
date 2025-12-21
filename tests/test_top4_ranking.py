"""
Regression tests for Top-4 Ranking (Phase 1.1 Closure)

Contract tests:
1. Score-based ordering (not positional)
2. Market role weights applied correctly
3. Chaos adjustments work
4. Margin-based win suppression
"""

import pytest
from app.strategy.top4_ranker import rank_top4


def test_score_based_ordering_not_positional():
    """Test that Top-4 is score-based, not first 4 IDs."""
    # Create runners with inverted odds (r6 best, r1 worst)
    runners = [
        {"runner_id": "r1", "odds_decimal": 20.0, "market_role": "NOISE", "role_reason": "High odds"},
        {"runner_id": "r2", "odds_decimal": 15.0, "market_role": "NOISE", "role_reason": "High odds"},
        {"runner_id": "r3", "odds_decimal": 5.0, "market_role": "RELEASE", "role_reason": "Mid odds"},
        {"runner_id": "r4", "odds_decimal": 3.0, "market_role": "RELEASE", "role_reason": "Mid odds"},
        {"runner_id": "r5", "odds_decimal": 2.5, "market_role": "ANCHOR", "role_reason": "Low odds"},
        {"runner_id": "r6", "odds_decimal": 1.5, "market_role": "ANCHOR", "role_reason": "Lowest odds"},
    ]
    
    race_ctx = {"chaos_level": 0.3, "race_id": "test_race"}
    
    top4, _ = rank_top4(runners, race_ctx)
    
    # Should be ordered by score (best first), not by position
    runner_id = top4[0].get("runner_id") if isinstance(top4[0], dict) else getattr(top4[0], "runner_id", None)
    assert runner_id in ["r6", "r5"], \
        f"Expected r6 or r5 first (best odds), got {runner_id}"
    
    # Should NOT be r1, r2, r3, r4 (positional)
    top4_ids = []
    for r in top4:
        rid = r.get("runner_id") if isinstance(r, dict) else getattr(r, "runner_id", None)
        top4_ids.append(rid)
    
    assert top4_ids != ["r1", "r2", "r3", "r4"], \
        f"Top-4 appears positional: {top4_ids}"


def test_market_role_weights_applied():
    """Test that ANCHOR gets boost, NOISE gets penalty."""
    # Create two runners with similar odds but different roles
    runners = [
        {"runner_id": "anchor", "odds_decimal": 2.0, "market_role": "ANCHOR", "role_reason": "Strong favorite"},
        {"runner_id": "noise", "odds_decimal": 2.0, "market_role": "NOISE", "role_reason": "Weak support"},
    ]
    
    race_ctx = {"chaos_level": 0.3, "race_id": "test_race"}
    
    _, breakdowns = rank_top4(runners, race_ctx)
    
    # ANCHOR should score higher than NOISE with same odds
    anchor_score = breakdowns["anchor"].total
    noise_score = breakdowns["noise"].total
    
    assert anchor_score > noise_score, \
        f"ANCHOR score ({anchor_score:.3f}) should be > NOISE score ({noise_score:.3f})"


def test_chaos_adjustments_work():
    """Test that high chaos boosts RELEASE, low chaos boosts ANCHOR."""
    runners = [
        {"runner_id": "anchor", "odds_decimal": 2.0, "market_role": "ANCHOR", "role_reason": "Favorite"},
        {"runner_id": "release", "odds_decimal": 5.0, "market_role": "RELEASE", "role_reason": "Mid-range"},
    ]
    
    # Low chaos scenario (favor ANCHOR)
    race_ctx_low = {"chaos_level": 0.2, "race_id": "test_race"}
    _, breakdowns_low = rank_top4(runners, race_ctx_low)
    anchor_score_low = breakdowns_low["anchor"].total
    release_score_low = breakdowns_low["release"].total
    
    # High chaos scenario (favor RELEASE)
    race_ctx_high = {"chaos_level": 0.8, "race_id": "test_race"}
    _, breakdowns_high = rank_top4(runners, race_ctx_high)
    anchor_score_high = breakdowns_high["anchor"].total
    release_score_high = breakdowns_high["release"].total
    
    # In high chaos, gap between ANCHOR and RELEASE should be smaller
    gap_low = anchor_score_low - release_score_low
    gap_high = anchor_score_high - release_score_high
    
    assert gap_high < gap_low, \
        f"High chaos should reduce ANCHOR advantage: gap_low={gap_low:.3f}, gap_high={gap_high:.3f}"


def test_top4_returns_exactly_4_or_less():
    """Test that Top-4 returns at most 4 runners."""
    # Test with 10 runners
    runners = [
        {"runner_id": f"r{i}", "odds_decimal": float(i+1), "market_role": "RELEASE", "role_reason": "Mid"}
        for i in range(10)
    ]
    
    race_ctx = {"chaos_level": 0.5, "race_id": "test_race"}
    top4, _ = rank_top4(runners, race_ctx)
    
    assert len(top4) <= 4, \
        f"Expected at most 4 runners, got {len(top4)}"
    
    # Test with 2 runners
    runners_small = [
        {"runner_id": "r1", "odds_decimal": 2.0, "market_role": "ANCHOR", "role_reason": "Fav"},
        {"runner_id": "r2", "odds_decimal": 5.0, "market_role": "RELEASE", "role_reason": "Mid"},
    ]
    
    top4_small, _ = rank_top4(runners_small, race_ctx)
    
    assert len(top4_small) == 2, \
        f"Expected 2 runners when input is 2, got {len(top4_small)}"


def test_scores_are_positive():
    """Test that all final scores are positive."""
    runners = [
        {"runner_id": "r1", "odds_decimal": 1.5, "market_role": "ANCHOR", "role_reason": "Fav"},
        {"runner_id": "r2", "odds_decimal": 10.0, "market_role": "NOISE", "role_reason": "Weak"},
    ]
    
    race_ctx = {"chaos_level": 0.5, "race_id": "test_race"}
    _, breakdowns = rank_top4(runners, race_ctx)
    
    for runner_id, breakdown in breakdowns.items():
        assert breakdown.total > 0, \
            f"Runner {runner_id} has non-positive score: {breakdown.total}"


def test_top4_includes_required_fields():
    """Test that each Top-4 runner has required fields."""
    runners = [
        {"runner_id": "r1", "odds_decimal": 2.0, "market_role": "ANCHOR", "role_reason": "Fav"},
    ]
    
    race_ctx = {"chaos_level": 0.5, "race_id": "test_race"}
    top4, _ = rank_top4(runners, race_ctx)
    
    required_fields = ["runner_id", "market_role", "odds_decimal"]
    
    for runner in top4:
        for field in required_fields:
            if isinstance(runner, dict):
                assert field in runner, \
                    f"Runner {runner.get('runner_id')} missing field: {field}"
            else:
                assert hasattr(runner, field), \
                    f"Runner {getattr(runner, 'runner_id', 'unknown')} missing field: {field}"


def test_anchor_weight_guard_applied():
    """Test that strong ANCHOR gets +0.10 boost."""
    # Create strong favorite (>60% implied prob = odds < 1.67)
    runners = [
        {"runner_id": "strong_anchor", "odds_decimal": 1.5, "market_role": "ANCHOR", "role_reason": "Strong fav"},
        {"runner_id": "weak_anchor", "odds_decimal": 3.0, "market_role": "ANCHOR", "role_reason": "Weak fav"},
    ]
    
    race_ctx = {"chaos_level": 0.3, "race_id": "test_race"}
    _, breakdowns = rank_top4(runners, race_ctx)
    
    strong_score = breakdowns["strong_anchor"].total
    weak_score = breakdowns["weak_anchor"].total
    
    # Strong anchor should have significantly higher score due to +0.10 boost
    assert strong_score > weak_score + 0.05, \
        f"Strong ANCHOR ({strong_score:.3f}) should be significantly > weak ANCHOR ({weak_score:.3f})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
