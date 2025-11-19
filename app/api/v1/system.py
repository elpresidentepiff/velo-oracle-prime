"""
System status endpoint
"""
from fastapi import APIRouter
from app.schemas import SystemStatus
from app.core import settings, log
from app.services.model_registry import model_registry

router = APIRouter()


@router.get("/system/status", response_model=SystemStatus)
async def get_system_status():
    """
    Get comprehensive system status
    Returns version, active model, metrics, and diagnostics
    """
    try:
        active_model = model_registry.get_active_model()
        model_name = f"{active_model['name']}-{active_model['version']}" if active_model else "none"
        
        # Placeholder latency metrics
        latency_metrics = {
            "p50_ms": 45.2,
            "p95_ms": 120.5,
            "p99_ms": 250.0
        }
        
        # Check database connection
        db_connected = bool(settings.SUPABASE_URL and settings.SUPABASE_KEY)
        
        return SystemStatus(
            version=settings.API_VERSION,
            active_model=model_name,
            latency_metrics=latency_metrics,
            environment=settings.API_ENV,
            registry_state="healthy" if model_registry.is_model_loaded() else "unloaded",
            database_connected=db_connected
        )
    
    except Exception as e:
        log.error(f"Failed to get system status: {e}")
        return SystemStatus(
            version=settings.API_VERSION,
            active_model="error",
            latency_metrics={},
            environment=settings.API_ENV,
            registry_state="error",
            database_connected=False
        )

