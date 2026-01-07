"""
VÉLØ Phase 1: Parse Quality Metadata
Quality calculation and validation logic for parsed racing data

Date: 2026-01-07
"""

from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)


def calculate_runner_confidence(runner_data: dict) -> Tuple[float, List[str], str]:
    """
    Calculate confidence score for a single runner
    
    Args:
        runner_data: Dictionary containing runner information
    
    Returns:
        Tuple of (confidence, flags, extraction_method)
        - confidence: float 0.0-1.0 (1.0 = perfect extraction)
        - flags: List of quality issue strings
        - extraction_method: "table" | "text" | "ocr" | "fallback"
    """
    confidence = 1.0
    flags = []
    method = "table"  # Default assumption
    
    # Penalties for missing/poor data
    if not runner_data.get("horse_name"):
        confidence -= 0.5
        flags.append("missing_horse_name")
    
    if not runner_data.get("odds") and runner_data.get("odds") != 0:
        confidence -= 0.3
        flags.append("missing_odds")
    elif runner_data.get("odds") == 0:
        confidence -= 0.3
        flags.append("missing_odds")
    
    if not runner_data.get("jockey"):
        confidence -= 0.1
        flags.append("missing_jockey")
    
    # Check for fuzzy/estimated data (if applicable)
    if runner_data.get("odds_estimated"):
        confidence -= 0.2
        flags.append("estimated_odds")
        method = "fallback"
    
    # Clamp to 0.0-1.0
    confidence = max(0.0, min(1.0, confidence))
    
    return confidence, flags, method


def calculate_race_quality(race_data: dict, runners: List[dict]) -> Tuple[float, float, List[str]]:
    """
    Calculate aggregate quality for a race
    
    Args:
        race_data: Dictionary containing race information
        runners: List of runner dictionaries with confidence scores
    
    Returns:
        Tuple of (parse_confidence, quality_score, flags)
        - parse_confidence: Average of runner confidences (0.0-1.0)
        - quality_score: Overall quality metric (0.0-1.0)
        - flags: List of race-level quality issues
    """
    if not runners:
        return 0.0, 0.0, ["no_runners"]
    
    # Average runner confidence
    parse_confidence = sum(r.get("confidence", 0.0) for r in runners) / len(runners)
    
    # Start with parse confidence
    quality_score = parse_confidence
    flags = []
    
    # Race-level penalties
    if not race_data.get("course"):
        quality_score -= 0.2
        flags.append("missing_course")
    
    if not race_data.get("distance"):
        quality_score -= 0.1
        flags.append("missing_distance")
    
    # Runner count sanity check
    runner_count = len(runners)
    if runner_count < 4:
        quality_score -= 0.2
        flags.append("too_few_runners")
    elif runner_count > 30:
        quality_score -= 0.1
        flags.append("too_many_runners")
    
    # Check for duplicate names
    names = [r.get("horse_name") for r in runners if r.get("horse_name")]
    if len(names) != len(set(names)):
        quality_score -= 0.3
        flags.append("duplicate_horse_names")
    
    # Clamp to 0.0-1.0
    quality_score = max(0.0, min(1.0, quality_score))
    
    return parse_confidence, quality_score, flags
