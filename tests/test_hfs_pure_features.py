#!/usr/bin/env python3
"""
Tests for VÉLØ HFS Pure Feature Functions
"""

import unittest
from datetime import datetime, timedelta, timezone
from app.services.hfs_pure_features import (
    compute_mpi_from_pre_race_odds,
    compute_chaos_bloom_from_mpi,
    validate_odds_temporal_safety,
    build_feature_provenance
)

class TestHFSPureFeatures(unittest.TestCase):

    def test_mpi_tight_market(self):
        # A tight market (low overround, distinct favorite)
        odds = [2.0, 4.0, 6.0, 10.0, 20.0]
        # Overround = 0.5 + 0.25 + 0.16 + 0.1 + 0.05 = 1.06 (Low)
        mpi = compute_mpi_from_pre_race_odds(odds)
        self.assertLess(mpi, 30.0)

    def test_mpi_blown_market(self):
        # A blown market (high overround, price clustering)
        odds = [3.0, 3.0, 3.0, 3.0, 3.0]
        # Overround = 0.33 * 5 = 1.66 (High)
        mpi = compute_mpi_from_pre_race_odds(odds)
        self.assertGreater(mpi, 70.0)

    def test_mpi_empty_or_invalid(self):
        self.assertEqual(compute_mpi_from_pre_race_odds([]), 50.0)
        self.assertEqual(compute_mpi_from_pre_race_odds([1.0, 0.0]), 50.0)

    def test_chaos_bloom_scaling(self):
        # Small field, low MPI
        small_chaos = compute_chaos_bloom_from_mpi(10.0, 4)
        # Large field, high MPI
        large_chaos = compute_chaos_bloom_from_mpi(80.0, 20)
        
        self.assertLess(small_chaos, large_chaos)
        self.assertLessEqual(large_chaos, 100.0)
        self.assertGreaterEqual(small_chaos, 0.0)

    def test_chaos_bloom_empty_field(self):
        self.assertEqual(compute_chaos_bloom_from_mpi(50.0, 0), 0.0)

    def test_temporal_safety(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=5)
        future = now + timedelta(minutes=5)
        
        self.assertTrue(validate_odds_temporal_safety(past, now))
        self.assertTrue(validate_odds_temporal_safety(now, now))
        self.assertFalse(validate_odds_temporal_safety(future, now))

    def test_temporal_safety_invalid_types(self):
        self.assertFalse(validate_odds_temporal_safety("2026-05-01", datetime.now(timezone.utc)))

    def test_provenance_schema(self):
        meta = build_feature_provenance("V17_REPAIR_B1", "historical_backfill", race_id="test_001")
        self.assertEqual(meta["version"], "V17_REPAIR_B1")
        self.assertEqual(meta["source"], "historical_backfill")
        self.assertEqual(meta["race_id"], "test_001")
        self.assertIn("computed_at", meta)
        self.assertEqual(meta["method"], "pure_function_v1")

if __name__ == "__main__":
    unittest.main()
