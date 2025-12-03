"""
Features API Router
Provides endpoints for feature serving via Feast
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle')

from src.features.feast_integration import VeloFeatureStore

router = APIRouter(prefix="/features", tags=["features"])

# Initialize Feast feature store
try:
    feature_store = VeloFeatureStore()
    print("✓ Feast Feature Store initialized")
except Exception as e:
    print(f"⚠ Failed to initialize Feast: {e}")
    feature_store = None


class FeatureRequest(BaseModel):
    """Request model for feature retrieval."""
    horse_id: str
    trainer_id: str
    jockey_id: str
    race_id: str
    odds: Optional[float] = None


class FeatureResponse(BaseModel):
    """Response model for feature retrieval."""
    features: Dict
    latency_ms: float


@router.post("/get_online_features", response_model=FeatureResponse)
async def get_online_features(request: FeatureRequest):
    """
    Get features for online inference (low-latency).
    
    Returns all features needed for prediction in <10ms.
    """
    if feature_store is None:
        raise HTTPException(status_code=503, detail="Feature store not available")
    
    import time
    start_time = time.time()
    
    try:
        # Get online features
        features = feature_store.get_online_features(
            horse_id=request.horse_id,
            trainer_id=request.trainer_id,
            jockey_id=request.jockey_id,
            race_id=request.race_id
        )
        
        # Add request-time features
        if request.odds is not None:
            features['odds'] = request.odds
        
        latency_ms = (time.time() - start_time) * 1000
        
        return FeatureResponse(
            features=features,
            latency_ms=latency_ms
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feature retrieval failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Check if feature store is operational."""
    if feature_store is None:
        return {
            "status": "degraded",
            "message": "Feature store not initialized"
        }
    
    return {
        "status": "healthy",
        "message": "Feature store operational"
    }


@router.get("/stats")
async def get_feature_stats():
    """Get feature store statistics."""
    if feature_store is None:
        raise HTTPException(status_code=503, detail="Feature store not available")
    
    try:
        # Get feature views
        feature_views = feature_store.store.list_feature_views()
        
        stats = {
            "feature_views": len(feature_views),
            "feature_view_names": [fv.name for fv in feature_views],
            "online_store_type": feature_store.store.config.online_store.type,
            "offline_store_type": feature_store.store.config.offline_store.type
        }
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
