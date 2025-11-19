"""
Prediction endpoint
"""
import time
from fastapi import APIRouter, HTTPException
from app.schemas import PredictRequest, PredictResponse
from app.core import log, ValidationError, InternalModelFailure
from app.services.predictor import predictor
from app.services.feature_engineering import feature_engineer
from app.services.validation import validator

router = APIRouter()


@router.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    """
    Make a prediction for a race
    
    Steps:
    1. Validate request payload
    2. Engineer features
    3. Load model
    4. Generate prediction
    5. Return response with confidence and reasoning
    """
    start_time = time.time()
    
    try:
        # Step 1: Validate request
        log.info(f"Prediction request for race_id: {request.race_id}")
        validator.validate_features(request.features)
        
        # Step 2: Feature engineering
        feature_vector = feature_engineer.transform(request.features)
        
        # Step 3 & 4: Get prediction
        result = await predictor.predict(
            features=feature_vector,
            race_id=request.race_id,
            meta=request.meta
        )
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        
        return PredictResponse(
            prediction=result["prediction"],
            confidence=result["confidence"],
            model_version=result["model_version"],
            processing_time_ms=round(processing_time, 2),
            reasoning=result.get("reasoning", "Prediction generated successfully"),
            raw_output=result.get("raw_output")
        )
    
    except ValidationError as e:
        log.warning(f"Validation error: {e.detail}")
        raise e
    
    except InternalModelFailure as e:
        log.error(f"Model failure: {e.detail}")
        raise e
    
    except Exception as e:
        log.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

