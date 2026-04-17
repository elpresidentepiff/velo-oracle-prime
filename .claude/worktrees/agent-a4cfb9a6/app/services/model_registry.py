"""
Model registry - manages available ML models
"""
import os
import json
from typing import Optional, Dict, List, Any
from pathlib import Path
from app.core import log, settings, ModelNotFoundError


class ModelRegistry:
    """Manages ML model registration and metadata"""
    
    def __init__(self):
        self.registry_path = Path(settings.MODEL_REGISTRY_PATH)
        self.active_model = None
        self.models_cache = {}
        
    def scan_models(self) -> List[Dict[str, Any]]:
        """Scan model directory and load metadata"""
        models = []
        
        if not self.registry_path.exists():
            log.warning(f"Model registry path does not exist: {self.registry_path}")
            return models
        
        for model_dir in self.registry_path.iterdir():
            if model_dir.is_dir():
                metadata_path = model_dir / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                            models.append(metadata)
                            self.models_cache[metadata.get('name')] = metadata
                    except Exception as e:
                        log.error(f"Failed to load metadata from {metadata_path}: {e}")
        
        return models
    
    def get_active_model(self) -> Optional[Dict[str, Any]]:
        """Get currently active model metadata"""
        if self.active_model:
            return self.active_model
        
        # Try to load from settings
        model_name = settings.ACTIVE_MODEL_NAME
        model_version = settings.ACTIVE_MODEL_VERSION
        
        if model_name in self.models_cache:
            self.active_model = self.models_cache[model_name]
            return self.active_model
        
        # Fallback: return placeholder
        return {
            "name": model_name,
            "version": model_version,
            "status": "registered"
        }
    
    def set_active_model(self, model_name: str):
        """Set the active model"""
        if model_name not in self.models_cache:
            raise ModelNotFoundError(model_name)
        
        self.active_model = self.models_cache[model_name]
        log.info(f"Active model set to: {model_name}")
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all available models"""
        if not self.models_cache:
            self.scan_models()
        
        return list(self.models_cache.values())
    
    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded"""
        return self.active_model is not None


# Global registry instance
model_registry = ModelRegistry()

