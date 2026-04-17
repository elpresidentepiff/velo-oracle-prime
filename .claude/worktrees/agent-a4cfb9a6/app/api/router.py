"""
API router - aggregates all versioned endpoints
"""
from fastapi import APIRouter
from app.api.v1 import predict, health, models, system

# Create main API router
api_router = APIRouter()

# Include v1 endpoints
api_router.include_router(predict.router, prefix="/v1", tags=["predictions"])
api_router.include_router(health.router, prefix="/v1", tags=["health"])
api_router.include_router(models.router, prefix="/v1", tags=["models"])
api_router.include_router(system.router, prefix="/v1", tags=["system"])

