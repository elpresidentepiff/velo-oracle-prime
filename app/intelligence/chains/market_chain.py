"""
VÉLØ Oracle - Market Chain
Market manipulation and anomaly detection pipeline
"""
import time
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


async def run_market_chain(race: Dict[str, Any], odds_history: List[Dict]) -> Dict[str, Any]:
    """
    Execute market manipulation detection chain
    
    Pipeline:
    1. Analyze odds movements
    2. Detect spoofing
    3. Detect echo moves
    4. Detect stop-loss wipes
    5. Detect multi-venue sync
    6. Output risk score (0-100)
    
    Returns:
        Market manipulation analysis with risk score
    """
    start_time = time.time()
    
    try:
        # Step 1: Analyze odds movements
        movements = await analyze_odds_movements(odds_history)
        
        # Step 2-5: Run detection algorithms
        spoofing = await detect_spoofing(odds_history, movements)
        echo = await detect_echo_moves(odds_history, movements)
        stoploss = await detect_stoploss_wipes(odds_history, movements)
        sync = await detect_multi_venue_sync(odds_history)
        
        # Step 6: Calculate risk score
        risk_score = calculate_market_risk_score(spoofing, echo, stoploss, sync)
        
        execution_time = (time.time() - start_time) * 1000
        
        return {
            "status": "success",
            "signals": {
                "spoofing": spoofing,
                "echo_moves": echo,
                "stoploss_wipes": stoploss,
                "multi_venue_sync": sync
            },
            "risk_score": risk_score,
            "risk_category": categorize_risk(risk_score),
            "confidence_scores": {
                "spoofing": spoofing.get("confidence", 0.0),
                "echo": echo.get("confidence", 0.0),
                "stoploss": stoploss.get("confidence", 0.0),
                "sync": sync.get("confidence", 0.0)
            },
            "execution_duration_ms": round(execution_time, 2),
            "chain": "market"
        }
        
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Market chain failed: {e}")
        
        return {
            "status": "error",
            "error": str(e),
            "execution_duration_ms": round(execution_time, 2),
            "chain": "market"
        }


async def analyze_odds_movements(odds_history: List[Dict]) -> Dict[str, Any]:
    """Analyze odds movement patterns"""
    
    if not odds_history:
        return {"movement_count": 0, "volatility": 0.0}
    
    movements = []
    for entry in odds_history:
        if "odds" in entry and "timestamp" in entry:
            movements.append({
                "odds": entry["odds"],
                "timestamp": entry["timestamp"],
                "volume": entry.get("volume", 0)
            })
    
    # Calculate volatility
    if len(movements) > 1:
        changes = [abs(movements[i]["odds"] - movements[i-1]["odds"]) 
                   for i in range(1, len(movements))]
        volatility = sum(changes) / len(changes)
    else:
        volatility = 0.0
    
    return {
        "movement_count": len(movements),
        "volatility": volatility,
        "movements": movements
    }


async def detect_spoofing(odds_history: List[Dict], movements: Dict) -> Dict[str, Any]:
    """
    Detect spoofing (fake orders to manipulate odds)
    
    Spoofing indicators:
    - Large volume at specific odds
    - Rapid withdrawal of orders
    - Repeated pattern
    """
    
    if movements["movement_count"] < 3:
        return {"detected": False, "confidence": 0.0, "pattern": None}
    
    # Look for rapid back-and-forth
    movement_list = movements.get("movements", [])
    rapid_reversals = 0
    
    for i in range(2, len(movement_list)):
        prev_change = movement_list[i-1]["odds"] - movement_list[i-2]["odds"]
        curr_change = movement_list[i]["odds"] - movement_list[i-1]["odds"]
        
        # Reversal detected
        if (prev_change > 0 and curr_change < 0) or (prev_change < 0 and curr_change > 0):
            rapid_reversals += 1
    
    spoofing_score = min(rapid_reversals / 5.0, 1.0)  # Normalize to [0, 1]
    
    return {
        "detected": spoofing_score > 0.3,
        "confidence": spoofing_score,
        "pattern": "rapid_reversal" if spoofing_score > 0.3 else None,
        "reversal_count": rapid_reversals
    }


async def detect_echo_moves(odds_history: List[Dict], movements: Dict) -> Dict[str, Any]:
    """
    Detect echo moves (coordinated movements across multiple runners)
    
    Echo indicators:
    - Similar timing of movements
    - Correlated direction
    """
    
    # Simplified: Check for synchronized movements
    # In production, would compare across multiple runners
    
    volatility = movements.get("volatility", 0.0)
    
    # High volatility suggests coordinated activity
    echo_detected = volatility > 1.5
    
    return {
        "detected": echo_detected,
        "confidence": min(volatility / 3.0, 1.0),
        "pattern": "coordinated" if echo_detected else None
    }


async def detect_stoploss_wipes(odds_history: List[Dict], movements: Dict) -> Dict[str, Any]:
    """
    Detect stop-loss wipes (sharp moves to trigger stop losses)
    
    Indicators:
    - Sudden large movement
    - Followed by reversion
    - High volume spike
    """
    
    movement_list = movements.get("movements", [])
    
    if len(movement_list) < 3:
        return {"detected": False, "confidence": 0.0, "pattern": None}
    
    # Look for spike-and-revert pattern
    max_spike = 0.0
    
    for i in range(1, len(movement_list) - 1):
        spike = abs(movement_list[i]["odds"] - movement_list[i-1]["odds"])
        revert = abs(movement_list[i+1]["odds"] - movement_list[i]["odds"])
        
        # Spike followed by reversion
        if spike > 1.0 and revert > 0.5:
            max_spike = max(max_spike, spike)
    
    stoploss_score = min(max_spike / 3.0, 1.0)
    
    return {
        "detected": stoploss_score > 0.4,
        "confidence": stoploss_score,
        "pattern": "spike_revert" if stoploss_score > 0.4 else None,
        "max_spike": max_spike
    }


async def detect_multi_venue_sync(odds_history: List[Dict]) -> Dict[str, Any]:
    """
    Detect multi-venue synchronization (arbitrage or manipulation)
    
    Indicators:
    - Odds converging across venues
    - Synchronized timing
    """
    
    # Stub: Would require multi-venue data
    # For now, return low confidence
    
    return {
        "detected": False,
        "confidence": 0.0,
        "pattern": None,
        "venues_analyzed": 1
    }


def calculate_market_risk_score(
    spoofing: Dict,
    echo: Dict,
    stoploss: Dict,
    sync: Dict
) -> int:
    """
    Calculate overall market risk score (0-100)
    
    Weighted combination of all detection signals
    """
    
    weights = {
        "spoofing": 0.3,
        "echo": 0.25,
        "stoploss": 0.3,
        "sync": 0.15
    }
    
    score = (
        spoofing.get("confidence", 0.0) * weights["spoofing"] +
        echo.get("confidence", 0.0) * weights["echo"] +
        stoploss.get("confidence", 0.0) * weights["stoploss"] +
        sync.get("confidence", 0.0) * weights["sync"]
    )
    
    # Scale to 0-100
    return int(score * 100)


def categorize_risk(risk_score: int) -> str:
    """Categorize risk score into bands"""
    
    if risk_score >= 75:
        return "CRITICAL"
    elif risk_score >= 50:
        return "HIGH"
    elif risk_score >= 25:
        return "MEDIUM"
    else:
        return "LOW"
