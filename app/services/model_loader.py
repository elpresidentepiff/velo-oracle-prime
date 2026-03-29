"""
Model loader - handles loading ML models from disk
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

from app.core import InternalModelFailure, ModelNotFoundError, log, settings


class ModelLoader:
    """Loads and caches ML models"""

    def __init__(self):
        self.registry_path = Path(settings.MODEL_REGISTRY_PATH)
        self.cache = {}

    @lru_cache(maxsize=settings.MODEL_CACHE_SIZE)  # noqa: B019
    def load_model(self, model_name: str, model_version: str) -> Any:
        """
        Load a model from disk with caching

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Loaded model object
        """
        cache_key = f"{model_name}_{model_version}"

        # Check cache first
        if cache_key in self.cache:
            log.debug(f"Model {cache_key} loaded from cache")
            return self.cache[cache_key]

        # Load from disk
        model_path = self.registry_path / model_name / model_version / "model.pkl"

        if not model_path.exists():
            log.error(f"Model file not found: {model_path}")
            raise ModelNotFoundError(f"{model_name}-{model_version}")

        try:
            log.info(f"Loading model from {model_path}")
            model = joblib.load(model_path)
            self.cache[cache_key] = model
            return model

        except Exception as e:
            log.error(f"Failed to load model {cache_key}: {e}")
            raise InternalModelFailure(f"Failed to load model: {str(e)}") from e

    def get_active_model(self) -> Any | None:
        """Get the currently active model"""
        model_name = settings.ACTIVE_MODEL_NAME
        model_version = settings.ACTIVE_MODEL_VERSION

        try:
            return self.load_model(model_name, model_version)
        except Exception as e:
            log.warning(f"Could not load active model: {e}")
            return None


# Global loader instance
model_loader = ModelLoader()
