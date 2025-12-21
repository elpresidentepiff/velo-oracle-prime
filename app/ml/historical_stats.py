"""
VELO Historical Stats Integration v1 (Phase 2A.3)

Trainer/Jockey historical performance stats as confidence priors.
NOT predictors. NOT overrides. Bounded influence.

Integration rules:
1. ±0.05 max influence on composite score
2. Low sample → auto-decay to zero
3. Every modifier logs reasoning
4. Stats cannot override stability signals
5. Missing/malformed = zero influence + log

Author: VELO Team
Version: 1.0 (Phase 2A.3)
Date: December 21, 2025
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class HistoricalStats:
    """Historical performance statistics."""
    trainer_win_rate: float  # 0.0-1.0
    jockey_win_rate: float  # 0.0-1.0
    combo_win_rate: float  # Trainer+Jockey combo
    
    trainer_sample_size: int
    jockey_sample_size: int
    combo_sample_size: int
    
    track: str
    distance_band: str
    surface: str
    recency_days: int


def classify_distance_band(distance_meters: int) -> str:
    """
    Classify distance into bands.
    
    Args:
        distance_meters: Race distance in meters
        
    Returns:
        Band: SPRINT, MILE, MIDDLE, LONG
    """
    if distance_meters < 1400:
        return "SPRINT"  # < 7f
    elif distance_meters < 1800:
        return "MILE"  # 7f-9f
    elif distance_meters < 2400:
        return "MIDDLE"  # 9f-12f
    else:
        return "LONG"  # > 12f


def calculate_sample_weight(sample_size: int, min_threshold: int = 10) -> float:
    """
    Calculate weight based on sample size.
    
    Low sample → low weight (auto-decay).
    
    Args:
        sample_size: Number of samples
        min_threshold: Minimum samples for full weight
        
    Returns:
        Weight (0.0-1.0)
    """
    if sample_size <= 0:
        return 0.0
    
    if sample_size >= min_threshold:
        return 1.0
    
    # Linear decay below threshold
    return sample_size / min_threshold


def calculate_stat_modifier(
    win_rate: float,
    sample_size: int,
    baseline: float = 0.10,
    max_influence: float = 0.05
) -> Tuple[float, str]:
    """
    Calculate stat-based modifier with sample weighting.
    
    Args:
        win_rate: Historical win rate (0.0-1.0)
        sample_size: Number of samples
        baseline: Expected baseline win rate
        max_influence: Maximum modifier magnitude
        
    Returns:
        (modifier, reason) tuple
    """
    # Sample weight
    weight = calculate_sample_weight(sample_size)
    
    if weight == 0.0:
        return 0.0, f"insufficient_sample_size={sample_size}"
    
    # Deviation from baseline
    deviation = win_rate - baseline
    
    # Scale by weight and cap
    raw_modifier = deviation * weight
    capped_modifier = max(-max_influence, min(max_influence, raw_modifier))
    
    reason = f"win_rate={win_rate:.3f},baseline={baseline:.3f},samples={sample_size},weight={weight:.2f}"
    
    return capped_modifier, reason


def extract_trainer_modifier(stats: Optional[HistoricalStats]) -> Tuple[float, str]:
    """
    Extract trainer-based modifier.
    
    Args:
        stats: HistoricalStats or None
        
    Returns:
        (modifier, reason) tuple
    """
    if stats is None:
        return 0.0, "no_stats"
    
    return calculate_stat_modifier(
        win_rate=stats.trainer_win_rate,
        sample_size=stats.trainer_sample_size,
        baseline=0.10,
        max_influence=0.05
    )


def extract_jockey_modifier(stats: Optional[HistoricalStats]) -> Tuple[float, str]:
    """
    Extract jockey-based modifier.
    
    Args:
        stats: HistoricalStats or None
        
    Returns:
        (modifier, reason) tuple
    """
    if stats is None:
        return 0.0, "no_stats"
    
    return calculate_stat_modifier(
        win_rate=stats.jockey_win_rate,
        sample_size=stats.jockey_sample_size,
        baseline=0.10,
        max_influence=0.05
    )


def extract_combo_modifier(stats: Optional[HistoricalStats]) -> Tuple[float, str]:
    """
    Extract trainer+jockey combo modifier.
    
    Combo gets lower max influence (0.03) due to smaller sample sizes.
    
    Args:
        stats: HistoricalStats or None
        
    Returns:
        (modifier, reason) tuple
    """
    if stats is None:
        return 0.0, "no_stats"
    
    return calculate_stat_modifier(
        win_rate=stats.combo_win_rate,
        sample_size=stats.combo_sample_size,
        baseline=0.10,
        max_influence=0.03  # Lower for combo
    )


def calculate_historical_modifier(
    stats: Optional[HistoricalStats],
    use_trainer: bool = True,
    use_jockey: bool = True,
    use_combo: bool = False
) -> Dict[str, any]:
    """
    Calculate composite historical modifier.
    
    Args:
        stats: HistoricalStats or None
        use_trainer: Include trainer stats
        use_jockey: Include jockey stats
        use_combo: Include combo stats (exclusive with trainer+jockey)
        
    Returns:
        Dict with:
        - total_modifier: float
        - trainer_modifier: float
        - jockey_modifier: float
        - combo_modifier: float
        - reason: str
    """
    if stats is None:
        return {
            "total_modifier": 0.0,
            "trainer_modifier": 0.0,
            "jockey_modifier": 0.0,
            "combo_modifier": 0.0,
            "reason": "no_historical_stats"
        }
    
    trainer_mod, trainer_reason = 0.0, "not_used"
    jockey_mod, jockey_reason = 0.0, "not_used"
    combo_mod, combo_reason = 0.0, "not_used"
    
    # Combo is exclusive with individual stats
    if use_combo:
        combo_mod, combo_reason = extract_combo_modifier(stats)
        total = combo_mod
        reason = f"combo:{combo_reason}"
    else:
        if use_trainer:
            trainer_mod, trainer_reason = extract_trainer_modifier(stats)
        if use_jockey:
            jockey_mod, jockey_reason = extract_jockey_modifier(stats)
        
        total = trainer_mod + jockey_mod
        reason = f"trainer:{trainer_reason};jockey:{jockey_reason}"
    
    # Final cap (should already be capped, but safety check)
    total = max(-0.05, min(0.05, total))
    
    logger.debug(f"Historical modifier: {total:.4f} ({reason})")
    
    return {
        "total_modifier": total,
        "trainer_modifier": trainer_mod,
        "jockey_modifier": jockey_mod,
        "combo_modifier": combo_mod,
        "reason": reason
    }


def fetch_historical_stats(
    trainer: str,
    jockey: str,
    track: str,
    distance_meters: int,
    surface: str,
    recency_days: int = 365
) -> Optional[HistoricalStats]:
    """
    Fetch historical stats from database.
    
    This is a stub - actual implementation would query Supabase.
    
    Args:
        trainer: Trainer name
        jockey: Jockey name
        track: Track code
        distance_meters: Race distance
        surface: Surface type (AW/Turf)
        recency_days: Lookback window
        
    Returns:
        HistoricalStats or None
    """
    # TODO: Implement actual database query
    # For now, return None (no stats available)
    logger.warning(f"Historical stats fetch not implemented for {trainer}/{jockey} at {track}")
    return None


def validate_stats(stats: HistoricalStats) -> bool:
    """
    Validate historical stats for sanity.
    
    Args:
        stats: HistoricalStats
        
    Returns:
        True if valid, False otherwise
    """
    # Win rates must be in [0, 1]
    if not (0.0 <= stats.trainer_win_rate <= 1.0):
        logger.error(f"Invalid trainer win rate: {stats.trainer_win_rate}")
        return False
    
    if not (0.0 <= stats.jockey_win_rate <= 1.0):
        logger.error(f"Invalid jockey win rate: {stats.jockey_win_rate}")
        return False
    
    if not (0.0 <= stats.combo_win_rate <= 1.0):
        logger.error(f"Invalid combo win rate: {stats.combo_win_rate}")
        return False
    
    # Sample sizes must be non-negative
    if stats.trainer_sample_size < 0 or stats.jockey_sample_size < 0 or stats.combo_sample_size < 0:
        logger.error(f"Negative sample sizes: T={stats.trainer_sample_size}, J={stats.jockey_sample_size}, C={stats.combo_sample_size}")
        return False
    
    return True
