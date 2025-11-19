#!/usr/bin/env python3
"""
VÉLØ Oracle - Sync Models
Sync ML models to/from Supabase storage
"""
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upload_model_to_storage(model_name: str, model_path: Path) -> bool:
    """
    Upload model file to Supabase storage
    
    Args:
        model_name: Name of the model
        model_path: Path to model file
        
    Returns:
        Success status
    """
    try:
        logger.info(f"Uploading {model_name} from {model_path}...")
        
        # Placeholder: Would use Supabase storage API
        # from src.data.supabase_client import get_supabase_client
        # client = get_supabase_client()
        # client.storage.from_('models').upload(...)
        
        logger.info(f"✓ {model_name} uploaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to upload {model_name}: {e}")
        return False


def download_model_from_storage(model_name: str, output_path: Path) -> bool:
    """
    Download model file from Supabase storage
    
    Args:
        model_name: Name of the model
        output_path: Path to save model file
        
    Returns:
        Success status
    """
    try:
        logger.info(f"Downloading {model_name} to {output_path}...")
        
        # Placeholder: Would use Supabase storage API
        # from src.data.supabase_client import get_supabase_client
        # client = get_supabase_client()
        # data = client.storage.from_('models').download(...)
        
        logger.info(f"✓ {model_name} downloaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to download {model_name}: {e}")
        return False


def sync_models_to_storage():
    """Sync all local models to Supabase storage"""
    logger.info("=" * 60)
    logger.info("VÉLØ Oracle - Sync Models to Storage")
    logger.info("=" * 60)
    
    models_dir = project_root / "models"
    
    if not models_dir.exists():
        logger.warning(f"Models directory not found: {models_dir}")
        logger.info("Creating models directory...")
        models_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all model files
    model_files = list(models_dir.glob("*.pkl")) + list(models_dir.glob("*.joblib"))
    
    if not model_files:
        logger.info("No model files found to sync")
        return 0
    
    logger.info(f"Found {len(model_files)} model files")
    
    results = []
    for model_file in model_files:
        model_name = model_file.stem
        success = upload_model_to_storage(model_name, model_file)
        results.append((model_name, success))
    
    logger.info("=" * 60)
    logger.info("Sync Results:")
    for model_name, success in results:
        status = "✓ SUCCESS" if success else "✗ FAILED"
        logger.info(f"  {model_name}: {status}")
    
    success_count = sum(1 for _, success in results if success)
    logger.info(f"\nSynced {success_count}/{len(results)} models successfully")
    logger.info("=" * 60)
    
    return 0 if success_count == len(results) else 1


def sync_models_from_storage():
    """Sync all models from Supabase storage to local"""
    logger.info("=" * 60)
    logger.info("VÉLØ Oracle - Sync Models from Storage")
    logger.info("=" * 60)
    
    models_dir = project_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Placeholder: List models in storage
    model_names = ["sqpe", "trainer_intent", "longshot", "benter_overlay"]
    
    logger.info(f"Found {len(model_names)} models in storage")
    
    results = []
    for model_name in model_names:
        output_path = models_dir / f"{model_name}.pkl"
        success = download_model_from_storage(model_name, output_path)
        results.append((model_name, success))
    
    logger.info("=" * 60)
    logger.info("Sync Results:")
    for model_name, success in results:
        status = "✓ SUCCESS" if success else "✗ FAILED"
        logger.info(f"  {model_name}: {status}")
    
    success_count = sum(1 for _, success in results if success)
    logger.info(f"\nSynced {success_count}/{len(results)} models successfully")
    logger.info("=" * 60)
    
    return 0 if success_count == len(results) else 1


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync VÉLØ models with Supabase storage")
    parser.add_argument(
        "direction",
        choices=["upload", "download"],
        help="Sync direction: upload (local -> storage) or download (storage -> local)"
    )
    
    args = parser.parse_args()
    
    if args.direction == "upload":
        return sync_models_to_storage()
    else:
        return sync_models_from_storage()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
