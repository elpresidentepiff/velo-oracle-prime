"""
Health check endpoint
"""
import time
from fastapi import APIRouter
from app.schemas import HealthResponse
from app.core import settings, log
from app.services.model_registry import model_registry

router = APIRouter()

# Track startup time
startup_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    Returns system status, uptime, and service connectivity
    """
    try:
        # Check model loaded
        model_loaded = model_registry.is_model_loaded()
        
        # Check connected services
        connected_services = []
        if settings.SUPABASE_URL:
            connected_services.append("supabase")
        if model_registry.get_active_model():
            connected_services.append("model_registry")
        
        # Calculate uptime
        uptime = time.time() - startup_time
        
        return HealthResponse(
            status="ok",
            model_loaded=model_loaded,
            connected_services=connected_services,
            uptime_seconds=round(uptime, 2),
            version=settings.API_VERSION
        )
    except Exception as e:
        log.error(f"Health check failed: {e}")
        return HealthResponse(
            status="degraded",
            model_loaded=False,
            connected_services=[],
            uptime_seconds=round(time.time() - startup_time, 2),
            version=settings.API_VERSION
        )

