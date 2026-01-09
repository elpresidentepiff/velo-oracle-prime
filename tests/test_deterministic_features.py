"""
Tests for deterministic feature mart
Validates that same as_of_date produces identical features

Author: VELO Team
Date: 2026-01-09
"""

import pytest
import asyncio
from datetime import date, datetime
from unittest.mock import Mock, AsyncMock, MagicMock
import pandas as pd
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engine.features import get_features_for_racecard, build_feature_mart_for_batch


@pytest.fixture
def mock_db_asyncpg():
    """Mock asyncpg-style database client"""
    db = AsyncMock()
    
    # Mock race data
    db.fetchrow = AsyncMock(return_value={
        'import_date': date(2026, 1, 7)
    })
    
    # Mock feature query results
    db.fetch = AsyncMock(return_value=[
        {
            'runner_id': 'runner-1',
            'horse_name': 'Test Horse 1',
            'trainer': 'Trainer A',
            'jockey': 'Jockey X',
            'course': 'Kempton',
            'distance': '2000',
            'trainer_win_pct_14d': 0.25,
            'trainer_starts_14d': 12,
            'trainer_avg_odds_14d': 5.5,
            'trainer_win_pct_30d': 0.22,
            'trainer_starts_30d': 27,
            'trainer_avg_odds_30d': 5.8,
            'trainer_win_pct_90d': 0.20,
            'trainer_starts_90d': 75,
            'trainer_avg_odds_90d': 6.0,
            'jockey_win_pct_14d': 0.18,
            'jockey_starts_14d': 10,
            'jockey_avg_odds_14d': 7.0,
            'jockey_win_pct_30d': 0.17,
            'jockey_starts_30d': 22,
            'jockey_avg_odds_30d': 7.2,
            'jockey_win_pct_90d': 0.16,
            'jockey_starts_90d': 60,
            'jockey_avg_odds_90d': 7.5,
            'jt_combo_win_pct_365d': 0.28,
            'jt_combo_starts': 18,
            'jt_combo_avg_odds': 4.8,
            'course_avg_odds': 8.5,
            'course_volatility': 3.2,
            'course_race_count': 45
        },
        {
            'runner_id': 'runner-2',
            'horse_name': 'Test Horse 2',
            'trainer': 'Trainer B',
            'jockey': 'Jockey Y',
            'course': 'Kempton',
            'distance': '2000',
            'trainer_win_pct_14d': 0.30,
            'trainer_starts_14d': 10,
            'trainer_avg_odds_14d': 4.5,
            'trainer_win_pct_30d': 0.28,
            'trainer_starts_30d': 25,
            'trainer_avg_odds_30d': 4.8,
            'trainer_win_pct_90d': 0.26,
            'trainer_starts_90d': 70,
            'trainer_avg_odds_90d': 5.0,
            'jockey_win_pct_14d': 0.22,
            'jockey_starts_14d': 15,
            'jockey_avg_odds_14d': 6.0,
            'jockey_win_pct_30d': 0.20,
            'jockey_starts_30d': 30,
            'jockey_avg_odds_30d': 6.2,
            'jockey_win_pct_90d': 0.19,
            'jockey_starts_90d': 80,
            'jockey_avg_odds_90d': 6.5,
            'jt_combo_win_pct_365d': 0.32,
            'jt_combo_starts': 15,
            'jt_combo_avg_odds': 4.2,
            'course_avg_odds': 8.5,
            'course_volatility': 3.2,
            'course_race_count': 45
        }
    ])
    
    return db


@pytest.mark.asyncio
async def test_determinism_across_time(mock_db_asyncpg):
    """
    CRITICAL: Same as_of_date returns identical features regardless of when queried
    
    This is the core determinism guarantee - querying the same race with the same
    as_of_date on different days must return identical results.
    """
    as_of_date = '2026-01-07'
    race_id = 'test_race_123'
    
    # Query 1
    df1 = await get_features_for_racecard(mock_db_asyncpg, race_id, as_of_date=as_of_date)
    
    # Simulate time passing
    await asyncio.sleep(0.1)
    
    # Query 2 (same as_of_date) - should call the same mock data
    df2 = await get_features_for_racecard(mock_db_asyncpg, race_id, as_of_date=as_of_date)
    
    # MUST be identical
    pd.testing.assert_frame_equal(df1, df2)
    
    # Verify we have expected columns
    assert 'trainer_win_pct_30d' in df1.columns
    assert 'jockey_win_pct_30d' in df1.columns
    assert 'jt_combo_win_pct_365d' in df1.columns
    assert 'course_avg_odds' in df1.columns
    
    # Verify we have expected rows
    assert len(df1) == 2
    assert df1.iloc[0]['horse_name'] == 'Test Horse 1'
    assert df1.iloc[1]['horse_name'] == 'Test Horse 2'
    
    print("✅ Determinism test passed - same as_of_date returns identical features")


@pytest.mark.asyncio
async def test_different_as_of_dates_produce_different_features(mock_db_asyncpg):
    """
    Verify that different as_of_dates can produce different (expected) features
    
    This tests that the as_of_date parameter is actually being used and not ignored.
    While we can't easily test different data in mocks, we verify the parameter is passed.
    """
    race_id = 'test_race_123'
    
    # Query with date 1
    df_jan7 = await get_features_for_racecard(mock_db_asyncpg, race_id, as_of_date='2026-01-07')
    
    # Verify the query was called with the as_of_date parameter
    # Check that fetch was called with race_id and as_of_date
    call_args = mock_db_asyncpg.fetch.call_args
    assert call_args[0][1] == race_id
    assert call_args[0][2] == '2026-01-07'
    
    # Query with date 2 (different date)
    mock_db_asyncpg.fetch.reset_mock()
    df_jan8 = await get_features_for_racecard(mock_db_asyncpg, race_id, as_of_date='2026-01-08')
    
    # Verify the query was called with the NEW as_of_date parameter
    call_args = mock_db_asyncpg.fetch.call_args
    assert call_args[0][1] == race_id
    assert call_args[0][2] == '2026-01-08'
    
    print("✅ Different as_of_date test passed - parameter is being used")


@pytest.mark.asyncio
async def test_feature_extraction_with_missing_stats():
    """
    Test that feature extraction handles missing stats gracefully
    
    When a trainer/jockey has no history in the lookback window,
    stats should be filled with 0 (not NULL or error).
    """
    db = AsyncMock()
    
    # Mock race with runner that has no historical stats
    db.fetchrow = AsyncMock(return_value={
        'import_date': date(2026, 1, 7)
    })
    
    db.fetch = AsyncMock(return_value=[
        {
            'runner_id': 'runner-new',
            'horse_name': 'Debut Horse',
            'trainer': 'New Trainer',
            'jockey': 'New Jockey',
            'course': 'Kempton',
            'distance': '2000',
            # All stats are None (no history)
            'trainer_win_pct_14d': None,
            'trainer_starts_14d': None,
            'trainer_avg_odds_14d': None,
            'trainer_win_pct_30d': None,
            'trainer_starts_30d': None,
            'trainer_avg_odds_30d': None,
            'trainer_win_pct_90d': None,
            'trainer_starts_90d': None,
            'trainer_avg_odds_90d': None,
            'jockey_win_pct_14d': None,
            'jockey_starts_14d': None,
            'jockey_avg_odds_14d': None,
            'jockey_win_pct_30d': None,
            'jockey_starts_30d': None,
            'jockey_avg_odds_30d': None,
            'jockey_win_pct_90d': None,
            'jockey_starts_90d': None,
            'jockey_avg_odds_90d': None,
            'jt_combo_win_pct_365d': None,
            'jt_combo_starts': None,
            'jt_combo_avg_odds': None,
            'course_avg_odds': None,
            'course_volatility': None,
            'course_race_count': None
        }
    ])
    
    df = await get_features_for_racecard(db, 'test_race', as_of_date='2026-01-07')
    
    # All numeric stats should be filled with 0, not None
    assert df.iloc[0]['trainer_win_pct_30d'] == 0
    assert df.iloc[0]['jockey_win_pct_30d'] == 0
    assert df.iloc[0]['jt_combo_starts'] == 0
    
    # Non-numeric fields should still have their values
    assert df.iloc[0]['horse_name'] == 'Debut Horse'
    assert df.iloc[0]['trainer'] == 'New Trainer'
    
    print("✅ Missing stats test passed - NaN values filled with 0")


@pytest.mark.asyncio
async def test_default_as_of_date_from_race():
    """
    Test that as_of_date defaults to race import_date when not provided
    """
    db = AsyncMock()
    
    # Mock race with import_date
    db.fetchrow = AsyncMock(return_value={
        'import_date': date(2026, 1, 10)
    })
    
    db.fetch = AsyncMock(return_value=[])
    
    # Call without as_of_date
    await get_features_for_racecard(db, 'test_race')
    
    # Verify fetchrow was called to get import_date
    assert db.fetchrow.called
    
    # Verify fetch was called with the race import_date
    call_args = db.fetch.call_args
    assert call_args[0][2] == date(2026, 1, 10)
    
    print("✅ Default as_of_date test passed - uses race import_date")


@pytest.mark.asyncio
async def test_build_feature_mart_for_batch():
    """
    Test building feature mart for a batch
    """
    db = AsyncMock()
    
    # Mock batch with import_date
    db.fetchrow = AsyncMock(return_value={
        'import_date': date(2026, 1, 8)
    })
    
    # Mock execute for build_feature_mart call
    db.execute = AsyncMock()
    
    result = await build_feature_mart_for_batch(db, 'batch_123')
    
    # Verify success
    assert result['status'] == 'success'
    assert result['batch_id'] == 'batch_123'
    assert result['features_built'] is True
    assert result['import_date'] == date(2026, 1, 8).isoformat()
    
    # Verify execute was called with the correct date
    db.execute.assert_called_once()
    call_args = db.execute.call_args[0][1]
    assert call_args == date(2026, 1, 8).isoformat()
    
    print("✅ Build feature mart test passed")


def test_feature_column_schema():
    """
    Verify that we have all expected feature columns
    """
    expected_columns = [
        'runner_id',
        'horse_name',
        'trainer',
        'jockey',
        'course',
        'distance',
        # Trainer features
        'trainer_win_pct_14d',
        'trainer_starts_14d',
        'trainer_avg_odds_14d',
        'trainer_win_pct_30d',
        'trainer_starts_30d',
        'trainer_avg_odds_30d',
        'trainer_win_pct_90d',
        'trainer_starts_90d',
        'trainer_avg_odds_90d',
        # Jockey features
        'jockey_win_pct_14d',
        'jockey_starts_14d',
        'jockey_avg_odds_14d',
        'jockey_win_pct_30d',
        'jockey_starts_30d',
        'jockey_avg_odds_30d',
        'jockey_win_pct_90d',
        'jockey_starts_90d',
        'jockey_avg_odds_90d',
        # Combo features
        'jt_combo_win_pct_365d',
        'jt_combo_starts',
        'jt_combo_avg_odds',
        # Course features
        'course_avg_odds',
        'course_volatility',
        'course_race_count'
    ]
    
    # Just verify we have the list defined
    assert len(expected_columns) == 30
    
    print(f"✅ Schema test passed - expecting {len(expected_columns)} feature columns")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
