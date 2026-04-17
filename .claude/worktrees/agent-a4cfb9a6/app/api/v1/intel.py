"""
VÉLØ Oracle - Intelligence API
Intelligence chain execution endpoints
"""
from fastapi import APIRouter, HTTPException, Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/intel", tags=["intelligence"])


@router.get("/chain/predict/{race_id}")
async def run_prediction_chain_endpoint(
    race_id: str = Path(..., description="Race identifier")
) -> Dict[str, Any]:
    """
    Execute complete prediction chain for a race
    
    Pipeline:
    - Load models
    - Extract features
    - Run SQPE, TIE, Longshot, Overlay
    - Apply risk layer
    - Analyze narrative, manipulation, pace
    - Unify output
    
    Returns:
        Complete prediction analysis with all signals
    """
    try:
        from app.intelligence.chains import run_prediction_chain
        
        # Fetch race and runners from database
        race, runners = await fetch_race_data(race_id)
        
        # Run prediction chain
        result = await run_prediction_chain(race, runners)
        
        # Add metadata
        result["race_id"] = race_id
        
        return result
        
    except Exception as e:
        logger.error(f"Prediction chain error for {race_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/narrative/{race_id}")
async def run_narrative_chain_endpoint(
    race_id: str = Path(..., description="Race identifier")
) -> Dict[str, Any]:
    """
    Execute narrative analysis chain for a race
    
    Pipeline:
    - Analyze odds movements
    - Detect primary narrative
    - Detect secondary bias
    - Build narrative signature
    
    Returns:
        Narrative analysis with confidence scores
    """
    try:
        from app.intelligence.chains import run_narrative_chain
        
        # Fetch race and odds data
        race, odds_movements = await fetch_race_with_odds(race_id)
        
        # Run narrative chain
        result = await run_narrative_chain(race, odds_movements)
        
        # Add metadata
        result["race_id"] = race_id
        
        return result
        
    except Exception as e:
        logger.error(f"Narrative chain error for {race_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/{race_id}")
async def run_market_chain_endpoint(
    race_id: str = Path(..., description="Race identifier")
) -> Dict[str, Any]:
    """
    Execute market manipulation detection chain
    
    Pipeline:
    - Analyze odds movements
    - Detect spoofing
    - Detect echo moves
    - Detect stop-loss wipes
    - Detect multi-venue sync
    - Output risk score (0-100)
    
    Returns:
        Market manipulation analysis with risk score
    """
    try:
        from app.intelligence.chains import run_market_chain
        
        # Fetch race and odds history
        race, odds_history = await fetch_race_with_odds(race_id)
        
        # Run market chain
        result = await run_market_chain(race, odds_history)
        
        # Add metadata
        result["race_id"] = race_id
        
        return result
        
    except Exception as e:
        logger.error(f"Market chain error for {race_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pace/{race_id}")
async def run_pace_chain_endpoint(
    race_id: str = Path(..., description="Race identifier")
) -> Dict[str, Any]:
    """
    Execute pace analysis chain
    
    Pipeline:
    - Extract runner speeds
    - Build pace clusters
    - Predict early pressure
    - Compute late energy curve
    - Classify race shape
    
    Returns:
        Pace analysis with race shape classification
    """
    try:
        from app.intelligence.chains import run_pace_chain
        
        # Fetch race and runners
        race, runners = await fetch_race_data(race_id)
        
        # Run pace chain
        result = await run_pace_chain(runners, race)
        
        # Add metadata
        result["race_id"] = race_id
        
        return result
        
    except Exception as e:
        logger.error(f"Pace chain error for {race_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/radar/{race_id}")
async def get_manipulation_radar(
    race_id: str = Path(..., description="Race identifier")
) -> Dict[str, Any]:
    """
    Get comprehensive manipulation risk radar
    
    Combines:
    - Market chain signals
    - Volatility index
    - Stability index
    - Observatory signals
    
    Returns:
        Risk radar (0-100) with detected patterns and recommendations
    """
    try:
        from app.intelligence.chains import run_market_chain
        from app.observatory import (
            compute_volatility_index,
            compute_stability_index,
            compute_manipulation_radar
        )
        
        # Fetch data
        race, runners = await fetch_race_data(race_id)
        _, odds_movements = await fetch_race_with_odds(race_id)
        
        # Run market chain
        market_result = await run_market_chain(race, odds_movements)
        
        # Compute observatory indices
        volatility = compute_volatility_index(odds_movements, runners, race)
        stability = compute_stability_index(runners, race)
        
        # Compute manipulation radar
        radar = compute_manipulation_radar(
            market_result,
            volatility,
            stability,
            odds_movements
        )
        
        # Build comprehensive response
        result = {
            "race_id": race_id,
            "radar": radar,
            "volatility": volatility,
            "stability": stability,
            "market_signals": market_result.get("signals", {}),
            "risk_summary": {
                "risk_radar": radar["risk_radar"],
                "risk_category": radar["risk_category"],
                "recommendation": radar["recommendation"]
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Radar endpoint error for {race_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions

async def fetch_race_data(race_id: str) -> tuple:
    """Fetch race and runners from database"""
    # Stub: Would fetch from Supabase
    race = {
        "race_id": race_id,
        "course": "Flemington",
        "distance": 1600,
        "going": "Good"
    }
    
    runners = [
        {
            "runner_id": "R01",
            "horse": "Test Horse 1",
            "odds": 5.0,
            "draw": 3,
            "trainer": "Test Trainer",
            "jockey": "Test Jockey"
        },
        {
            "runner_id": "R02",
            "horse": "Test Horse 2",
            "odds": 3.5,
            "draw": 7,
            "trainer": "Test Trainer 2",
            "jockey": "Test Jockey 2"
        }
    ]
    
    return race, runners


async def fetch_race_with_odds(race_id: str) -> tuple:
    """Fetch race with odds movements"""
    race, _ = await fetch_race_data(race_id)
    
    # Stub: Would fetch real odds history
    odds_movements = [
        {"odds": 5.0, "timestamp": "2025-11-19T10:00:00", "volume": 100},
        {"odds": 4.8, "timestamp": "2025-11-19T10:30:00", "volume": 150},
        {"odds": 4.5, "timestamp": "2025-11-19T11:00:00", "volume": 200}
    ]
    
    return race, odds_movements
