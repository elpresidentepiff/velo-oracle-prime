#!/usr/bin/env python3
"""
Train VÉLØ Models on Real Data

Trains SQPE and TIE on real raceform data.

Usage:
    python scripts/train_real_data.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.training import TrainingPipeline, TrainingConfig


def main():
    print("=" * 80)
    print("VÉLØ ORACLE - REAL DATA TRAINING")
    print("=" * 80)
    
    # Configure training
    config = TrainingConfig(
        # Data
        data_path="/home/ubuntu/velo-oracle/data/train_5k_clean.csv",
        output_dir="/home/ubuntu/velo-oracle/models/v1_real",
        test_size=0.2,
        
        # SQPE hyperparameters
        sqpe_n_estimators=400,
        sqpe_learning_rate=0.05,
        sqpe_max_depth=3,
        sqpe_min_samples_leaf=40,
        sqpe_time_splits=5,
        
        # TIE hyperparameters
        tie_min_trainer_runs=50,
        tie_lookback_days=90,
        tie_regularization_c=0.5,
        
        # Intent labeling
        intent_class_drop_threshold=-1.0,
        intent_rest_days_min=14,
        intent_rest_days_max=28,
        intent_trainer_wr_min=0.15,
        
        # Logging
        log_level="INFO",
        save_artifacts=True,
    )
    
    print("\nConfiguration:")
    print(f"  Data: {config.data_path}")
    print(f"  Output: {config.output_dir}")
    print(f"  Test size: {config.test_size}")
    print(f"  SQPE estimators: {config.sqpe_n_estimators}")
    print(f"  SQPE time splits: {config.sqpe_time_splits}")
    print()
    
    # Run training
    pipeline = TrainingPipeline(config)
    results = pipeline.run()
    
    # Print summary
    print("\n" + "=" * 80)
    print("TRAINING SUMMARY")
    print("=" * 80)
    
    print("\n📊 SQPE Metrics:")
    sqpe_metrics = results['sqpe_metrics']
    print(f"  Test Log Loss:    {sqpe_metrics['test_log_loss']:.4f}")
    print(f"  Test Brier Score: {sqpe_metrics['test_brier_score']:.4f}")
    print(f"  Test AUC:         {sqpe_metrics['test_auc']:.4f}")
    print(f"  Test Samples:     {sqpe_metrics['test_samples']:,}")
    print(f"  Test Positives:   {sqpe_metrics['test_positives']:,}")
    
    print("\n📊 TIE Metrics:")
    tie_metrics = results['tie_metrics']
    print(f"  Test Accuracy:    {tie_metrics['test_accuracy']:.4f}")
    print(f"  Test Precision:   {tie_metrics['test_precision']:.4f}")
    print(f"  Test Recall:      {tie_metrics['test_recall']:.4f}")
    print(f"  Test F1:          {tie_metrics['test_f1']:.4f}")
    print(f"  Test Samples:     {tie_metrics['test_samples']:,}")
    print(f"  Test Positives:   {tie_metrics['test_positives']:,}")
    
    print("\n📁 Artifacts:")
    for key, value in results['artifacts'].items():
        if 'path' in key:
            print(f"  {key}: {value}")
    
    print("\n✅ TRAINING COMPLETE")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

