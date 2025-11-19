"""
VÉLØ Oracle FastAPI Service v2 - With Supabase Integration
============================================================

Production prediction endpoint with database logging.

Author: VÉLØ Oracle Team
Version: 2.0.0
"""

import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# VÉLØ Core Imports
from src.data.supabase_client import get_supabase_client, SupabaseClient

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
    race_time: str
    race_name: str
    dist: str
    going: str
    class_: str = Field(alias="class")
    runners: List[RunnerInput]

class PredictionOutput(BaseModel):
    """Output schema for a single runner prediction."""
    horse: str
    predicted_position: int
    win_probability: float
    confidence: float
    recommended_bet: bool
    model_version: str

class RacePredictionResponse(BaseModel):
    """Response schema for race predictions."""
    request_id: str
    race_id: str
    timestamp: str
    predictions: List[PredictionOutput]
    model_info: Dict[str, str]
    logged_to_database: bool

class RaceCardInput(BaseModel):
    """Input schema for storing race card."""
    race_id: str
    race_date: str
    course: str
    race_time: str
    race_name: str
    runners: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None

class ModelInfo(BaseModel):
    """Model information schema."""
    model_name: str
    model_version: str
    accuracy: float
    performance_metrics: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    database_connected: bool
    timestamp: str

# --- FastAPI App ---

app = FastAPI(
    title="VÉLØ Oracle API",
    description="Production ML prediction service for horse racing with Supabase integration",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global State ---
supabase_client: Optional[SupabaseClient] = None

@app.on_event("startup")
async def startup_event():
    """Initialize Supabase client on startup."""
    global supabase_client
    
    logger.info("=== VÉLØ Oracle API v2 Starting Up ===")
    
    try:
        # Initialize Supabase client
        supabase_client = get_supabase_client()
        
        # Health check
        if supabase_client.health_check():
            logger.info("✅ Supabase connection established")
        else:
            logger.warning("⚠️ Supabase health check failed")
    
    except Exception as e:
        logger.error(f"❌ Failed to initialize Supabase: {e}")
        supabase_client = None
    
    logger.info("=== VÉLØ Oracle API v2 Ready ===")

def get_db() -> SupabaseClient:
    """Dependency to get Supabase client."""
    if supabase_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available"
        )
    return supabase_client

# --- Endpoints ---

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "VÉLØ Oracle API",
        "status": "operational",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
async def health(db: SupabaseClient = Depends(get_db)):
    """Detailed health check."""
    db_connected = db.health_check()
    
    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        version="2.0.0",
        database_connected=db_connected,
        timestamp=datetime.utcnow().isoformat()
    )

@app.get("/v1/health")
async def health_v1():
    """Legacy health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/v1/predict", response_model=RacePredictionResponse)
async def predict_race(
    race: RaceInput,
    db: SupabaseClient = Depends(get_db)
):
    """
    Generate predictions for a race and log to database.
    
    Args:
        race: RaceInput containing race details and runners
        db: Supabase client (injected)
        
    Returns:
        RacePredictionResponse with predictions for all runners
    """
    request_id = f"req_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    timestamp = datetime.utcnow().isoformat()
    
    logger.info(f"[{request_id}] Prediction request for race {race.race_id}")
    
    try:
        # Simple prediction logic (replace with actual model)
        predictions = []
        logged_count = 0
        
        for i, runner in enumerate(race.runners):
            # Mock prediction (replace with actual model inference)
            win_prob = 1.0 / len(race.runners)  # Equal probability for demo
            predicted_pos = i + 1
            confidence = 0.75
            
            # Log prediction to database
            try:
                db.log_prediction(
                    race_id=race.race_id,
                    horse_name=runner.horse,
                    model_name="velo-oracle-v13",
                    predicted_position=predicted_pos,
                    confidence=confidence,
                    win_probability=win_prob,
                    metadata={
                        "trainer": runner.trainer,
                        "jockey": runner.jockey,
                        "odds": runner.odds,
                        "request_id": request_id
                    }
                )
                logged_count += 1
            except Exception as e:
                logger.error(f"Failed to log prediction for {runner.horse}: {e}")
            
            predictions.append(PredictionOutput(
                horse=runner.horse,
                predicted_position=predicted_pos,
                win_probability=win_prob,
                confidence=confidence,
                recommended_bet=0.15 <= win_prob <= 0.40,
                model_version="v13.0.0"
            ))
        
        logger.info(f"[{request_id}] Generated {len(predictions)} predictions, logged {logged_count} to database")
        
        return RacePredictionResponse(
            request_id=request_id,
            race_id=race.race_id,
            timestamp=timestamp,
            predictions=predictions,
            model_info={
                "name": "velo-oracle-v13",
                "version": "13.0.0",
                "type": "ensemble"
            },
            logged_to_database=logged_count > 0
        )
    
    except Exception as e:
        logger.error(f"[{request_id}] Prediction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )

@app.post("/v1/racecard")
async def store_racecard(
    racecard: RaceCardInput,
    db: SupabaseClient = Depends(get_db)
):
    """
    Store race card data in database.
    
    Args:
        racecard: RaceCardInput containing race details
        db: Supabase client (injected)
        
    Returns:
        Confirmation of storage
    """
    try:
        result = db.store_racecard(
            race_id=racecard.race_id,
            race_date=racecard.race_date,
            course=racecard.course,
            race_time=racecard.race_time,
            race_name=racecard.race_name,
            runners=racecard.runners,
            metadata=racecard.metadata
        )
        
        logger.info(f"✅ Race card stored: {racecard.race_id}")
        
        return {
            "status": "success",
            "race_id": racecard.race_id,
            "stored_at": datetime.utcnow().isoformat(),
            "record_id": result.get('id')
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to store race card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store race card: {str(e)}"
        )

@app.get("/v1/models")
async def get_models(db: SupabaseClient = Depends(get_db)):
    """
    Get all model records from database.
    
    Returns:
        List of model records
    """
    try:
        models = db.get_models()
        
        return {
            "status": "success",
            "count": len(models),
            "models": models
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to get models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get models: {str(e)}"
        )

@app.post("/v1/models")
async def store_model(
    model: ModelInfo,
    db: SupabaseClient = Depends(get_db)
):
    """
    Store model performance log.
    
    Args:
        model: ModelInfo containing model details
        db: Supabase client (injected)
        
    Returns:
        Confirmation of storage
    """
    try:
        result = db.store_model_log(
            model_name=model.model_name,
            model_version=model.model_version,
            accuracy=model.accuracy,
            performance_metrics=model.performance_metrics,
            metadata=model.metadata
        )
        
        logger.info(f"✅ Model log stored: {model.model_name} v{model.model_version}")
        
        return {
            "status": "success",
            "model_name": model.model_name,
            "model_version": model.model_version,
            "stored_at": datetime.utcnow().isoformat(),
            "record_id": result.get('id')
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to store model log: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store model log: {str(e)}"
        )

@app.get("/v1/races/{race_id}")
async def get_race(
    race_id: str,
    db: SupabaseClient = Depends(get_db)
):
    """
    Get race card by ID.
    
    Args:
        race_id: Race identifier
        db: Supabase client (injected)
        
    Returns:
        Race card data
    """
    try:
        racecard = db.get_racecard(race_id)
        
        if not racecard:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Race {race_id} not found"
            )
        
        return {
            "status": "success",
            "race": racecard
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get race: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get race: {str(e)}"
        )

@app.get("/v1/predictions/{race_id}")
async def get_predictions(
    race_id: str,
    db: SupabaseClient = Depends(get_db)
):
    """
    Get all predictions for a race.
    
    Args:
        race_id: Race identifier
        db: Supabase client (injected)
        
    Returns:
        List of predictions
    """
    try:
        predictions = db.get_predictions_by_race(race_id)
        
        return {
            "status": "success",
            "race_id": race_id,
            "count": len(predictions),
            "predictions": predictions
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to get predictions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get predictions: {str(e)}"
        )


if __name__ == "__main__":
    # Set environment variables for local testing
    os.environ['SUPABASE_URL'] = os.getenv('SUPABASE_URL', 'https://ltbsxbvfsxtnharjvqcm.supabase.co')
    os.environ['SUPABASE_KEY'] = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0YnN4YnZmc3h0bmhhcmp2cWNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjM0ODgzNjksImV4cCI6MjA3OTA2NDM2OX0.iS1Sixo77BhZ2UQVwqVQcGOyBocSIy9ApABvsgLGmhY')
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
