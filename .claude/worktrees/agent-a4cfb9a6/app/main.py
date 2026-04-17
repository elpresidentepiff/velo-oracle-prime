"""
VÉLØ Oracle - FastAPI Main Application
Production-ready with CORS, health checks, and API routing
"""
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="VÉLØ Oracle API",
    version="v1.0",
    description="Production horse racing prediction engine",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware - CRITICAL for Cloudflare Worker
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Import and include routers
try:
    from app.routers.features import router as features_router
    from app.routers.monitoring import router as monitoring_router
    
    app.include_router(features_router, prefix="/features", tags=["features"])
    app.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
    logger.info("✅ Feast Feature Store and Evidently Monitoring routers loaded")
except ImportError as e:
    logger.warning(f"⚠️  Feature/Monitoring routers not available: {e}")

# Environment
ENV = os.getenv("ENV", "production")
API_KEY = os.getenv("API_KEY", "")

# API Key validation
async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key from header"""
    if not API_KEY:
        # If no API key configured, skip validation
        return True
    
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return True


# Health check endpoint - CRITICAL for Railway
@app.get("/health")
async def health_check():
    """
    Health check endpoint for Railway and monitoring
    
    Returns:
        Status and metadata
    """
    return {
        "status": "ok",
        "app": "VÉLØ Oracle",
        "version": "v1.0",
        "environment": ENV,
        "timestamp": datetime.utcnow().isoformat()
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "VÉLØ Oracle API",
        "version": "v1.0",
        "docs": "/docs",
        "health": "/health"
    }


# API v1 endpoints
@app.get("/api/v1/status")
async def api_status(authorized: bool = Depends(verify_api_key)):
    """API status endpoint"""
    return {
        "status": "operational",
        "version": "v1.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# Prediction endpoints
@app.post("/api/v1/predict/quick")
async def predict_quick(
    race_data: dict,
    authorized: bool = Depends(verify_api_key)
):
    """
    Quick prediction endpoint
    
    Args:
        race_data: Race and runner data
        
    Returns:
        Prediction with probability, edge, confidence
    """
    try:
        # Import UMA
        from app.engine.uma import UMA
        
        # Create UMA instance
        uma = UMA()
        
        # Run prediction
        result = uma.predict(
            race_id=race_data.get("race_id"),
            runner_id=race_data.get("runner_id"),
            features=race_data.get("features", {}),
            market_odds=race_data.get("market_odds")
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/predict/full")
async def predict_full(
    race_data: dict,
    authorized: bool = Depends(verify_api_key)
):
    """
    Full prediction with intelligence layers
    
    Args:
        race_data: Complete race data
        
    Returns:
        Full prediction with intelligence signals
    """
    try:
        from app.intelligence.chains.prediction_chain import run_prediction_chain
        
        result = run_prediction_chain(race_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Full prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Intelligence endpoints
@app.get("/api/v1/intel/narrative/{race_id}")
async def get_narrative(
    race_id: str,
    authorized: bool = Depends(verify_api_key)
):
    """Get narrative intelligence for race"""
    try:
        from app.intelligence.chains.narrative_chain import run_narrative_chain
        
        result = run_narrative_chain(race_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Narrative analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/intel/market/{race_id}")
async def get_market_intel(
    race_id: str,
    authorized: bool = Depends(verify_api_key)
):
    """Get market manipulation intelligence"""
    try:
        from app.intelligence.chains.market_chain import run_market_chain
        
        result = run_market_chain(race_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Market analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# System endpoints
@app.get("/api/v1/system/models")
async def get_models(authorized: bool = Depends(verify_api_key)):
    """Get loaded models and versions"""
    try:
        from app.ml.model_ops.loader import get_loaded_models
        
        models = get_loaded_models()
        
        return {
            "models": models,
            "count": len(models),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Get models failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not found",
            "path": str(request.url),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(500)
async def server_error_handler(request, exc):
    """Handle 500 errors"""
    logger.error(f"Server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Startup tasks"""
    logger.info("="*60)
    logger.info("VÉLØ Oracle API Starting")
    logger.info("="*60)
    logger.info(f"Environment: {ENV}")
    logger.info(f"API Key configured: {bool(API_KEY)}")
    logger.info("="*60)


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown tasks"""
    logger.info("VÉLØ Oracle API Shutting Down")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=ENV != "production"
    )
