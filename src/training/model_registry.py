"""
VÉLØ v10.1 - Model Registry
============================

Versioned model storage with YAML manifests.
Implements semantic versioning and model hashing.

Author: VÉLØ Oracle Team
Version: 10.1.0
"""

import os
import logging
import hashlib
import pickle
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Model registry with semantic versioning.
    
    Features:
    - Semantic versioning (MAJOR.MINOR.PATCH)
    - Model hashing for integrity
    - YAML manifest for metadata
    - Model comparison and rollback
    """
    
    def __init__(self, registry_dir: str = "out/models"):
        """
        Initialize model registry.
        
        Args:
            registry_dir: Directory for model storage
        """
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.registry_dir / "registry.yaml"
        
        # Load or create manifest
        self.manifest = self._load_manifest()
        
        logger.info(f"ModelRegistry initialized at {self.registry_dir}")
    
    def _load_manifest(self) -> Dict:
        """
        Load registry manifest.
        
        Returns:
            Manifest dictionary
        """
        if self.manifest_path.exists():
            with open(self.manifest_path, 'r') as f:
                manifest = yaml.safe_load(f)
            logger.info(f"Loaded manifest with {len(manifest.get('models', []))} models")
        else:
            manifest = {
                'registry_version': '1.0',
                'created_at': datetime.now().isoformat(),
                'models': []
            }
            logger.info("Created new manifest")
        
        return manifest
    
    def _save_manifest(self):
        """Save registry manifest."""
        with open(self.manifest_path, 'w') as f:
            yaml.dump(self.manifest, f, default_flow_style=False)
        logger.debug("Manifest saved")
    
    def register_model(
        self,
        version: str,
        fundamental_model: Any,
        market_model: Dict,
        scaler: Any,
        alpha: float,
        beta: float,
        metrics: Dict,
        feature_names: List[str],
        description: str = ""
    ) -> Path:
        """
        Register a new model version.
        
        Args:
            version: Semantic version (e.g., 'v1.0.0')
            fundamental_model: Trained fundamental model
            market_model: Market model dictionary
            scaler: Feature scaler
            alpha: Fundamental weight
            beta: Market weight
            metrics: Performance metrics
            feature_names: List of feature names
            description: Model description
        
        Returns:
            Path to saved model
        """
        logger.info(f"Registering model {version}...")
        
        # Validate version format
        if not self._validate_version(version):
            raise ValueError(f"Invalid version format: {version}")
        
        # Check if version already exists
        if self._version_exists(version):
            raise ValueError(f"Version {version} already exists")
        
        # Create version directory
        version_dir = self.registry_dir / version
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model components
        model_data = {
            'fundamental_model': fundamental_model,
            'market_model': market_model,
            'scaler': scaler,
            'alpha': alpha,
            'beta': beta,
            'feature_names': feature_names
        }
        
        model_path = version_dir / "model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        # Compute model hash
        model_hash = self._compute_hash(model_path)
        
        # Save metrics
        metrics_path = version_dir / "metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        # Create model metadata
        metadata = {
            'version': version,
            'created_at': datetime.now().isoformat(),
            'description': description,
            'model_hash': model_hash,
            'alpha': alpha,
            'beta': beta,
            'metrics': metrics,
            'n_features': len(feature_names),
            'model_path': str(model_path),
            'metrics_path': str(metrics_path)
        }
        
        # Save metadata
        metadata_path = version_dir / "metadata.yaml"
        with open(metadata_path, 'w') as f:
            yaml.dump(metadata, f, default_flow_style=False)
        
        # Update manifest
        self.manifest['models'].append(metadata)
        self.manifest['latest_version'] = version
        self.manifest['updated_at'] = datetime.now().isoformat()
        self._save_manifest()
        
        logger.info(f"Model {version} registered successfully")
        logger.info(f"  Hash: {model_hash}")
        logger.info(f"  Path: {model_path}")
        
        return model_path
    
    def load_model(self, version: str = None) -> Dict:
        """
        Load a model version.
        
        Args:
            version: Model version (None for latest)
        
        Returns:
            Model data dictionary
        """
        if version is None:
            version = self.manifest.get('latest_version')
            if version is None:
                raise ValueError("No models in registry")
        
        logger.info(f"Loading model {version}...")
        
        # Find model in manifest
        model_metadata = self._find_model(version)
        if model_metadata is None:
            raise ValueError(f"Model {version} not found")
        
        # Load model
        model_path = Path(model_metadata['model_path'])
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        
        # Verify hash
        current_hash = self._compute_hash(model_path)
        if current_hash != model_metadata['model_hash']:
            logger.warning(f"Model hash mismatch! Expected {model_metadata['model_hash']}, got {current_hash}")
        
        logger.info(f"Model {version} loaded successfully")
        
        return model_data
    
    def list_models(self) -> List[Dict]:
        """
        List all registered models.
        
        Returns:
            List of model metadata dictionaries
        """
        return self.manifest.get('models', [])
    
    def get_latest_version(self) -> Optional[str]:
        """
        Get latest model version.
        
        Returns:
            Latest version string or None
        """
        return self.manifest.get('latest_version')
    
    def compare_models(self, version1: str, version2: str) -> Dict:
        """
        Compare two model versions.
        
        Args:
            version1: First version
            version2: Second version
        
        Returns:
            Comparison dictionary
        """
        model1 = self._find_model(version1)
        model2 = self._find_model(version2)
        
        if model1 is None or model2 is None:
            raise ValueError("One or both versions not found")
        
        comparison = {
            'version1': version1,
            'version2': version2,
            'metrics_comparison': {}
        }
        
        # Compare metrics
        for metric_name in model1['metrics'].keys():
            if metric_name in model2['metrics']:
                val1 = model1['metrics'][metric_name]
                val2 = model2['metrics'][metric_name]
                diff = val2 - val1
                pct_change = (diff / val1 * 100) if val1 != 0 else 0
                
                comparison['metrics_comparison'][metric_name] = {
                    'v1': val1,
                    'v2': val2,
                    'diff': diff,
                    'pct_change': pct_change
                }
        
        return comparison
    
    def delete_model(self, version: str):
        """
        Delete a model version.
        
        Args:
            version: Version to delete
        """
        logger.warning(f"Deleting model {version}...")
        
        # Find model
        model_metadata = self._find_model(version)
        if model_metadata is None:
            raise ValueError(f"Model {version} not found")
        
        # Delete files
        version_dir = self.registry_dir / version
        if version_dir.exists():
            import shutil
            shutil.rmtree(version_dir)
        
        # Remove from manifest
        self.manifest['models'] = [
            m for m in self.manifest['models'] if m['version'] != version
        ]
        
        # Update latest if needed
        if self.manifest.get('latest_version') == version:
            if self.manifest['models']:
                self.manifest['latest_version'] = self.manifest['models'][-1]['version']
            else:
                self.manifest['latest_version'] = None
        
        self._save_manifest()
        
        logger.info(f"Model {version} deleted")
    
    def _validate_version(self, version: str) -> bool:
        """
        Validate semantic version format.
        
        Args:
            version: Version string (e.g., 'v1.0.0')
        
        Returns:
            True if valid
        """
        import re
        pattern = r'^v\d+\.\d+\.\d+$'
        return bool(re.match(pattern, version))
    
    def _version_exists(self, version: str) -> bool:
        """
        Check if version already exists.
        
        Args:
            version: Version string
        
        Returns:
            True if exists
        """
        return any(m['version'] == version for m in self.manifest.get('models', []))
    
    def _find_model(self, version: str) -> Optional[Dict]:
        """
        Find model metadata by version.
        
        Args:
            version: Version string
        
        Returns:
            Model metadata or None
        """
        for model in self.manifest.get('models', []):
            if model['version'] == version:
                return model
        return None
    
    def _compute_hash(self, file_path: Path) -> str:
        """
        Compute SHA256 hash of file.
        
        Args:
            file_path: Path to file
        
        Returns:
            Hash string
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()[:16]  # First 16 chars
    
    def print_registry(self):
        """Print formatted registry information."""
        print("\n" + "="*60)
        print("MODEL REGISTRY")
        print("="*60)
        
        models = self.list_models()
        
        if not models:
            print("\nNo models registered")
            return
        
        print(f"\nTotal models: {len(models)}")
        print(f"Latest version: {self.get_latest_version()}")
        
        print("\n" + "-"*60)
        for model in models:
            print(f"\nVersion: {model['version']}")
            print(f"Created: {model['created_at']}")
            print(f"Hash: {model['model_hash']}")
            print(f"Features: {model['n_features']}")
            print(f"α={model['alpha']:.2f}, β={model['beta']:.2f}")
            
            if 'metrics' in model:
                metrics = model['metrics']
                print(f"  AUC: {metrics.get('auc', 0):.4f}")
                print(f"  A/E: {metrics.get('ae_ratio', 0):.4f}")
                print(f"  ROI@20%: {metrics.get('roi_top20', 0):.2f}%")
        
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    # Test model registry
    logging.basicConfig(level=logging.INFO)
    
    registry = ModelRegistry()
    registry.print_registry()
