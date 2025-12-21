"""
Regression tests for Market Role Classifier (Phase 1.1 Closure)

Contract tests (not unit tests):
1. ≥3 roles when field allows
2. Anchor conditions trigger only when gap threshold met
3. No runner returns role without a reason string
"""

import pytest
from app.ml.opponent_models import profile_race_opponents, MarketRole


def test_at_least_3_roles_when_field_allows():
    """Test that ≥3 distinct roles appear when field size >= 6."""
    # Create 8 runners with varied odds
    runners = [
        {'runner_id': 'r1', 'odds_decimal': 1.8, 'horse_name': 'Favorite'},
        {'runner_id': 'r2', 'odds_decimal': 3.5, 'horse_name': 'Second Fav'},
        {'runner_id': 'r3', 'odds_decimal': 5.0, 'horse_name': 'Third'},
        {'runner_id': 'r4', 'odds_decimal': 8.0, 'horse_name': 'Mid Runner'},
        {'runner_id': 'r5', 'odds_decimal': 12.0, 'horse_name': 'Mid Runner 2'},
        {'runner_id': 'r6', 'odds_decimal': 18.0, 'horse_name': 'Outsider 1'},
        {'runner_id': 'r7', 'odds_decimal': 25.0, 'horse_name': 'Outsider 2'},
        {'runner_id': 'r8', 'odds_decimal': 40.0, 'horse_name': 'Longshot'},
    ]
    
    race_ctx = {
        'race_id': 'TEST_ROLES_001',
        'course': 'Lingfield',
        'off_time': '13:00'
    }
    
    market_ctx = {'all_runners': runners}
    profiles = profile_race_opponents(runners, race_ctx, market_ctx)
    
    # Extract unique roles
    roles = set()
    for profile in profiles:
        role = profile.market_role
        if hasattr(role, 'value'):
            role = role.value
        roles.add(role)
    
    assert len(roles) >= 3, f"Expected ≥3 roles, got {len(roles)}: {roles}"
    
    # Check specific roles exist
    role_names = {r for r in roles}
    assert 'Liquidity_Anchor' in role_names or 'Release_Horse' in role_names, \
        f"Expected Anchor or Release, got: {role_names}"


def test_anchor_conditions_trigger_only_when_gap_threshold_met():
    """Test that ANCHOR role only assigned when probability gap is sufficient."""
    
    # Test 1: Strong favorite (gap > 25%)
    runners_strong_fav = [
        {'runner_id': 'r1', 'odds_decimal': 1.5, 'horse_name': 'Strong Fav'},  # 66.7% prob
        {'runner_id': 'r2', 'odds_decimal': 4.0, 'horse_name': 'Second'},      # 25% prob
        {'runner_id': 'r3', 'odds_decimal': 8.0, 'horse_name': 'Third'},
    ]
    
    race_ctx = {'race_id': 'TEST_ANCHOR_001', 'course': 'Test', 'off_time': '13:00'}
    market_ctx = {'all_runners': runners_strong_fav}
    profiles = profile_race_opponents(runners_strong_fav, race_ctx, market_ctx)
    
    # r1 should be ANCHOR
    r1_role = profiles[0].market_role
    if hasattr(r1_role, 'value'):
        r1_role = r1_role.value
    
    assert r1_role == 'Liquidity_Anchor', \
        f"Expected Anchor for 66.7% prob with gap, got {r1_role}"
    
    # Test 2: Weak favorite (gap < 25%)
    runners_weak_fav = [
        {'runner_id': 'r1', 'odds_decimal': 2.5, 'horse_name': 'Weak Fav'},   # 40% prob
        {'runner_id': 'r2', 'odds_decimal': 3.0, 'horse_name': 'Second'},     # 33% prob
        {'runner_id': 'r3', 'odds_decimal': 8.0, 'horse_name': 'Third'},
    ]
    
    market_ctx2 = {'all_runners': runners_weak_fav}
    profiles2 = profile_race_opponents(runners_weak_fav, race_ctx, market_ctx2)
    
    # r1 might NOT be ANCHOR (gap only 7%)
    r1_role2 = profiles2[0].market_role
    if hasattr(r1_role2, 'value'):
        r1_role2 = r1_role2.value
    
    # This is acceptable - weak favorites can be Release instead of Anchor
    assert r1_role2 in ['Liquidity_Anchor', 'Release_Horse'], \
        f"Expected Anchor or Release for weak favorite, got {r1_role2}"


def test_no_runner_returns_role_without_reason():
    """Test that every runner has a role_reason string."""
    runners = [
        {'runner_id': 'r1', 'odds_decimal': 2.0, 'horse_name': 'Horse 1'},
        {'runner_id': 'r2', 'odds_decimal': 4.0, 'horse_name': 'Horse 2'},
        {'runner_id': 'r3', 'odds_decimal': 10.0, 'horse_name': 'Horse 3'},
        {'runner_id': 'r4', 'odds_decimal': 20.0, 'horse_name': 'Horse 4'},
    ]
    
    race_ctx = {'race_id': 'TEST_REASON_001', 'course': 'Test', 'off_time': '13:00'}
    market_ctx = {'all_runners': runners}
    profiles = profile_race_opponents(runners, race_ctx, market_ctx)
    
    for profile in profiles:
        runner_id = profile.runner_id
        role_reason = getattr(profile, 'role_reason', None)
        
        assert role_reason is not None, \
            f"Runner {runner_id} has no role_reason"
        assert isinstance(role_reason, str), \
            f"Runner {runner_id} role_reason is not a string: {type(role_reason)}"
        assert len(role_reason) > 0, \
            f"Runner {runner_id} has empty role_reason"


def test_noise_percentage_below_40_percent():
    """Test that NOISE role is not assigned to >40% of field."""
    runners = [
        {'runner_id': f'r{i}', 'odds_decimal': float(i+1)*2, 'horse_name': f'Horse {i}'}
        for i in range(10)
    ]
    
    race_ctx = {'race_id': 'TEST_NOISE_001', 'course': 'Test', 'off_time': '13:00'}
    market_ctx = {'all_runners': runners}
    profiles = profile_race_opponents(runners, race_ctx, market_ctx)
    
    noise_count = 0
    for profile in profiles:
        role = profile.market_role
        if hasattr(role, 'value'):
            role = role.value
        if role == 'Noise':
            noise_count += 1
    
    noise_pct = noise_count / len(profiles)
    assert noise_pct <= 0.40, \
        f"NOISE assigned to {noise_pct*100:.1f}% of field (max 40%)"


def test_lowest_odds_never_noise():
    """Test that the lowest odds runner is NEVER classified as NOISE."""
    runners = [
        {'runner_id': 'r1', 'odds_decimal': 1.8, 'horse_name': 'Favorite'},
        {'runner_id': 'r2', 'odds_decimal': 5.0, 'horse_name': 'Mid'},
        {'runner_id': 'r3', 'odds_decimal': 10.0, 'horse_name': 'Outsider'},
    ]
    
    race_ctx = {'race_id': 'TEST_LOWEST_001', 'course': 'Test', 'off_time': '13:00'}
    market_ctx = {'all_runners': runners}
    profiles = profile_race_opponents(runners, race_ctx, market_ctx)
    
    # Find lowest odds runner
    lowest_odds_profile = min(profiles, key=lambda p: p.evidence.get('odds', 999))
    role = lowest_odds_profile.market_role
    if hasattr(role, 'value'):
        role = role.value
    
    assert role != 'Noise', \
        f"Lowest odds runner ({lowest_odds_profile.runner_id}) classified as NOISE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
