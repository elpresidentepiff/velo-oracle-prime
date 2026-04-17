# src/registry/model_registry.py

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Literal, Optional
import logging
from filelock import FileLock

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Type Definitions ---
ModelStage = Literal["staging", "production", "archived"]

@dataclass
class ModelRecord:
    """
    A dataclass representing a single, versioned model in the registry.
    """
    name: str
    version: str
    stage: ModelStage
    artifacts_paths: Dict[str, str]
    metadata: Dict[str, Any]
    registered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        return asdict(self)

# --- Core Registry Class ---
class ModelRegistry:
    """
    Manages the registration, retrieval, and promotion of ML models.
    
    This implementation uses a central JSON file for metadata and a corresponding
    directory structure for storing model artifacts. It is thread-safe for
    concurrent file access.
    """
    def __init__(self, registry_path: Path, models_base_dir: Path):
        self.registry_path = Path(registry_path)
        self.models_base_dir = Path(models_base_dir)
        self.lock_path = self.registry_path.with_suffix('.lock')

        # Ensure base directories exist
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.models_base_dir.mkdir(parents=True, exist_ok=True)

    def _load_registry(self) -> List[ModelRecord]:
        """Loads the registry from the JSON file, returning a list of ModelRecord objects."""
        with FileLock(self.lock_path):
            if not self.registry_path.exists():
                return []
            with open(self.registry_path, 'r') as f:
                try:
                    data = json.load(f)
                    return [ModelRecord(**record_data) for record_data in data]
                except json.JSONDecodeError:
                    logger.warning("Registry file is empty or corrupt. Starting fresh.")
                    return []

    def _save_registry(self, records: List[ModelRecord]) -> None:
        """Saves the list of ModelRecord objects to the JSON file."""
        with FileLock(self.lock_path):
            records.sort(key=lambda r: r.registered_at, reverse=True)
            with open(self.registry_path, 'w') as f:
                json.dump([r.to_dict() for r in records], f, indent=2)

    def register_model(self, record: ModelRecord) -> ModelRecord:
        """
        Registers a new model version. Ensures the version does not already exist.

        Args:
            record: A ModelRecord object describing the model to register.

        Returns:
            The registered ModelRecord.

        Raises:
            ValueError: If a model with the same name and version is already registered.
        """
        records = self._load_registry()
        
        # Validate for uniqueness
        if any(r.name == record.name and r.version == record.version for r in records):
            raise ValueError(f"Model '{record.name}' version '{record.version}' is already registered.")

        # Ensure artifact paths are valid relative to the models base directory
        for artifact_name, artifact_path in record.artifacts_paths.items():
            full_path = self.models_base_dir / artifact_path
            if not full_path.exists():
                logger.warning(f"Artifact '{artifact_name}' not found at expected path: {full_path}")
        
        records.append(record)
        self._save_registry(records)
        logger.info(f"Successfully registered model '{record.name}' version '{record.version}' with stage '{record.stage}'.")
        return record

    def get_model(self, name: str, stage: ModelStage = "production") -> Optional[ModelRecord]:
        """
        Retrieves the latest model record for a given name and stage.

        Args:
            name: The name of the model (e.g., "sqpe").
            stage: The deployment stage ("staging", "production", "archived").

        Returns:
            The latest ModelRecord matching the criteria, or None if not found.
        """
        records = self._load_registry()
        
        # Filter by name and stage, already sorted by date descending from _save_registry
        candidates = [r for r in records if r.name == name and r.stage == stage]
        
        if not candidates:
            logger.warning(f"No model found for name '{name}' and stage '{stage}'.")
            return None
            
        return candidates[0] # The first one is the latest

    def promote_model(self, name: str, version: str, new_stage: ModelStage) -> ModelRecord:
        """
        Promotes or demotes a specific model version to a new stage.
        If another model was in that stage (e.g., 'production'), it is moved to 'archived'.

        Args:
            name: The name of the model.
            version: The version of the model to promote.
            new_stage: The target stage.

        Returns:
            The updated ModelRecord for the promoted model.
        """
        if new_stage == "archived":
            # Simple case: just demote the specific version
            return self._set_model_stage(name, version, "archived")

        # Complex case: promotion to 'staging' or 'production'
        # First, find any existing model in the target stage and archive it
        current_model_in_stage = self.get_model(name, new_stage)
        if current_model_in_stage and current_model_in_stage.version != version:
            logger.info(
                f"Archiving current '{new_stage}' model '{name}' version '{current_model_in_stage.version}' "
                f"to make way for version '{version}'."
            )
            self._set_model_stage(name, current_model_in_stage.version, "archived")

        # Now, promote the new version
        promoted_record = self._set_model_stage(name, version, new_stage)
        logger.info(f"Successfully promoted model '{name}' version '{version}' to '{new_stage}'.")
        return promoted_record

    def _set_model_stage(self, name: str, version: str, stage: ModelStage) -> ModelRecord:
        """Internal helper to update the stage of a single model version."""
        records = self._load_registry()
        target_record = None
        for record in records:
            if record.name == name and record.version == version:
                record.stage = stage
                target_record = record
                break
        
        if not target_record:
            raise ValueError(f"Model '{name}' version '{version}' not found in registry.")

        self._save_registry(records)
        return target_record

    def get_champion(self, name: str) -> Optional[ModelRecord]:
        """Get the production (champion) model."""
        return self.get_model(name, stage="production")

    def get_challenger(self, name: str) -> Optional[ModelRecord]:
        """Get the staging (challenger) model."""
        return self.get_model(name, stage="staging")

# --- Default Instance ---
# Provides a singleton-like instance for easy import across the application
# Assumes project root is the parent of the 'src' directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "registry" / "models.json"
DEFAULT_MODELS_BASE_DIR = PROJECT_ROOT / "models"

default_model_registry = ModelRegistry(
    registry_path=DEFAULT_REGISTRY_PATH,
    models_base_dir=DEFAULT_MODELS_BASE_DIR
)

