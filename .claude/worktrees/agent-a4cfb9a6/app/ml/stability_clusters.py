"""
VELO Stability Cluster Engine v1 (Phase 2A)

Rule-based clustering of runners by performance patterns.
Descriptive, not predictive. Labels structure, doesn't decide outcomes.

Cluster dimensions:
1. Stability class (STABLE/MODERATE/VOLATILE)
2. Consistency score band
3. Recent form trend
4. Field-relative ranking

NO ML. NO k-means. Auditable, explainable.

Author: VELO Team
Version: 1.0 (Phase 2A)
Date: December 21, 2025
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class StabilityProfile:
    """Runner stability profile."""
    runner_id: str
    stability_class: str  # STABLE, MODERATE, VOLATILE, INSUFFICIENT_DATA
    consistency_band: str  # HIGH, MEDIUM, LOW
    form_trend: str  # IMPROVING, STABLE, DECLINING, UNKNOWN
    field_rank_band: str  # TOP, MID, BOTTOM
    cluster_id: str  # Composite cluster identifier
    
    # Raw metrics
    consistency_score: float
    recent_form_score: float
    win_rate: float
    place_rate: float


def classify_consistency_band(consistency: float) -> str:
    """
    Classify consistency into bands.
    
    Args:
        consistency: Consistency score (0.0-1.0)
        
    Returns:
        Band: HIGH, MEDIUM, LOW
    """
    if consistency >= 0.7:
        return "HIGH"
    elif consistency >= 0.4:
        return "MEDIUM"
    else:
        return "LOW"


def classify_form_trend(positions: List[Optional[int]], lookback: int = 5) -> str:
    """
    Classify form trend from recent positions.
    
    Args:
        positions: List of positions (most recent first)
        lookback: Number of races to analyze
        
    Returns:
        Trend: IMPROVING, STABLE, DECLINING, UNKNOWN
    """
    if not positions or len(positions) < 3:
        return "UNKNOWN"
    
    # Take last N races
    recent = positions[:lookback]
    valid = [p for p in recent if p is not None]
    
    if len(valid) < 3:
        return "UNKNOWN"
    
    # Positions are most-recent-first, reverse to get chronological order
    chronological = list(reversed(valid))
    
    # Split into older half and recent half
    mid = len(chronological) // 2
    older_half = chronological[:mid]
    recent_half = chronological[mid:]
    
    avg_older = sum(older_half) / len(older_half)
    avg_recent = sum(recent_half) / len(recent_half)
    
    # Lower position = better (1st is best)
    # If recent avg is lower than older avg, runner is improving
    diff = avg_older - avg_recent
    
    if diff > 1.0:
        return "IMPROVING"  # Recent positions better than older
    elif diff < -1.0:
        return "DECLINING"  # Recent positions worse than older
    else:
        return "STABLE"  # Consistent


def classify_field_rank_band(field_position: int, field_size: int) -> str:
    """
    Classify runner's position in field.
    
    Args:
        field_position: Runner's rank in field (1 = favorite)
        field_size: Total number of runners
        
    Returns:
        Band: TOP, MID, BOTTOM
    """
    if field_size <= 0:
        return "UNKNOWN"
    
    # Normalize to percentile (1-indexed, so subtract 1)
    percentile = (field_position - 1) / field_size
    
    if percentile < 0.33:
        return "TOP"
    elif percentile < 0.67:
        return "MID"
    else:
        return "BOTTOM"


def generate_cluster_id(
    stability_class: str,
    consistency_band: str,
    form_trend: str,
    field_rank_band: str
) -> str:
    """
    Generate composite cluster identifier.
    
    Format: {stability}_{consistency}_{trend}_{rank}
    Example: STABLE_HIGH_IMPROVING_TOP
    
    Args:
        stability_class: STABLE, MODERATE, VOLATILE, INSUFFICIENT_DATA
        consistency_band: HIGH, MEDIUM, LOW
        form_trend: IMPROVING, STABLE, DECLINING, UNKNOWN
        field_rank_band: TOP, MID, BOTTOM
        
    Returns:
        Cluster ID string
    """
    return f"{stability_class}_{consistency_band}_{form_trend}_{field_rank_band}"


def build_stability_profile(
    runner_id: str,
    form_metrics: Dict[str, float],
    positions: List[Optional[int]],
    field_position: int,
    field_size: int
) -> StabilityProfile:
    """
    Build complete stability profile for a runner.
    
    Args:
        runner_id: Runner identifier
        form_metrics: Dict from form_parser.analyze_form()
        positions: List of positions for trend analysis
        field_position: Runner's rank in current field
        field_size: Total field size
        
    Returns:
        StabilityProfile
    """
    # Extract metrics
    consistency = form_metrics.get("consistency", 0.0)
    recent_form = form_metrics.get("recent_form", 0.5)
    win_rate = form_metrics.get("win_rate", 0.0)
    place_rate = form_metrics.get("place_rate", 0.0)
    valid_races = form_metrics.get("valid_races", 0)
    
    # Classify stability
    if valid_races < 3:
        stability_class = "INSUFFICIENT_DATA"
    elif consistency >= 0.7:
        stability_class = "STABLE"
    elif consistency <= 0.4:
        stability_class = "VOLATILE"
    else:
        stability_class = "MODERATE"
    
    # Classify dimensions
    consistency_band = classify_consistency_band(consistency)
    form_trend = classify_form_trend(positions)
    field_rank_band = classify_field_rank_band(field_position, field_size)
    
    # Generate cluster ID
    cluster_id = generate_cluster_id(
        stability_class,
        consistency_band,
        form_trend,
        field_rank_band
    )
    
    return StabilityProfile(
        runner_id=runner_id,
        stability_class=stability_class,
        consistency_band=consistency_band,
        form_trend=form_trend,
        field_rank_band=field_rank_band,
        cluster_id=cluster_id,
        consistency_score=consistency,
        recent_form_score=recent_form,
        win_rate=win_rate,
        place_rate=place_rate
    )


def cluster_field(runners_data: List[Dict]) -> Dict[str, List[StabilityProfile]]:
    """
    Cluster all runners in a field by stability profiles.
    
    Args:
        runners_data: List of runner dicts with:
            - runner_id
            - form_metrics (from analyze_form)
            - positions (parsed form)
            - field_position
            - field_size
            
    Returns:
        Dict mapping cluster_id to list of StabilityProfiles
    """
    clusters = {}
    
    for runner in runners_data:
        profile = build_stability_profile(
            runner_id=runner["runner_id"],
            form_metrics=runner["form_metrics"],
            positions=runner["positions"],
            field_position=runner["field_position"],
            field_size=runner["field_size"]
        )
        
        # Add to cluster
        if profile.cluster_id not in clusters:
            clusters[profile.cluster_id] = []
        
        clusters[profile.cluster_id].append(profile)
    
    logger.info(f"Clustered {len(runners_data)} runners into {len(clusters)} clusters")
    
    return clusters


def get_cluster_trust_modifier(cluster_id: str) -> float:
    """
    Get trust modifier for a cluster (for Top-4 ranking).
    
    Trust modifier adjusts confidence in predictions.
    Range: -0.10 to +0.10 (additive to score)
    
    Args:
        cluster_id: Cluster identifier
        
    Returns:
        Trust modifier (-0.10 to +0.10)
    """
    # Parse cluster ID
    parts = cluster_id.split("_")
    if len(parts) != 4:
        return 0.0
    
    stability, consistency, trend, rank = parts
    
    modifier = 0.0
    
    # Stability contribution
    if stability == "STABLE":
        modifier += 0.05
    elif stability == "VOLATILE":
        modifier -= 0.05
    
    # Consistency contribution
    if consistency == "HIGH":
        modifier += 0.03
    elif consistency == "LOW":
        modifier -= 0.03
    
    # Trend contribution (smaller weight)
    if trend == "IMPROVING":
        modifier += 0.02
    elif trend == "DECLINING":
        modifier -= 0.02
    
    # Clamp to range
    modifier = max(-0.10, min(0.10, modifier))
    
    return modifier


def identify_hidden_value(clusters: Dict[str, List[StabilityProfile]]) -> List[str]:
    """
    Identify runners with hidden value (improving + mid-field).
    
    These are runners the market may undervalue.
    
    Args:
        clusters: Dict from cluster_field()
        
    Returns:
        List of runner_ids with potential hidden value
    """
    hidden_value = []
    
    for cluster_id, profiles in clusters.items():
        # Look for: IMPROVING + MID/BOTTOM rank + STABLE/MODERATE
        if "IMPROVING" in cluster_id and ("MID" in cluster_id or "BOTTOM" in cluster_id):
            if "STABLE" in cluster_id or "MODERATE" in cluster_id:
                hidden_value.extend([p.runner_id for p in profiles])
    
    return hidden_value


def identify_liquidity_traps(clusters: Dict[str, List[StabilityProfile]]) -> List[str]:
    """
    Identify potential liquidity traps (volatile favorites).
    
    These are favorites with inconsistent performance.
    
    Args:
        clusters: Dict from cluster_field()
        
    Returns:
        List of runner_ids that may be liquidity traps
    """
    traps = []
    
    for cluster_id, profiles in clusters.items():
        # Look for: VOLATILE + TOP rank
        if "VOLATILE" in cluster_id and "TOP" in cluster_id:
            traps.extend([p.runner_id for p in profiles])
    
    return traps
