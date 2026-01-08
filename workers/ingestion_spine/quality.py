"""
Parse quality calculation and validation logic
Decorates parsed data with confidence scores and flags
"""

from typing import List, Tuple, Dict, Any
from datetime import datetime


def calculate_runner_confidence(runner_data: dict) -> Tuple[float, List[str], str]:
    """
    Calculate confidence score for a single runner
    
    Args:
        runner_data: Raw parsed runner data
    
    Returns:
        (confidence, quality_flags, extraction_method)
        - confidence: 0.0-1.0 (1.0 = perfect)
        - quality_flags: list of issues found
        - extraction_method: "table" | "text" | "ocr" | "fallback"
    """
    confidence = 1.0
    flags = []
    method = "table"  # Default assumption
    
    # Critical field penalties
    if not runner_data.get("horse_name") or not runner_data["horse_name"].strip():
        confidence -= 0.5
        flags.append("missing_horse_name")
    
    if not runner_data.get("odds") or runner_data.get("odds") == 0:
        confidence -= 0.3
        flags.append("missing_odds")
    
    # Optional field penalties (smaller)
    if not runner_data.get("jockey"):
        confidence -= 0.1
        flags.append("missing_jockey")
    
    if not runner_data.get("trainer"):
        confidence -= 0.05
        flags.append("missing_trainer")
    
    if not runner_data.get("weight"):
        confidence -= 0.05
        flags.append("missing_weight")
    
    # Check for estimated/fuzzy data
    if runner_data.get("odds_estimated"):
        confidence -= 0.2
        flags.append("estimated_odds")
        method = "fallback"
    
    if runner_data.get("fuzzy_extraction"):
        confidence -= 0.15
        flags.append("fuzzy_extraction")
        method = "text"
    
    # Sanity checks on odds
    odds = runner_data.get("odds")
    if odds and (odds < 1.0 or odds > 1000):
        confidence -= 0.2
        flags.append("suspicious_odds")
    
    # Clamp to valid range
    confidence = max(0.0, min(1.0, confidence))
    
    return confidence, flags, method


def calculate_race_quality(race_data: dict, runners: List[dict]) -> Tuple[float, float, List[str]]:
    """
    Calculate aggregate quality metrics for a race
    
    Args:
        race_data: Race metadata (course, distance, etc.)
        runners: List of runner dicts (must include 'confidence' field)
    
    Returns:
        (parse_confidence, quality_score, quality_flags)
        - parse_confidence: average runner confidence
        - quality_score: overall quality (0.0-1.0)
        - quality_flags: race-level issues
    """
    if not runners:
        return 0.0, 0.0, ["no_runners"]
    
    # Average runner confidence
    parse_confidence = sum(r.get("confidence", 0.0) for r in runners) / len(runners)
    
    # Start with parse confidence
    quality_score = parse_confidence
    flags = []
    
    # Critical race metadata
    if not race_data.get("course"):
        quality_score -= 0.2
        flags.append("missing_course")
    
    if not race_data.get("distance"):
        quality_score -= 0.1
        flags.append("missing_distance")
    
    if not race_data.get("race_time"):
        quality_score -= 0.05
        flags.append("missing_race_time")
    
    # Runner count sanity checks
    runner_count = len(runners)
    if runner_count < 4:
        quality_score -= 0.2
        flags.append("too_few_runners")
    elif runner_count > 30:
        quality_score -= 0.1
        flags.append("too_many_runners")
    
    # Check for duplicate horse names (data corruption indicator)
    names = [r.get("horse_name", "").strip().lower() for r in runners if r.get("horse_name")]
    if len(names) != len(set(names)):
        quality_score -= 0.3
        flags.append("duplicate_horse_names")
    
    # Check runner quality distribution
    low_confidence_count = sum(1 for r in runners if r.get("confidence", 1.0) < 0.6)
    if low_confidence_count > len(runners) * 0.3:  # >30% low confidence
        quality_score -= 0.15
        flags.append("many_low_confidence_runners")
    
    # Clamp to valid range
    quality_score = max(0.0, min(1.0, quality_score))
    
    return parse_confidence, quality_score, flags


def validate_race(race: dict) -> Dict[str, Any]:
    """
    Apply RIC+ validation rules to categorize a race
    
    Args:
        race: Race dict with quality metadata
    
    Returns:
        {
            "race_id": str,
            "status": "valid" | "needs_review" | "rejected",
            "issues": List[str],
            "quality_score": float
        }
    """
    issues = []
    status = "valid"
    quality_score = race.get("quality_score", 0.0)
    quality_flags = race.get("quality_flags", [])
    
    # HARD REJECTIONS (critical data missing)
    if not race.get("course"):
        issues.append("REJECT: Missing course")
        status = "rejected"
    
    if not race.get("distance"):
        issues.append("REJECT: Missing distance")
        status = "rejected"
    
    runners = race.get("runners", [])
    if len(runners) == 0:
        issues.append("REJECT: No runners")
        status = "rejected"
    
    # Duplicate names = data corruption
    if "duplicate_horse_names" in quality_flags:
        issues.append("REJECT: Duplicate horse names detected")
        status = "rejected"
    
    # NEEDS REVIEW (suspicious but not fatal)
    if status == "valid":  # Only check if not already rejected
        if len(runners) < 4:
            issues.append("FLAG: Unusually few runners (<4)")
            status = "needs_review"
        
        if len(runners) > 30:
            issues.append("FLAG: Unusually many runners (>30)")
            status = "needs_review"
        
        if quality_score < 0.5:
            issues.append("FLAG: Low quality score (<0.5)")
            status = "needs_review"
        
        # Check for too many low-confidence runners
        if "many_low_confidence_runners" in quality_flags:
            issues.append("FLAG: Many runners have low extraction confidence")
            status = "needs_review"
    
    return {
        "race_id": race.get("id", "unknown"),
        "status": status,
        "issues": issues,
        "quality_score": round(quality_score, 3)
    }
