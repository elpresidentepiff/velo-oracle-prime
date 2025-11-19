"""
VÉLØ Oracle - Stability Index
Market stability and confidence scoring
"""
from typing import Dict, Any, List
import logging
import numpy as np

logger = logging.getLogger(__name__)


def compute_stability_index(
    runners: List[Dict],
    race: Dict,
    narrative: Dict = None
) -> Dict[str, Any]:
    """
    Compute Market Stability Score (0-1)
    
    Reverse indicator of volatility:
    - trainer_stability: Consistent trainer performance
    - jockey_strike_patterns: Reliable jockey patterns
    - market_confidence: Market consensus strength
    - narrative_alignment: Narrative consistency
    
    Output:
    - stability_score: float (0-1)
    
    Args:
        runners: List of runners
        race: Race information
        narrative: Optional narrative analysis
        
    Returns:
        Stability analysis dictionary
    """
    logger.info("Computing stability index...")
    
    # Component 1: Trainer stability
    trainer_stability_score = calculate_trainer_stability(runners)
    
    # Component 2: Jockey strike patterns
    jockey_pattern_score = calculate_jockey_patterns(runners)
    
    # Component 3: Market confidence
    market_confidence_score = calculate_market_confidence(runners)
    
    # Component 4: Narrative alignment
    narrative_alignment_score = calculate_narrative_alignment(runners, narrative)
    
    # Weighted combination
    weights = {
        "trainer_stability": 0.30,
        "jockey_patterns": 0.25,
        "market_confidence": 0.30,
        "narrative_alignment": 0.15
    }
    
    stability_score = (
        trainer_stability_score * weights["trainer_stability"] +
        jockey_pattern_score * weights["jockey_patterns"] +
        market_confidence_score * weights["market_confidence"] +
        narrative_alignment_score * weights["narrative_alignment"]
    )
    
    # Clamp to 0-1
    stability_score = max(0.0, min(stability_score, 1.0))
    
    # Categorize
    category = categorize_stability(stability_score)
    
    result = {
        "stability_score": round(stability_score, 3),
        "category": category,
        "components": {
            "trainer_stability": round(trainer_stability_score, 3),
            "jockey_patterns": round(jockey_pattern_score, 3),
            "market_confidence": round(market_confidence_score, 3),
            "narrative_alignment": round(narrative_alignment_score, 3)
        },
        "description": get_stability_description(category)
    }
    
    logger.info(f"✅ Stability index: {stability_score:.3f} ({category})")
    
    return result


def calculate_trainer_stability(runners: List[Dict]) -> float:
    """Calculate trainer stability score (0-1)"""
    
    if not runners:
        return 0.5
    
    # Extract trainer strike rates
    trainer_srs = []
    
    for runner in runners:
        trainer = runner.get("trainer", "")
        
        # Stub: Would look up actual trainer stats
        # For now, use heuristic based on trainer name presence
        if trainer:
            # Assume established trainers have higher stability
            trainer_srs.append(0.7)
        else:
            trainer_srs.append(0.3)
    
    if not trainer_srs:
        return 0.5
    
    # High average SR = high stability
    avg_sr = sum(trainer_srs) / len(trainer_srs)
    
    # Low variance = high stability
    variance = np.var(trainer_srs) if len(trainer_srs) > 1 else 0.0
    
    stability = avg_sr * (1 - variance)
    
    return min(max(stability, 0.0), 1.0)


def calculate_jockey_patterns(runners: List[Dict]) -> float:
    """Calculate jockey pattern reliability (0-1)"""
    
    if not runners:
        return 0.5
    
    # Extract jockey information
    jockey_scores = []
    
    for runner in runners:
        jockey = runner.get("jockey", "")
        
        # Stub: Would analyze jockey riding patterns
        # For now, use heuristic
        if jockey:
            jockey_scores.append(0.65)
        else:
            jockey_scores.append(0.35)
    
    if not jockey_scores:
        return 0.5
    
    avg_score = sum(jockey_scores) / len(jockey_scores)
    
    return avg_score


def calculate_market_confidence(runners: List[Dict]) -> float:
    """Calculate market confidence level (0-1)"""
    
    if not runners:
        return 0.5
    
    # Extract odds
    odds_list = [r.get("odds", 10.0) for r in runners]
    
    if len(odds_list) < 2:
        return 0.5
    
    # Market confidence indicators:
    # 1. Clear favorite (low odds)
    min_odds = min(odds_list)
    has_clear_favorite = min_odds < 3.0
    
    # 2. Odds distribution (not too flat)
    odds_range = max(odds_list) - min_odds
    good_distribution = odds_range > 5.0
    
    # 3. Not too many short-priced runners
    short_priced_count = sum(1 for o in odds_list if o < 5.0)
    not_too_compressed = short_priced_count <= len(odds_list) * 0.4
    
    # Calculate confidence
    confidence = 0.0
    
    if has_clear_favorite:
        confidence += 0.4
    
    if good_distribution:
        confidence += 0.3
    
    if not_too_compressed:
        confidence += 0.3
    
    return confidence


def calculate_narrative_alignment(runners: List[Dict], narrative: Dict = None) -> float:
    """Calculate narrative alignment score (0-1)"""
    
    if not narrative:
        return 0.5  # Neutral if no narrative
    
    # Check narrative confidence
    narrative_confidence = narrative.get("confidence", 0.0)
    
    # Check disruption risk (inverse)
    disruption_risk = narrative.get("disruption_risk", 0.5)
    
    # High narrative confidence + low disruption = high alignment
    alignment = narrative_confidence * (1 - disruption_risk)
    
    return alignment


def categorize_stability(score: float) -> str:
    """Categorize stability score"""
    
    if score >= 0.75:
        return "VERY_STABLE"
    elif score >= 0.55:
        return "STABLE"
    elif score >= 0.35:
        return "MODERATE"
    else:
        return "UNSTABLE"


def get_stability_description(category: str) -> str:
    """Get description for stability category"""
    
    descriptions = {
        "VERY_STABLE": "Highly stable market with strong confidence",
        "STABLE": "Stable market conditions with good confidence",
        "MODERATE": "Moderate stability, some uncertainty present",
        "UNSTABLE": "Unstable market with low confidence"
    }
    
    return descriptions.get(category, "Unknown stability level")
