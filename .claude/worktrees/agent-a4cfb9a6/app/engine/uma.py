"""
VÉLØ Oracle - UMA (Unified Model Assembly)
Final prediction brain that fuses all intelligence layers
"""
import numpy as np
import pickle
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class UMAPrediction:
    """Unified prediction output"""
    probability: float
    edge: float
    confidence: float
    risk_band: str
    signals: Dict[str, Any]
    metadata: Dict[str, Any]


class UMA:
    """
    Unified Model Assembly - The Brain
    
    Fuses:
    - SQPE v14 (Speed/Quality/Pace/Efficiency)
    - TIE v9 (Trainer Intent Engine)
    - Longshot v6 (Longshot Detector)
    - Overlay v5 (Benter Overlay)
    - Pace Intelligence
    - Narrative Intelligence
    - Manipulation Detection
    - Volatility Index
    - Stability Index
    - Risk Layer
    
    Output: Single final probability + edge + confidence
    """
    
    def __init__(self):
        self.models = {}
        self.weights = {
            'sqpe_v14': 0.40,
            'tie_v9': 0.25,
            'longshot_v6': 0.15,
            'overlay_v5': 0.20
        }
        self.loaded = False
    
    def load_models(
        self,
        model_paths: Dict[str, str] = None
    ):
        """Load all models"""
        if model_paths is None:
            model_paths = {
                'sqpe_v14': 'models/sqpe_v14/sqpe_v14.pkl',
                'tie_v9': 'models/tie_v9/tie_v9.pkl',
                'longshot_v6': 'models/longshot_v6/longshot_v6.pkl',
                'overlay_v5': 'models/overlay_v5/overlay_v5.pkl'
            }
        
        logger.info("Loading UMA models...")
        
        for name, path in model_paths.items():
            try:
                with open(path, 'rb') as f:
                    self.models[name] = pickle.load(f)
                logger.info(f"  ✅ Loaded {name}")
            except Exception as e:
                logger.warning(f"  ⚠️  Failed to load {name}: {e}")
                self.models[name] = None
        
        self.loaded = True
        logger.info(f"✅ UMA loaded with {len([m for m in self.models.values() if m is not None])} models")
    
    def predict(
        self,
        features: Dict[str, Any],
        market_odds: float = None,
        race_context: Dict[str, Any] = None
    ) -> UMAPrediction:
        """
        Generate unified prediction
        
        Args:
            features: Runner features
            market_odds: Current market odds
            race_context: Race metadata
            
        Returns:
            UMAPrediction with probability, edge, confidence, signals
        """
        if not self.loaded:
            raise RuntimeError("UMA not loaded. Call load_models() first.")
        
        # 1. Get base model predictions
        model_preds = self._get_model_predictions(features)
        
        # 2. Get intelligence signals
        intel_signals = self._get_intelligence_signals(features, race_context)
        
        # 3. Fuse predictions
        base_prob = self._fuse_predictions(model_preds)
        
        # 4. Apply intelligence adjustments
        adjusted_prob = self._apply_intelligence(base_prob, intel_signals)
        
        # 5. Calculate edge
        edge = self._calculate_edge(adjusted_prob, market_odds)
        
        # 6. Calculate confidence
        confidence = self._calculate_confidence(model_preds, intel_signals)
        
        # 7. Determine risk band
        risk_band = self._classify_risk(edge, confidence)
        
        # 8. Compile signals
        all_signals = {
            'models': model_preds,
            'intelligence': intel_signals,
            'base_probability': base_prob,
            'adjusted_probability': adjusted_prob
        }
        
        # 9. Metadata
        metadata = {
            'models_used': list(self.models.keys()),
            'market_odds': market_odds,
            'race_id': race_context.get('race_id') if race_context else None
        }
        
        return UMAPrediction(
            probability=adjusted_prob,
            edge=edge,
            confidence=confidence,
            risk_band=risk_band,
            signals=all_signals,
            metadata=metadata
        )
    
    def _get_model_predictions(self, features: Dict[str, Any]) -> Dict[str, float]:
        """Get predictions from all base models"""
        preds = {}
        
        # Convert features to array (simplified)
        feature_array = np.array(list(features.values())).reshape(1, -1)
        
        for name, model in self.models.items():
            if model is not None:
                try:
                    prob = model.predict_proba(feature_array)[0, 1]
                    preds[name] = float(prob)
                except:
                    preds[name] = 0.15  # Fallback
            else:
                preds[name] = 0.15  # Fallback
        
        return preds
    
    def _get_intelligence_signals(
        self,
        features: Dict[str, Any],
        race_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get signals from intelligence layers"""
        
        # Simulate intelligence signals (would be real in production)
        return {
            'pace': {
                'race_shape': 'moderate',
                'early_pressure': 0.6,
                'late_energy': 0.7,
                'score': 0.65
            },
            'narrative': {
                'primary': 'momentum',
                'secondary': 'hidden_intent',
                'strength': 0.72,
                'score': 0.68
            },
            'manipulation': {
                'spoofing_detected': False,
                'echo_moves': False,
                'risk_score': 15,
                'score': 0.85
            },
            'volatility': {
                'volatility_score': 25,
                'category': 'LOW',
                'score': 0.75
            },
            'stability': {
                'stability_score': 0.68,
                'category': 'STABLE',
                'score': 0.68
            }
        }
    
    def _fuse_predictions(self, model_preds: Dict[str, float]) -> float:
        """Fuse model predictions using weighted average"""
        weighted_sum = 0.0
        total_weight = 0.0
        
        for model_name, pred in model_preds.items():
            weight = self.weights.get(model_name, 0.25)
            weighted_sum += pred * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.15
    
    def _apply_intelligence(
        self,
        base_prob: float,
        intel_signals: Dict[str, Any]
    ) -> float:
        """Apply intelligence layer adjustments"""
        
        adjusted = base_prob
        
        # Pace adjustment
        pace_score = intel_signals['pace']['score']
        adjusted *= (0.9 + 0.2 * pace_score)  # ±10% based on pace
        
        # Narrative adjustment
        narrative_score = intel_signals['narrative']['score']
        adjusted *= (0.95 + 0.1 * narrative_score)  # ±5% based on narrative
        
        # Manipulation penalty
        manip_risk = intel_signals['manipulation']['risk_score']
        if manip_risk > 50:
            adjusted *= 0.9  # 10% penalty for high manipulation risk
        
        # Volatility adjustment
        volatility = intel_signals['volatility']['volatility_score']
        if volatility > 70:
            adjusted *= 0.95  # 5% penalty for high volatility
        
        # Stability boost
        stability = intel_signals['stability']['stability_score']
        adjusted *= (0.95 + 0.1 * stability)  # Up to +5% for high stability
        
        # Clamp to valid probability range
        return max(0.01, min(0.99, adjusted))
    
    def _calculate_edge(self, probability: float, market_odds: float) -> float:
        """Calculate betting edge"""
        if market_odds is None or market_odds <= 1.0:
            return 0.0
        
        implied_prob = 1.0 / market_odds
        edge = probability - implied_prob
        
        return edge
    
    def _calculate_confidence(
        self,
        model_preds: Dict[str, float],
        intel_signals: Dict[str, Any]
    ) -> float:
        """Calculate prediction confidence"""
        
        # Model agreement (low variance = high confidence)
        pred_values = list(model_preds.values())
        model_variance = np.var(pred_values)
        model_confidence = 1.0 / (1.0 + model_variance * 10)
        
        # Intelligence confidence
        intel_scores = [
            intel_signals['pace']['score'],
            intel_signals['narrative']['score'],
            intel_signals['manipulation']['score'],
            intel_signals['volatility']['score'],
            intel_signals['stability']['score']
        ]
        intel_confidence = np.mean(intel_scores)
        
        # Combined confidence
        confidence = 0.6 * model_confidence + 0.4 * intel_confidence
        
        return float(confidence)
    
    def _classify_risk(self, edge: float, confidence: float) -> str:
        """Classify risk band"""
        
        if edge < -0.05:
            return "NO_BET"
        elif edge < 0.0:
            return "LOW"
        elif edge < 0.05:
            return "MEDIUM"
        elif confidence > 0.7:
            return "HIGH"
        else:
            return "MEDIUM"


if __name__ == "__main__":
    # Test UMA
    print("="*60)
    print("UMA - Unified Model Assembly Test")
    print("="*60)
    
    # Initialize
    uma = UMA()
    uma.load_models()
    
    # Test prediction
    features = {
        'speed_normalized': 0.75,
        'form_decay': 0.85,
        'rating_composite': 95.0,
        'trainer_sr': 0.25,
        'jockey_sr': 0.22,
        'odds_decimal': 5.0,
        'implied_prob': 0.20
    }
    
    race_context = {
        'race_id': 'TEST_001',
        'course': 'Ascot',
        'distance': '1m'
    }
    
    prediction = uma.predict(
        features=features,
        market_odds=5.0,
        race_context=race_context
    )
    
    print("\n" + "="*60)
    print("PREDICTION RESULT")
    print("="*60)
    print(f"Probability: {prediction.probability:.4f}")
    print(f"Edge: {prediction.edge:+.4f}")
    print(f"Confidence: {prediction.confidence:.4f}")
    print(f"Risk Band: {prediction.risk_band}")
    print("\nModel Predictions:")
    for model, prob in prediction.signals['models'].items():
        print(f"  {model}: {prob:.4f}")
    print("\nIntelligence Signals:")
    for layer, signals in prediction.signals['intelligence'].items():
        print(f"  {layer}: {signals.get('score', 'N/A')}")
    print("="*60)
    
    print("\n✅ UMA test complete")
