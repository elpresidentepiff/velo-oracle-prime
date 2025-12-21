"""
Unit tests for deterministic score contract (Phase 1.1)

Tests:
1. len(top4) == min(4, field_size)
2. All runners scored
3. Ranking changes when odds permute
"""

import pytest
from app.strategy.top4_ranker import rank_top4, calculate_runner_score
from app.ml.opponent_models import OpponentProfile, MarketRole, IntentClass, StableTactic
from app.core.errors import V12Error, V12ErrorCode


def create_test_profile(runner_id: str, odds: float, role: MarketRole = MarketRole.RELEASE_HORSE):
    """Helper to create test profile."""
    return OpponentProfile(
        runner_id=runner_id,
        horse_name=f"Horse {runner_id}",
        intent_class=IntentClass.UNKNOWN,
        market_role=role,
        stable_tactic=StableTactic.SOLO,
        confidence=0.7,
        evidence={'odds': odds}
    )


def test_top4_count_equals_min_4_field():
    """Test that Top-4 count equals min(4, field_size)."""
    race_ctx = {
        'race_id': 'TEST_001',
        'chaos_level': 0.5,
        'field_size': 6
    }
    
    # Test with 6 runners (expect 4)
    profiles_6 = [
        create_test_profile('r1', 2.0, MarketRole.LIQUIDITY_ANCHOR),
        create_test_profile('r2', 3.0),
        create_test_profile('r3', 5.0),
        create_test_profile('r4', 8.0),
        create_test_profile('r5', 12.0),
        create_test_profile('r6', 20.0, MarketRole.NOISE),
    ]
    
    top4, breakdowns = rank_top4(profiles_6, race_ctx)
    assert len(top4) == 4, f"Expected 4 runners in Top-4, got {len(top4)}"
    
    # Test with 3 runners (expect 3)
    profiles_3 = profiles_6[:3]
    race_ctx['field_size'] = 3
    top4, breakdowns = rank_top4(profiles_3, race_ctx)
    assert len(top4) == 3, f"Expected 3 runners in Top-4, got {len(top4)}"
    
    # Test with 10 runners (expect 4)
    profiles_10 = [create_test_profile(f'r{i}', float(i+1)) for i in range(10)]
    race_ctx['field_size'] = 10
    top4, breakdowns = rank_top4(profiles_10, race_ctx)
    assert len(top4) == 4, f"Expected 4 runners in Top-4, got {len(top4)}"


def test_all_runners_scored():
    """Test that all runners get scores."""
    race_ctx = {
        'race_id': 'TEST_002',
        'chaos_level': 0.5,
        'field_size': 5
    }
    
    profiles = [
        create_test_profile('r1', 2.0),
        create_test_profile('r2', 4.0),
        create_test_profile('r3', 6.0),
        create_test_profile('r4', 10.0),
        create_test_profile('r5', 15.0),
    ]
    
    top4, breakdowns = rank_top4(profiles, race_ctx)
    
    # Check all runners have scores
    assert len(breakdowns) == 5, f"Expected 5 score breakdowns, got {len(breakdowns)}"
    
    for profile in profiles:
        runner_id = profile.runner_id
        assert runner_id in breakdowns, f"Runner {runner_id} missing from score breakdowns"
        
        bd = breakdowns[runner_id]
        assert bd.total is not None, f"Runner {runner_id} has no total score"
        assert bd.total >= 0, f"Runner {runner_id} has negative score: {bd.total}"
        assert bd.components, f"Runner {runner_id} has no score components"
        
        # Check all components exist
        required_components = ['role', 'odds', 'chaos', 'field']
        for comp in required_components:
            assert comp in bd.components, f"Runner {runner_id} missing component: {comp}"


def test_ranking_changes_when_odds_permute():
    """Test that ranking changes when odds are permuted."""
    race_ctx = {
        'race_id': 'TEST_003',
        'chaos_level': 0.5,
        'field_size': 4
    }
    
    # Original odds: r1=2.0, r2=4.0, r3=8.0, r4=16.0
    profiles_original = [
        create_test_profile('r1', 2.0, MarketRole.LIQUIDITY_ANCHOR),
        create_test_profile('r2', 4.0, MarketRole.RELEASE_HORSE),
        create_test_profile('r3', 8.0, MarketRole.RELEASE_HORSE),
        create_test_profile('r4', 16.0, MarketRole.NOISE),
    ]
    
    top4_original, _ = rank_top4(profiles_original, race_ctx)
    original_order = [p.runner_id for p in top4_original]
    
    # Permuted odds: r1=16.0, r2=8.0, r3=4.0, r4=2.0 (reversed)
    profiles_permuted = [
        create_test_profile('r1', 16.0, MarketRole.NOISE),
        create_test_profile('r2', 8.0, MarketRole.RELEASE_HORSE),
        create_test_profile('r3', 4.0, MarketRole.RELEASE_HORSE),
        create_test_profile('r4', 2.0, MarketRole.LIQUIDITY_ANCHOR),
    ]
    
    top4_permuted, _ = rank_top4(profiles_permuted, race_ctx)
    permuted_order = [p.runner_id for p in top4_permuted]
    
    # Rankings MUST be different
    assert original_order != permuted_order, \
        f"Rankings unchanged after odds permutation: {original_order} vs {permuted_order}"
    
    # r4 should be #1 in permuted (it has lowest odds)
    assert permuted_order[0] == 'r4', \
        f"Expected r4 to be #1 in permuted ranking, got {permuted_order[0]}"
    
    # r1 should be #1 in original (it has lowest odds)
    assert original_order[0] == 'r1', \
        f"Expected r1 to be #1 in original ranking, got {original_order[0]}"


def test_score_components_sum_to_total():
    """Test that score components sum to total (within tolerance)."""
    race_ctx = {
        'race_id': 'TEST_004',
        'chaos_level': 0.5,
        'field_size': 3
    }
    
    profile = create_test_profile('r1', 3.0, MarketRole.LIQUIDITY_ANCHOR)
    breakdown = calculate_runner_score(profile, race_ctx)
    
    # Sum components
    component_sum = sum(breakdown.components.values())
    
    # Check within tolerance (0.01)
    assert abs(breakdown.total - component_sum) < 0.01, \
        f"Component sum {component_sum:.3f} != total {breakdown.total:.3f}"


def test_fail_fast_on_missing_score():
    """Test that validation fails if score is missing."""
    from app.core.errors import validate_scores
    
    # Missing score for r2
    incomplete_breakdowns = {
        'r1': type('obj', (object,), {'total': 0.8, 'components': {'role': 0.4, 'odds': 0.3, 'chaos': 0.1}})(),
        # r2 missing
    }
    
    with pytest.raises(V12Error) as exc_info:
        validate_scores(incomplete_breakdowns, field_size=2)
    
    assert exc_info.value.code == V12ErrorCode.MISSING_SCORE


def test_fail_fast_on_invalid_top4_count():
    """Test that validation fails if Top-4 count is wrong."""
    from app.core.errors import validate_top4
    
    # Field of 6, but only 3 in Top-4
    invalid_top4 = ['r1', 'r2', 'r3']
    
    with pytest.raises(V12Error) as exc_info:
        validate_top4(invalid_top4, field_size=6)
    
    assert exc_info.value.code == V12ErrorCode.INVALID_TOP4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
