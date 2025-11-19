"""
Prediction request schema
"""
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """Request schema for prediction endpoint"""
    
    race_id: str = Field(..., description="Unique race identifier")
    features: Dict[str, float] = Field(..., description="Feature vector for prediction")
    meta: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "race_id": "race_2025_001",
                "features": {
                    "speed_rating": 85.5,
                    "form_score": 0.92,
                    "distance_suitability": 0.88
                },
                "meta": {
                    "horse_name": "Thunder Bolt",
                    "course": "Ascot"
                }
            }
        }

