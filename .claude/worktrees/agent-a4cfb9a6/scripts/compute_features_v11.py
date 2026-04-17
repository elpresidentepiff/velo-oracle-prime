"""
VÉLØ v1.1.0 - Feature Computation Script
=========================================

Compute 21 production features for training set.
Filter to 5.0-21.0 odds range (avoid favorite tax).
Save to parquet for training.

Author: VÉLØ Oracle Team
Version: 10.2.0
"""

import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle')

import logging
from pathlib import Path
import pandas as pd
import numpy as np
from src.features.builder_v11 import FeatureBuilderV11

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_sp_to_decimal(sp_str):
    """Convert SP string to decimal odds."""
    if pd.isna(sp_str) or sp_str == '':
        return None
    
    sp_str = str(sp_str).strip()
    sp_str = sp_str.replace('F', '').replace('J', '').strip()
    
    if '/' in sp_str:
        try:
            parts = sp_str.split('/')
            numerator = float(parts[0])
            denominator = float(parts[1])
            return (numerator / denominator) + 1.0
        except:
            return None
    
    try:
        return float(sp_str)
    except:
        return None


def main():
    """Main feature computation script."""
    logger.info("="*60)
    logger.info("VÉLØ v1.1.0 - FEATURE COMPUTATION")
    logger.info("="*60)
    
    # Paths
    project_dir = Path("/home/ubuntu/velo-oracle")
    db_path = project_dir / "velo_racing.db"
    output_dir = project_dir / "out"
    output_dir.mkdir(exist_ok=True)
    
    # Initialize feature builder
    logger.info("\nInitializing feature builder...")
    builder = FeatureBuilderV11(str(db_path))
    
    # Build features for SAMPLE (10K records for v1.1.0 validation)
    logger.info("\nBuilding features for 10K record sample...")
    logger.info("This will take 2-3 minutes...")
    
    df = builder.build_all_features(sample_size=10000)
    
    logger.info(f"\n✅ Features computed: {len(df):,} records")
    
    # Filter to training period (before 2024-07-01)
    logger.info("\nFiltering to training period (2015 - 2024-06-30)...")
    df['date'] = pd.to_datetime(df['date'])
    df_train = df[df['date'] < '2024-07-01'].copy()
    logger.info(f"  Training records: {len(df_train):,}")
    
    # Parse SP to decimal odds
    logger.info("\nParsing starting prices...")
    df_train['odds'] = df_train['sp'].apply(parse_sp_to_decimal)
    df_train = df_train[df_train['odds'].notna()]
    logger.info(f"  Records with valid odds: {len(df_train):,}")
    
    # Filter to 5.0-21.0 odds range (avoid favorite tax)
    logger.info("\nFiltering to 5.0-21.0 odds range...")
    df_train = df_train[(df_train['odds'] >= 5.0) & (df_train['odds'] <= 21.0)]
    logger.info(f"  Final training set: {len(df_train):,} records")
    
    # Create win label
    df_train['win'] = (df_train['pos'] == '1').astype(int)
    win_rate = df_train['win'].mean()
    logger.info(f"  Win rate: {win_rate*100:.2f}%")
    
    # Save to parquet
    output_path = output_dir / "features_v11_train.parquet"
    logger.info(f"\nSaving to {output_path}...")
    df_train.to_parquet(output_path, index=False)
    
    # Feature summary
    feature_cols = builder.get_feature_names()
    logger.info("\n" + "="*60)
    logger.info("FEATURE SUMMARY")
    logger.info("="*60)
    
    for col in feature_cols:
        if col in df_train.columns:
            null_pct = df_train[col].isna().mean() * 100
            mean_val = df_train[col].mean()
            std_val = df_train[col].std()
            logger.info(f"  {col:25s} | Null: {null_pct:5.2f}% | Mean: {mean_val:8.4f} | Std: {std_val:8.4f}")
    
    logger.info("\n" + "="*60)
    logger.info("FEATURE COMPUTATION COMPLETE")
    logger.info("="*60)
    logger.info(f"Output: {output_path}")
    logger.info(f"Records: {len(df_train):,}")
    logger.info(f"Features: {len(feature_cols)}")
    logger.info(f"Odds range: 5.0-21.0")
    logger.info(f"Win rate: {win_rate*100:.2f}%")
    logger.info("="*60)


if __name__ == "__main__":
    main()
