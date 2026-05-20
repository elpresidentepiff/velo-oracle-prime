#!/usr/bin/env python3
"""
Tests for Playbook G Shadow Adapter Safety
"""

import json
import os
import sys
import unittest
from pathlib import Path

# Add root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.playbook_g_shadow_adapter import PlaybookGShadowAdapter

class TestPlaybookGShadowAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_events = ROOT / "data" / "test_shadow_events.jsonl"
        cls.test_state = ROOT / "data" / "sentient_state_shadow.json"
        cls.test_audit = ROOT / "data" / "test_shadow_adapter_audit.json"
        cls.live_state = ROOT / "data" / "sentient_state.json"

    def setUp(self):
        # Clean up test files
        for f in [self.test_events, self.test_state, self.test_audit]:
            if f.exists(): f.unlink()
        
        # Ensure live state exists or create mock
        if not self.live_state.exists():
            self.live_state.write_text(json.dumps({"total_races_observed": 10}))

    def test_learning_allowed_false_skipped(self):
        """Test that learning_allowed=false events are skipped by the adapter"""
        event = {
            "race_id": "race_1",
            "idempotency_key": "race_1:2026-05-01",
            "learning_allowed": False,
            "prediction_snapshot": {"horse_id": "h1", "velo_prime_prob": 0.4},
            "result_snapshot": {"winner_id": "h1", "favourite_won": True}
        }
        self.test_events.write_text(json.dumps(event) + "\n")
        
        adapter = PlaybookGShadowAdapter(str(self.test_events), str(self.test_state), str(self.test_audit))
        adapter.run()
        
        audit = json.loads(self.test_audit.read_text())
        self.assertEqual(audit["events_read"], 1)
        self.assertEqual(audit["events_skipped_learning_not_allowed"], 1)
        self.assertEqual(audit["engine_updates_applied"], 0)
        self.assertEqual(audit["verdict"], "PASS_GATED")

    def test_duplicate_skipped(self):
        """Test that duplicate idempotency keys are skipped"""
        event = {
            "race_id": "race_1",
            "idempotency_key": "race_1:2026-05-01",
            "learning_allowed": True,
            "prediction_snapshot": {"horse_id": "h1", "velo_prime_prob": 0.4},
            "result_snapshot": {"winner_id": "h1", "favourite_won": True}
        }
        self.test_events.write_text(json.dumps(event) + "\n" + json.dumps(event) + "\n")
        
        adapter = PlaybookGShadowAdapter(str(self.test_events), str(self.test_state), str(self.test_audit))
        adapter.run()
        
        audit = json.loads(self.test_audit.read_text())
        self.assertEqual(audit["events_read"], 2)
        self.assertEqual(audit["events_skipped_duplicate"], 1)
        self.assertEqual(audit["engine_updates_applied"], 1)

    def test_live_state_isolation(self):
        """Prove that the adapter never touches the live sentient_state.json"""
        initial_mtime = self.live_state.stat().st_mtime
        
        event = {
            "race_id": "race_1",
            "idempotency_key": "race_1:2026-05-01",
            "learning_allowed": True,
            "prediction_snapshot": {"horse_id": "h1", "velo_prime_prob": 0.4},
            "result_snapshot": {"winner_id": "h1", "favourite_won": True}
        }
        self.test_events.write_text(json.dumps(event) + "\n")
        
        adapter = PlaybookGShadowAdapter(str(self.test_events), str(self.test_state), str(self.test_audit))
        adapter.run()
        
        self.assertEqual(self.live_state.stat().st_mtime, initial_mtime, "CRITICAL: Live state was modified!")
        self.assertTrue(self.test_state.exists(), "Shadow state should have been created")

    def test_disable_cloud_backup_enforced(self):
        """Test that the adapter correctly sets the disable_cloud_backup flag on the engine"""
        adapter = PlaybookGShadowAdapter(str(self.test_events), str(self.test_state), str(self.test_audit))
        self.assertTrue(adapter.engine.disable_cloud_backup)

    def test_safety_violation_on_non_shadow_file(self):
        """Test that the adapter raises an error if targeted at a non-shadow state file"""
        with self.assertRaises(ValueError):
            PlaybookGShadowAdapter(str(self.test_events), str(self.live_state), str(self.test_audit))

if __name__ == "__main__":
    unittest.main()
