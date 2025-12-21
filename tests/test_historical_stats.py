"""
Unit tests for Historical Stats Integration (Phase 2A.3)
"""

import pytest
from app.ml.historical_stats import (
    HistoricalStats,
    classify_distance_band,
    calculate_sample_weight,
    calculate_stat_modifier,
    extract_trainer_modifier,
    extract_jockey_modifier,
    extract_combo_modifier,
    calculate_historical_modifier,
    validate_stats
)


def test_classify_distance_band():
    """Test distance band classification."""
    assert classify_distance_band(1200) == "SPRINT"  # 6f
    assert classify_distance_band(1600) == "MILE"  # 8f
    assert classify_distance_band(2000) == "MIDDLE"  # 10f
    assert classify_distance_band(3200) == "LONG"  # 16f


def test_calculate_sample_weight_full():
    """Test sample weight with sufficient samples."""
    weight = calculate_sample_weight(20, min_threshold=10)
    assert weight == 1.0


def test_calculate_sample_weight_partial():
    """Test sample weight with partial samples."""
    weight = calculate_sample_weight(5, min_threshold=10)
    assert weight == 0.5


def test_calculate_sample_weight_zero():
    """Test sample weight with zero samples."""
    weight = calculate_sample_weight(0, min_threshold=10)
    assert weight == 0.0


def test_calculate_stat_modifier_positive():
    """Test stat modifier with above-baseline win rate."""
    modifier, reason = calculate_stat_modifier(
        win_rate=0.20,  # 20% (above 10% baseline)
        sample_size=20,
        baseline=0.10,
        max_influence=0.05
    )
    
    assert modifier > 0.0, "Above-baseline should have positive modifier"
    assert modifier <= 0.05, "Should not exceed max influence"
    assert "win_rate=0.200" in reason


def test_calculate_stat_modifier_negative():
    """Test stat modifier with below-baseline win rate."""
    modifier, reason = calculate_stat_modifier(
        win_rate=0.05,  # 5% (below 10% baseline)
        sample_size=20,
        baseline=0.10,
        max_influence=0.05
    )
    
    assert modifier < 0.0, "Below-baseline should have negative modifier"
    assert modifier >= -0.05, "Should not exceed max influence"


def test_calculate_stat_modifier_low_sample():
    """Test stat modifier with low sample size."""
    modifier, reason = calculate_stat_modifier(
        win_rate=0.20,  # Good win rate (above baseline)
        sample_size=3,  # But only 3 samples (30% weight)
        baseline=0.10,
        max_influence=0.05
    )
    
    # Should be dampened by low sample weight
    # Expected: (0.20 - 0.10) * 0.3 = 0.03
    assert 0.0 < modifier < 0.05, "Low sample should dampen modifier below max"
    assert "samples=3" in reason


def test_calculate_stat_modifier_zero_sample():
    """Test stat modifier with zero samples."""
    modifier, reason = calculate_stat_modifier(
        win_rate=0.50,
        sample_size=0,
        baseline=0.10,
        max_influence=0.05
    )
    
    assert modifier == 0.0, "Zero samples should give zero modifier"
    assert "insufficient_sample_size=0" in reason


def test_extract_trainer_modifier():
    """Test trainer modifier extraction."""
    stats = HistoricalStats(
        trainer_win_rate=0.20,
        jockey_win_rate=0.10,
        combo_win_rate=0.15,
        trainer_sample_size=20,
        jockey_sample_size=15,
        combo_sample_size=5,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    modifier, reason = extract_trainer_modifier(stats)
    
    assert modifier > 0.0, "Good trainer should have positive modifier"
    assert modifier <= 0.05, "Should respect max influence"


def test_extract_jockey_modifier():
    """Test jockey modifier extraction."""
    stats = HistoricalStats(
        trainer_win_rate=0.10,
        jockey_win_rate=0.05,  # Below baseline
        combo_win_rate=0.08,
        trainer_sample_size=20,
        jockey_sample_size=20,
        combo_sample_size=5,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    modifier, reason = extract_jockey_modifier(stats)
    
    assert modifier < 0.0, "Poor jockey should have negative modifier"


def test_extract_combo_modifier():
    """Test combo modifier extraction."""
    stats = HistoricalStats(
        trainer_win_rate=0.15,
        jockey_win_rate=0.15,
        combo_win_rate=0.25,  # Strong combo
        trainer_sample_size=20,
        jockey_sample_size=20,
        combo_sample_size=10,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    modifier, reason = extract_combo_modifier(stats)
    
    assert modifier > 0.0, "Strong combo should have positive modifier"
    assert modifier <= 0.03, "Combo should have lower max influence"


def test_calculate_historical_modifier_no_stats():
    """Test historical modifier with no stats."""
    result = calculate_historical_modifier(None)
    
    assert result["total_modifier"] == 0.0
    assert result["reason"] == "no_historical_stats"


def test_calculate_historical_modifier_trainer_jockey():
    """Test historical modifier with trainer+jockey."""
    stats = HistoricalStats(
        trainer_win_rate=0.15,
        jockey_win_rate=0.12,
        combo_win_rate=0.20,
        trainer_sample_size=20,
        jockey_sample_size=20,
        combo_sample_size=10,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    result = calculate_historical_modifier(
        stats,
        use_trainer=True,
        use_jockey=True,
        use_combo=False
    )
    
    assert result["total_modifier"] > 0.0
    assert result["trainer_modifier"] > 0.0
    assert result["jockey_modifier"] > 0.0
    assert result["combo_modifier"] == 0.0
    assert "trainer:" in result["reason"]
    assert "jockey:" in result["reason"]


def test_calculate_historical_modifier_combo_only():
    """Test historical modifier with combo only."""
    stats = HistoricalStats(
        trainer_win_rate=0.15,
        jockey_win_rate=0.12,
        combo_win_rate=0.25,
        trainer_sample_size=20,
        jockey_sample_size=20,
        combo_sample_size=10,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    result = calculate_historical_modifier(
        stats,
        use_trainer=False,
        use_jockey=False,
        use_combo=True
    )
    
    assert result["total_modifier"] > 0.0
    assert result["trainer_modifier"] == 0.0
    assert result["jockey_modifier"] == 0.0
    assert result["combo_modifier"] > 0.0
    assert "combo:" in result["reason"]


def test_calculate_historical_modifier_bounded():
    """Test that total modifier is bounded."""
    # Create stats with extreme values
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
    
    result = calculate_historical_modifier(
        stats,
        use_trainer=True,
        use_jockey=True,
        use_combo=False
    )
    
    # Even with extreme values, should be capped at ±0.05
    assert -0.05 <= result["total_modifier"] <= 0.05


def test_validate_stats_valid():
    """Test stats validation with valid data."""
    stats = HistoricalStats(
        trainer_win_rate=0.15,
        jockey_win_rate=0.12,
        combo_win_rate=0.20,
        trainer_sample_size=20,
        jockey_sample_size=15,
        combo_sample_size=10,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    assert validate_stats(stats) is True


def test_validate_stats_invalid_win_rate():
    """Test stats validation with invalid win rate."""
    stats = HistoricalStats(
        trainer_win_rate=1.5,  # Invalid (>1.0)
        jockey_win_rate=0.12,
        combo_win_rate=0.20,
        trainer_sample_size=20,
        jockey_sample_size=15,
        combo_sample_size=10,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    assert validate_stats(stats) is False


def test_validate_stats_negative_sample():
    """Test stats validation with negative sample size."""
    stats = HistoricalStats(
        trainer_win_rate=0.15,
        jockey_win_rate=0.12,
        combo_win_rate=0.20,
        trainer_sample_size=-5,  # Invalid
        jockey_sample_size=15,
        combo_sample_size=10,
        track="AYR",
        distance_band="MILE",
        surface="Turf",
        recency_days=365
    )
    
    assert validate_stats(stats) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
