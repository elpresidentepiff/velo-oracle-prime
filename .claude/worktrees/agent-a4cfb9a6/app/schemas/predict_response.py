"""
Prediction response schema
"""
from typing import Optional, Any
from pydantic import BaseModel, Field


class PredictResponse(BaseModel):
    """Response schema for prediction endpoint"""
    
    prediction: float = Field(..., description="Predicted win probability")
    confidence: float = Field(..., description="Model confidence score")
    model_version: str = Field(..., description="Model version used for prediction")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    reasoning: str = Field(..., description="Human-readable prediction rationale")
    raw_output: Optional[Any] = Field(default=None, description="Raw model output")
    
    class Config:
        schema_extra = {
            "example": {
                "prediction": 0.35,
                "confidence": 0.92,
                "model_version": "SQPE-v1_real",
                "processing_time_ms": 45.2,
                "reasoning": "Strong form + favorable conditions",
                "raw_output": {"logits": [0.65, 0.35]}
            }
        }

