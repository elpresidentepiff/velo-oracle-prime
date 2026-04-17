"""
VÉLØ Oracle - Manipulation Radar
Comprehensive market manipulation risk assessment
"""
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def compute_manipulation_radar(
    market_chain_result: Dict,
    volatility_index: Dict,
    stability_index: Dict,
    odds_movements: List[Dict] = None
) -> Dict[str, Any]:
    """
    Compute comprehensive Manipulation Risk Radar (0-100)
    
    Merges:
    - Market chain manipulation signals
    - Observatory volatility signals
    - Stability indicators
    - Additional pattern detection
    
    Output:
    - risk_radar: int (0-100)
    - risk_category: SAFE | CAUTION | WARNING | CRITICAL
    - detected_patterns: List of manipulation patterns
    
    Args:
        market_chain_result: Result from market chain
        volatility_index: Volatility index result
        stability_index: Stability index result
        odds_movements: Optional odds movements
        
    Returns:
        Manipulation radar dictionary
    """
    logger.info("Computing manipulation radar...")
    
    # Extract component scores
    market_risk = market_chain_result.get("risk_score", 0) / 100.0  # Normalize to 0-1
    volatility_score = volatility_index.get("volatility_score", 0) / 100.0
    stability_score = stability_index.get("stability_score", 0.5)
    
    # Instability contributes to manipulation risk
    instability_score = 1.0 - stability_score
    
    # Weighted combination
    weights = {
        "market_signals": 0.40,
        "volatility": 0.30,
        "instability": 0.30
    }
    
    risk_radar = int(
        (market_risk * weights["market_signals"] +
         volatility_score * weights["volatility"] +
         instability_score * weights["instability"]) * 100
    )
    
    # Clamp to 0-100
    risk_radar = max(0, min(risk_radar, 100))
    
    # Detect patterns
    detected_patterns = detect_manipulation_patterns(
        market_chain_result,
        volatility_index,
        stability_index
    )
    
    # Categorize risk
    risk_category = categorize_manipulation_risk(risk_radar)
    
    # Generate recommendation
    recommendation = generate_recommendation(risk_radar, detected_patterns)
    
    result = {
        "risk_radar": risk_radar,
        "risk_category": risk_category,
        "detected_patterns": detected_patterns,
        "components": {
            "market_signals": round(market_risk, 3),
            "volatility": round(volatility_score, 3),
            "instability": round(instability_score, 3)
        },
        "recommendation": recommendation,
        "description": get_risk_description(risk_category)
    }
    
    logger.info(f"✅ Manipulation radar: {risk_radar} ({risk_category})")
    
    return result


def detect_manipulation_patterns(
    market_chain: Dict,
    volatility: Dict,
    stability: Dict
) -> List[str]:
    """Detect specific manipulation patterns"""
    
    patterns = []
    
    # Extract signals
    market_signals = market_chain.get("signals", {})
    volatility_category = volatility.get("category", "MEDIUM")
    stability_category = stability.get("category", "MODERATE")
    
    # Pattern 1: Spoofing detected
    if market_signals.get("spoofing", {}).get("detected"):
        patterns.append("spoofing")
    
    # Pattern 2: Echo moves detected
    if market_signals.get("echo_moves", {}).get("detected"):
        patterns.append("echo_moves")
    
    # Pattern 3: Stop-loss wipes detected
    if market_signals.get("stoploss_wipes", {}).get("detected"):
        patterns.append("stoploss_wipes")
    
    # Pattern 4: High volatility + low stability
    if volatility_category in ["HIGH", "CHAOS"] and stability_category in ["UNSTABLE", "MODERATE"]:
        patterns.append("chaotic_conditions")
    
    # Pattern 5: Multi-venue sync
    if market_signals.get("multi_venue_sync", {}).get("detected"):
        patterns.append("multi_venue_sync")
    
    return patterns


def categorize_manipulation_risk(risk_radar: int) -> str:
    """Categorize manipulation risk level"""
    
    if risk_radar >= 75:
        return "CRITICAL"
    elif risk_radar >= 50:
        return "WARNING"
    elif risk_radar >= 25:
        return "CAUTION"
    else:
        return "SAFE"


def generate_recommendation(risk_radar: int, patterns: List[str]) -> str:
    """Generate actionable recommendation"""
    
    if risk_radar >= 75:
        return "AVOID - Critical manipulation risk detected. Do not bet on this race."
    
    elif risk_radar >= 50:
        if "spoofing" in patterns or "stoploss_wipes" in patterns:
            return "HIGH CAUTION - Significant manipulation signals. Reduce stake sizes or avoid."
        else:
            return "CAUTION - Elevated risk. Proceed with extreme caution."
    
    elif risk_radar >= 25:
        if patterns:
            return f"MONITOR - Some manipulation patterns detected: {', '.join(patterns)}. Watch closely."
        else:
            return "LOW RISK - Minor concerns. Normal betting acceptable with monitoring."
    
    else:
        return "SAFE - Low manipulation risk. Normal betting conditions."


def get_risk_description(category: str) -> str:
    """Get description for risk category"""
    
    descriptions = {
        "SAFE": "Low manipulation risk, market appears clean",
        "CAUTION": "Moderate manipulation risk, some suspicious activity",
        "WARNING": "High manipulation risk, significant suspicious patterns",
        "CRITICAL": "Critical manipulation risk, avoid this market"
    }
    
    return descriptions.get(category, "Unknown risk level")


def calculate_confidence_score(
    market_chain: Dict,
    volatility: Dict,
    stability: Dict
) -> float:
    """Calculate confidence in manipulation radar assessment (0-1)"""
    
    # Base confidence on data quality and signal strength
    market_confidence = market_chain.get("confidence_scores", {})
    
    # Average confidence across all signals
    confidences = [
        market_confidence.get("spoofing", 0.0),
        market_confidence.get("echo", 0.0),
        market_confidence.get("stoploss", 0.0),
        market_confidence.get("sync", 0.0)
    ]
    
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
    
    return avg_confidence
