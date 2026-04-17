"""
Regression tests for Chaos Engine (Phase 1.1 Closure)

Contract tests:
1. Chaos monotonicity: more concentrated probs → lower chaos
2. Chaos changes when odds distribution changes
3. Chaos bounded [0,1]
"""

import pytest
from app.ml.chaos_calculator import calculate_chaos


def test_chaos_bounded_0_to_1():
    """Test that chaos is always in [0, 1] range."""
    # Test various odds distributions
    test_cases = [
        # (odds_list, field_size)
        ([1.5, 3.0, 5.0, 10.0], 4),  # Concentrated
        ([2.0, 2.5, 3.0, 3.5], 4),   # Very flat
        ([1.2, 50.0], 2),             # Extreme gap
        ([5.0] * 10, 10),             # All equal
    ]
    
    for odds_list, field_size in test_cases:
        chaos = calculate_chaos(odds_list, field_size)
        assert 0.0 <= chaos <= 1.0, \
            f"Chaos {chaos} out of bounds [0,1] for odds {odds_list}"


def test_chaos_monotonicity_concentrated_vs_flat():
    """Test that more concentrated probabilities → lower chaos."""
    # Concentrated: strong favorite
    odds_concentrated = [1.5, 5.0, 10.0, 20.0]  # 66.7%, 20%, 10%, 5%
    chaos_concentrated = calculate_chaos(odds_concentrated, len(odds_concentrated))
    
    # Flat: no clear favorite
    odds_flat = [3.0, 3.5, 4.0, 4.5]  # 33%, 29%, 25%, 22%
    chaos_flat = calculate_chaos(odds_flat, len(odds_flat))
    
    assert chaos_concentrated < chaos_flat, \
        f"Expected concentrated ({chaos_concentrated:.3f}) < flat ({chaos_flat:.3f})"


def test_chaos_changes_when_odds_distribution_changes():
    """Test that chaos is not constant across different odds distributions."""
    # Create 5 different odds distributions
    distributions = [
        [1.5, 3.0, 8.0, 15.0],      # Strong favorite
        [2.5, 3.0, 4.0, 6.0],       # Weak favorite
        [3.0, 3.5, 4.0, 4.5],       # Very flat
        [1.2, 10.0, 20.0, 50.0],    # Extreme favorite
        [5.0, 5.5, 6.0, 6.5],       # Mid-range flat
    ]
    
    chaos_values = []
    for odds in distributions:
        chaos = calculate_chaos(odds, len(odds))
        chaos_values.append(chaos)
    
    # Check that we have at least 3 distinct chaos values
    unique_chaos = set(round(c, 3) for c in chaos_values)
    assert len(unique_chaos) >= 3, \
        f"Expected ≥3 distinct chaos values, got {len(unique_chaos)}: {unique_chaos}"
    
    # Check that chaos is not constant
    assert not all(abs(c - chaos_values[0]) < 0.01 for c in chaos_values), \
        f"Chaos appears constant across distributions: {chaos_values}"


def test_chaos_increases_with_field_size():
    """Test that chaos generally increases with larger fields (more uncertainty)."""
    # Same odds pattern, different field sizes
    # Small field: 4 runners
    odds_small = [2.0, 3.0, 5.0, 8.0]
    chaos_small = calculate_chaos(odds_small, len(odds_small))
    
    # Large field: 12 runners (same pattern repeated + extras)
    odds_large = [2.0, 3.0, 5.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0, 25.0, 30.0, 40.0]
    chaos_large = calculate_chaos(odds_large, len(odds_large))
    
    # Larger fields should have higher chaos (more uncertainty)
    assert chaos_large >= chaos_small, \
        f"Expected large field chaos ({chaos_large:.3f}) >= small field ({chaos_small:.3f})"


def test_chaos_decreases_with_strong_favorite():
    """Test that chaos decreases when a strong favorite exists."""
    # No clear favorite
    odds_no_fav = [3.0, 3.5, 4.0, 5.0, 6.0]
    chaos_no_fav = calculate_chaos(odds_no_fav, len(odds_no_fav))
    
    # Strong favorite (>60% implied prob)
    odds_strong_fav = [1.5, 5.0, 8.0, 12.0, 20.0]  # 66.7% favorite
    chaos_strong_fav = calculate_chaos(odds_strong_fav, len(odds_strong_fav))
    
    assert chaos_strong_fav < chaos_no_fav, \
        f"Expected strong favorite chaos ({chaos_strong_fav:.3f}) < no favorite ({chaos_no_fav:.3f})"


def test_chaos_extreme_cases():
    """Test chaos behavior in extreme cases."""
    # Case 1: Single runner (no chaos possible)
    chaos_single = calculate_chaos([1.5], 1)
    assert chaos_single == 0.0, \
        f"Single runner should have chaos=0.0, got {chaos_single}"
    
    # Case 2: Two equal odds
    chaos_equal = calculate_chaos([2.0, 2.0], 2)
    assert chaos_equal > 0.4, \
        f"Equal odds should have high chaos, got {chaos_equal}"
    
    # Case 3: Extreme favorite
    chaos_extreme = calculate_chaos([1.1, 50.0, 100.0], 3)
    assert chaos_extreme < 0.3, \
        f"Extreme favorite should have low chaos, got {chaos_extreme}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
