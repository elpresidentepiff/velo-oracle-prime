"""
VÉLØ Oracle - Prediction Schema
Comprehensive prediction output with VÉLØ scoring components
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class PredictionSchema(BaseModel):
    """Individual runner prediction with VÉLØ scoring breakdown"""
    prediction_id: str = Field(..., description="Unique prediction identifier")
    race_id: str = Field(..., description="Associated race identifier")
    runner_id: str = Field(..., description="Runner identifier")
    runner_name: str = Field(..., description="Horse name")
    
    # Core VÉLØ scores
    sqpe_score: float = Field(..., ge=0, le=1, description="SQPE (Speed, Quality, Pace, Efficiency) score")
    tie_signal: float = Field(..., ge=0, le=1, description="Trainer Intent Engine signal strength")
    longshot_score: float = Field(..., ge=0, le=1, description="Longshot detection score")
    final_probability: float = Field(..., ge=0, le=1, description="Final win probability")
    
    # Optional component scores
    speed_score: Optional[float] = Field(None, ge=0, le=1, description="Speed component")
    quality_score: Optional[float] = Field(None, ge=0, le=1, description="Quality component")
    pace_score: Optional[float] = Field(None, ge=0, le=1, description="Pace component")
    efficiency_score: Optional[float] = Field(None, ge=0, le=1, description="Efficiency component")
    
    # Market intelligence
    market_odds: Optional[float] = Field(None, gt=0, description="Current market odds")
    implied_probability: Optional[float] = Field(None, ge=0, le=1, description="Market implied probability")
    value_edge: Optional[float] = Field(None, description="Edge over market (final_probability - implied_probability)")
    
    # Confidence and risk
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Prediction confidence level")
    risk_level: Optional[str] = Field(None, max_length=20, description="Risk classification (Low/Medium/High)")
    
    # Metadata
    model_version: Optional[str] = Field(None, max_length=50, description="Model version used")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Prediction timestamp")
    
    # Additional context
    notes: Optional[str] = Field(None, max_length=500, description="Prediction notes or flags")
    features_used: Optional[Dict[str, Any]] = Field(None, description="Feature values used in prediction")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prediction_id": "P20251119001",
                "race_id": "RC20251119001",
                "runner_id": "R001",
                "runner_name": "Without A Fight",
                "sqpe_score": 0.87,
                "tie_signal": 0.92,
                "longshot_score": 0.15,
                "final_probability": 0.23,
                "speed_score": 0.89,
                "quality_score": 0.91,
                "pace_score": 0.84,
                "efficiency_score": 0.85,
                "market_odds": 5.50,
                "implied_probability": 0.18,
                "value_edge": 0.05,
                "confidence": 0.78,
                "risk_level": "Medium",
                "model_version": "v13.0",
                "notes": "Strong trainer intent signal, favorable pace scenario"
            }
        }


class RacePredictionSchema(BaseModel):
    """Complete race prediction with all runners"""
    race_id: str = Field(..., description="Race identifier")
    predictions: list[PredictionSchema] = Field(..., min_items=1, description="Predictions for all runners")
    race_timestamp: datetime = Field(..., description="Race scheduled time")
    prediction_timestamp: datetime = Field(default_factory=datetime.utcnow, description="When predictions were generated")
    
    # Race-level analytics
    favorite_runner_id: Optional[str] = Field(None, description="Market favorite runner ID")
    velo_top_pick: Optional[str] = Field(None, description="VÉLØ top selection runner ID")
    overlay_count: Optional[int] = Field(None, ge=0, description="Number of overlay opportunities detected")
    
    class Config:
        json_schema_extra = {
            "example": {
                "race_id": "RC20251119001",
                "race_timestamp": "2025-11-19T15:00:00Z",
                "prediction_timestamp": "2025-11-19T14:30:00Z",
                "favorite_runner_id": "R003",
                "velo_top_pick": "R001",
                "overlay_count": 2,
                "predictions": [
                    {
                        "prediction_id": "P20251119001",
                        "race_id": "RC20251119001",
                        "runner_id": "R001",
                        "runner_name": "Without A Fight",
                        "sqpe_score": 0.87,
                        "tie_signal": 0.92,
                        "longshot_score": 0.15,
                        "final_probability": 0.23
                    }
                ]
            }
        }
