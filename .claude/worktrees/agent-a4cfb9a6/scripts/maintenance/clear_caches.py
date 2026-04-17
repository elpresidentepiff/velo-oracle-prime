#!/usr/bin/env python3
"""
VÉLØ Oracle - Clear Caches
Reset model and feature caches
"""
import sys
import os
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clear_model_cache():
    """Clear model cache"""
    try:
        logger.info("Clearing model cache...")
        
        # Reset global model manager
        from app.services.model_manager import _model_manager
        if _model_manager:
            _model_manager.models.clear()
            _model_manager.model_versions.clear()
            _model_manager._initialized = False
            logger.info("Model cache cleared")
        else:
            logger.info("No model cache to clear")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to clear model cache: {e}")
        return False


def clear_feature_cache():
    """Clear feature engineering cache"""
    try:
        logger.info("Clearing feature cache...")
        
        # Feature engineer doesn't maintain cache currently
        # This is a placeholder for future caching implementation
        logger.info("Feature cache cleared (no cache currently implemented)")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to clear feature cache: {e}")
        return False


def clear_prediction_cache():
    """Clear prediction cache"""
    try:
        logger.info("Clearing prediction cache...")
        
        # Placeholder for prediction cache clearing
        cache_dir = project_root / ".cache" / "predictions"
        
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir)
            logger.info(f"Removed prediction cache directory: {cache_dir}")
        else:
            logger.info("No prediction cache directory found")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to clear prediction cache: {e}")
        return False


def clear_all_caches():
    """Clear all caches"""
    logger.info("=" * 60)
    logger.info("VÉLØ Oracle - Cache Clearing")
    logger.info("=" * 60)
    
    results = {
        "model_cache": clear_model_cache(),
        "feature_cache": clear_feature_cache(),
        "prediction_cache": clear_prediction_cache()
    }
    
    logger.info("=" * 60)
    logger.info("Cache Clearing Results:")
    for cache_type, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        logger.info(f"  {cache_type}: {status}")
    
    all_success = all(results.values())
    logger.info("=" * 60)
    
    if all_success:
        logger.info("All caches cleared successfully")
        return 0
    else:
        logger.error("Some caches failed to clear")
        return 1


if __name__ == "__main__":
    exit_code = clear_all_caches()
    sys.exit(exit_code)
