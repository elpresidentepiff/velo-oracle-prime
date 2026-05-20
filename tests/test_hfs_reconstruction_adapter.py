#!/usr/bin/env python3
"""
Tests for VÉLØ HFS Reconstruction Adapter
"""

import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from scripts.backfill_historical_feature_store import build_rows_for_race, HFS_COLS, RunStats

class TestHFSReconstructionAdapter(unittest.TestCase):

    def setUp(self):
        self.mock_mm = MagicMock()
        self.mock_mm.ALL_V17_FEATURES = ["sp_dec", "implied_prob", "or_vs_field", "rpr_vs_field"]
        self.mock_mm.predict_sqpe.return_value = 0.15
        
        self.test_race = {
            "race_id": "test_race_001",
            "course": "Ascot",
            "distance_f": 8.0,
            "reconciled_at": datetime.now(timezone.utc)
        }
        self.test_runners = [
            {"horse_id": "h1", "horse_name": "Horse 1", "sp_dec": 2.0, "is_winner": True, "position": 1},
            {"horse_id": "h2", "horse_name": "Horse 2", "sp_dec": 2.0, "is_winner": False, "position": 2},
            {"horse_id": "h3", "horse_name": "Horse 3", "sp_dec": 2.0, "is_winner": False, "position": 3}
        ]
        # Odds 2.0, 2.0, 2.0 -> Overround 1.5 -> MPI > 0
        self.stats = RunStats()

    def test_row_schema_compliance(self):
        """Test that build_rows_for_race output length matches HFS_COLS length"""
        rows, _, _, _, _ = build_rows_for_race(self.test_race, self.test_runners, self.mock_mm, self.stats)
        
        expected_len = len(HFS_COLS.split(","))
        self.assertEqual(len(rows[0]), expected_len)
        self.assertEqual(len(rows), 3)

    def test_mpi_chaos_consistency(self):
        """Test that Chaos Bloom is constant within race and MPI is calculated"""
        rows, _, chaos_vals, _, _ = build_rows_for_race(self.test_race, self.test_runners, self.mock_mm, self.stats)
        
        # MPI is index 22, Chaos is index 23
        mpi = rows[0][22]
        chaos = rows[0][23]
        
        self.assertGreater(mpi, 0)
        self.assertGreater(chaos, 0)
        
        for row in rows:
            self.assertEqual(row[22], mpi)
            self.assertEqual(row[23], chaos)
            
        self.assertEqual(len(set(chaos_vals)), 1)

    def test_leakage_risk_no_timestamp(self):
        """Test that sp_dec without timestamp creates LEAKAGE_RISK and training_safe=false"""
        rows, _, _, _, _ = build_rows_for_race(self.test_race, self.test_runners, self.mock_mm, self.stats)
        
        payload = json.loads(rows[0][35])
        self.assertFalse(payload["training_safe"])
        self.assertEqual(payload["leakage_status"], "LEAKAGE_RISK")
        self.assertEqual(self.stats.rows_leakage_risk, 3)
        self.assertEqual(self.stats.rows_training_safe, 0)

    def test_training_safe_with_timestamp(self):
        """Test that valid odds_ts marks row as training_safe"""
        now = datetime.now(timezone.utc)
        runners_with_ts = [
            {"horse_id": "h1", "horse_name": "H1", "sp_dec": 2.0, "is_winner": True, "position": 1, "odds_ts": now - timedelta(minutes=10)}
        ]
        race_with_reconciled = {
            "race_id": "r1",
            "reconciled_at": now
        }
        
        rows, _, _, _, _ = build_rows_for_race(race_with_reconciled, runners_with_ts, self.mock_mm, self.stats)
        payload = json.loads(rows[0][35])
        
        self.assertTrue(payload["training_safe"])
        self.assertEqual(payload["leakage_status"], "CLEAN")
        self.assertEqual(self.stats.rows_training_safe, 1)

    def test_provenance_presence(self):
        """Test that batch_id, audit_id, and reconstruction_version are present"""
        rows, _, _, _, _ = build_rows_for_race(self.test_race, self.test_runners, self.mock_mm, self.stats)
        
        # Reconstruction version is index 3
        self.assertEqual(rows[0][3], "V17_REPAIR_B1")
        
        payload = json.loads(rows[0][35])
        meta = payload["_meta"]
        self.assertEqual(meta["batch_id"], self.stats.batch_id)
        self.assertEqual(meta["audit_id"], self.stats.audit_id)
        self.assertEqual(meta["version"], "V17_REPAIR_B1")

if __name__ == "__main__":
    unittest.main()
