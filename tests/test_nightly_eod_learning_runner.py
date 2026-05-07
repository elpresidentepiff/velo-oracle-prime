#!/usr/bin/env python3
"""
Hardened Tests for VÉLØ Nightly EOD Learning Runner
Ensures strict fixture isolation using temporary directories.
"""

import json
import os
import sys
import unittest
import shutil
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# Add root to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.nightly_eod_learning_runner import NightlyEODRunner

class TestNightlyEODRunner(unittest.TestCase):
    def setUp(self):
        # Create a unique temporary directory for each test
        self.test_dir = Path(tempfile.mkdtemp())
        self.data_dir = self.test_dir / "data"
        self.data_dir.mkdir()
        
        # Test parameters
        self.test_date = "2026-12-31" # Use a date unlikely to exist in real data
        self.date_tag = self.test_date.replace("-", "_")
        
        # Path overrides
        self.test_preds = self.data_dir / f"velo_prime_verdicts_{self.date_tag}.json"
        self.test_results = self.data_dir / f"results_{self.date_tag}.json"
        self.test_state = self.data_dir / "sentient_state_shadow.json"
        self.live_state = self.data_dir / "sentient_state.json"
        
        # Initialize mock live state
        self.live_state.write_text(json.dumps({"total_races_observed": 10}))
        
        # Create mock data
        self.mock_preds = [
            {"race_id": "test_r1", "date": self.test_date, "top": {"horse_id": "h1", "velo_prime_prob": 0.4}}
        ]
        self.mock_results = [
            {"race_id": "test_r1", "runners": [{"horse_id": "h1", "position": "1"}], "favourite_won": True}
        ]
        
        # Monkeypatch ROOT in the runner to point to our temp dir
        import scripts.nightly_eod_learning_runner
        self.original_root = scripts.nightly_eod_learning_runner.ROOT
        scripts.nightly_eod_learning_runner.ROOT = self.test_dir

    def tearDown(self):
        # Restore ROOT
        import scripts.nightly_eod_learning_runner
        scripts.nightly_eod_learning_runner.ROOT = self.original_root
        # Remove temp directory
        shutil.rmtree(self.test_dir)

    def test_missing_predictions_fail(self):
        # No pred file created
        runner = NightlyEODRunner(self.test_date, str(self.test_state))
        verdict = runner.run()
        self.assertEqual(verdict, "FAIL")
        
        status_file = self.data_dir / f"nightly_eod_learning_status_{self.date_tag}.json"
        status = json.loads(status_file.read_text())
        self.assertEqual(status["verdict"], "FAIL")

    def test_matched_races_zero_fail(self):
        self.test_preds.write_text(json.dumps(self.mock_preds))
        self.test_results.write_text(json.dumps([])) # Empty results
        
        runner = NightlyEODRunner(self.test_date, str(self.test_state))
        verdict = runner.run()
        self.assertEqual(verdict, "FAIL")
        
        failures_file = self.data_dir / f"nightly_eod_learning_failures_{self.date_tag}.json"
        failures = json.loads(failures_file.read_text())
        self.assertTrue(any(f["type"] == "MATCHED_RACES_ZERO" for f in failures))

    def test_successful_run_and_idempotency(self):
        self.test_preds.write_text(json.dumps(self.mock_preds))
        self.test_results.write_text(json.dumps(self.mock_results))
        
        runner = NightlyEODRunner(self.test_date, str(self.test_state))
        verdict = runner.run()
        self.assertEqual(verdict, "PASS")
        
        status_file = self.data_dir / f"nightly_eod_learning_status_{self.date_tag}.json"
        status = json.loads(status_file.read_text())
        
        # Verify first run applied update
        self.assertEqual(status["engine_updates_applied_first_run"], 1)
        
        # Verify second run (internal to run() method) applied zero additional updates
        self.assertEqual(status["engine_updates_applied_duplicate_run"], 0)
        self.assertEqual(status["duplicates_skipped_second_run"], 1)
        
        # Verify council audit exists
        council_file = self.data_dir / f"nightly_eod_learning_council_audit_{self.date_tag}.json"
        self.assertTrue(council_file.exists())

    def test_data_error_rate_threshold(self):
        # 1 matched, 1 unmatched -> 50% error rate
        self.mock_preds.append({"race_id": "test_r_missing", "date": self.test_date, "top": {"horse_id": "h2"}})
        self.test_preds.write_text(json.dumps(self.mock_preds))
        self.test_results.write_text(json.dumps(self.mock_results))
        
        runner = NightlyEODRunner(self.test_date, str(self.test_state), data_error_threshold=0.1)
        verdict = runner.run()
        self.assertEqual(verdict, "FAIL")
        
        status_file = self.data_dir / f"nightly_eod_learning_status_{self.date_tag}.json"
        status = json.loads(status_file.read_text())
        self.assertGreater(status["data_error_rate"], 0.1)

    def test_live_state_isolation(self):
        self.test_preds.write_text(json.dumps(self.mock_preds))
        self.test_results.write_text(json.dumps(self.mock_results))
        
        initial_hash = hashlib.sha256(self.live_state.read_bytes()).hexdigest()
        runner = NightlyEODRunner(self.test_date, str(self.test_state))
        runner.run()
        
        after_hash = hashlib.sha256(self.live_state.read_bytes()).hexdigest()
        self.assertEqual(initial_hash, after_hash, "Live state was modified!")

if __name__ == "__main__":
    unittest.main()
