"""
Unit tests for Form Parser (Phase 2A)
"""

import pytest
from app.ml.form_parser import (
    parse_form_string,
    calculate_consistency_score,
    calculate_recent_form_score,
    extract_win_rate,
    extract_place_rate,
    analyze_form,
    classify_stability
)


def test_parse_form_string_basic():
    """Test basic form string parsing."""
    assert parse_form_string("332") == [3, 3, 2]
    assert parse_form_string("1421") == [1, 4, 2, 1]
    assert parse_form_string("") == []
    assert parse_form_string("-") == []


def test_parse_form_string_with_gaps():
    """Test form strings with gaps (-)."""
    assert parse_form_string("3-2") == [3, None, 2]
    assert parse_form_string("1-4-1") == [1, None, 4, None, 1]


def test_parse_form_string_with_dnf():
    """Test form strings with DNF (0)."""
    assert parse_form_string("320") == [3, 2, None]
    assert parse_form_string("0000") == [None, None, None, None]


def test_consistency_score_perfect():
    """Test consistency with identical positions."""
    positions = [2, 2, 2, 2]
    consistency = calculate_consistency_score(positions)
    assert consistency == 1.0, "Identical positions should have consistency 1.0"


def test_consistency_score_variable():
    """Test consistency with variable positions."""
    positions = [1, 5, 2, 8]
    consistency = calculate_consistency_score(positions)
    assert 0.0 < consistency < 1.0, "Variable positions should have 0 < consistency < 1"


def test_consistency_score_insufficient_data():
    """Test consistency with insufficient data."""
    assert calculate_consistency_score([]) == 0.0
    assert calculate_consistency_score([1]) == 0.0
    assert calculate_consistency_score([None, None]) == 0.0


def test_recent_form_score_excellent():
    """Test recent form with wins."""
    positions = [1, 1, 2]
    score = calculate_recent_form_score(positions, lookback=3)
    assert score > 0.8, "Recent wins should have high form score"


def test_recent_form_score_poor():
    """Test recent form with poor positions."""
    positions = [8, 9, 7]
    score = calculate_recent_form_score(positions, lookback=3)
    assert score < 0.4, "Poor recent positions should have low form score"


def test_recent_form_score_with_gaps():
    """Test recent form ignores gaps."""
    positions = [1, None, None, 2]
    score = calculate_recent_form_score(positions, lookback=4)
    assert score > 0.7, "Should ignore gaps and score valid positions"


def test_win_rate_calculation():
    """Test win rate calculation."""
    positions = [1, 2, 1, 3, 1]
    win_rate = extract_win_rate(positions)
    assert win_rate == 0.6, "3 wins out of 5 = 60%"


def test_win_rate_no_wins():
    """Test win rate with no wins."""
    positions = [2, 3, 4, 5]
    win_rate = extract_win_rate(positions)
    assert win_rate == 0.0


def test_place_rate_calculation():
    """Test place rate calculation."""
    positions = [1, 2, 3, 4, 5]
    place_rate = extract_place_rate(positions, place_threshold=3)
    assert place_rate == 0.6, "3 places out of 5 = 60%"


def test_analyze_form_complete():
    """Test full form analysis."""
    result = analyze_form("1221")
    
    assert "consistency" in result
    assert "recent_form" in result
    assert "win_rate" in result
    assert "place_rate" in result
    assert "valid_races" in result
    
    assert result["valid_races"] == 4
    assert result["win_rate"] == 0.5  # 2 wins out of 4
    assert result["consistency"] > 0.5  # Fairly consistent (1,2,2,1)


def test_analyze_form_with_gaps():
    """Test form analysis with gaps."""
    result = analyze_form("1-2-1")
    
    assert result["valid_races"] == 3  # Gaps not counted
    assert result["win_rate"] == pytest.approx(0.666, rel=0.01)


def test_analyze_form_empty():
    """Test form analysis with empty string."""
    result = analyze_form("")
    
    assert result["valid_races"] == 0
    assert result["consistency"] == 0.0
    assert result["win_rate"] == 0.0


def test_classify_stability_stable():
    """Test stability classification - stable."""
    assert classify_stability(consistency=0.8, valid_races=5) == "STABLE"


def test_classify_stability_volatile():
    """Test stability classification - volatile."""
    assert classify_stability(consistency=0.3, valid_races=5) == "VOLATILE"


def test_classify_stability_insufficient_data():
    """Test stability classification - insufficient data."""
    assert classify_stability(consistency=0.8, valid_races=2) == "INSUFFICIENT_DATA"


def test_classify_stability_moderate():
    """Test stability classification - moderate."""
    assert classify_stability(consistency=0.5, valid_races=5) == "MODERATE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
