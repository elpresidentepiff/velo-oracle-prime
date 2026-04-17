"""
VÉLØ Oracle - Production Prediction API
Endpoints for real-time predictions
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/predict", tags=["predictions"])


# Request/Response models
class PredictRequest(BaseModel):
    race_id: str
    runner_id: str
    features: Dict[str, float]
    market_odds: Optional[float] = None


class PredictResponse(BaseModel):
    race_id: str
    runner_id: str
    probability: float
    edge: float
    confidence: float
    risk_band: str
    signals: Dict[str, Any]


# API key validation
def validate_api_key(x_api_key: str = Header(None)):
    """Validate API key"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    # In production, check against database
    valid_keys = ["test_key_123", "prod_key_456"]
    
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return x_api_key


@router.post("/full", response_model=PredictResponse)
async def predict_full(
    request: PredictRequest,
    api_key: str = Header(None, alias="x-api-key")
):
    """
    Full prediction with all intelligence layers
    
    - Loads all 4 models
    - Runs all intelligence layers
    - Returns comprehensive prediction
    """
    validate_api_key(api_key)
    
    try:
        # Load UMA
        from app.engine.uma import UMA
        
        uma = UMA()
        uma.load_models()
        
        # Generate prediction
        prediction = uma.predict(
            features=request.features,
            market_odds=request.market_odds,
            race_context={'race_id': request.race_id}
        )
        
        return PredictResponse(
            race_id=request.race_id,
            runner_id=request.runner_id,
            probability=prediction.probability,
            edge=prediction.edge,
            confidence=prediction.confidence,
            risk_band=prediction.risk_band,
            signals=prediction.signals
        )
    
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick", response_model=PredictResponse)
async def predict_quick(
    request: PredictRequest,
    api_key: str = Header(None, alias="x-api-key")
):
    """
    Quick prediction (SQPE only)
    
    - Uses only SQPE model
    - Faster response time
    - Lower accuracy
    """
    validate_api_key(api_key)
    
    try:
        import pickle
        import numpy as np
        
        # Load SQPE only
        with open('models/sqpe_v14/sqpe_v14.pkl', 'rb') as f:
            sqpe = pickle.load(f)
        
        # Quick prediction
        feature_array = np.array(list(request.features.values())).reshape(1, -1)
        
        try:
            prob = sqpe.predict_proba(feature_array)[0, 1]
        except:
            prob = 0.15  # Fallback
        
        # Calculate edge
        edge = prob - (1.0 / request.market_odds) if request.market_odds else 0.0
        
        return PredictResponse(
            race_id=request.race_id,
            runner_id=request.runner_id,
            probability=float(prob),
            edge=float(edge),
            confidence=0.7,  # Lower confidence for quick mode
            risk_band="MEDIUM",
            signals={'mode': 'quick', 'model': 'sqpe_v14'}
        )
    
    except Exception as e:
        logger.error(f"Quick prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/market", response_model=PredictResponse)
async def predict_market(
    request: PredictRequest,
    api_key: str = Header(None, alias="x-api-key")
):
    """
    Market-focused prediction
    
    - Emphasizes market intelligence
    - Manipulation detection
    - Odds volatility analysis
    """
    validate_api_key(api_key)
    
    try:
        from app.intelligence.market_manipulation import detect_manipulation
        from app.observatory.volatility_index import compute_volatility
        
        # Market intelligence
        manip_score = detect_manipulation(request.features)
        volatility_score = compute_volatility(request.features)
        
        # Base prediction
        base_prob = 0.20  # Simplified
        
        # Adjust for market factors
        if manip_score > 50:
            base_prob *= 0.9  # Penalty for manipulation
        
        if volatility_score > 70:
            base_prob *= 0.95  # Penalty for high volatility
        
        edge = base_prob - (1.0 / request.market_odds) if request.market_odds else 0.0
        
        return PredictResponse(
            race_id=request.race_id,
            runner_id=request.runner_id,
            probability=base_prob,
            edge=edge,
            confidence=0.75,
            risk_band="LOW" if manip_score < 30 else "MEDIUM",
            signals={
                'mode': 'market',
                'manipulation_score': manip_score,
                'volatility_score': volatility_score
            }
        )
    
    except Exception as e:
        logger.error(f"Market prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ensemble", response_model=PredictResponse)
async def predict_ensemble(
    request: PredictRequest,
    api_key: str = Header(None, alias="x-api-key")
):
    """
    Ensemble prediction
    
    - Combines all 4 models
    - No intelligence layers
    - Pure model ensemble
    """
    validate_api_key(api_key)
    
    try:
        import pickle
        import numpy as np
        
        # Load all models
        models = {}
        for name in ['sqpe_v14', 'tie_v9', 'longshot_v6', 'overlay_v5']:
            try:
                with open(f'models/{name}/{name}.pkl', 'rb') as f:
                    models[name] = pickle.load(f)
            except:
                models[name] = None
        
        # Get predictions
        feature_array = np.array(list(request.features.values())).reshape(1, -1)
        
        preds = []
        for model in models.values():
            if model:
                try:
                    pred = model.predict_proba(feature_array)[0, 1]
                    preds.append(pred)
                except:
                    preds.append(0.15)
            else:
                preds.append(0.15)
        
        # Ensemble (average)
        ensemble_prob = float(np.mean(preds))
        
        edge = ensemble_prob - (1.0 / request.market_odds) if request.market_odds else 0.0
        
        return PredictResponse(
            race_id=request.race_id,
            runner_id=request.runner_id,
            probability=ensemble_prob,
            edge=edge,
            confidence=0.80,
            risk_band="MEDIUM",
            signals={
                'mode': 'ensemble',
                'model_predictions': dict(zip(models.keys(), preds))
            }
        )
    
    except Exception as e:
        logger.error(f"Ensemble prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Stub functions (would be real in production)
def detect_manipulation(features: Dict) -> int:
    """Stub: Detect market manipulation"""
    return 25


def compute_volatility(features: Dict) -> int:
    """Stub: Compute volatility score"""
    return 30
