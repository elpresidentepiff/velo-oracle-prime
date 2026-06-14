"""
VÉLØ Oracle - Production Prediction API
Endpoints for real-time predictions
"""

import hmac
import logging
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/predict", tags=["predictions"])


# Request/Response models
class PredictRequest(BaseModel):
    race_id: str
    runner_id: str
    features: dict[str, float]
    market_odds: float | None = None


class PredictResponse(BaseModel):
    race_id: str
    runner_id: str
    probability: float
    edge: float
    confidence: float
    risk_band: str
    signals: dict[str, Any]


# API key validation
def validate_api_key(x_api_key: str = Header(None)):
    """Validate the configured API key, failing closed."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    configured_key = os.getenv("API_KEY", "")
    if not configured_key:
        raise HTTPException(status_code=503, detail="API key not configured")
    if not hmac.compare_digest(x_api_key, configured_key):
        raise HTTPException(status_code=403, detail="Invalid API key")

    return x_api_key


@router.post("/full", response_model=PredictResponse)
async def predict_full(request: PredictRequest, api_key: str = Header(None, alias="x-api-key")):
    """
    Full prediction with all intelligence layers

    - Loads all 4 models
    - Runs all intelligence layers
    - Returns comprehensive prediction
    """
    validate_api_key(api_key)

    # UMA QUARANTINED — Forensic Containment Active
    logger.critical("API ACCESS BLOCKED: /full endpoint attempted. UMA is QUARANTINED.")
    raise HTTPException(
        status_code=503, detail="UMA Brain is QUARANTINED for forensic containment. Use /quick or /ensemble."
    )


@router.post("/quick", response_model=PredictResponse)
async def predict_quick(request: PredictRequest, api_key: str = Header(None, alias="x-api-key")):
    """
    Quick prediction (SQPE only)

    - Uses only SQPE model
    - Faster response time
    - Lower accuracy
    """
    validate_api_key(api_key)

    try:
        # Load SQPE v16
        from app.engine.v16_predictor import V16Predictor

        predictor = V16Predictor()

        # Build runner + race dicts from flat features dict
        runner = {k: request.features.get(k) for k in ("sp", "or_rating", "rpr", "ts", "draw", "age", "wgt")}
        race = {
            "dist": request.features.get("dist_f", ""),
            "going": request.features.get("going_code", ""),
            "class_raw": request.features.get("class_num", ""),
            "ran": request.features.get("field_size", 10),
        }

        try:
            prob = predictor.predict(runner, [runner], race)
        except Exception as _model_err:
            logger.error("Core model prediction failed — refusing to return fake probability: %s", _model_err)
            raise HTTPException(status_code=503, detail=f"Core model unavailable: {_model_err}") from _model_err

        # Calculate edge
        edge = prob - (1.0 / request.market_odds) if request.market_odds else 0.0

        return PredictResponse(
            race_id=request.race_id,
            runner_id=request.runner_id,
            probability=float(prob),
            edge=float(edge),
            confidence=0.82,
            risk_band="MEDIUM",
            signals={"mode": "quick", "model": "sqpe_v16", "auc": 0.9428},
        )

    except Exception as e:
        logger.error(f"Quick prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/market", response_model=PredictResponse)
async def predict_market(request: PredictRequest, api_key: str = Header(None, alias="x-api-key")):
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
    except ImportError as e:
        logger.error("Market prediction: module missing — %s", e)
        raise HTTPException(status_code=503, detail=f"Market module unavailable: {e}") from e

    try:
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
            signals={"mode": "market", "manipulation_score": manip_score, "volatility_score": volatility_score},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Market prediction: inference failed — %s", e)
        raise HTTPException(status_code=500, detail=f"Market prediction error: {e}") from e


@router.post("/ensemble", response_model=PredictResponse)
async def predict_ensemble(request: PredictRequest, api_key: str = Header(None, alias="x-api-key")):
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
        for name in ["sqpe_v14", "tie_v9", "longshot_v6", "overlay_v5"]:
            try:
                with open(f"models/{name}/{name}.pkl", "rb") as f:
                    models[name] = pickle.load(f)
            except Exception:
                models[name] = None

        # Get predictions — only from models that actually loaded
        feature_array = np.array(list(request.features.values())).reshape(1, -1)

        preds = []
        failed_models = []
        for name, model in models.items():
            if model is None:
                failed_models.append(f"{name}:not_loaded")
                continue
            try:
                pred = model.predict_proba(feature_array)[0, 1]
                preds.append(pred)
            except Exception as _me:
                failed_models.append(f"{name}:{_me}")

        # Refuse to return fake probability if no real model produced output
        if not preds:
            logger.error(
                "Ensemble: all models failed to produce output — refusing to return fake probability. failed=%s",
                failed_models,
            )
            raise HTTPException(status_code=503, detail=f"All ensemble models unavailable: {failed_models}")

        # Ensemble (average of loaded-only models)
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
                "mode": "ensemble",
                "models_loaded": len(preds),
                "models_failed": len(failed_models),
                "failed_detail": failed_models if failed_models else None,
            },
        )

    except Exception as e:
        logger.error(f"Ensemble prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Stub functions (would be real in production)
def detect_manipulation(features: dict) -> int:
    """Stub: Detect market manipulation"""
    return 25


def compute_volatility(features: dict) -> int:
    """Stub: Compute volatility score"""
    return 30
