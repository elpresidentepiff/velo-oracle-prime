"""
VELO Form Parser v1 (Phase 2A)

Parses form strings from racing data (e.g., "332-2", "1-421", "0000")
and extracts performance metrics.

Form string format examples:
- "332-2" = 3rd, 3rd, 2nd, [gap], 2nd (most recent on left)
- "1-421" = 1st, [gap], 4th, 2nd, 1st
- "0" = Did not finish/place
- "-" = No form data

Author: VELO Team
Version: 1.0 (Phase 2A)
Date: December 21, 2025
"""

from typing import List, Dict, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)


class FormParseError(Exception):
    """Raised when form string cannot be parsed."""
    pass


def parse_form_string(form_str: str) -> List[Optional[int]]:
    """
    Parse form string into list of positions (most recent first).
    
    Args:
        form_str: Form string (e.g., "332-2", "1-421")
        
    Returns:
        List of positions (None for gaps/invalid)
        
    Examples:
        "332-2" -> [3, 3, 2, None, 2]
        "1-421" -> [1, None, 4, 2, 1]
        "0000" -> [None, None, None, None]
        "" -> []
    """
    if not form_str or form_str == "-":
        return []
    
    positions = []
    for char in form_str:
        if char == "-":
            positions.append(None)  # Gap (e.g., season break)
        elif char == "0":
            positions.append(None)  # DNF/unplaced
        elif char.isdigit():
            positions.append(int(char))
        else:
            # Ignore non-numeric characters (e.g., letters for special codes)
            logger.debug(f"Ignoring non-numeric character '{char}' in form string")
    
    return positions


def calculate_consistency_score(positions: List[Optional[int]]) -> float:
    """
    Calculate consistency score from positions.
    
    Consistency = how often runner finishes in similar positions.
    Range: 0.0 (inconsistent) to 1.0 (very consistent)
    
    Args:
        positions: List of positions (None for gaps/DNF)
        
    Returns:
        Consistency score (0.0-1.0)
    """
    if not positions:
        return 0.0
    
    # Filter out None values
    valid_positions = [p for p in positions if p is not None]
    
    if len(valid_positions) < 2:
        return 0.0
    
    # Calculate standard deviation of positions
    mean_pos = sum(valid_positions) / len(valid_positions)
    variance = sum((p - mean_pos) ** 2 for p in valid_positions) / len(valid_positions)
    std_dev = variance ** 0.5
    
    # Normalize to 0-1 range (lower std_dev = higher consistency)
    # Assume max std_dev of 3 (e.g., positions ranging from 1 to 7)
    consistency = max(0.0, 1.0 - (std_dev / 3.0))
    
    return consistency


def calculate_recent_form_score(positions: List[Optional[int]], lookback: int = 3) -> float:
    """
    Calculate recent form score from last N positions.
    
    Score: Lower positions = better score
    Range: 0.0 (poor) to 1.0 (excellent)
    
    Args:
        positions: List of positions (most recent first)
        lookback: Number of recent races to consider
        
    Returns:
        Recent form score (0.0-1.0)
    """
    if not positions:
        return 0.5  # Neutral
    
    # Take last N races
    recent = positions[:lookback]
    
    # Filter out None values
    valid_positions = [p for p in recent if p is not None]
    
    if not valid_positions:
        return 0.5  # Neutral
    
    # Average position (lower is better)
    avg_pos = sum(valid_positions) / len(valid_positions)
    
    # Normalize to 0-1 range (assume positions 1-9)
    # Position 1 = 1.0, Position 9 = 0.0
    score = max(0.0, min(1.0, (10 - avg_pos) / 9.0))
    
    return score


def extract_win_rate(positions: List[Optional[int]]) -> float:
    """
    Calculate win rate (% of races won).
    
    Args:
        positions: List of positions
        
    Returns:
        Win rate (0.0-1.0)
    """
    if not positions:
        return 0.0
    
    valid_positions = [p for p in positions if p is not None]
    
    if not valid_positions:
        return 0.0
    
    wins = sum(1 for p in valid_positions if p == 1)
    win_rate = wins / len(valid_positions)
    
    return win_rate


def extract_place_rate(positions: List[Optional[int]], place_threshold: int = 3) -> float:
    """
    Calculate place rate (% of races placed in top N).
    
    Args:
        positions: List of positions
        place_threshold: Top N positions to count as "placed"
        
    Returns:
        Place rate (0.0-1.0)
    """
    if not positions:
        return 0.0
    
    valid_positions = [p for p in positions if p is not None]
    
    if not valid_positions:
        return 0.0
    
    places = sum(1 for p in valid_positions if p <= place_threshold)
    place_rate = places / len(valid_positions)
    
    return place_rate


def analyze_form(form_str: str) -> Dict[str, float]:
    """
    Full form analysis - parse and extract all metrics.
    
    Args:
        form_str: Form string (e.g., "332-2")
        
    Returns:
        Dict with metrics:
        - consistency: 0.0-1.0
        - recent_form: 0.0-1.0
        - win_rate: 0.0-1.0
        - place_rate: 0.0-1.0
        - valid_races: int
    """
    try:
        positions = parse_form_string(form_str)
        
        valid_positions = [p for p in positions if p is not None]
        
        return {
            "consistency": calculate_consistency_score(positions),
            "recent_form": calculate_recent_form_score(positions),
            "win_rate": extract_win_rate(positions),
            "place_rate": extract_place_rate(positions),
            "valid_races": len(valid_positions)
        }
    except Exception as e:
        logger.error(f"Form analysis failed for '{form_str}': {e}")
        return {
            "consistency": 0.0,
            "recent_form": 0.5,
            "win_rate": 0.0,
            "place_rate": 0.0,
            "valid_races": 0
        }


def classify_stability(consistency: float, valid_races: int) -> str:
    """
    Classify runner stability based on consistency and sample size.
    
    Args:
        consistency: Consistency score (0.0-1.0)
        valid_races: Number of valid races in form
        
    Returns:
        Stability class: "STABLE", "VOLATILE", "INSUFFICIENT_DATA"
    """
    if valid_races < 3:
        return "INSUFFICIENT_DATA"
    
    if consistency >= 0.7:
        return "STABLE"
    elif consistency <= 0.4:
        return "VOLATILE"
    else:
        return "MODERATE"
