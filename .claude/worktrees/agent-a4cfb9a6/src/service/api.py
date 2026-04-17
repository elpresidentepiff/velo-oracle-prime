# src/service/api.py
"""
VÉLØ Oracle FastAPI Service - Production prediction endpoint.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field

# VÉLØ Core Imports
from src.registry.model_registry import default_model_registry
from src.deployment.cc_manager import default_cc_manager
from src.features.builder import FeatureBuilder
from src.features.cache import FeatureCache
from src.logging.prediction_logger import (
    default_prediction_logger,
    PredictionLogRecord,
    generate_request_id
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- API Models ---

class RunnerInput(BaseModel):
    """Input schema for a single runner in a race."""
    horse: str
    trainer: str
    jockey: str
    age: int
    weight: float
    rating_or: Optional[float] = None
    rating_rpr: Optional[float] = None
    rating_ts: Optional[float] = None
    odds: Optional[float] = None

class RaceInput(BaseModel):
    """Input schema for a complete race."""
    race_id: str
    course: str
    date: str
    dist: str
    going: str
    class_: str = Field(alias="class")
    runners: List[RunnerInput]

class PredictionOutput(BaseModel):
    """Output schema for a single runner prediction."""
    horse: str
    sqpe_prob: float
    tie_intent: float
    final_prob: float
    recommended_bet: bool
    model_version: str

class RacePredictionResponse(BaseModel):
    """Response schema for race predictions."""
    request_id: str
    race_id: str
    timestamp: str
    predictions: List[PredictionOutput]
    model_info: Dict[str, str]

# --- FastAPI App ---

app = FastAPI(
    title="VÉLØ Oracle API",
    description="Production ML prediction service for horse racing",
    version="13.0.0"
)

# --- Global State ---
# These will be initialized on startup
feature_builder: Optional[FeatureBuilder] = None
feature_cache: Optional[FeatureCache] = None

@app.on_event("startup")
async def startup_event():
    """Initialize feature builder and cache on startup."""
    global feature_builder, feature_cache
    
    logger.info("=== VÉLØ Oracle API Starting Up ===")
    
    # Load champion orchestrator to verify it exists
    champion = default_cc_manager.get_champion_orchestrator()
    if not champion:
        logger.error("CRITICAL: No champion model found in registry!")
        raise RuntimeError("Cannot start API without a champion model in production stage")
    
    # Initialize feature builder
    feature_builder = FeatureBuilder()
    logger.info("Feature Builder initialized")
    
    # Initialize feature cache (optional - can be None)
    try:
        # Load cache if it exists, otherwise builder will work without it
        feature_cache = None  # Will be loaded on demand
        logger.info("Feature Cache will be loaded on demand")
    except Exception as e:
        logger.warning(f"Could not load feature cache: {e}")
        feature_cache = None
    
    logger.info("=== VÉLØ Oracle API Ready ===")

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "VÉLØ Oracle API",
        "status": "operational",
        "version": "13.0.0"
    }

@app.get("/health")
async def health():
    """Detailed health check."""
    champion = default_cc_manager.get_champion_orchestrator()
    challenger = default_cc_manager.get_challenger_orchestrator()
    
    return {
        "status": "healthy",
        "champion_loaded": champion is not None,
        "challenger_loaded": challenger is not None,
        "feature_builder_ready": feature_builder is not None
    }

@app.post("/predict", response_model=RacePredictionResponse)
async def predict_race(race: RaceInput):
    """
    Generate predictions for a race.
    
    Args:
        race: RaceInput containing race details and runners
        
    Returns:
        RacePredictionResponse with predictions for all runners
    """
    request_id = generate_request_id()
    timestamp = datetime.utcnow().isoformat()
    
    logger.info(f"[{request_id}] Prediction request for race {race.race_id}")
    
    try:
        # Load champion orchestrator
        champion = default_cc_manager.get_champion_orchestrator()
        if not champion:
            raise HTTPException(status_code=503, detail="Champion model not available")
        
        # Convert input to DataFrame
        runners_data = []
        for runner in race.runners:
            row = {
                'race_id': race.race_id,
                'horse': runner.horse,
                'trainer': runner.trainer,
                'jockey': runner.jockey,
                'age': runner.age,
                'weight': runner.weight,
                'rating_or': runner.rating_or or 0,
                'rating_rpr': runner.rating_rpr or 0,
                'rating_ts': runner.rating_ts or 0,
                'course': race.course,
                'date': race.date,
                'dist': race.dist,
                'going': race.going,
                'class': race.class_,
                'odds': runner.odds or 0
            }
            runners_data.append(row)
        
        df = pd.DataFrame(runners_data)
        
        # Build features
        logger.info(f"[{request_id}] Building features for {len(df)} runners")
        # Note: In production, you'd pass historical data for form features
        # For now, we'll use the builder without history (features will be basic)
        sqpe_features = feature_builder.build_sqpe_features(df, history=pd.DataFrame())
        tie_features = feature_builder.build_tie_features(df, history=pd.DataFrame())
        
        # Get predictions from champion
        logger.info(f"[{request_id}] Generating predictions")
        predictions = champion.predict(sqpe_features, tie_features)
        
        # Format output
        output_predictions = []
        log_records = []
        
        for i, runner in enumerate(race.runners):
            pred = predictions[i] if i < len(predictions) else {}
            
            sqpe_prob = pred.get('sqpe_prob', 0.0)
            tie_intent = pred.get('tie_intent', 0.0)
            final_prob = pred.get('final_prob', 0.0)
            
            # Simple betting logic: bet if prob between 15-40%
            recommended_bet = 0.15 <= final_prob <= 0.40
            
            output_predictions.append(PredictionOutput(
                horse=runner.horse,
                sqpe_prob=sqpe_prob,
                tie_intent=tie_intent,
                final_prob=final_prob,
                recommended_bet=recommended_bet,
                model_version=champion.get_model_versions().get('sqpe', 'unknown')
            ))
            
            # Create log record
            log_records.append(PredictionLogRecord(
                timestamp=timestamp,
                request_id=request_id,
                race_id=race.race_id,
                horse_id=runner.horse,
                model_name="sqpe",
                model_version=champion.get_model_versions().get('sqpe', 'unknown'),
                is_champion=True,
                sqpe_prob=sqpe_prob,
                tie_intent=tie_intent,
                final_prob=final_prob
            ))
        
        # Log predictions
        default_prediction_logger.log(log_records)
        
        logger.info(f"[{request_id}] Predictions complete: {len(output_predictions)} runners")
        
        return RacePredictionResponse(
            request_id=request_id,
            race_id=race.race_id,
            timestamp=timestamp,
            predictions=output_predictions,
            model_info=champion.get_model_versions()
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models/champion")
async def get_champion_info():
    """Get information about the current champion model."""
    sqpe_record = default_model_registry.get_champion("sqpe")
    tie_record = default_model_registry.get_champion("tie")
    
    if not sqpe_record or not tie_record:
        raise HTTPException(status_code=404, detail="Champion models not found")
    
    return {
        "sqpe": {
            "version": sqpe_record.version,
            "stage": sqpe_record.stage,
            "registered_at": sqpe_record.registered_at,
            "metadata": sqpe_record.metadata
        },
        "tie": {
            "version": tie_record.version,
            "stage": tie_record.stage,
            "registered_at": tie_record.registered_at,
            "metadata": tie_record.metadata
        }
    }

@app.get("/models/challenger")
async def get_challenger_info():
    """Get information about the current challenger model (if any)."""
    sqpe_record = default_model_registry.get_challenger("sqpe")
    tie_record = default_model_registry.get_challenger("tie")
    
    if not sqpe_record or not tie_record:
        return {"message": "No challenger models in staging"}
    
    return {
        "sqpe": {
            "version": sqpe_record.version,
            "stage": sqpe_record.stage,
            "registered_at": sqpe_record.registered_at,
            "metadata": sqpe_record.metadata
        },
        "tie": {
            "version": tie_record.version,
            "stage": tie_record.stage,
            "registered_at": tie_record.registered_at,
            "metadata": tie_record.metadata
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

