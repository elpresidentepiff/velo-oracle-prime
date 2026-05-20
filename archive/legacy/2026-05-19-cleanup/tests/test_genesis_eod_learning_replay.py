#!/usr/bin/env python3
"""
Tests for VÉLØ Genesis EOD Learning Replay
"""

import json
import os
import sys
import unittest
import shutil
from pathlib import Path

# Add root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.genesis_eod_learning_replay import GenesisEODReplay

class TestGenesisEODReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_preds = ROOT / "data" / "test_genesis_preds.json"
        cls.test_results = ROOT / "data" / "test_genesis_results.json"
        cls.test_state = ROOT / "data" / "sentient_state_shadow.json"
        cls.test_events = ROOT / "data" / "test_genesis_events.jsonl"
        cls.test_report = ROOT / "data" / "test_genesis_report.json"
        cls.test_failures = ROOT / "data" / "test_genesis_failures.json"
        cls.live_state = ROOT / "data" / "sentient_state.json"

    def setUp(self):
        # Clear files
        for f in [self.test_preds, self.test_results, self.test_state, self.test_events, self.test_report, self.test_failures]:
            if f.exists(): f.unlink()
            
        # Ensure live state exists or create mock
        if not self.live_state.exists():
            self.live_state.write_text(json.dumps({"total_races_observed": 10}))
            
        # Create mock data
        self.mock_preds = [
            {
                "race_id": "gen_1",
                "date": "2026-01-01",
                "top": {"horse_id": "h1", "velo_prime_prob": 0.4}
            },
            {
                "race_id": "gen_2_unsafe",
                "date": "2026-01-01",
                "top": {"horse_id": "h2", "velo_prime_prob": 0.3, "strictly_ordered_vector": [1, 2, 3]}
            }
        ]
        self.mock_results = [
            {
                "race_id": "gen_1",
                "runners": [{"horse_id": "h1", "position": "1"}],
                "favourite_won": True
            },
            {
                "race_id": "gen_2_unsafe",
                "runners": [{"horse_id": "h3", "position": "1"}],
                "favourite_won": True
            }
        ]
        self.test_preds.write_text(json.dumps(self.mock_preds))
        self.test_results.write_text(json.dumps(self.mock_results))

    def test_learning_allowed_filtering(self):
        """Test that only safe events have learning_allowed=True"""
        replay = GenesisEODReplay(
            "data/test_genesis_preds.json",
            "data/test_genesis_results.json",
            str(self.test_state),
            str(self.test_events),
            str(self.test_report),
            str(self.test_failures)
        )
        replay.run()
        
        events = [json.loads(line) for line in self.test_events.read_text().splitlines() if line.strip()]
        self.assertEqual(len(events), 2)
        
        # gen_1 should be allowed
        gen_1 = next(e for e in events if e["race_id"] == "gen_1")
        self.assertTrue(gen_1["learning_allowed"])
        self.assertEqual(gen_1["learning_permission_reason"], "OUTCOME_ONLY_NO_HFS_FEATURES")
        
        # gen_2_unsafe should be blocked
        gen_2 = next(e for e in events if e["race_id"] == "gen_2_unsafe")
        self.assertFalse(gen_2["learning_allowed"])
        self.assertEqual(gen_2["failure_reason"], "UNSAFE_HFS_FIELD_PRESENT")

    def test_live_state_isolation(self):
        """Prove that genesis replay never touches the live sentient_state.json"""
        initial_mtime = self.live_state.stat().st_mtime
        
        replay = GenesisEODReplay(
            "data/test_genesis_preds.json",
            "data/test_genesis_results.json",
            str(self.test_state),
            str(self.test_events),
            str(self.test_report),
            str(self.test_failures)
        )
        replay.run()
        
        self.assertEqual(self.live_state.stat().st_mtime, initial_mtime, "CRITICAL: Live state was modified!")

    def test_idempotency_proof(self):
        """Test that engine updates are only applied on the first run of the adapter"""
        replay = GenesisEODReplay(
            "data/test_genesis_preds.json",
            "data/test_genesis_results.json",
            str(self.test_state),
            str(self.test_events),
            str(self.test_report),
            str(self.test_failures)
        )
        replay.run()
        
        report = json.loads(self.test_report.read_text())
        self.assertEqual(report["engine_updates_applied_first_run"], 1)
        self.assertEqual(report["engine_updates_applied_duplicate_run"], 0)
        self.assertEqual(report["duplicates_skipped_second_run"], 2) # gen_1 matched, gen_2 skipped due to safety

    def test_failures_ledger_accuracy(self):
        """Test that missing results are correctly logged as failures"""
        # Add a prediction with no matching result
        self.mock_preds.append({"race_id": "gen_missing", "date": "2026-01-02", "top": {"horse_id": "h4"}})
        self.test_preds.write_text(json.dumps(self.mock_preds))
        
        replay = GenesisEODReplay(
            "data/test_genesis_preds.json",
            "data/test_genesis_results.json",
            str(self.test_state),
            str(self.test_events),
            str(self.test_report),
            str(self.test_failures)
        )
        replay.run()
        
        failures = json.loads(self.test_failures.read_text())
        self.assertTrue(any(f["type"] == "MISSING_RESULT" and f["race_id"] == "gen_missing" for f in failures))

if __name__ == "__main__":
    unittest.main()
