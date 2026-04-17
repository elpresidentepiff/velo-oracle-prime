"""
Request validation service
"""
from typing import Dict
from app.core import log, ValidationError


class Validator:
    """Validates API requests and data"""
    
    def validate_features(self, features: Dict[str, float]) -> bool:
        """
        Validate feature dictionary
        
        Args:
            features: Dictionary of features
            
        Returns:
            True if valid
            
        Raises:
            ValidationError if invalid
        """
        if not features:
            raise ValidationError("Features dictionary cannot be empty")
        
        if not isinstance(features, dict):
            raise ValidationError("Features must be a dictionary")
        
        # Check for numeric values
        for key, value in features.items():
            if not isinstance(value, (int, float)):
                raise ValidationError(f"Feature '{key}' must be numeric, got {type(value).__name__}")
            
            # Check for NaN or Inf
            if value != value:  # NaN check
                raise ValidationError(f"Feature '{key}' contains NaN")
            
            if abs(value) == float('inf'):
                raise ValidationError(f"Feature '{key}' contains Inf")
        
        log.debug(f"Validated {len(features)} features")
        return True
    
    def validate_race_id(self, race_id: str) -> bool:
        """Validate race ID format"""
        if not race_id or not isinstance(race_id, str):
            raise ValidationError("race_id must be a non-empty string")
        
        return True


# Global validator instance
validator = Validator()

