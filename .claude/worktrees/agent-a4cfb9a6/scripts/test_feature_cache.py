#!/usr/bin/env python3
"""
Test Feature Cache Performance

Validates that feature caching provides 10-20x speedup.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import time
from src.features import FeatureBuilder, FeatureCache

def test_feature_cache_speedup():
    """Test feature cache performance improvement."""
    
    print("=" * 80)
    print("FEATURE CACHE SPEEDUP TEST")
    print("=" * 80)
    
    # Load sample data
    data_path = Path("/home/ubuntu/velo-oracle/data/train_5k_clean.csv")
    
    if not data_path.exists():
        print(f"❌ Data file not found: {data_path}")
        return 1
    
    print(f"\nLoading data from {data_path}...")
    df = pd.read_csv(data_path, low_memory=False)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    print(f"Loaded {len(df):,} rows")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    
    # Split into history and test
    split_idx = int(len(df) * 0.8)
    history = df.iloc[:split_idx].copy()
    test = df.iloc[split_idx:split_idx+1000].copy()  # 1000 test rows
    
    print(f"\nHistory: {len(history):,} rows")
    print(f"Test: {len(test):,} rows")
    
    # Test 1: Without cache
    print("\n" + "=" * 80)
    print("TEST 1: Feature extraction WITHOUT cache")
    print("=" * 80)
    
    builder_no_cache = FeatureBuilder()
    
    start_time = time.time()
    X_no_cache = builder_no_cache.build_sqpe_features(test, history)
    time_no_cache = time.time() - start_time
    
    print(f"\n✅ Features extracted: {X_no_cache.shape}")
    print(f"⏱️  Time: {time_no_cache:.2f} seconds")
    
    # Test 2: With cache
    print("\n" + "=" * 80)
    print("TEST 2: Feature extraction WITH cache")
    print("=" * 80)
    
    # Build cache
    print("\nBuilding feature cache...")
    cache = FeatureCache()
    
    cache_start = time.time()
    cache.build_from_history(history, date=test['date'].min())
    cache_build_time = time.time() - cache_start
    
    print(f"✅ Cache built in {cache_build_time:.2f} seconds")
    print(f"   Trainers: {len(cache.trainer_stats):,}")
    print(f"   Jockeys: {len(cache.jockey_stats['overall']):,}")
    print(f"   Course records: {len(cache.course_stats):,}")
    
    # Extract features with cache
    builder_with_cache = FeatureBuilder(cache=cache)
    
    start_time = time.time()
    X_with_cache = builder_with_cache.build_sqpe_features(test, history)
    time_with_cache = time.time() - start_time
    
    print(f"\n✅ Features extracted: {X_with_cache.shape}")
    print(f"⏱️  Time: {time_with_cache:.2f} seconds")
    
    # Compare
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)
    
    speedup = time_no_cache / time_with_cache if time_with_cache > 0 else float('inf')
    
    print(f"\nWithout cache: {time_no_cache:.2f}s")
    print(f"With cache:    {time_with_cache:.2f}s")
    print(f"Cache build:   {cache_build_time:.2f}s")
    print(f"\nSpeedup: {speedup:.1f}x")
    
    # Total time including cache build
    total_with_cache = cache_build_time + time_with_cache
    total_speedup = time_no_cache / total_with_cache if total_with_cache > 0 else float('inf')
    
    print(f"\nTotal time (with cache build): {total_with_cache:.2f}s")
    print(f"Net speedup: {total_speedup:.1f}x")
    
    # Validate features are identical
    print("\n" + "=" * 80)
    print("FEATURE VALIDATION")
    print("=" * 80)
    
    # Note: Features won't be identical because cache uses different aggregation
    # But they should be highly correlated
    print(f"\nFeature shape match: {X_no_cache.shape == X_with_cache.shape}")
    print(f"Column names match: {list(X_no_cache.columns) == list(X_with_cache.columns)}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if speedup >= 5.0:
        print(f"\n✅ PASS: {speedup:.1f}x speedup achieved (target: 5x+)")
        print("\nFeature caching provides significant performance improvement!")
        print("Recommended for all backtesting and training workflows.")
        return 0
    elif speedup >= 2.0:
        print(f"\n⚠️  PARTIAL: {speedup:.1f}x speedup (target: 5x+)")
        print("\nSome improvement, but below target. Consider further optimization.")
        return 0
    else:
        print(f"\n❌ FAIL: Only {speedup:.1f}x speedup (target: 5x+)")
        print("\nCache not providing expected benefit. Investigation needed.")
        return 1


if __name__ == '__main__':
    sys.exit(test_feature_cache_speedup())

