#!/usr/bin/env python3
"""
Pipeline Validation Script

Tests the Feature Builder and Training Pipeline on a sample of data.

Usage:
    python scripts/validate_pipeline.py

Author: VÉLØ Oracle Team
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from src.training import TrainingPipeline, TrainingConfig


def create_sample_data(n_rows: int = 1000) -> pd.DataFrame:
    """Create synthetic sample data for testing."""
    print(f"Creating sample data with {n_rows} rows...")
    
    np.random.seed(42)
    
    dates = pd.date_range('2023-01-01', periods=n_rows // 10, freq='D')
    courses = ['Ascot', 'Newmarket', 'York', 'Cheltenham', 'Doncaster']
    horses = [f'Horse_{i}' for i in range(100)]
    trainers = [f'Trainer_{i}' for i in range(20)]
    jockeys = [f'Jockey_{i}' for i in range(30)]
    
    data = []
    for i in range(n_rows):
        date = np.random.choice(dates)
        course = np.random.choice(courses)
        row = {
            'date': date,
            'course': course,
            'race_id': f"{date}_{course}_{i % 10}",
            'horse': np.random.choice(horses),
            'trainer': np.random.choice(trainers),
            'jockey': np.random.choice(jockeys),
            'age': np.random.randint(3, 10),
            'class': np.random.randint(1, 8),
            'dist': np.random.randint(1000, 4000),
            'going': np.random.choice(['firm', 'good', 'soft', 'heavy']),
            'pattern': 'flat',
            'or_int': np.random.randint(60, 120),
            'rpr_int': np.random.randint(60, 120),
            'ts_int': np.random.randint(60, 120),
            'lbs': np.random.randint(110, 140),
            'sp_decimal': np.random.uniform(2.0, 20.0),
            'pos_int': np.random.randint(1, 15),
            'btn_int': np.random.uniform(0, 20),
            'num': np.random.randint(1, 20),
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    df = df.sort_values('date').reset_index(drop=True)
    
    print(f"Sample data created: {df.shape}")
    return df


def validate_feature_builder():
    """Test Feature Builder."""
    print("\n" + "=" * 80)
    print("VALIDATING FEATURE BUILDER")
    print("=" * 80)
    
    from src.features import FeatureBuilder
    
    # Create sample data
    df = create_sample_data(500)
    
    # Initialize builder
    builder = FeatureBuilder()
    
    # Test SQPE features
    print("\nBuilding SQPE features...")
    sqpe_features = builder.build_sqpe_features(df, history=df)
    print(f"SQPE features shape: {sqpe_features.shape}")
    print(f"SQPE feature columns: {list(sqpe_features.columns[:10])}...")
    
    # Test TIE features
    print("\nBuilding TIE features...")
    tie_features = builder.build_tie_features(df, history=df)
    print(f"TIE features shape: {tie_features.shape}")
    print(f"TIE feature columns: {list(tie_features.columns)}")
    
    # Test targets
    print("\nBuilding targets...")
    targets = builder.build_targets(df)
    print(f"Targets shape: {targets.shape}")
    print(f"Target columns: {list(targets.columns)}")
    print(f"Win rate: {targets['won'].mean():.1%}")
    
    print("\n✅ Feature Builder validation PASSED")
    return True


def validate_training_pipeline():
    """Test Training Pipeline."""
    print("\n" + "=" * 80)
    print("VALIDATING TRAINING PIPELINE")
    print("=" * 80)
    
    # Create sample data and save to temp file
    df = create_sample_data(2000)
    temp_data_path = Path("/tmp/velo_sample_data.csv")
    df.to_csv(temp_data_path, index=False)
    print(f"Sample data saved to {temp_data_path}")
    
    # Configure pipeline
    config = TrainingConfig(
        data_path=str(temp_data_path),
        output_dir="/tmp/velo_models_test",
        test_size=0.2,
        sqpe_n_estimators=50,  # Reduced for speed
        sqpe_time_splits=2,    # Reduced for speed
        log_level="INFO",
    )
    
    # Run pipeline
    print("\nRunning training pipeline...")
    pipeline = TrainingPipeline(config)
    
    try:
        results = pipeline.run()
        
        print("\n" + "=" * 80)
        print("TRAINING RESULTS")
        print("=" * 80)
        
        print("\nSQPE Metrics:")
        for key, value in results['sqpe_metrics'].items():
            print(f"  {key}: {value}")
        
        print("\nTIE Metrics:")
        for key, value in results['tie_metrics'].items():
            print(f"  {key}: {value}")
        
        print("\nArtifacts:")
        for key, value in results['artifacts'].items():
            print(f"  {key}: {value}")
        
        print("\n✅ Training Pipeline validation PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Training Pipeline validation FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validations."""
    print("=" * 80)
    print("VÉLØ ORACLE PIPELINE VALIDATION")
    print("=" * 80)
    
    results = []
    
    # Validate Feature Builder
    try:
        results.append(("Feature Builder", validate_feature_builder()))
    except Exception as e:
        print(f"\n❌ Feature Builder validation FAILED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Feature Builder", False))
    
    # Validate Training Pipeline
    try:
        results.append(("Training Pipeline", validate_training_pipeline()))
    except Exception as e:
        print(f"\n❌ Training Pipeline validation FAILED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Training Pipeline", False))
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n🎉 ALL VALIDATIONS PASSED")
        return 0
    else:
        print("\n⚠️  SOME VALIDATIONS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

