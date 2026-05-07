#!/usr/bin/env python3
"""
Tests for VÉLØ HFS Real Dry-Run No-Write Harness
"""

import json
import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add root to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.hfs_real_dry_run_no_write import HFSDryRunHarness

class TestHFSDryRunHarness(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.data_dir = self.test_dir / "data"
        self.data_dir.mkdir()
        
        # Create mock genesis events
        self.events_path = self.data_dir / "genesis_eod_learning_events.jsonl"
        self.now = datetime.now(timezone.utc)
        
        events = [
            {
                "race_id": "r1_safe",
                "prediction_timestamp": self.now.isoformat(),
                "prediction_snapshot": {
                    "horse_id": "h1", "sp_dec": 5.0,
                    "odds_timestamp": (self.now - timedelta(minutes=10)).isoformat()
                }
            },
            {
                "race_id": "r2_leaky",
                "prediction_timestamp": self.now.isoformat(),
                "prediction_snapshot": {
                    "horse_id": "h2", "sp_dec": 10.0
                    # Missing odds_timestamp
                }
            }
        ]
        with open(self.events_path, "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
        
        # Monkeypatch ROOT in harness
        import scripts.hfs_real_dry_run_no_write
        self.original_root = scripts.hfs_real_dry_run_no_write.ROOT
        scripts.hfs_real_dry_run_no_write.ROOT = self.test_dir

    def tearDown(self):
        import scripts.hfs_real_dry_run_no_write
        scripts.hfs_real_dry_run_no_write.ROOT = self.original_root
        shutil.rmtree(self.test_dir)

    def test_missing_odds_timestamp_forces_leakage_risk(self):
        harness = HFSDryRunHarness()
        harness.run()
        leaky = next(r for r in harness.sample_rows if r["race_id"] == "r2_leaky")
        self.assertFalse(leaky["training_safe"])
        self.assertEqual(leaky["leakage_status"], "LEAKAGE_RISK")

    def test_sp_only_row_cannot_be_training_safe(self):
        harness = HFSDryRunHarness()
        harness.run()
        leaky = next(r for r in harness.sample_rows if r["race_id"] == "r2_leaky")
        self.assertFalse(leaky["training_safe"])

    def test_pre_race_timestamp_valid_is_safe(self):
        harness = HFSDryRunHarness()
        harness.run()
        safe = next(r for r in harness.sample_rows if r["race_id"] == "r1_safe")
        self.assertTrue(safe["training_safe"])
        self.assertEqual(safe["leakage_status"], "CLEAN")

    def test_provenance_integrity(self):
        harness = HFSDryRunHarness()
        harness.run()
        row = harness.sample_rows[0]
        self.assertEqual(row["reconstruction_version"], "V17_REPAIR_B3")
        self.assertTrue(len(row["batch_id"]) > 0)
        self.assertTrue(len(row["audit_id"]) > 0)

    def test_no_database_writes(self):
        harness = HFSDryRunHarness()
        harness.run()
        self.assertFalse(harness.report["supabase_writes_attempted"])
        self.assertEqual(harness.report["historical_feature_store_rows_written"], 0)

    def test_report_artifacts_created(self):
        harness = HFSDryRunHarness()
        harness.run()
        self.assertTrue((self.data_dir / "hfs_real_dry_run_report_v1.json").exists())
        self.assertTrue((self.data_dir / "hfs_real_dry_run_sample_rows_v1.json").exists())

if __name__ == "__main__":
    unittest.main()
