#!/usr/bin/env python3
"""
Tests for VÉLØ Shadow Overlay Observation Runner
"""

import json
import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Add root to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.shadow_overlay_observation_runner import ShadowObservationRunner

class TestShadowObservationRunner(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.data_dir = self.test_dir / "data"
        self.data_dir.mkdir()
        
        self.test_date = "2026-05-01"
        self.date_tag = self.test_date.replace("-", "_")
        self.test_preds = self.data_dir / f"velo_prime_verdicts_{self.date_tag}.json"
        self.test_results = self.data_dir / f"results_{self.date_tag}.json"
        self.test_state = self.data_dir / "sentient_state_shadow.json"
        
        # Monkeypatch ROOT
        import scripts.shadow_overlay_observation_runner
        self.original_root = scripts.shadow_overlay_observation_runner.ROOT
        scripts.shadow_overlay_observation_runner.ROOT = self.test_dir

        # Create mock data
        preds = [
            {"race_id": "r1", "top": {"horse_id": "h1", "velo_prime_prob": 0.5}},
            {"race_id": "r2", "top": {"horse_id": "h2", "velo_prime_prob": 0.6}}
        ]
        results = [
            {"race_id": "r1", "runners": [{"horse_id": "h1", "position": "1"}]},
            {"race_id": "r2", "runners": [{"horse_id": "h_other", "position": "1"}]}
        ]
        self.test_preds.write_text(json.dumps(preds))
        self.test_results.write_text(json.dumps(results))

    def tearDown(self):
        import scripts.shadow_overlay_observation_runner
        scripts.shadow_overlay_observation_runner.ROOT = self.original_root
        shutil.rmtree(self.test_dir)

    def test_cap_35_lowers_high_probabilities(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        obs = json.loads(runner.output_path.read_text())
        # Prob 0.5 and 0.6 both capped to 0.35
        # We verify that brier_score is different (lower is better, but here we just check it was computed)
        self.assertLess(obs["overlays"]["calibration_cap_35"]["brier_score"], obs["baseline"]["brier_score"])

    def test_overlays_do_not_change_selection(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        obs = json.loads(runner.output_path.read_text())
        # Selection is fixed to the same horse_id, so strike rate must be identical
        self.assertEqual(obs["overlays"]["calibration_cap_35"]["strike_rate"], obs["baseline"]["strike_rate"])

    def test_high_confidence_losses_reduction(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        obs = json.loads(runner.output_path.read_text())
        # r2 was LOSS with 0.6 prob -> HCL = 1
        # Capping at 0.35 means 0.6 becomes 0.35 (<0.45) -> HCL = 0
        self.assertEqual(obs["baseline"]["high_confidence_losses"], 1)
        self.assertEqual(obs["overlays"]["calibration_cap_35"]["high_confidence_losses"], 0)

    def test_safety_fields_active(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        obs = json.loads(runner.output_path.read_text())
        self.assertFalse(obs["production_scoring_changed"])
        self.assertFalse(obs["supabase_writes_attempted"])
        self.assertFalse(obs["hfs_features_used"])

if __name__ == "__main__":
    unittest.main()
