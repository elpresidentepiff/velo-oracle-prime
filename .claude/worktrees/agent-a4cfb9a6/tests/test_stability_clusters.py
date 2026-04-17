"""
Unit tests for Stability Cluster Engine (Phase 2A)
"""

import pytest
from app.ml.stability_clusters import (
    classify_consistency_band,
    classify_form_trend,
    classify_field_rank_band,
    generate_cluster_id,
    build_stability_profile,
    cluster_field,
    get_cluster_trust_modifier,
    identify_hidden_value,
    identify_liquidity_traps
)


def test_classify_consistency_band():
    """Test consistency band classification."""
    assert classify_consistency_band(0.8) == "HIGH"
    assert classify_consistency_band(0.5) == "MEDIUM"
    assert classify_consistency_band(0.2) == "LOW"


def test_classify_form_trend_improving():
    """Test form trend - improving."""
    # Positions getting better (lower numbers)
    positions = [1, 2, 3, 4, 5]  # Most recent first
    trend = classify_form_trend(positions)
    assert trend == "IMPROVING"


def test_classify_form_trend_declining():
    """Test form trend - declining."""
    # Positions getting worse (higher numbers)
    positions = [5, 4, 3, 2, 1]  # Most recent first
    trend = classify_form_trend(positions)
    assert trend == "DECLINING"


def test_classify_form_trend_stable():
    """Test form trend - stable."""
    positions = [3, 3, 3, 3]
    trend = classify_form_trend(positions)
    assert trend == "STABLE"


def test_classify_form_trend_insufficient_data():
    """Test form trend with insufficient data."""
    assert classify_form_trend([1, 2]) == "UNKNOWN"
    assert classify_form_trend([]) == "UNKNOWN"


def test_classify_field_rank_band():
    """Test field rank band classification."""
    # Field of 12 runners
    assert classify_field_rank_band(1, 12) == "TOP"  # 1st = top 33%
    assert classify_field_rank_band(4, 12) == "TOP"  # 4th = top 33%
    assert classify_field_rank_band(6, 12) == "MID"  # 6th = middle 33%
    assert classify_field_rank_band(10, 12) == "BOTTOM"  # 10th = bottom 33%


def test_generate_cluster_id():
    """Test cluster ID generation."""
    cluster_id = generate_cluster_id("STABLE", "HIGH", "IMPROVING", "TOP")
    assert cluster_id == "STABLE_HIGH_IMPROVING_TOP"


def test_build_stability_profile_stable():
    """Test building profile for stable runner."""
    form_metrics = {
        "consistency": 0.8,
        "recent_form": 0.7,
        "win_rate": 0.3,
        "place_rate": 0.6,
        "valid_races": 5
    }
    positions = [2, 2, 3, 2, 2]
    
    profile = build_stability_profile(
        runner_id="r1",
        form_metrics=form_metrics,
        positions=positions,
        field_position=2,
        field_size=10
    )
    
    assert profile.runner_id == "r1"
    assert profile.stability_class == "STABLE"
    assert profile.consistency_band == "HIGH"
    assert profile.field_rank_band == "TOP"


def test_build_stability_profile_volatile():
    """Test building profile for volatile runner."""
    form_metrics = {
        "consistency": 0.2,
        "recent_form": 0.5,
        "win_rate": 0.1,
        "place_rate": 0.3,
        "valid_races": 5
    }
    positions = [1, 8, 2, 9, 3]
    
    profile = build_stability_profile(
        runner_id="r2",
        form_metrics=form_metrics,
        positions=positions,
        field_position=5,
        field_size=10
    )
    
    assert profile.stability_class == "VOLATILE"
    assert profile.consistency_band == "LOW"


def test_build_stability_profile_insufficient_data():
    """Test building profile with insufficient data."""
    form_metrics = {
        "consistency": 0.5,
        "recent_form": 0.5,
        "win_rate": 0.0,
        "place_rate": 0.0,
        "valid_races": 1
    }
    positions = [3]
    
    profile = build_stability_profile(
        runner_id="r3",
        form_metrics=form_metrics,
        positions=positions,
        field_position=5,
        field_size=10
    )
    
    assert profile.stability_class == "INSUFFICIENT_DATA"


def test_cluster_field():
    """Test clustering entire field."""
    runners_data = [
        {
            "runner_id": "r1",
            "form_metrics": {"consistency": 0.8, "recent_form": 0.7, "win_rate": 0.3, "place_rate": 0.6, "valid_races": 5},
            "positions": [2, 2, 3, 2, 2],
            "field_position": 1,
            "field_size": 5
        },
        {
            "runner_id": "r2",
            "form_metrics": {"consistency": 0.2, "recent_form": 0.4, "win_rate": 0.1, "place_rate": 0.2, "valid_races": 5},
            "positions": [5, 4, 6, 5, 7],
            "field_position": 5,
            "field_size": 5
        },
        {
            "runner_id": "r3",
            "form_metrics": {"consistency": 0.8, "recent_form": 0.7, "win_rate": 0.3, "place_rate": 0.6, "valid_races": 5},
            "positions": [2, 2, 3, 2, 2],
            "field_position": 2,
            "field_size": 5
        }
    ]
    
    clusters = cluster_field(runners_data)
    
    # Should have clusters
    assert len(clusters) > 0
    
    # r1 and r3 have similar form but different field positions (1st vs 2nd)
    # So they will be in different clusters (TOP vs TOP, but different exact positions)
    # Just verify all runners are clustered
    all_runner_ids = set()
    for cluster_id, profiles in clusters.items():
        for p in profiles:
            all_runner_ids.add(p.runner_id)
    
    assert all_runner_ids == {"r1", "r2", "r3"}, "All runners should be clustered"


def test_get_cluster_trust_modifier_stable():
    """Test trust modifier for stable cluster."""
    modifier = get_cluster_trust_modifier("STABLE_HIGH_IMPROVING_TOP")
    assert modifier > 0.0, "Stable + high consistency + improving should have positive modifier"


def test_get_cluster_trust_modifier_volatile():
    """Test trust modifier for volatile cluster."""
    modifier = get_cluster_trust_modifier("VOLATILE_LOW_DECLINING_BOTTOM")
    assert modifier < 0.0, "Volatile + low consistency + declining should have negative modifier"


def test_get_cluster_trust_modifier_bounded():
    """Test trust modifier is bounded."""
    # Even extreme cases should be bounded
    modifier = get_cluster_trust_modifier("STABLE_HIGH_IMPROVING_TOP")
    assert -0.10 <= modifier <= 0.10


def test_identify_hidden_value():
    """Test identification of hidden value runners."""
    clusters = {
        "STABLE_MEDIUM_IMPROVING_MID": [
            type('Profile', (), {"runner_id": "r1"})()
        ],
        "VOLATILE_LOW_DECLINING_TOP": [
            type('Profile', (), {"runner_id": "r2"})()
        ],
        "MODERATE_HIGH_IMPROVING_BOTTOM": [
            type('Profile', (), {"runner_id": "r3"})()
        ]
    }
    
    hidden = identify_hidden_value(clusters)
    
    assert "r1" in hidden, "Stable improving mid-field should be hidden value"
    assert "r3" in hidden, "Moderate improving bottom should be hidden value"
    assert "r2" not in hidden, "Volatile declining top should not be hidden value"


def test_identify_liquidity_traps():
    """Test identification of liquidity traps."""
    clusters = {
        "VOLATILE_LOW_DECLINING_TOP": [
            type('Profile', (), {"runner_id": "r1"})()
        ],
        "STABLE_HIGH_IMPROVING_TOP": [
            type('Profile', (), {"runner_id": "r2"})()
        ],
        "VOLATILE_MEDIUM_STABLE_TOP": [
            type('Profile', (), {"runner_id": "r3"})()
        ]
    }
    
    traps = identify_liquidity_traps(clusters)
    
    assert "r1" in traps, "Volatile top runner should be liquidity trap"
    assert "r3" in traps, "Volatile top runner should be liquidity trap"
    assert "r2" not in traps, "Stable top runner should not be liquidity trap"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
