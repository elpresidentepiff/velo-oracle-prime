#!/usr/bin/env python3
"""
VELO Test Runner (no pytest dependency)
Runs minimal unit tests for CI

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

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


def create_sample_race_data():
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
    assert FEATURE_VERSION == "v12", f"Expected v12, got {FEATURE_VERSION}"
    print(f"✓ TEST 1 PASSED: Feature version = {FEATURE_VERSION}")
    return True


def test_v12_features_no_nan_explosion():
    """Test 1: Ensure features don't create excessive NaNs."""
    print("\n" + "="*80)
    print("TEST 2: NaN Explosion Check")
    print("="*80)
    
    sample_data = create_sample_race_data()
    engineer = V12FeatureEngineer()
    df_features = engineer.transform(sample_data.copy())
    
    # Calculate NaN rate
    nan_rate = df_features.isna().sum().sum() / (len(df_features) * len(df_features.columns))
    
    print(f"  NaN rate: {nan_rate:.2%}")
    print(f"  Output shape: {df_features.shape}")
    
    # Acceptance criteria: < 30% NaN rate
    assert nan_rate < 0.30, f"NaN explosion detected: {nan_rate:.2%} > 30%"
    assert len(df_features) > 0, "No data returned"
    assert len(df_features.columns) > 10, "Too few features"
    
    print(f"✓ TEST 2 PASSED: NaN rate {nan_rate:.2%} < 30%")
    return True


def test_feature_schema_exact_match():
    """Test 2: Ensure output matches schema contract exactly."""
    print("\n" + "="*80)
    print("TEST 3: Schema Contract Validation")
    print("="*80)
    
    sample_data = create_sample_race_data()
    engineer = V12FeatureEngineer()
    df_features = engineer.transform(sample_data.copy())
    
    # Get schema feature names
    schema_features = set(engineer.get_feature_names())
    
    # Get actual feature names (exclude targets)
    actual_features = set(df_features.columns) - {'win', 'place'}
    
    # Check for missing features
    missing = schema_features - actual_features
    extra = actual_features - schema_features
    
    print(f"  Schema features: {len(schema_features)}")
    print(f"  Actual features: {len(actual_features)}")
    
    if missing:
        print(f"  ✗ Missing features: {missing}")
    if extra:
        print(f"  ✗ Extra features: {extra}")
    
    # Acceptance criteria: exact match
    assert len(missing) == 0, f"Missing features: {missing}"
    assert len(extra) == 0, f"Extra features: {extra}"
    
    print(f"✓ TEST 3 PASSED: Schema validation exact match")
    return True


def test_transform_deterministic():
    """Test 3: Ensure same inputs → identical output hash."""
    print("\n" + "="*80)
    print("TEST 4: Determinism Check")
    print("="*80)
    
    sample_data = create_sample_race_data()
    engineer1 = V12FeatureEngineer()
    engineer2 = V12FeatureEngineer()
    
    # Transform same data twice
    df1 = engineer1.transform(sample_data.copy())
    df2 = engineer2.transform(sample_data.copy())
    
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
    
    print(f"  Hash 1: {hash1}")
    print(f"  Hash 2: {hash2}")
    
    assert hash1 == hash2, "Determinism violated: same inputs produced different outputs"
    
    print(f"✓ TEST 4 PASSED: Determinism verified")
    return True


def test_leakage_firewall():
    """Test leakage firewall blocks future data."""
    print("\n" + "="*80)
    print("TEST 5: Leakage Firewall")
    print("="*80)
    
    firewall = LeakageFirewall()
    
    # Create data with leakage
    df_bad = pd.DataFrame({
        'rpr': [95, 92, 88],
        'or': [90, 87, 85],
        'pos': [1, 2, 3],  # BLOCKED
        'sp': [3.5, 5.0, 8.0]  # BLOCKED
    })
    
    # Should detect leakage
    try:
        firewall.validate_columns(df_bad, strict=True)
        raise AssertionError("Firewall failed to detect leakage")
    except ValueError as e:
        if "LEAKAGE DETECTED" in str(e):
            print(f"  ✓ Correctly detected leakage: {e}")
        else:
            raise
    
    # Clean data should pass
    df_clean = pd.DataFrame({
        'rpr': [95, 92, 88],
        'or': [90, 87, 85],
        'draw': [1, 2, 3]
    })
    
    assert firewall.validate_columns(df_clean, strict=True)
    print(f"  ✓ Clean data passed firewall")
    
    print(f"✓ TEST 5 PASSED: Leakage firewall working")
    return True


def test_engine_run_reproducibility():
    """Test that engine runs are reproducible from stored inputs."""
    print("\n" + "="*80)
    print("TEST 6: Engine Run Reproducibility")
    print("="*80)
    
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
    
    print(f"  ✓ Engine run ID: {engine_run.engine_run_id}")
    print(f"  ✓ Verdict reproduced: {loaded.verdict.top_strike_selection}")
    
    print(f"✓ TEST 6 PASSED: Engine run reproducibility verified")
    return True


def main():
    """Run all tests."""
    print("="*80)
    print("VELO v12 FEATURE ENGINEERING TEST SUITE")
    print("="*80)
    print(f"Start: {datetime.now()}")
    print()
    
    tests = [
        ("Feature Version", test_feature_version),
        ("NaN Explosion Check", test_v12_features_no_nan_explosion),
        ("Schema Contract Validation", test_feature_schema_exact_match),
        ("Determinism Check", test_transform_deterministic),
        ("Leakage Firewall", test_leakage_firewall),
        ("Engine Run Reproducibility", test_engine_run_reproducibility),
    ]
    
    passed = 0
    failed = 0
    errors = []
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"\n✗ TEST FAILED: {name}")
            print(f"  Error: {e}")
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"PASSED: {passed}/{len(tests)}")
    print(f"FAILED: {failed}/{len(tests)}")
    
    if errors:
        print("\nFAILURES:")
        for name, error in errors:
            print(f"  - {name}: {error}")
    
    print(f"\nEnd: {datetime.now()}")
    print("="*80)
    
    # Exit with error code if any tests failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
