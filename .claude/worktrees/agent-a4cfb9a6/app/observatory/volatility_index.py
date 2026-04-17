"""
VÉLØ Oracle - Volatility Index
Race volatility scoring and classification
"""
from typing import Dict, Any, List
import logging
import numpy as np

logger = logging.getLogger(__name__)


def compute_volatility_index(
    odds_movements: List[Dict],
    runners: List[Dict],
    race: Dict
) -> Dict[str, Any]:
    """
    Compute Race Volatility Score (0-100)
    
    Inputs:
    - odds_speed: Rate of odds changes
    - drift_amplitude: Magnitude of odds drifts
    - steam_bursts: Sudden sharp movements
    - sectional_variance: Expected pace variance
    
    Output:
    - volatility_score: int (0-100)
    - category: LOW | MEDIUM | HIGH | CHAOS
    
    Args:
        odds_movements: Historical odds movements
        runners: List of runners
        race: Race information
        
    Returns:
        Volatility analysis dictionary
    """
    logger.info("Computing volatility index...")
    
    # Component 1: Odds speed
    odds_speed_score = calculate_odds_speed(odds_movements)
    
    # Component 2: Drift amplitude
    drift_amplitude_score = calculate_drift_amplitude(odds_movements)
    
    # Component 3: Steam bursts
    steam_burst_score = detect_steam_bursts(odds_movements)
    
    # Component 4: Sectional variance
    sectional_variance_score = calculate_sectional_variance(runners)
    
    # Weighted combination
    weights = {
        "odds_speed": 0.30,
        "drift_amplitude": 0.25,
        "steam_bursts": 0.30,
        "sectional_variance": 0.15
    }
    
    volatility_score = int(
        odds_speed_score * weights["odds_speed"] * 100 +
        drift_amplitude_score * weights["drift_amplitude"] * 100 +
        steam_burst_score * weights["steam_bursts"] * 100 +
        sectional_variance_score * weights["sectional_variance"] * 100
    )
    
    # Clamp to 0-100
    volatility_score = max(0, min(volatility_score, 100))
    
    # Categorize
    category = categorize_volatility(volatility_score)
    
    result = {
        "volatility_score": volatility_score,
        "category": category,
        "components": {
            "odds_speed": round(odds_speed_score, 3),
            "drift_amplitude": round(drift_amplitude_score, 3),
            "steam_bursts": round(steam_burst_score, 3),
            "sectional_variance": round(sectional_variance_score, 3)
        },
        "description": get_volatility_description(category)
    }
    
    logger.info(f"✅ Volatility index: {volatility_score} ({category})")
    
    return result


def calculate_odds_speed(odds_movements: List[Dict]) -> float:
    """Calculate rate of odds changes (0-1)"""
    
    if not odds_movements or len(odds_movements) < 2:
        return 0.0
    
    # Count movements per time window
    total_movements = len(odds_movements)
    
    # Calculate average change magnitude
    changes = []
    for i in range(1, len(odds_movements)):
        if "odds" in odds_movements[i] and "odds" in odds_movements[i-1]:
            change = abs(odds_movements[i]["odds"] - odds_movements[i-1]["odds"])
            changes.append(change)
    
    if not changes:
        return 0.0
    
    avg_change = sum(changes) / len(changes)
    
    # Normalize: high speed = many changes with large magnitude
    speed_score = min((total_movements / 20.0) * (avg_change / 2.0), 1.0)
    
    return speed_score


def calculate_drift_amplitude(odds_movements: List[Dict]) -> float:
    """Calculate magnitude of odds drifts (0-1)"""
    
    if not odds_movements or len(odds_movements) < 2:
        return 0.0
    
    odds_values = [m["odds"] for m in odds_movements if "odds" in m]
    
    if len(odds_values) < 2:
        return 0.0
    
    # Calculate total drift
    initial_odds = odds_values[0]
    final_odds = odds_values[-1]
    
    total_drift = abs(final_odds - initial_odds)
    
    # Normalize by initial odds
    drift_amplitude = min(total_drift / initial_odds, 1.0)
    
    return drift_amplitude


def detect_steam_bursts(odds_movements: List[Dict]) -> float:
    """Detect sudden sharp movements (0-1)"""
    
    if not odds_movements or len(odds_movements) < 2:
        return 0.0
    
    # Look for sharp single-period changes
    max_burst = 0.0
    burst_count = 0
    
    for i in range(1, len(odds_movements)):
        if "odds" in odds_movements[i] and "odds" in odds_movements[i-1]:
            change = abs(odds_movements[i]["odds"] - odds_movements[i-1]["odds"])
            
            # Burst threshold: change > 1.0 odds point
            if change > 1.0:
                burst_count += 1
                max_burst = max(max_burst, change)
    
    # Score based on burst count and magnitude
    burst_score = min((burst_count / 5.0) + (max_burst / 10.0), 1.0)
    
    return burst_score


def calculate_sectional_variance(runners: List[Dict]) -> float:
    """Calculate expected sectional variance (0-1)"""
    
    if not runners:
        return 0.5  # Default medium variance
    
    # Extract sectional times
    sectional_times = []
    
    for runner in runners:
        sectionals = runner.get("sectional_times", {})
        if "last_200m" in sectionals:
            sectional_times.append(sectionals["last_200m"])
    
    if len(sectional_times) < 2:
        return 0.5
    
    # Calculate variance
    variance = np.var(sectional_times)
    
    # Normalize: high variance = high volatility
    variance_score = min(variance / 2.0, 1.0)
    
    return variance_score


def categorize_volatility(score: int) -> str:
    """Categorize volatility score"""
    
    if score >= 75:
        return "CHAOS"
    elif score >= 50:
        return "HIGH"
    elif score >= 25:
        return "MEDIUM"
    else:
        return "LOW"


def get_volatility_description(category: str) -> str:
    """Get description for volatility category"""
    
    descriptions = {
        "LOW": "Stable market with minimal volatility",
        "MEDIUM": "Moderate market volatility, normal fluctuations",
        "HIGH": "Elevated volatility, significant market uncertainty",
        "CHAOS": "Extreme volatility, chaotic market conditions"
    }
    
    return descriptions.get(category, "Unknown volatility level")
