#!/usr/bin/env python3
"""
Tests for VÉLØ EOD Shadow Learning Bridge (Replay Validation)
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

from scripts.eod_shadow_learning_bridge import ShadowLearningBridge, SHADOW_OUTCOME_LEDGER, SHADOW_LOSS_LEDGER, SHADOW_SENTIENT_STATE

class TestShadowReplayValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_date = "2026-05-01"
        cls.prediction_file = ROOT / "data" / f"velo_prime_verdicts_{cls.test_date.replace('-', '_')}.json"
        cls.result_file = ROOT / "data" / f"results_{cls.test_date.replace('-', '_')}.json"
        
        # Backup existing files if they exist
        cls.backups = {}
        for f in [SHADOW_OUTCOME_LEDGER, SHADOW_LOSS_LEDGER, SHADOW_SENTIENT_STATE, cls.prediction_file, cls.result_file]:
            if f.exists():
                cls.backups[f] = f.read_bytes()
                f.unlink()

    @classmethod
    def tearDownClass(cls):
        # Restore backups
        for f, content in cls.backups.items():
            f.write_bytes(content)

    def setUp(self):
        # Clear files before each test
        for f in [SHADOW_OUTCOME_LEDGER, SHADOW_LOSS_LEDGER, SHADOW_SENTIENT_STATE]:
            if f.exists():
                f.unlink()
        
        # Create mock data
        self.mock_predictions = [
            {
                "race_id": "race_replay_1",
                "top": {"horse_id": "h1", "horse": "Horse 1", "velo_prime_prob": 0.4, "chaos_bloom": 0.2, "improvement_score": 0.1}
            },
            {
                "race_id": "race_replay_2",
                "top": {"horse_id": "h2", "horse": "Horse 2", "velo_prime_prob": 0.3, "chaos_bloom": 0.2, "improvement_score": 0.1}
            }
        ]
        self.mock_results = {
            "results": [
                {
                    "race_id": "race_replay_1",
                    "runners": [{"horse_id": "h1", "position": "1"}],
                    "favourite_won": True
                },
                {
                    "race_id": "race_replay_2",
                    "runners": [{"horse_id": "h_other", "position": "1"}],
                    "favourite_won": True
                }
            ]
        }
        self.prediction_file.write_text(json.dumps(self.mock_predictions))
        self.result_file.write_text(json.dumps(self.mock_results))

    def test_shadow_state_updated(self):
        """Test that shadow sentient state total_races_observed increases"""
        bridge = ShadowLearningBridge(date_str=self.test_date)
        initial_races = bridge.engine.state.get("total_races_observed", 0)
        bridge.run()
        
        updated_races = bridge.engine.state.get("total_races_observed", 0)
        self.assertEqual(updated_races, initial_races + 2)
        self.assertTrue(SHADOW_SENTIENT_STATE.exists())

    def test_replay_idempotency_state(self):
        """Test that re-running replay on same events does not double-count in state"""
        bridge = ShadowLearningBridge(date_str=self.test_date)
        bridge.run()
        
        state_after_1 = json.loads(SHADOW_SENTIENT_STATE.read_text())
        races_1 = state_after_1.get("total_races_observed")
        
        # Run again
        bridge.run()
        state_after_2 = json.loads(SHADOW_SENTIENT_STATE.read_text())
        races_2 = state_after_2.get("total_races_observed")
        
        self.assertEqual(races_1, races_2, "Idempotency failed: state double-counted races")

    def test_live_state_isolation(self):
        """Prove live sentient_state.json is untouched"""
        live_state_file = ROOT / "data" / "sentient_state.json"
        if not live_state_file.exists():
            live_state_file.write_text(json.dumps({"total_races_observed": 10}))
            
        initial_mtime = live_state_file.stat().st_mtime
        
        bridge = ShadowLearningBridge(date_str=self.test_date)
        bridge.run()
        
        self.assertEqual(live_state_file.stat().st_mtime, initial_mtime, "Live state was modified!")

    def test_learning_allowed_remains_false(self):
        """Prove learning_allowed remains false while HFS_TRAINING_SAFE = false"""
        bridge = ShadowLearningBridge(date_str=self.test_date)
        bridge.run()
        
        with open(SHADOW_OUTCOME_LEDGER, "r") as f:
            for line in f:
                event = json.loads(line)
                self.assertFalse(event["learning_allowed"])
                self.assertFalse(event["hfs_training_safe"])

    def test_loss_classification_reflection(self):
        """Prove loss types are reflected in shadow state BEC"""
        bridge = ShadowLearningBridge(date_str=self.test_date)
        initial_state = json.loads(SHADOW_SENTIENT_STATE.read_text())
        initial_fav_prot = initial_state.get("house_behaviour_map", {}).get("favourites_protected", 0)
        
        bridge.run()
        
        # race_replay_1: WIN, fav_won=True -> favourites_protected += 1
        # race_replay_2: LOSS, fav_won=True -> favourites_protected += 1
        # total favourites_protected should increase by 2
        
        state = json.loads(SHADOW_SENTIENT_STATE.read_text())
        bec = state.get("house_behaviour_map", {})
        self.assertEqual(bec.get("favourites_protected"), initial_fav_prot + 2)

if __name__ == "__main__":
    unittest.main()
