"""
Set up Evidently AI monitoring with reference dataset
"""
import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle')

import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("="*60)
    logger.info("VÉLØ Oracle - Set Up Evidently Monitoring")
    logger.info("="*60)
    
    # Load training data as reference
    logger.info("\nLoading reference dataset (training data)...")
    data_path = Path("/home/ubuntu/velo-oracle/out/features_v11_train.parquet")
    
    if not data_path.exists():
        logger.error(f"Training data not found: {data_path}")
        return
    
    df = pd.read_parquet(data_path)
    logger.info(f"Loaded {len(df)} records")
    
    # Save as reference dataset
    reference_dir = Path("/home/ubuntu/velo-oracle/reports/evidently/reference")
    reference_dir.mkdir(parents=True, exist_ok=True)
    
    reference_path = reference_dir / "reference_data.parquet"
    df.to_parquet(reference_path, index=False)
    
    logger.info(f"\n✓ Reference dataset saved: {reference_path}")
    logger.info(f"  Records: {len(df)}")
    logger.info(f"  Features: {len(df.columns)}")
    
    # Create monitoring configuration
    config = {
        "reference_data_path": str(reference_path),
        "drift_threshold": 0.3,
        "monitoring_frequency": "weekly",
        "report_retention_days": 90
    }
    
    import json
    config_path = reference_dir / "monitoring_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"\n✓ Monitoring configuration saved: {config_path}")
    logger.info("\n" + "="*60)
    logger.info("✓ Evidently monitoring is ready!")
    logger.info("="*60)


if __name__ == "__main__":
    main()
