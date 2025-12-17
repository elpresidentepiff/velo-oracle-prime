#!/usr/bin/env python3
"""
VELO v12 Feature Engineering Tests
Minimal unit tests for CI (non-negotiable)

Tests:
1. test_v12_features_no_nan_explosion - Ensure features don't create excessive NaNs
2. test_feature_schema_exact_match - Ensure output matches schema contract
3. test_transform_deterministic - Ensure same inputs → identical output hash

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import hashlib
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml.v12_feature_engineering import V12FeatureEngineer, FEATURE_VERSION
from app.ml.leakage_firewall import LeakageFirewall
from app.ml.feature_pipeline import FeaturePipeline


@pytest.fixture
def sample_race_data():
    """Create sample race data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    data = []
    for i in range(100):
        data.append({
            'race_id': f'race_{i//10}',
            'horse': f'Horse_{i%10}',
            'date': dates[i],
            'course': 'Newmarket',
            'dist': 1200,
            'going': 'Good',
            'ran': 10,
            'num': i % 10 + 1,
            'age': 4 + (i % 4),
            'rpr': 85 + (i % 20),
            'or': 80 + (i % 20),
            'ts': 75 + (i % 20),
            'wgt': f"{9 + (i % 3)}-{(i % 14)}",
            'draw': (i % 10) + 1,
            'pos': str((i % 10) + 1),
            'jockey': f'Jockey_{i%5}',
            'trainer': f'Trainer_{i%5}',
            'sire': f'Sire_{i%5}',
            'sex': ['G', 'M', 'C'][i % 3],
            'type': 'Flat'
        })
    
    return pd.DataFrame(data)


def test_feature_version():
    """Test that FEATURE_VERSION constant is set."""
    assert FEATURE_VERSION == "v12"
    print(f"✓ Feature version: {FEATURE_VERSION}")


def test_v12_features_no_nan_explosion(sample_race_data):
    """
    Test 1: Ensure features don't create excessive NaNs.
    
    Acceptance: < 30% NaN rate across all features
    """
    engineer = V12FeatureEngineer()
    df_features = engineer.transform(sample_race_data.copy())
    
    # Calculate NaN rate
    nan_rate = df_features.isna().sum().sum() / (len(df_features) * len(df_features.columns))
    
    print(f"✓ NaN rate: {nan_rate:.2%}")
    print(f"✓ Output shape: {df_features.shape}")
    
    # Acceptance criteria: < 30% NaN rate
    assert nan_rate < 0.30, f"NaN explosion detected: {nan_rate:.2%} > 30%"
    
    # Ensure we have data
    assert len(df_features) > 0, "No data returned"
    assert len(df_features.columns) > 10, "Too few features"


def test_feature_schema_exact_match(sample_race_data):
    """
    Test 2: Ensure output matches schema contract exactly.
    
    Acceptance: All schema features present, no extras
    """
    engineer = V12FeatureEngineer()
    df_features = engineer.transform(sample_race_data.copy())
    
    # Get schema feature names
    schema_features = set(engineer.get_feature_names())
    
    # Get actual feature names (exclude targets)
    actual_features = set(df_features.columns) - {'win', 'place'}
    
    # Check for missing features
    missing = schema_features - actual_features
    extra = actual_features - schema_features
    
    print(f"✓ Schema features: {len(schema_features)}")
    print(f"✓ Actual features: {len(actual_features)}")
    
    if missing:
        print(f"✗ Missing features: {missing}")
    if extra:
        print(f"✗ Extra features: {extra}")
    
    # Acceptance criteria: exact match
    assert len(missing) == 0, f"Missing features: {missing}"
    assert len(extra) == 0, f"Extra features: {extra}"
    
    print("✓ Schema validation passed")


def test_transform_deterministic(sample_race_data):
    """
    Test 3: Ensure same inputs → identical output hash.
    
    Acceptance: Running transform twice on same data produces identical results
    """
    engineer1 = V12FeatureEngineer()
    engineer2 = V12FeatureEngineer()
    
    # Transform same data twice
    df1 = engineer1.transform(sample_race_data.copy())
    df2 = engineer2.transform(sample_race_data.copy())
    
    # Sort columns for comparison
    df1 = df1.sort_index(axis=1)
    df2 = df2.sort_index(axis=1)
    
    # Compare shapes
    assert df1.shape == df2.shape, f"Shape mismatch: {df1.shape} != {df2.shape}"
    
    # Compare column names
    assert list(df1.columns) == list(df2.columns), "Column mismatch"
    
    # Compare values (allowing for floating point precision)
    pd.testing.assert_frame_equal(df1, df2, check_exact=False, rtol=1e-10)
    
    # Hash comparison
    hash1 = hashlib.md5(pd.util.hash_pandas_object(df1, index=True).values).hexdigest()
    hash2 = hashlib.md5(pd.util.hash_pandas_object(df2, index=True).values).hexdigest()
    
    print(f"✓ Hash 1: {hash1}")
    print(f"✓ Hash 2: {hash2}")
    
    assert hash1 == hash2, "Determinism violated: same inputs produced different outputs"
    
    print("✓ Determinism test passed")


def test_leakage_firewall():
    """Test leakage firewall blocks future data."""
    firewall = LeakageFirewall()
    
    # Create data with leakage
    df_bad = pd.DataFrame({
        'rpr': [95, 92, 88],
        'or': [90, 87, 85],
        'pos': [1, 2, 3],  # BLOCKED
        'sp': [3.5, 5.0, 8.0]  # BLOCKED
    })
    
    # Should detect leakage
    with pytest.raises(ValueError, match="LEAKAGE DETECTED"):
        firewall.validate_columns(df_bad, strict=True)
    
    print("✓ Leakage firewall correctly detected blocked columns")
    
    # Clean data should pass
    df_clean = pd.DataFrame({
        'rpr': [95, 92, 88],
        'or': [90, 87, 85],
        'draw': [1, 2, 3]
    })
    
    assert firewall.validate_columns(df_clean, strict=True)
    print("✓ Leakage firewall passed clean data")


def test_feature_pipeline_day_card():
    """Test feature pipeline can process full day card without crashing."""
    pipeline = FeaturePipeline()
    
    # Create mock day card (3 races)
    races = []
    for i in range(3):
        races.append({
            'race_id': f'test_race_{i}',
            'course': 'Newmarket',
            'date': '2025-12-17',
            'dist': 1200,
            'going': 'Good',
            'class': 3,
            'runners': [
                {
                    'horse': f'Horse_{j}',
                    'age': 4,
                    'rpr': 90 + j,
                    'or': 85 + j,
                    'ts': 80 + j,
                    'draw': j + 1,
                    'ran': 10,
                    'num': j + 1,
                    'jockey': f'Jockey_{j%3}',
                    'trainer': f'Trainer_{j%3}',
                    'sire': f'Sire_{j%3}',
                    'sex': 'G',
                    'wgt': '9-0'
                }
                for j in range(5)
            ]
        })
    
    # Process day card
    results = pipeline.generate_day_card_features(races)
    
    # Acceptance: All races processed
    assert len(results) == 3, f"Expected 3 races, got {len(results)}"
    
    for race_id, df in results.items():
        assert len(df) == 5, f"Expected 5 runners in {race_id}, got {len(df)}"
        assert len(df.columns) > 10, f"Too few features in {race_id}"
    
    print(f"✓ Day card processing: {len(results)} races, {sum(len(df) for df in results.values())} total runners")


def test_engine_run_reproducibility():
    """Test that engine runs are reproducible from stored inputs."""
    from app.engine.engine_run import EngineRun, RaceContext, EngineVerdict
    
    # Create engine run
    race_ctx = RaceContext(
        race_id="test_race_001",
        course="Newmarket",
        datetime=datetime.now(),
        distance=1200,
        going="Good",
        class_level=3,
        surface="Turf",
        field_size=10
    )
    
    engine_run = EngineRun(
        race_ctx=race_ctx,
        mode="TEST",
        chaos_level=0.35
    )
    
    engine_run.set_verdict(EngineVerdict(
        top_strike_selection='r1',
        top4_structure=['r1', 'r2', 'r3', 'r4'],
        confidence=0.78
    ))
    
    # Convert to dict and back
    data = engine_run.to_dict()
    loaded = EngineRun.from_dict(data)
    
    # Verify reproducibility
    assert loaded.engine_run_id == engine_run.engine_run_id
    assert loaded.mode == engine_run.mode
    assert loaded.chaos_level == engine_run.chaos_level
    assert loaded.verdict.top_strike_selection == engine_run.verdict.top_strike_selection
    
    print("✓ Engine run reproducibility verified")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
