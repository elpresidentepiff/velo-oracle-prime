"""
Prediction service
"""
import numpy as np
from typing import Dict, Any, Optional
from app.core import log, settings, InternalModelFailure
from app.services.model_loader import model_loader
from app.services.model_registry import model_registry


class Predictor:
    """Handles model inference and prediction generation"""
    
    async def predict(
        self,
        features: np.ndarray,
        race_id: str,
        meta: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate prediction from features
        
        Args:
            features: Feature vector (numpy array)
            race_id: Race identifier
            meta: Optional metadata
            
        Returns:
            Dictionary with prediction, confidence, and reasoning
        """
        try:
            # Get active model
            model = model_loader.get_active_model()
            
            if model is None:
                # Fallback: return mock prediction
                log.warning("No model loaded, returning mock prediction")
                return self._mock_prediction()
            
            # Run inference
            if hasattr(model, 'predict_proba'):
                probas = model.predict_proba(features)
                prediction = float(probas[0][1]) if probas.shape[1] > 1 else float(probas[0][0])
                confidence = float(np.max(probas))
                raw_output = probas.tolist()
            elif hasattr(model, 'predict'):
                pred = model.predict(features)
                prediction = float(pred[0])
                confidence = 0.85  # Default confidence
                raw_output = pred.tolist()
            else:
                raise InternalModelFailure("Model has no predict method")
            
            # Get model version
            active_model = model_registry.get_active_model()
            model_version = f"{active_model['name']}-{active_model['version']}"
            
            # Generate reasoning
            reasoning = self._generate_reasoning(prediction, confidence)
            
            return {
                "prediction": prediction,
                "confidence": confidence,
                "model_version": model_version,
                "reasoning": reasoning,
                "raw_output": raw_output
            }
        
        except Exception as e:
            log.error(f"Prediction failed: {e}")
            raise InternalModelFailure(str(e))
    
    def _mock_prediction(self) -> Dict[str, Any]:
        """Generate mock prediction when no model is loaded"""
        return {
            "prediction": 0.35,
            "confidence": 0.75,
            "model_version": f"{settings.ACTIVE_MODEL_NAME}-{settings.ACTIVE_MODEL_VERSION}",
            "reasoning": "Mock prediction - model not loaded",
            "raw_output": [[0.65, 0.35]]
        }
    
    def _generate_reasoning(self, prediction: float, confidence: float) -> str:
        """Generate human-readable reasoning for prediction"""
        if prediction > 0.5:
            strength = "Strong" if confidence > 0.8 else "Moderate"
            return f"{strength} win probability based on feature analysis"
        else:
            return f"Lower win probability ({prediction:.2%}) - unfavorable conditions"


# Global predictor instance
predictor = Predictor()

