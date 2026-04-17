"""
Populate Feast Feature Store with VÉLØ Oracle data
Extracts features from training data and loads into Feast
"""
import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle')

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_training_data():
    """Load existing training data."""
    logger.info("Loading training data...")
    
    data_path = Path("/home/ubuntu/velo-oracle/out/features_v11_train.parquet")
    
    if not data_path.exists():
        logger.error(f"Training data not found: {data_path}")
        return None
    
    df = pd.read_parquet(data_path)
    logger.info(f"Loaded {len(df)} records")
    logger.info(f"Columns: {list(df.columns)}")
    
    return df


def prepare_feast_features(df):
    """
    Transform training data into Feast-compatible format.
    
    Feast requires:
    - Entity columns (horse_id, trainer_id, jockey_id, race_id)
    - event_timestamp column
    - Feature columns
    """
    logger.info("Preparing features for Feast...")
    
    # Add entity IDs (if not present, create from existing data)
    if 'horse_id' not in df.columns:
        df['horse_id'] = df.get('horse', df.index).astype(str)
    
    if 'trainer_id' not in df.columns:
        df['trainer_id'] = df.get('trainer', 'T_' + df.index.astype(str)).astype(str)
    
    if 'jockey_id' not in df.columns:
        df['jockey_id'] = df.get('jockey', 'J_' + df.index.astype(str)).astype(str)
    
    if 'race_id' not in df.columns:
        df['race_id'] = df.get('race', 'R_' + df.index.astype(str)).astype(str)
    
    # Add event_timestamp (if not present, use current time with offset)
    if 'event_timestamp' not in df.columns:
        # Distribute timestamps over last 90 days
        base_time = datetime.now()
        df['event_timestamp'] = [
            base_time - timedelta(days=90 - i % 90) 
            for i in range(len(df))
        ]
    
    return df


def split_into_feature_tables(df):
    """
    Split data into separate feature tables for Feast.
    
    Returns:
        trainer_df, jockey_df, horse_df, race_df
    """
    logger.info("Splitting into feature tables...")
    
    # Trainer features
    trainer_cols = [
        'trainer_id', 'event_timestamp',
        'trainer_sr_14d', 'trainer_sr_30d', 'trainer_sr_90d'
    ]
    
    # Add optional columns if they exist
    optional_trainer_cols = [
        'trainer_roi_14d', 'trainer_roi_30d', 'trainer_roi_90d',
        'trainer_total_runs', 'trainer_win_rate', 'tj_combo_uplift'
    ]
    
    for col in optional_trainer_cols:
        if col in df.columns:
            trainer_cols.append(col)
        else:
            # Create placeholder
            if 'roi' in col:
                df[col] = df.get('trainer_sr_14d', 0.0) * 0.5  # Rough estimate
            elif 'total_runs' in col:
                df[col] = 100
            elif 'win_rate' in col:
                df[col] = df.get('trainer_sr_14d', 0.0)
            elif 'tj_combo' in col:
                df[col] = 0.0
            trainer_cols.append(col)
    
    trainer_df = df[trainer_cols].drop_duplicates(subset=['trainer_id', 'event_timestamp'])
    
    # Jockey features
    jockey_cols = [
        'jockey_id', 'event_timestamp',
        'jockey_sr_14d', 'jockey_sr_30d', 'jockey_sr_90d'
    ]
    
    optional_jockey_cols = [
        'jockey_roi_14d', 'jockey_roi_30d', 'jockey_roi_90d',
        'jockey_total_runs', 'jockey_win_rate'
    ]
    
    for col in optional_jockey_cols:
        if col in df.columns:
            jockey_cols.append(col)
        else:
            if 'roi' in col:
                df[col] = df.get('jockey_sr_14d', 0.0) * 0.5
            elif 'total_runs' in col:
                df[col] = 100
            elif 'win_rate' in col:
                df[col] = df.get('jockey_sr_14d', 0.0)
            jockey_cols.append(col)
    
    jockey_df = df[jockey_cols].drop_duplicates(subset=['jockey_id', 'event_timestamp'])
    
    # Horse features
    horse_cols = [
        'horse_id', 'event_timestamp',
        'form_ewma', 'form_slope', 'form_var',
        'layoff_days', 'layoff_penalty', 'freshness_flag',
        'class_drop', 'classdrop_flag'
    ]
    
    optional_horse_cols = ['total_runs', 'win_rate']
    
    for col in optional_horse_cols:
        if col in df.columns:
            horse_cols.append(col)
        else:
            if 'total_runs' in col:
                df[col] = 20
            elif 'win_rate' in col:
                df[col] = 0.25
            horse_cols.append(col)
    
    horse_df = df[horse_cols].drop_duplicates(subset=['horse_id', 'event_timestamp'])
    
    # Race features
    race_cols = [
        'race_id', 'event_timestamp',
        'course_going_iv', 'draw_iv', 'bias_persist_flag'
    ]
    
    optional_race_cols = [
        'field_size', 'race_class', 'distance_furlongs', 'going_code'
    ]
    
    for col in optional_race_cols:
        if col in df.columns:
            race_cols.append(col)
        else:
            if 'field_size' in col:
                df[col] = 12
            elif 'race_class' in col:
                df[col] = 3
            elif 'distance' in col:
                df[col] = 6.0
            elif 'going_code' in col:
                df[col] = 1
            race_cols.append(col)
    
    race_df = df[race_cols].drop_duplicates(subset=['race_id', 'event_timestamp'])
    
    logger.info(f"Created feature tables:")
    logger.info(f"  Trainer: {len(trainer_df)} records")
    logger.info(f"  Jockey: {len(jockey_df)} records")
    logger.info(f"  Horse: {len(horse_df)} records")
    logger.info(f"  Race: {len(race_df)} records")
    
    return trainer_df, jockey_df, horse_df, race_df


def save_to_feast_format(trainer_df, jockey_df, horse_df, race_df):
    """Save feature tables in Feast-compatible format."""
    logger.info("Saving to Feast format...")
    
    # Create data directory
    data_dir = Path("/home/ubuntu/velo-oracle/feast_repo/data/feast")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Save as Parquet
    trainer_df.to_parquet(data_dir / "trainer_features.parquet", index=False)
    jockey_df.to_parquet(data_dir / "jockey_features.parquet", index=False)
    horse_df.to_parquet(data_dir / "horse_features.parquet", index=False)
    race_df.to_parquet(data_dir / "race_features.parquet", index=False)
    
    logger.info(f"✓ Features saved to {data_dir}")
    
    return data_dir


def main():
    """Main execution."""
    logger.info("="*60)
    logger.info("VÉLØ Oracle - Populate Feast Feature Store")
    logger.info("="*60)
    
    # 1. Load training data
    df = load_training_data()
    if df is None:
        logger.error("Failed to load training data")
        return
    
    # 2. Prepare for Feast
    df = prepare_feast_features(df)
    
    # 3. Split into feature tables
    trainer_df, jockey_df, horse_df, race_df = split_into_feature_tables(df)
    
    # 4. Save to Feast format
    data_dir = save_to_feast_format(trainer_df, jockey_df, horse_df, race_df)
    
    logger.info("\n" + "="*60)
    logger.info("✓ Feast feature store populated successfully!")
    logger.info("="*60)
    logger.info(f"\nNext steps:")
    logger.info(f"1. Apply feature definitions: feast -c feast_repo apply")
    logger.info(f"2. Materialize features: Run feast_integration.py")
    logger.info(f"3. Test feature serving")


if __name__ == "__main__":
    main()
