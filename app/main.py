"""
VÉLØ Oracle - FastAPI Main Application
Production-ready with CORS, health checks, and API routing
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_sentient_state: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models once at startup, release on shutdown."""
    global _sentient_state
    from app.services.model_manager import get_model_manager
    mm = get_model_manager()
    logger.info(f"Models initialised at startup: {mm.model_versions}")

    # Sentient bridge — Phase 1 (audit only, no scoring change)
    try:
        from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
        _g = SentientLoopbackEngine()
        _raw = _g.get_evolutionary_state()
        _source = "disk" if _raw.get("total_races_observed", 0) > 0 else "unknown"
        _sentient_state = {**_raw, "_source": _source}
        logger.info(
            "[sentient] G state loaded at startup — source=%s races_observed=%d aggression=%.3f",
            _source,
            _raw.get("total_races_observed", 0),
            _raw.get("appetite_state", {}).get("aggression_level", -1.0),
        )
    except Exception as e:
        _sentient_state = None
        logger.warning("[sentient] G state load failed at startup (non-fatal): %s", e)

    yield
    logger.info("VÉLØ Oracle API shutting down")


# Create FastAPI app
app = FastAPI(
    title="VÉLØ Oracle API",
    version="v1.0",
    description="Production horse racing prediction engine",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
    Quick single-runner prediction (SQPE v17 + VELO_PRIME_prob where available).

    Accepts: {"runner": {...}, "race": {...}}
    Returns: probability, velo_prime_prob, overlay, model_version
    """
    try:
        from app.services.model_manager import get_model_manager
        from workers.racing_api_normalizer import normalize_runner, normalize_race

        mm     = get_model_manager()
        runner = race_data.get("runner", {})
        race   = race_data.get("race", {})

        # Normalize inputs through canonical schema
        norm_runner = normalize_runner(runner)
        norm_race   = normalize_race({**race, "runners": [runner]})

        sqpe_prob = mm.predict_sqpe(runner=norm_runner, race=norm_race)

        odds    = norm_runner.get("best_odds_decimal") or 0
        overlay = mm.detect_overlay(sqpe_prob, float(odds)) if odds else {"is_overlay": False, "edge": 0.0}

        return {
            "probability":     round(sqpe_prob, 4),
            "velo_prime_prob": round(sqpe_prob, 4),   # same as SQPE for single-runner; use /predict/race for full ensemble
            "overlay":         overlay,
            "model_version":   mm.model_versions.get("sqpe", "unknown"),
            "ensemble_version": "sqpe_only_single_runner",
        }

    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/predict/race")
async def predict_race(
    race_data: dict,
    persist: bool = False,
    authorized: bool = Depends(verify_api_key)
):
    """
    Full race prediction using VELO_PRIME_prob meta-ensemble.

    Accepts a normalized race dict (output of racing_api_normalizer.normalize_race())
    OR a raw Racing API Standard racecard entry.

    Query param:  ?persist=true  to write top verdict to velo_verdicts in Supabase.

    Returns:
        Ranked list of runners with velo_prime_prob + all specialist scores
        + macro regime context.
    """
    try:
        from workers.racing_api_normalizer import normalize_race
        from app.services.velo_prime_service import score_race_velo_prime, persist_race_predictions

        # Accept either pre-normalized or raw racecard
        if "runners" not in race_data:
            raise HTTPException(status_code=400, detail="race_data must contain 'runners' list")

        norm_race   = normalize_race(race_data)
        predictions = score_race_velo_prime(norm_race, sentient_state=_sentient_state)

        if persist:
            persist_race_predictions(norm_race, predictions)

        return {
            "race_id":          norm_race.get("race_id"),
            "course":           norm_race.get("course"),
            "off_time":         norm_race.get("off_time"),
            "field_size":       len(norm_race.get("runners", [])),
            "ensemble_version": "velo_prime_v1",
            "predictions":      predictions,
            "top_pick":         predictions[0] if predictions else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Race prediction failed: {e}")
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

        race = race_data.get("race", race_data)
        runners = race_data.get("runners", [])

        result = await run_prediction_chain(race, runners)

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
        from workers.racing_api_fetcher import RacingAPIFetcher
        fetcher = RacingAPIFetcher()
        race = fetcher.get_race(race_id)
        result = await run_narrative_chain(race)
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
        from workers.racing_api_fetcher import RacingAPIFetcher
        fetcher = RacingAPIFetcher()
        race = fetcher.get_race(race_id)
        result = await run_market_chain(race, odds_history=[])
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


# Startup/shutdown are handled by the lifespan context manager above.


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=ENV != "production"
    )
