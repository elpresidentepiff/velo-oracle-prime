"""
VÉLØ v10.1 - Model Training Script
===================================

Train Benter model on 1.96M historical records.

Author: VÉLØ Oracle Team
Version: 10.1.0
"""

import sys
import os
sys.path.insert(0, '/home/ubuntu/velo-oracle')

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import pickle
import json

from src.training import (
    FeatureStore,
    LabelCreator,
    ModelMetrics,
    BenterTrainer,
    ModelRegistry
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_training_data(db_path: str, train_end_date: str, val_days: int = 90):
    """
    Load training and validation data from database.
    
    Args:
        db_path: Path to SQLite database
        train_end_date: End date for training (validation starts after)
        val_days: Number of days for validation
    
    Returns:
        Tuple of (train_df, val_df)
    """
    logger.info(f"Loading data from {db_path}...")
    
    conn = sqlite3.connect(db_path)
    
    # Parse dates
    train_end = datetime.strptime(train_end_date, '%Y-%m-%d')
    val_start = train_end + timedelta(days=1)
    val_end = val_start + timedelta(days=val_days)
    
    logger.info(f"Training: up to {train_end.date()}")
    logger.info(f"Validation: {val_start.date()} to {val_end.date()}")
    
    # Load training data (sample for speed)
    logger.info("Loading training data (sampling 100K records)...")
    train_query = f"""
        SELECT * FROM racing_data 
        WHERE date <= '{train_end_date}'
        AND pos NOT IN ('PU', 'F', 'U', 'BD', 'RO', 'SU', 'UR')
        AND sp IS NOT NULL
        AND sp != ''
        ORDER BY RANDOM()
        LIMIT 100000
    """
    train_df = pd.read_sql_query(train_query, conn)
    
    # Load validation data
    logger.info("Loading validation data...")
    val_query = f"""
        SELECT * FROM racing_data 
        WHERE date > '{train_end_date}'
        AND date <= '{val_end.date()}'
        AND pos NOT IN ('PU', 'F', 'U', 'BD', 'RO', 'SU', 'UR')
        AND sp IS NOT NULL
        AND sp != ''
        LIMIT 50000
    """
    val_df = pd.read_sql_query(val_query, conn)
    
    conn.close()
    
    logger.info(f"Training set: {len(train_df):,} records")
    logger.info(f"Validation set: {len(val_df):,} records")
    
    return train_df, val_df


def parse_sp_to_decimal(sp_str):
    """Convert SP string to decimal odds."""
    if pd.isna(sp_str) or sp_str == '':
        return None
    
    sp_str = str(sp_str).strip()
    
    # Handle favorites (e.g., "1/3F")
    sp_str = sp_str.replace('F', '').replace('J', '').strip()
    
    # Handle fractions (e.g., "5/2")
    if '/' in sp_str:
        try:
            parts = sp_str.split('/')
            numerator = float(parts[0])
            denominator = float(parts[1])
            return (numerator / denominator) + 1.0
        except:
            return None
    
    # Handle decimals (e.g., "3.5")
    try:
        return float(sp_str)
    except:
        return None


def preprocess_data(df):
    """Preprocess raw data for training."""
    logger.info("Preprocessing data...")
    
    # Convert SP to decimal odds
    df['odds'] = df['sp'].apply(parse_sp_to_decimal)
    
    # Convert position to integer
    df['finish_position'] = pd.to_numeric(df['pos'], errors='coerce')
    
    # Filter valid records
    df = df[df['odds'].notna() & df['finish_position'].notna()]
    df = df[df['odds'] >= 1.01]  # Valid odds
    df = df[df['finish_position'] >= 1]  # Valid position
    
    # Add field_size
    df['field_size'] = df.groupby('race_id')['horse'].transform('count')
    
    logger.info(f"After preprocessing: {len(df):,} valid records")
    
    return df


def main():
    """Main training script."""
    logger.info("="*60)
    logger.info("VÉLØ v10.1 - MODEL TRAINING")
    logger.info("="*60)
    
    start_time = datetime.now()
    
    # Paths
    project_dir = Path("/home/ubuntu/velo-oracle")
    db_path = project_dir / "velo_racing.db"
    
    # Load data
    train_df, val_df = load_training_data(
        str(db_path),
        train_end_date='2024-06-30',
        val_days=90
    )
    
    # Preprocess
    train_df = preprocess_data(train_df)
    val_df = preprocess_data(val_df)
    
    # Initialize modules
    logger.info("\nInitializing training modules...")
    feature_store = FeatureStore(cache_dir="out/features")
    label_creator = LabelCreator(place_positions=3)
    model_registry = ModelRegistry(registry_dir="out/models")
    
    trainer = BenterTrainer(
        feature_store=feature_store,
        label_creator=label_creator,
        model_registry=model_registry,
        output_dir="out/models"
    )
    
    # Train model
    logger.info("\nStarting Benter training pipeline...")
    result = trainer.train(
        train_df=train_df,
        val_df=val_df,
        cv_folds=3,  # Reduced for speed
        calibrate=True,
        grid_search=True
    )
    
    # Save model
    logger.info("\nSaving model as v1.0.0...")
    trainer.save_model(result, version='v1.0.0')
    
    # Save training report
    report_path = project_dir / "out/reports/training_report_v1.0.0.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        'version': 'v1.0.0',
        'trained_at': result['trained_at'],
        'training_records': len(train_df),
        'validation_records': len(val_df),
        'alpha': result['alpha'],
        'beta': result['beta'],
        'metrics': result['metrics'],
        'feature_count': len(result['feature_names'])
    }
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("\n" + "="*60)
    logger.info("TRAINING COMPLETE")
    logger.info("="*60)
    logger.info(f"Version: v1.0.0")
    logger.info(f"Training time: {duration:.1f}s ({duration/60:.1f} min)")
    logger.info(f"Alpha: {result['alpha']:.2f}")
    logger.info(f"Beta: {result['beta']:.2f}")
    logger.info(f"AUC: {result['metrics'].get('auc', 0):.4f}")
    logger.info(f"A/E: {result['metrics'].get('ae_ratio', 0):.4f}")
    logger.info(f"ROI@20%: {result['metrics'].get('roi_top20', 0):.2f}%")
    logger.info(f"Report: {report_path}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
