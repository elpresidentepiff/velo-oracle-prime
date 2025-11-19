"""
VÉLØ Oracle - Model Ops Validator
Model validation and schema checking
"""
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def validate_model_schema(model: Dict[str, Any]) -> bool:
    """
    Validate model schema has required fields
    
    Args:
        model: Model dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        "name",
        "version",
        "type",
        "loaded",
        "features",
        "performance"
    ]
    
    for field in required_fields:
        if field not in model:
            logger.error(f"❌ Model schema validation failed: missing '{field}'")
            return False
    
    # Validate types
    if not isinstance(model["name"], str):
        logger.error("❌ Model 'name' must be string")
        return False
    
    if not isinstance(model["version"], str):
        logger.error("❌ Model 'version' must be string")
        return False
    
    if not isinstance(model["features"], list):
        logger.error("❌ Model 'features' must be list")
        return False
    
    if not isinstance(model["performance"], dict):
        logger.error("❌ Model 'performance' must be dict")
        return False
    
    logger.info(f"✅ Model schema valid: {model['name']}")
    return True


def validate_feature_map(feature_map: Dict[str, Any]) -> bool:
    """
    Validate feature map has all required features
    
    Args:
        feature_map: Dictionary of features
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(feature_map, dict):
        logger.error("❌ Feature map must be dictionary")
        return False
    
    if len(feature_map) == 0:
        logger.error("❌ Feature map is empty")
        return False
    
    # Check all values are numeric
    for key, value in feature_map.items():
        if not isinstance(value, (int, float)):
            logger.error(f"❌ Feature '{key}' has non-numeric value: {type(value)}")
            return False
        
        # Check for NaN or inf
        if value != value:  # NaN check
            logger.error(f"❌ Feature '{key}' is NaN")
            return False
        
        if abs(value) == float('inf'):
            logger.error(f"❌ Feature '{key}' is infinite")
            return False
    
    logger.info(f"✅ Feature map valid: {len(feature_map)} features")
    return True


def validate_version(model: Dict[str, Any], expected_version: str) -> bool:
    """
    Validate model version matches expected version
    
    Args:
        model: Model dictionary
        expected_version: Expected version string
        
    Returns:
        True if versions match, False otherwise
    """
    actual_version = model.get("version", "")
    
    if actual_version != expected_version:
        logger.error(
            f"❌ Version mismatch: expected '{expected_version}', "
            f"got '{actual_version}'"
        )
        return False
    
    logger.info(f"✅ Version validated: {actual_version}")
    return True


def validate_performance_metrics(performance: Dict[str, float]) -> bool:
    """
    Validate performance metrics are within acceptable ranges
    
    Args:
        performance: Performance metrics dictionary
        
    Returns:
        True if valid, False otherwise
    """
    # Check accuracy
    if "accuracy" in performance:
        acc = performance["accuracy"]
        if not (0.0 <= acc <= 1.0):
            logger.error(f"❌ Accuracy out of range: {acc}")
            return False
    
    # Check AUC
    if "auc" in performance:
        auc = performance["auc"]
        if not (0.0 <= auc <= 1.0):
            logger.error(f"❌ AUC out of range: {auc}")
            return False
    
    # Check log loss
    if "log_loss" in performance:
        ll = performance["log_loss"]
        if ll < 0:
            logger.error(f"❌ Log loss negative: {ll}")
            return False
    
    # Check ROI
    if "roi" in performance:
        roi = performance["roi"]
        if roi < 0:
            logger.warning(f"⚠️ Negative ROI: {roi}")
    
    logger.info("✅ Performance metrics valid")
    return True


def validate_model_complete(model: Dict[str, Any], expected_version: str = None) -> bool:
    """
    Complete model validation
    
    Args:
        model: Model dictionary
        expected_version: Optional expected version
        
    Returns:
        True if all validations pass
    """
    logger.info(f"Validating model: {model.get('name', 'Unknown')}")
    
    # Schema validation
    if not validate_model_schema(model):
        return False
    
    # Version validation
    if expected_version and not validate_version(model, expected_version):
        return False
    
    # Performance validation
    if not validate_performance_metrics(model.get("performance", {})):
        return False
    
    logger.info(f"✅ Model fully validated: {model['name']}")
    return True


def validate_prediction_output(prediction: Dict[str, Any]) -> bool:
    """
    Validate prediction output format
    
    Args:
        prediction: Prediction dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        "runner_id",
        "runner_name",
        "final_probability"
    ]
    
    for field in required_fields:
        if field not in prediction:
            logger.error(f"❌ Prediction missing field: {field}")
            return False
    
    # Validate probability
    prob = prediction.get("final_probability")
    if not isinstance(prob, (int, float)):
        logger.error(f"❌ Probability not numeric: {type(prob)}")
        return False
    
    if not (0.0 <= prob <= 1.0):
        logger.error(f"❌ Probability out of range: {prob}")
        return False
    
    logger.info("✅ Prediction output valid")
    return True


def validate_batch_predictions(predictions: List[Dict[str, Any]]) -> bool:
    """
    Validate batch of predictions
    
    Args:
        predictions: List of prediction dictionaries
        
    Returns:
        True if all valid, False otherwise
    """
    if not predictions:
        logger.error("❌ Empty predictions list")
        return False
    
    for i, pred in enumerate(predictions):
        if not validate_prediction_output(pred):
            logger.error(f"❌ Prediction {i} invalid")
            return False
    
    logger.info(f"✅ Batch predictions valid: {len(predictions)} predictions")
    return True
