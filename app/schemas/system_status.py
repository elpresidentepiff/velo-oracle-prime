"""
System status response schema
"""
from typing import Dict, Optional
from pydantic import BaseModel, Field


class SystemStatus(BaseModel):
    """Response schema for system status endpoint"""
    
    version: str = Field(..., description="API version")
    active_model: str = Field(..., description="Currently active model")
    latency_metrics: Dict[str, float] = Field(..., description="Performance metrics")
    environment: str = Field(..., description="Deployment environment")
    registry_state: str = Field(..., description="Model registry status")
    database_connected: bool = Field(..., description="Database connection status")
    
    class Config:
        schema_extra = {
            "example": {
                "version": "v1",
                "active_model": "SQPE-v1_real",
                "latency_metrics": {
                    "p50_ms": 45.2,
                    "p95_ms": 120.5,
                    "p99_ms": 250.0
                },
                "environment": "production",
                "registry_state": "healthy",
                "database_connected": True
            }
        }

