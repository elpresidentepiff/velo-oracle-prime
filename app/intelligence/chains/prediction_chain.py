"""
VÉLØ Oracle - Prediction Chain
Complete prediction pipeline with all intelligence layers
"""
import time
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


async def run_prediction_chain(race: Dict[str, Any], runners: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Execute complete prediction chain
    
    Pipeline:
    1. Load models
    2. Extract features
    3. SQPE scoring
    4. Trainer Intent Engine
    5. Longshot detection
    6. Overlay detection
    7. Risk layer
    8. Narrative analysis
    9. Market manipulation check
    10. Pace analysis
    11. Unify output
    
    Returns:
        Unified prediction output with all signals
    """
    start_time = time.time()
    
    try:
        # Step 1: Load models
        models = await load_models()
        
        # Step 2: Extract features for all runners
        features_list = await extract_features_batch(runners, race)
        
        # Step 3-6: Run model predictions
        predictions = []
        for runner, features in zip(runners, features_list):
            pred = await run_model_predictions(runner, features, models)
            predictions.append(pred)
        
        # Step 7: Apply risk layer
        predictions = await apply_risk_layer(predictions)
        
        # Step 8: Narrative analysis
        narrative = await analyze_narrative(race, runners)
        
        # Step 9: Market manipulation check
        manipulation = await check_manipulation(race, runners)
        
        # Step 10: Pace analysis
        pace = await analyze_pace(runners, race)
        
        # Step 11: Unify output
        result = unify_output(predictions, narrative, manipulation, pace)
        
        execution_time = (time.time() - start_time) * 1000
        
        result.update({
            "status": "success",
            "execution_duration_ms": round(execution_time, 2),
            "chain": "prediction",
            "runners_analyzed": len(runners)
        })
        
        logger.info(f"✅ Prediction chain complete: {execution_time:.2f}ms")
        
        return result
        
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Prediction chain failed: {e}")
        
        return {
            "status": "error",
            "error": str(e),
            "execution_duration_ms": round(execution_time, 2),
            "chain": "prediction"
        }


async def load_models() -> Dict[str, Any]:
    """Load all required models"""
    from app.services.model_manager import get_model_manager
    
    model_manager = get_model_manager()
    
    return {
        "sqpe": model_manager.get_model("sqpe"),
        "tie": model_manager.get_model("trainer_intent"),
        "longshot": model_manager.get_model("longshot"),
        "overlay": model_manager.get_model("benter_overlay")
    }


async def extract_features_batch(runners: List[Dict], race: Dict) -> List[Dict]:
    """Extract features for all runners"""
    from app.services.feature_engineering import extract_features
    
    features_list = []
    for runner in runners:
        features = extract_features(runner, race, historical=None)
        features_list.append(features)
    
    return features_list


async def run_model_predictions(
    runner: Dict,
    features: Dict,
    models: Dict
) -> Dict[str, Any]:
    """Run all model predictions for a runner"""
    from app.services.model_manager import get_model_manager
    
    mm = get_model_manager()
    
    # SQPE
    sqpe_score = mm.predict_sqpe(features)
    
    # Trainer Intent
    tie_signal = mm.predict_trainer_intent(features)
    
    # Longshot
    odds = runner.get("odds", 5.0)
    longshot_score = mm.predict_longshot(features, odds)
    
    # Final probability (weighted combination)
    final_prob = (sqpe_score * 0.5) + (tie_signal * 0.3) + (longshot_score * 0.2)
    
    # Overlay detection
    overlay = mm.detect_overlay(final_prob, odds)
    
    return {
        "runner_id": runner.get("runner_id"),
        "runner_name": runner.get("horse"),
        "sqpe_score": sqpe_score,
        "tie_signal": tie_signal,
        "longshot_score": longshot_score,
        "final_probability": final_prob,
        "market_odds": odds,
        "overlay": overlay,
        "features": features
    }


async def apply_risk_layer(predictions: List[Dict]) -> List[Dict]:
    """Apply risk layer to all predictions"""
    from app.services.risk_layer import calculate_risk_metrics
    
    for pred in predictions:
        risk_metrics = calculate_risk_metrics(
            model_prob=pred["final_probability"],
            market_odds=pred["market_odds"],
            confidence=0.75
        )
        
        pred.update({
            "edge": risk_metrics["edge"],
            "risk_band": risk_metrics["risk_band"],
            "kelly_stake": risk_metrics["kelly_stake"],
            "expected_value": risk_metrics["expected_value"]
        })
    
    return predictions


async def analyze_narrative(race: Dict, runners: List[Dict]) -> Dict[str, Any]:
    """Run narrative analysis"""
    from app.intelligence.narrative_disruption import detect_market_story
    
    race_with_runners = race.copy()
    race_with_runners["runners"] = runners
    
    narrative = detect_market_story(race_with_runners)
    
    return {
        "narrative_type": narrative.get("story"),
        "disruption_risk": narrative.get("disruption_risk", 0.0),
        "confidence": narrative.get("confidence", 0.0)
    }


async def check_manipulation(race: Dict, runners: List[Dict]) -> Dict[str, Any]:
    """Check for market manipulation"""
    # Stub: Would use real odds history
    return {
        "manipulation_detected": False,
        "risk_score": 0.0,
        "confidence": 0.0
    }


async def analyze_pace(runners: List[Dict], race: Dict) -> Dict[str, Any]:
    """Run pace analysis"""
    from app.intelligence.pace_map import create_pace_map
    
    pace_map = create_pace_map(runners)
    
    return {
        "pace_scenario": pace_map.get("pace_scenario", {}).get("type"),
        "pace_pressure": pace_map.get("pace_pressure", 0.0),
        "advantaged_count": len(pace_map.get("advantaged_runners", []))
    }


def unify_output(
    predictions: List[Dict],
    narrative: Dict,
    manipulation: Dict,
    pace: Dict
) -> Dict[str, Any]:
    """Unify all chain outputs"""
    
    # Find top pick
    top_pick = max(predictions, key=lambda p: p["final_probability"])
    
    # Count overlays
    overlay_count = sum(1 for p in p["overlay"]["is_overlay"] for p in predictions if p.get("overlay"))
    
    return {
        "predictions": predictions,
        "top_pick": {
            "runner": top_pick["runner_name"],
            "probability": top_pick["final_probability"],
            "edge": top_pick.get("edge", 0.0),
            "risk_band": top_pick.get("risk_band", "NO_BET")
        },
        "signals": {
            "narrative": narrative,
            "manipulation": manipulation,
            "pace": pace
        },
        "overlay_count": overlay_count,
        "confidence_scores": {
            "narrative": narrative.get("confidence", 0.0),
            "manipulation": manipulation.get("confidence", 0.0),
            "pace": 0.75  # Stub
        }
    }
