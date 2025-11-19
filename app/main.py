"""
VÉLØ Oracle - Production FastAPI Application
Main entry point for the prediction API
"""
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core import log, settings
from app.core.security import get_cors_config
from app.api import api_router
from app.services import model_registry

# Track startup time
startup_time = time.time()

# Create FastAPI application
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    **get_cors_config()
)


# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses"""
    start_time = time.time()
    
    # Log request
    log.info(
        f"Request: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown"
        }
    )
    
    # Process request
    try:
        response = await call_next(request)
        
        # Calculate duration
        duration = (time.time() - start_time) * 1000  # ms
        
        # Log response
        log.info(
            f"Response: {response.status_code} ({duration:.2f}ms)",
            extra={
                "status_code": response.status_code,
                "duration_ms": round(duration, 2)
            }
        )
        
        return response
    
    except Exception as e:
        log.error(f"Request failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    log.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": request.url.path
        }
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    log.info("=" * 60)
    log.info("VÉLØ Oracle API — Booting Prediction Engine")
    log.info("=" * 60)
    log.info(f"Environment: {settings.API_ENV}")
    log.info(f"Version: {settings.API_VERSION}")
    
    # Scan and load models
    try:
        models = model_registry.scan_models()
        log.info(f"Found {len(models)} models in registry")
        
        active_model = model_registry.get_active_model()
        if active_model:
            log.info(f"Active model: {active_model.get('name')}-{active_model.get('version')}")
        else:
            log.warning("No active model configured")
    
    except Exception as e:
        log.error(f"Failed to initialize model registry: {e}")
    
    log.info("=" * 60)
    log.info("VÉLØ Oracle API Ready")
    log.info("=" * 60)


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    log.info("Shutting down VÉLØ Oracle API")


# Include API router
app.include_router(api_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API information"""
    uptime = time.time() - startup_time
    
    return {
        "service": "VÉLØ Oracle API",
        "version": settings.API_VERSION,
        "status": "online",
        "uptime_seconds": round(uptime, 2),
        "environment": settings.API_ENV,
        "docs": "/docs",
        "endpoints": {
            "health": "/v1/health",
            "predict": "/v1/predict",
            "models": "/v1/models",
            "system": "/v1/system/status"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

