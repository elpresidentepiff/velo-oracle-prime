"""
VÉLØ Oracle - Narrative Chain
Narrative detection and analysis pipeline
"""
import time
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


async def run_narrative_chain(race: Dict[str, Any], odds_movements: List[Dict] = None) -> Dict[str, Any]:
    """
    Execute narrative analysis chain
    
    Pipeline:
    1. Analyze odds movements
    2. Detect primary narrative
    3. Detect secondary bias
    4. Build narrative signature
    
    Returns:
        Narrative analysis with confidence scores
    """
    start_time = time.time()
    
    try:
        # Step 1: Analyze odds
        odds_analysis = await analyze_odds(race, odds_movements)
        
        # Step 2: Detect primary narrative
        primary_narrative = await detect_primary_narrative(race, odds_analysis)
        
        # Step 3: Detect secondary bias
        secondary_bias = await detect_secondary_bias(race, primary_narrative)
        
        # Step 4: Build narrative signature
        signature = await build_narrative_signature(
            race, 
            odds_movements, 
            primary_narrative, 
            secondary_bias
        )
        
        execution_time = (time.time() - start_time) * 1000
        
        return {
            "status": "success",
            "signals": {
                "primary_narrative": primary_narrative,
                "secondary_bias": secondary_bias,
                "signature": signature,
                "odds_analysis": odds_analysis
            },
            "confidence_scores": {
                "primary": primary_narrative.get("confidence", 0.0),
                "secondary": secondary_bias.get("confidence", 0.0),
                "overall": signature.get("confidence", 0.0)
            },
            "execution_duration_ms": round(execution_time, 2),
            "chain": "narrative"
        }
        
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Narrative chain failed: {e}")
        
        return {
            "status": "error",
            "error": str(e),
            "execution_duration_ms": round(execution_time, 2),
            "chain": "narrative"
        }


async def analyze_odds(race: Dict, odds_movements: List[Dict] = None) -> Dict[str, Any]:
    """Analyze odds movements and patterns"""
    
    if not odds_movements:
        return {
            "movement_detected": False,
            "volatility": 0.0,
            "trend": "stable"
        }
    
    # Calculate odds volatility
    volatilities = []
    for movement in odds_movements:
        if "odds_history" in movement:
            odds_list = movement["odds_history"]
            if len(odds_list) > 1:
                changes = [abs(odds_list[i] - odds_list[i-1]) for i in range(1, len(odds_list))]
                volatility = sum(changes) / len(changes) if changes else 0.0
                volatilities.append(volatility)
    
    avg_volatility = sum(volatilities) / len(volatilities) if volatilities else 0.0
    
    return {
        "movement_detected": avg_volatility > 0.5,
        "volatility": avg_volatility,
        "trend": "volatile" if avg_volatility > 1.0 else "stable",
        "runners_moving": len(volatilities)
    }


async def detect_primary_narrative(race: Dict, odds_analysis: Dict) -> Dict[str, Any]:
    """Detect primary market narrative"""
    from app.intelligence.narrative_disruption import detect_market_story
    
    narrative = detect_market_story(race)
    
    # Enhance with odds analysis
    if odds_analysis.get("movement_detected"):
        confidence_boost = 0.1
    else:
        confidence_boost = 0.0
    
    return {
        "type": narrative.get("story"),
        "description": narrative.get("description", ""),
        "confidence": min(narrative.get("confidence", 0.0) + confidence_boost, 1.0),
        "disruption_risk": narrative.get("disruption_risk", 0.0),
        "runners_affected": narrative.get("narrative_runners", [])
    }


async def detect_secondary_bias(race: Dict, primary_narrative: Dict) -> Dict[str, Any]:
    """Detect secondary market biases"""
    
    # Check for common biases
    biases = []
    
    # Favorite bias
    runners = race.get("runners", [])
    if runners:
        favorite_odds = min(r.get("odds", 100) for r in runners)
        if favorite_odds < 2.0:
            biases.append({
                "type": "favorite_bias",
                "strength": 0.7,
                "description": "Market heavily backing favorite"
            })
    
    # Local bias
    if race.get("course") in ["Flemington", "Randwick", "Rosehill"]:
        biases.append({
            "type": "local_bias",
            "strength": 0.5,
            "description": "Major metropolitan track"
        })
    
    # Prize money bias
    if race.get("prize_money", 0) > 1000000:
        biases.append({
            "type": "stakes_bias",
            "strength": 0.6,
            "description": "High-stakes race attracting public attention"
        })
    
    primary_bias = biases[0] if biases else {"type": "none", "strength": 0.0}
    
    return {
        "type": primary_bias.get("type"),
        "strength": primary_bias.get("strength", 0.0),
        "confidence": 0.6 if biases else 0.2,
        "all_biases": biases
    }


async def build_narrative_signature(
    race: Dict,
    odds_movements: List[Dict],
    primary_narrative: Dict,
    secondary_bias: Dict
) -> Dict[str, Any]:
    """Build comprehensive narrative signature"""
    
    # Combine narrative elements
    signature_components = []
    
    if primary_narrative.get("type"):
        signature_components.append(primary_narrative["type"])
    
    if secondary_bias.get("type") and secondary_bias["type"] != "none":
        signature_components.append(secondary_bias["type"])
    
    # Calculate overall confidence
    confidence = (
        primary_narrative.get("confidence", 0.0) * 0.6 +
        secondary_bias.get("confidence", 0.0) * 0.4
    )
    
    # Determine risk level
    disruption_risk = primary_narrative.get("disruption_risk", 0.0)
    
    if disruption_risk > 0.7:
        risk_level = "HIGH"
    elif disruption_risk > 0.4:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    
    return {
        "signature": "_".join(signature_components) if signature_components else "NEUTRAL",
        "components": signature_components,
        "confidence": confidence,
        "risk_level": risk_level,
        "disruption_risk": disruption_risk,
        "actionable": confidence > 0.6 and disruption_risk > 0.3
    }
