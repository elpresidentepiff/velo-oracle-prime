"""
Feature engineering service
"""
import json
import numpy as np
from typing import Dict, List
from pathlib import Path
from app.core import log, settings, FeatureEngineeringError


class FeatureEngineer:
    """Transforms raw features into model-ready format"""
    
    def __init__(self):
        self.feature_map = self._load_feature_map()
    
    def _load_feature_map(self) -> Dict:
        """Load feature map configuration"""
        feature_map_path = Path(settings.FEATURE_MAP_PATH)
        
        if not feature_map_path.exists():
            log.warning(f"Feature map not found: {feature_map_path}")
            return {}
        
        try:
            with open(feature_map_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Failed to load feature map: {e}")
            return {}
    
    def transform(self, features: Dict[str, float]) -> np.ndarray:
        """
        Transform raw features into model input format
        
        Args:
            features: Dictionary of feature name -> value
            
        Returns:
            numpy array ready for model inference
        """
        try:
            # If feature map is available, use it for ordering
            if self.feature_map and "feature_names" in self.feature_map:
                feature_names = self.feature_map["feature_names"]
                feature_vector = []
                
                for name in feature_names:
                    if name not in features:
                        log.warning(f"Missing feature: {name}, using default 0.0")
                        feature_vector.append(0.0)
                    else:
                        feature_vector.append(features[name])
                
                return np.array(feature_vector).reshape(1, -1)
            
            # Fallback: use features as-is
            feature_vector = list(features.values())
            return np.array(feature_vector).reshape(1, -1)
        
        except Exception as e:
            log.error(f"Feature engineering failed: {e}")
            raise FeatureEngineeringError(str(e))
    
    def validate_features(self, features: Dict[str, float]) -> bool:
        """Validate feature dictionary"""
        if not features:
            raise FeatureEngineeringError("Empty feature dictionary")
        
        # Check for non-numeric values
        for key, value in features.items():
            if not isinstance(value, (int, float)):
                raise FeatureEngineeringError(f"Feature '{key}' must be numeric, got {type(value)}")
        
        return True


# Global feature engineer instance
feature_engineer = FeatureEngineer()

