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
    
    Measures inequality in probability distribution.
    Range: 0.0 (perfect equality) to 1.0 (perfect inequality)
    
    Args:
        implied_probs: List of implied probabilities
        
    Returns:
        Gini coefficient (0.0-1.0)
    """
    if not implied_probs or len(implied_probs) < 2:
        return 0.0
    
    # Sort probabilities
    sorted_probs = sorted(implied_probs)
    n = len(sorted_probs)
    
    # Calculate Gini
    cumsum = 0.0
    for i, prob in enumerate(sorted_probs):
        cumsum += (2 * (i + 1) - n - 1) * prob
    
    total = sum(sorted_probs)
    if total == 0:
        return 0.0
    
    gini = cumsum / (n * total)
    
    return max(0.0, min(1.0, gini))


def calculate_chaos_level(runners: List[Dict]) -> float:
    """
    Calculate chaos level from runners list.
    
    Args:
        runners: List of runner dicts with odds_decimal field
        
    Returns:
        Chaos level (0.0-1.0)
    """
    odds_list = [r.get('odds_decimal', 10.0) for r in runners if r.get('odds_decimal', 0) > 0]
    return calculate_chaos(odds_list, len(odds_list))


def calculate_chaos(odds_list: List[float], field_size: int) -> float:
    """
    Calculate chaos level from odds distribution.
    
    LIVE-ONLY v1 (no history required):
    - Calculate HHI (concentration)
    - Calculate Gini (inequality)
    - Factor in field size
    
    Chaos interpretation:
    - Low HHI + High Gini + Large field = HIGH CHAOS
    - High HHI + Low Gini + Small field = LOW CHAOS
    
    Args:
        odds_list: List of decimal odds
        field_size: Number of runners
        
    Returns:
        Chaos level (0.0-1.0)
    """
    if not odds_list or field_size <= 0:
        logger.warning("Invalid input, returning default chaos 0.5")
        return 0.5
    
    # Single runner = no chaos possible
    if field_size == 1:
        return 0.0
    
    # Convert odds to implied probabilities
    implied_probs = [1.0 / odds for odds in odds_list]
    
    # Calculate metrics
    hhi = calculate_hhi(implied_probs)
    gini = calculate_gini(implied_probs)
    
    # Chaos formula:
    # - Low HHI (competitive) = more chaos
    # - High Gini (unequal) = LESS chaos (strong favorite)
    # - Large field = more chaos
    
    # Normalize field size (typical range 5-20 runners)
    field_factor = min(1.0, (field_size - 5) / 15.0)  # 0.0 at 5 runners, 1.0 at 20+
    
    # Invert HHI (lower concentration = more chaos)
    hhi_chaos = 1.0 - hhi
    
    # Invert Gini (higher inequality = LESS chaos, strong favorite)
    gini_chaos = 1.0 - gini
    
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
    Calculate manipulation risk from odds movements.
    
    Phase 1: STUB - returns 0.0 (no historical data)
    Phase 2: Will use odds history to detect suspicious movements
    
    Args:
        runners: List of runner dicts
        
    Returns:
        Manipulation risk (0.0-1.0)
    """
    logger.debug("Manipulation risk calculation not implemented (Phase 1)")
    return 0.0
