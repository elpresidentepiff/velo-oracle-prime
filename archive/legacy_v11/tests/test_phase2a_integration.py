"""
Phase 2A Integration Tests

Tests the full pipeline with form, stability, and historical stats.
"""

import pytest
from app.strategy.top4_ranker import calculate_runner_score, rank_top4
from app.ml.form_parser import analyze_form, parse_form_string
from app.ml.stability_clusters import build_stability_profile
from app.ml.historical_stats import HistoricalStats


def test_score_with_stability_modifier():
    """Test that stability modifier affects score."""
    # Create profile with stability
    profile = {
        'runner_id': 'r1',
        'market_role': 'ANCHOR',
        'odds_decimal': 2.5,
        'stability_profile': {
            'cluster_id': 'STABLE_HIGH_IMPROVING_TOP'
        }
    }
    
    race_ctx = {
        'chaos_level': 0.5,
        'field_size': 10,
        'manipulation_risk': 0.3
    }
    
    score = calculate_runner_score(profile, race_ctx)
    
    # Should have positive stability modifier
    assert score.components['stability'] > 0.0
    assert score.components['stability_reason'] == 'STABLE_HIGH_IMPROVING_TOP'


def test_score_with_historical_modifier():
    """Test that historical stats modifier affects score."""
    # Create profile with historical stats
    stats = HistoricalStats(
        trainer_win_rate=0.20,  # Above baseline
        jockey_win_rate=0.15,  # Above baseline
        combo_win_rate=0.25,
        trainer_sample_size=20,
        jockey_sample_size=20,
        combo_sample_size=10,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    profile = {
        'runner_id': 'r1',
        'market_role': 'ANCHOR',
        'odds_decimal': 2.5,
        'historical_stats': stats
    }
    
    race_ctx = {
        'chaos_level': 0.5,
        'field_size': 10,
        'manipulation_risk': 0.3
    }
    
    score = calculate_runner_score(profile, race_ctx)
    
    # Should have positive historical modifier
    assert score.components['historical'] > 0.0
    assert 'trainer:' in score.components['historical_reason']
    assert 'jockey:' in score.components['historical_reason']


def test_score_with_both_modifiers():
    """Test that stability and historical modifiers combine."""
    stats = HistoricalStats(
        trainer_win_rate=0.20,
        jockey_win_rate=0.15,
        combo_win_rate=0.25,
        trainer_sample_size=20,
        jockey_sample_size=20,
        combo_sample_size=10,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    profile = {
        'runner_id': 'r1',
        'market_role': 'ANCHOR',
        'odds_decimal': 2.5,
        'stability_profile': {
            'cluster_id': 'STABLE_HIGH_IMPROVING_TOP'
        },
        'historical_stats': stats
    }
    
    race_ctx = {
        'chaos_level': 0.5,
        'field_size': 10,
        'manipulation_risk': 0.3
    }
    
    score = calculate_runner_score(profile, race_ctx)
    
    # Both modifiers should be positive
    assert score.components['stability'] > 0.0
    assert score.components['historical'] > 0.0
    
    # Total should include both
    assert score.total > (score.components['role'] + score.components['odds'])


def test_score_without_modifiers():
    """Test that score works without Phase 2A data."""
    # Profile without stability or historical stats
    profile = {
        'runner_id': 'r1',
        'market_role': 'ANCHOR',
        'odds_decimal': 2.5
    }
    
    race_ctx = {
        'chaos_level': 0.5,
        'field_size': 10,
        'manipulation_risk': 0.3
    }
    
    score = calculate_runner_score(profile, race_ctx)
    
    # Modifiers should be zero
    assert score.components['stability'] == 0.0
    assert score.components['historical'] == 0.0
    assert score.components['stability_reason'] == 'not_available'
    assert score.components['historical_reason'] == 'not_available'
    
    # But score should still work (Phase 1 components)
    assert score.total > 0.0


def test_modifier_caps_respected():
    """Test that modifiers respect their caps."""
    # Create extreme stats
    stats = HistoricalStats(
        trainer_win_rate=0.50,  # Extreme
        jockey_win_rate=0.50,  # Extreme
        combo_win_rate=0.50,
        trainer_sample_size=100,
        jockey_sample_size=100,
        combo_sample_size=100,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    profile = {
        'runner_id': 'r1',
        'market_role': 'ANCHOR',
        'odds_decimal': 2.5,
        'stability_profile': {
            'cluster_id': 'STABLE_HIGH_IMPROVING_TOP'  # Max positive
        },
        'historical_stats': stats
    }
    
    race_ctx = {
        'chaos_level': 0.5,
        'field_size': 10,
        'manipulation_risk': 0.3
    }
    
    score = calculate_runner_score(profile, race_ctx)
    
    # Stability should be capped at ±0.10
    assert -0.10 <= score.components['stability'] <= 0.10
    
    # Historical should be capped at ±0.05
    assert -0.05 <= score.components['historical'] <= 0.05


def test_rank_top4_with_phase2a_data():
    """Test Top-4 ranking with Phase 2A data."""
    stats_good = HistoricalStats(
        trainer_win_rate=0.20,
        jockey_win_rate=0.15,
        combo_win_rate=0.25,
        trainer_sample_size=20,
        jockey_sample_size=20,
        combo_sample_size=10,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    stats_poor = HistoricalStats(
        trainer_win_rate=0.05,
        jockey_win_rate=0.05,
        combo_win_rate=0.05,
        trainer_sample_size=20,
        jockey_sample_size=20,
        combo_sample_size=10,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    profiles = [
        {
            'runner_id': 'r1',
            'market_role': 'ANCHOR',
            'odds_decimal': 2.5,
            'stability_profile': {'cluster_id': 'STABLE_HIGH_IMPROVING_TOP'},
            'historical_stats': stats_good
        },
        {
            'runner_id': 'r2',
            'market_role': 'RELEASE',
            'odds_decimal': 4.0,
            'stability_profile': {'cluster_id': 'VOLATILE_LOW_DECLINING_BOTTOM'},
            'historical_stats': stats_poor
        },
        {
            'runner_id': 'r3',
            'market_role': 'NOISE',
            'odds_decimal': 10.0
        }
    ]
    
    race_ctx = {
        'chaos_level': 0.5,
        'field_size': 3,
        'manipulation_risk': 0.3
    }
    
    top4, scores = rank_top4(profiles, race_ctx)
    
    # Should return all 3 runners (field < 4)
    assert len(top4) == 3
    
    # r1 should rank first (good everything)
    assert top4[0]['runner_id'] == 'r1'
    
    # All runners should have scores
    assert 'r1' in scores
    assert 'r2' in scores
    assert 'r3' in scores


def test_phase1_regression_with_phase2a():
    """Test that Phase 1 behavior is preserved when Phase 2A data is absent."""
    # Use Phase 1 test case
    profiles = [
        {'runner_id': 'r1', 'market_role': 'ANCHOR', 'odds_decimal': 2.0},
        {'runner_id': 'r2', 'market_role': 'RELEASE', 'odds_decimal': 4.0},
        {'runner_id': 'r3', 'market_role': 'NOISE', 'odds_decimal': 10.0},
        {'runner_id': 'r4', 'market_role': 'NOISE', 'odds_decimal': 15.0}
    ]
    
    race_ctx = {
        'chaos_level': 0.5,
        'field_size': 4,
        'manipulation_risk': 0.3
    }
    
    top4, scores = rank_top4(profiles, race_ctx)
    
    # Phase 1 contract: exactly 4 returned
    assert len(top4) == 4
    
    # All runners scored
    assert len(scores) == 4
    
    # Scores are positive
    for runner_id, score in scores.items():
        assert score.total > 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
