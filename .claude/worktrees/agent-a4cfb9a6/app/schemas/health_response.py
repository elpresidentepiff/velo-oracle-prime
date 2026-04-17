"""
Health check response schema
"""
from typing import List
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response schema for health check endpoint"""
    
    status: str = Field(..., description="Overall system status")
    model_loaded: bool = Field(..., description="Whether ML model is loaded")
    connected_services: List[str] = Field(..., description="List of connected services")
    uptime_seconds: float = Field(..., description="API uptime in seconds")
    version: str = Field(..., description="API version")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "ok",
                "model_loaded": True,
                "connected_services": ["supabase", "model_registry"],
                "uptime_seconds": 3600.5,
                "version": "v1"
            }
        }

