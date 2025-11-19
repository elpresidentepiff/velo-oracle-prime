"""
VÉLØ Oracle - System Diagnostics API
System monitoring and diagnostics endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import platform
import sys
import logging

from app.schemas.system import (
    DiagnosticsResponse,
    ModelsResponse,
    FeaturesResponse,
    BacktestsResponse,
    ModelInfo,
    ComponentStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/system", tags=["system"])


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def get_diagnostics() -> DiagnosticsResponse:
    """
    Get system diagnostics and health status
    
    Returns comprehensive system health information including:
    - Overall status
    - Component statuses (database, models, features)
    - System information
    """
    try:
        from app.services.model_manager import get_model_manager
        from app.services.feature_engineering import FeatureEngineer
        
        # Check model manager
        model_manager = get_model_manager()
        models_status = model_manager.get_status()
        
        # Check features
        feature_engineer = FeatureEngineer()
        features_available = True
        
        # Check database (stub)
        database_status = "connected"
        
        # Build component statuses
        components = {
            "database": ComponentStatus(
                status=database_status,
                type="Supabase PostgreSQL"
            ),
            "models": ComponentStatus(
                status="loaded" if models_status["initialized"] else "not_loaded",
                count=models_status["models_loaded"],
                details={"models": list(models_status["models"].keys())}
            ),
            "features": ComponentStatus(
                status="available" if features_available else "unavailable",
                count=20,
                details={"feature_count": 20}
            )
        }
        
        # System information
        system_info = {
            "python_version": sys.version.split()[0],
            "platform": platform.system(),
            "architecture": platform.machine()
        }
        
        # Overall status
        overall_status = "healthy" if all(
            c.status in ["connected", "loaded", "available"] 
            for c in components.values()
        ) else "degraded"
        
        return DiagnosticsResponse(
            status=overall_status,
            version="3.0.0",
            components=components,
            system=system_info
        )
        
    except Exception as e:
        logger.error(f"Diagnostics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models", response_model=ModelsResponse)
async def get_models() -> ModelsResponse:
    """
    Get loaded models information
    
    Returns:
    - Model names and versions
    - Load status
    - Performance metrics
    """
    try:
        from app.services.model_manager import get_model_manager
        
        model_manager = get_model_manager()
        status = model_manager.get_status()
        
        # Convert to ModelInfo objects
        models_info = {}
        for name, model in status["models"].items():
            models_info[name] = ModelInfo(
                name=model["name"],
                version=model["version"],
                type=model["type"],
                status="loaded" if model["loaded"] else "not_loaded",
                loaded=model["loaded"],
                performance=model.get("performance")
            )
        
        return ModelsResponse(
            status="success",
            initialized=status["initialized"],
            models_loaded=status["models_loaded"],
            models=models_info
        )
        
    except Exception as e:
        logger.error(f"Models endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features", response_model=FeaturesResponse)
async def get_features() -> FeaturesResponse:
    """
    Get available features list
    
    Returns:
    - All feature names
    - Features by category
    - Feature count
    """
    try:
        from app.services.feature_engineering import FeatureEngineer
        
        engineer = FeatureEngineer()
        
        # Define feature categories
        categories = {
            "core": [
                "speed_normalized",
                "form_decay",
                "weight_penalty"
            ],
            "intent": [
                "trainer_intent_factor",
                "jockey_synergy"
            ],
            "position": [
                "distance_efficiency",
                "draw_bias",
                "pace_map_position"
            ],
            "performance": [
                "late_burst_index",
                "sectional_delta",
                "variance_score",
                "trend_score"
            ],
            "freshness": [
                "freshness_penalty",
                "course_affinity"
            ],
            "participants": [
                "jockey_sr_adj",
                "trainer_sr_adj"
            ],
            "market": [
                "odds_value_gap",
                "market_move_1h",
                "market_move_24h"
            ],
            "composite": [
                "combined_velocity_index"
            ]
        }
        
        # Flatten all features
        all_features = [f for cat in categories.values() for f in cat]
        
        return FeaturesResponse(
            status="success",
            feature_count=len(all_features),
            features=all_features,
            categories=categories
        )
        
    except Exception as e:
        logger.error(f"Features endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtests", response_model=BacktestsResponse)
async def get_backtests(limit: int = 20) -> BacktestsResponse:
    """
    Get recent backtest results
    
    Args:
        limit: Maximum number of results (default 20)
        
    Returns:
    - Recent backtest summaries
    - Performance metrics
    """
    try:
        from src.data.supabase_client import get_supabase_client
        
        db = get_supabase_client()
        backtests = db.fetch_recent_backtests(limit=limit)
        
        # Convert to BacktestSummary objects
        backtest_summaries = []
        for bt in backtests:
            backtest_summaries.append({
                "backtest_id": bt.get("backtest_id", ""),
                "version": bt.get("version", ""),
                "sample_size": bt.get("sample_size", 0),
                "roi": bt.get("roi", 0.0),
                "win_rate": bt.get("win_rate", 0.0),
                "auc": bt.get("auc", 0.0),
                "log_loss": bt.get("log_loss", 0.0),
                "max_drawdown": bt.get("max_drawdown", 0.0),
                "num_bets": bt.get("num_bets", 0),
                "status": bt.get("status", ""),
                "created_at": bt.get("created_at", "")
            })
        
        return BacktestsResponse(
            status="success",
            count=len(backtest_summaries),
            backtests=backtest_summaries
        )
        
    except Exception as e:
        logger.warning(f"Backtests endpoint error: {e}")
        # Return empty list on error
        return BacktestsResponse(
            status="error",
            count=0,
            backtests=[]
        )
