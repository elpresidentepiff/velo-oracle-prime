"""
VÉLØ Feature Extraction Tests
Tests for hot window feature mart and feature extraction.

Author: VELO Team
Date: 2026-01-08
"""

import asyncio
import importlib.util
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from engine module
spec = importlib.util.spec_from_file_location(
    "engine.features",
    project_root / "engine" / "features.py"
)
engine_features = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_features)

get_features_for_racecard = engine_features.get_features_for_racecard
get_features_batch = engine_features.get_features_batch
calculate_distance_band = engine_features.calculate_distance_band


# ============================================================================
# Test Fixtures
# ============================================================================

# Test constants
EXPECTED_RUNNER_COUNT = 15  # Typical field size for testing


@pytest.fixture
def mock_db_client():
    """Mock database client with fetch method"""
    db = Mock()
    db.fetch = AsyncMock()
    return db


@pytest.fixture
def sample_race_data():
    """Sample race data for testing"""
    return [
        {
            'runner_id': 'r1',
            'horse_name': 'Test Horse 1',
            'odds': 3.5,
            'trainer': 'J Smith',
            'jockey': 'J Doe',
            'course': 'Newmarket',
            'distance': '1200m',
            'trainer_win_pct_14d': 0.25,
            'trainer_win_pct_30d': 0.22,
            'trainer_win_pct_90d': 0.20,
            'trainer_starts_30d': 10,
            'jockey_win_pct_14d': 0.30,
            'jockey_win_pct_30d': 0.28,
            'jockey_win_pct_90d': 0.25,
            'jt_combo_win_pct_365d': 0.35,
            'jt_combo_starts': 5,
            'course_avg_odds': 4.2,
            'course_volatility': 1.5
        },
        {
            'runner_id': 'r2',
            'horse_name': 'Test Horse 2',
            'odds': 5.0,
            'trainer': 'A Trainer',
            'jockey': 'B Jockey',
            'course': 'Newmarket',
            'distance': '1200m',
            'trainer_win_pct_14d': 0.15,
            'trainer_win_pct_30d': 0.18,
            'trainer_win_pct_90d': 0.17,
            'trainer_starts_30d': 15,
            'jockey_win_pct_14d': 0.20,
            'jockey_win_pct_30d': 0.19,
            'jockey_win_pct_90d': 0.18,
            'jt_combo_win_pct_365d': None,
            'jt_combo_starts': 1,
            'course_avg_odds': 4.2,
            'course_volatility': 1.5
        }
    ]


# ============================================================================
# Tests
# ============================================================================

@pytest.mark.asyncio
async def test_feature_query_performance(mock_db_client, sample_race_data):
    """
    Test 1: Feature query must complete in <1 second

    Acceptance: Query completes in <1s for 15-runner race
    """
    # Setup mock to return 15 runners
    race_data = sample_race_data * 8  # 16 runners
    race_data = race_data[:EXPECTED_RUNNER_COUNT]  # trim to 15
    mock_db_client.fetch.return_value = race_data

    race_id = "test_race_123"

    start = time.time()
    df = await get_features_for_racecard(mock_db_client, race_id)
    elapsed = time.time() - start

    # Verify performance
    assert elapsed < 1.0, f"Query took {elapsed:.2f}s (target: <1s)"

    # Verify data
    assert len(df) == EXPECTED_RUNNER_COUNT, f"Expected {EXPECTED_RUNNER_COUNT} runners, got {len(df)}"
    assert 'runner_id' in df.columns
    assert 'horse_name' in df.columns

    print(f"✓ Feature query completed in {elapsed:.4f}s for {len(df)} runners")


@pytest.mark.asyncio
async def test_feature_completeness(mock_db_client, sample_race_data):
    """
    Test 2: All expected features are present

    Acceptance: All required columns exist in output
    """
    mock_db_client.fetch.return_value = sample_race_data

    race_id = "test_race_123"
    df = await get_features_for_racecard(mock_db_client, race_id)

    # Required features from spec
    required_cols = [
        'trainer_win_pct_14d',
        'trainer_win_pct_30d',
        'trainer_win_pct_90d',
        'trainer_starts_30d',
        'jockey_win_pct_14d',
        'jockey_win_pct_30d',
        'jockey_win_pct_90d',
        'jt_combo_win_pct_365d',
        'jt_combo_starts',
        'course_avg_odds',
        'course_volatility',
        'trainer_form_trend',
        'jockey_form_trend',
        'has_combo_history'
    ]

    missing_cols = [col for col in required_cols if col not in df.columns]

    assert len(missing_cols) == 0, f"Missing required columns: {missing_cols}"

    print(f"✓ All {len(required_cols)} required features present")
    print(f"✓ Total columns: {len(df.columns)}")


@pytest.mark.asyncio
async def test_deterministic_output(mock_db_client, sample_race_data):
    """
    Test 3: Same input → same output

    Acceptance: Running twice on same data produces identical results
    """
    mock_db_client.fetch.return_value = sample_race_data

    race_id = "test_race_123"

    # Run twice
    df1 = await get_features_for_racecard(mock_db_client, race_id)
    df2 = await get_features_for_racecard(mock_db_client, race_id)

    # Sort columns for comparison
    df1 = df1.sort_index(axis=1)
    df2 = df2.sort_index(axis=1)

    # Compare
    assert df1.shape == df2.shape, f"Shape mismatch: {df1.shape} != {df2.shape}"
    assert list(df1.columns) == list(df2.columns), "Column mismatch"

    # Compare values (with float tolerance)
    pd.testing.assert_frame_equal(df1, df2, check_exact=False, rtol=1e-10)

    print("✓ Deterministic output verified")


@pytest.mark.asyncio
async def test_derived_features(mock_db_client, sample_race_data):
    """
    Test 4: Derived features calculated correctly

    Acceptance: Form trends and combo history flags work correctly
    """
    mock_db_client.fetch.return_value = sample_race_data

    race_id = "test_race_123"
    df = await get_features_for_racecard(mock_db_client, race_id)

    # Check trainer form trend (14d - 90d)
    expected_trend_r1 = 0.25 - 0.20
    assert abs(df.iloc[0]['trainer_form_trend'] - expected_trend_r1) < 0.001

    # Check has_combo_history (>= 3 starts)
    assert df.iloc[0]['has_combo_history']  # 5 starts
    assert not df.iloc[1]['has_combo_history']  # 1 start

    print("✓ Derived features calculated correctly")


@pytest.mark.asyncio
async def test_nan_handling(mock_db_client):
    """
    Test 5: NaN values handled properly

    Acceptance: Missing trainer/jockey data doesn't break extraction
    """
    # Data with missing features (new trainer/jockey)
    data_with_nans = [
        {
            'runner_id': 'r1',
            'horse_name': 'New Horse',
            'odds': 10.0,
            'trainer': 'New Trainer',
            'jockey': 'New Jockey',
            'course': 'Ascot',
            'distance': '1400m',
            'trainer_win_pct_14d': None,
            'trainer_win_pct_30d': None,
            'trainer_win_pct_90d': None,
            'trainer_starts_30d': None,
            'jockey_win_pct_14d': None,
            'jockey_win_pct_30d': None,
            'jockey_win_pct_90d': None,
            'jt_combo_win_pct_365d': None,
            'jt_combo_starts': None,
            'course_avg_odds': None,
            'course_volatility': None
        }
    ]

    mock_db_client.fetch.return_value = data_with_nans

    race_id = "test_race_456"
    df = await get_features_for_racecard(mock_db_client, race_id)

    # Verify no NaNs in numeric columns after processing
    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
    nan_count = df[numeric_cols].isna().sum().sum()

    assert nan_count == 0, f"Found {nan_count} NaN values after processing"

    # Verify defaults
    assert df.iloc[0]['trainer_win_pct_14d'] == 0.0
    assert df.iloc[0]['jockey_win_pct_30d'] == 0.0
    assert not df.iloc[0]['has_combo_history']

    print("✓ NaN handling works correctly")


@pytest.mark.asyncio
async def test_batch_extraction(mock_db_client, sample_race_data):
    """
    Test 6: Batch extraction for multiple races

    Acceptance: Can extract features for multiple races efficiently
    """
    mock_db_client.fetch.return_value = sample_race_data

    race_ids = ["race_1", "race_2", "race_3"]

    results = await get_features_batch(mock_db_client, race_ids)

    assert len(results) == 3, f"Expected 3 results, got {len(results)}"

    for race_id in race_ids:
        assert race_id in results
        assert len(results[race_id]) == 2  # 2 runners in sample data

    print(f"✓ Batch extraction successful for {len(race_ids)} races")


def test_distance_band_calculation():
    """
    Test 7: Distance band calculation

    Acceptance: Distance text correctly categorized
    """
    assert calculate_distance_band('1100m') == 'sprint'
    assert calculate_distance_band('1200m') == 'mile'
    assert calculate_distance_band('1400m') == 'mile'
    assert calculate_distance_band('1600m') == 'middle'
    assert calculate_distance_band('1800m') == 'middle'
    assert calculate_distance_band('2000m') == 'staying'
    assert calculate_distance_band('2400m') == 'staying'
    assert calculate_distance_band('invalid') == 'unknown'
    assert calculate_distance_band('') == 'unknown'

    print("✓ Distance band calculation correct")


@pytest.mark.asyncio
async def test_empty_race(mock_db_client):
    """
    Test 8: Handle empty race (no runners)

    Acceptance: Returns empty DataFrame without crashing
    """
    mock_db_client.fetch.return_value = []

    race_id = "empty_race"
    df = await get_features_for_racecard(mock_db_client, race_id)

    assert len(df) == 0, "Expected empty DataFrame"
    assert isinstance(df, pd.DataFrame), "Should return DataFrame"

    print("✓ Empty race handled correctly")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
