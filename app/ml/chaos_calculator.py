"""
VELO Chaos Calculator v1 (Live-Only)

Calculates chaos level from odds distribution using:
- HHI (Herfindahl-Hirschman Index) - market concentration
- Gini coefficient - inequality measure
- Field size - more runners = more chaos

NO HISTORICAL DATA REQUIRED - single snapshot only.

Author: VELO Team
Version: 1.0 (Phase 1)
Date: December 21, 2025
"""

from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def calculate_hhi(implied_probs: List[float]) -> float:
    """
    Calculate Herfindahl-Hirschman Index.
    
    HHI = sum of squared market shares
    Range: 1/n (perfect competition) to 1.0 (monopoly)
    
    Args:
        implied_probs: List of implied probabilities (sum to ~1.0)
        
    Returns:
        HHI score (0.0-1.0)
    """
    if not implied_probs:
        return 0.5
    
    # Normalize to ensure sum = 1.0
    total = sum(implied_probs)
    if total == 0:
        return 0.5
    
    normalized = [p / total for p in implied_probs]
    
    # Sum of squares
    hhi = sum(p * p for p in normalized)
    
    return hhi


def calculate_gini(implied_probs: List[float]) -> float:
    """
    Calculate Gini coefficient.
    
    Gini = measure of inequality
    Range: 0.0 (perfect equality) to 1.0 (perfect inequality)
    
    Args:
        implied_probs: List of implied probabilities
        
    Returns:
        Gini coefficient (0.0-1.0)
    """
    if not implied_probs or len(implied_probs) < 2:
        return 0.5
    
    # Sort ascending
    sorted_probs = sorted(implied_probs)
    n = len(sorted_probs)
    
    # Calculate Gini using formula:
    # G = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
    cumsum = sum((i + 1) * x for i, x in enumerate(sorted_probs))
    total = sum(sorted_probs)
    
    if total == 0:
        return 0.5
    
    gini = (2.0 * cumsum) / (n * total) - (n + 1.0) / n
    
    return max(0.0, min(1.0, gini))


def calculate_chaos_level(runners: List[Dict]) -> float:
    """
    Calculate chaos level from odds distribution.
    
    LIVE-ONLY v1 (no history required):
    - Extract odds from runners
    - Calculate HHI (concentration)
    - Calculate Gini (inequality)
    - Factor in field size
    
    Chaos interpretation:
    - Low HHI + High Gini + Large field = HIGH CHAOS
    - High HHI + Low Gini + Small field = LOW CHAOS
    
    Args:
        runners: List of runner dicts with 'odds_decimal'
        
    Returns:
        Chaos level (0.0-1.0)
    """
    if not runners:
        logger.warning("No runners provided, returning default chaos 0.5")
        return 0.5
    
    # Extract odds
    odds_list = []
    for r in runners:
        odds = r.get('odds_decimal', 10.0)
        if odds > 0:
            odds_list.append(odds)
    
    if not odds_list:
        logger.warning("No valid odds found, returning default chaos 0.5")
        return 0.5
    
    # Convert odds to implied probabilities
    implied_probs = [1.0 / odds for odds in odds_list]
    
    # Calculate metrics
    hhi = calculate_hhi(implied_probs)
    gini = calculate_gini(implied_probs)
    field_size = len(odds_list)
    
    # Chaos formula:
    # - Low HHI (competitive) = more chaos
    # - High Gini (unequal) = more chaos
    # - Large field = more chaos
    
    # Normalize field size (typical range 5-20 runners)
    field_factor = min(1.0, (field_size - 5) / 15.0)  # 0.0 at 5 runners, 1.0 at 20+
    
    # Invert HHI (lower concentration = more chaos)
    hhi_chaos = 1.0 - hhi
    
    # Gini directly contributes to chaos (higher inequality = more chaos)
    gini_chaos = gini
    
    # Weighted combination
    chaos = (
        0.4 * hhi_chaos +      # Market concentration (40%)
        0.3 * gini_chaos +     # Inequality (30%)
        0.3 * field_factor     # Field size (30%)
    )
    
    # Clamp to [0.0, 1.0]
    chaos = max(0.0, min(1.0, chaos))
    
    logger.info(f"Chaos calculation: HHI={hhi:.3f}, Gini={gini:.3f}, Field={field_size}, Chaos={chaos:.3f}")
    
    return chaos


def calculate_manipulation_risk(runners: List[Dict]) -> float:
    """
    Calculate manipulation risk from odds distribution.
    
    LIVE-ONLY v1 (no time-series required):
    - Detect odds gaps (large jumps between runners)
    - Detect extreme favorites (very short odds)
    - Detect suspicious patterns
    
    Args:
        runners: List of runner dicts with 'odds_decimal'
        
    Returns:
        Manipulation risk (0.0-1.0)
    """
    if not runners or len(runners) < 3:
        return 0.3  # Default moderate risk
    
    # Extract and sort odds
    odds_list = sorted([r.get('odds_decimal', 10.0) for r in runners if r.get('odds_decimal', 0) > 0])
    
    if len(odds_list) < 3:
        return 0.3
    
    # Check for extreme favorite (odds < 1.5)
    extreme_fav = odds_list[0] < 1.5
    
    # Check for large gaps (ratio > 2.0 between consecutive runners)
    large_gaps = sum(1 for i in range(len(odds_list) - 1) if odds_list[i + 1] / odds_list[i] > 2.0)
    gap_ratio = large_gaps / max(1, len(odds_list) - 1)
    
    # Check for very long outsiders (odds > 50.0)
    long_outsiders = sum(1 for odds in odds_list if odds > 50.0)
    outsider_ratio = long_outsiders / len(odds_list)
    
    # Manipulation risk formula
    risk = (
        0.3 * (1.0 if extreme_fav else 0.0) +     # Extreme favorite
        0.4 * gap_ratio +                          # Large odds gaps
        0.3 * outsider_ratio                       # Long outsiders
    )
    
    # Clamp to [0.0, 1.0]
    risk = max(0.0, min(1.0, risk))
    
    logger.info(f"Manipulation risk: ExtremeFav={extreme_fav}, Gaps={gap_ratio:.2f}, Risk={risk:.3f}")
    
    return risk


if __name__ == "__main__":
    # Test with example data
    test_runners = [
        {'runner_id': 'r1', 'odds_decimal': 1.44},  # Strong favorite
        {'runner_id': 'r2', 'odds_decimal': 3.75},
        {'runner_id': 'r3', 'odds_decimal': 9.0},
        {'runner_id': 'r4', 'odds_decimal': 19.0},
        {'runner_id': 'r5', 'odds_decimal': 29.0},
        {'runner_id': 'r6', 'odds_decimal': 34.0},
    ]
    
    chaos = calculate_chaos_level(test_runners)
    manip = calculate_manipulation_risk(test_runners)
    
    print(f"Chaos: {chaos:.3f}")
    print(f"Manipulation Risk: {manip:.3f}")
