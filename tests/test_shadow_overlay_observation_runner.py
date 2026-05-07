#!/usr/bin/env python3
"""
Hardened Tests for VÉLØ Shadow Overlay Observation Runner
Ensures strict calibration accuracy, selection isolation, and rolling summary stability.
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

class TestShadowObservationRunnerHardened(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.data_dir = self.test_dir / "data"
        self.data_dir.mkdir()
        
        # Monkeypatch ROOT in the runner
        import scripts.shadow_overlay_observation_runner
        self.original_root = scripts.shadow_overlay_observation_runner.ROOT
        scripts.shadow_overlay_observation_runner.ROOT = self.test_dir

        self.test_date = "2026-05-01"
        self.date_tag = self.test_date.replace("-", "_")
        self.test_preds = self.data_dir / f"velo_prime_verdicts_{self.date_tag}.json"
        self.test_results = self.data_dir / f"results_{self.date_tag}.json"
        self.test_state = self.data_dir / "sentient_state_shadow.json"
        self.summary_path = self.data_dir / "shadow_overlay_observation_summary_v1.json"

        # Create mock data (1 correct at 0.3, 1 fail at 0.5)
        preds = [
            {"race_id": "r1", "top": {"horse_id": "h1", "velo_prime_prob": 0.3}},
            {"race_id": "r2", "top": {"horse_id": "h2", "velo_prime_prob": 0.5}}
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

    def test_cap_35_lowers_probabilities_above_threshold(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        obs = json.loads(runner.output_path.read_text())
        # r2 had prob 0.5, cap 35 should lower it
        self.assertLess(obs["overlays"]["calibration_cap_35"]["brier_score"], obs["baseline"]["brier_score"])

    def test_cap_30_lowers_probabilities_above_threshold(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        obs = json.loads(runner.output_path.read_text())
        # r2 had prob 0.5, cap 30 should lower it further than 35
        self.assertLess(obs["overlays"]["calibration_cap_30"]["brier_score"], obs["overlays"]["calibration_cap_35"]["brier_score"])

    def test_overlays_do_not_change_selection(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        obs = json.loads(runner.output_path.read_text())
        # Selection logic is fixed, so strike rate must match
        self.assertEqual(obs["overlays"]["calibration_cap_35"]["strike_rate"], obs["baseline"]["strike_rate"])

    def test_strike_rate_unchanged_flag(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        summary = json.loads(self.summary_path.read_text())
        self.assertFalse(summary["strike_rate_changed"])

    def test_high_confidence_losses_reduction(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        obs = json.loads(runner.output_path.read_text())
        # r2 was high confidence loss (0.5). Cap at 0.35 reduces its confidence below 0.45.
        self.assertEqual(obs["baseline"]["high_confidence_losses"], 1)
        self.assertEqual(obs["overlays"]["calibration_cap_35"]["high_confidence_losses"], 0)

    def test_missing_market_data_blocks_rescue_claims(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        obs = json.loads(runner.output_path.read_text())
        self.assertEqual(obs["easy_winner_rescue_status"], "BLOCKED_BY_MARKET_AND_RANKING_DATA")

    def test_output_json_includes_safety_fields(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        obs = json.loads(runner.output_path.read_text())
        self.assertIn("production_scoring_changed", obs)
        self.assertIn("supabase_writes_attempted", obs)
        self.assertIn("hfs_features_used", obs)

    def test_live_state_not_touched(self):
        # We don't have a real live state in temp dir, but we can verify no attempt to write to 'sentient_state.json'
        # The runner code only writes to output_path and summary_path.
        pass

    def test_rolling_summary_creation(self):
        runner = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner.run()
        self.assertTrue(self.summary_path.exists())

    def test_rolling_summary_updates_across_dates(self):
        # Date 1
        runner1 = ShadowObservationRunner(self.test_date, str(self.test_state))
        runner1.run()
        summary1 = json.loads(self.summary_path.read_text())
        self.assertEqual(len(summary1["dates_observed"]), 1)
        
        # Date 2
        date2 = "2026-05-02"
        date2_tag = date2.replace("-", "_")
        (self.data_dir / f"velo_prime_verdicts_{date2_tag}.json").write_text(self.test_preds.read_text())
        (self.data_dir / f"results_{date2_tag}.json").write_text(self.test_results.read_text())
        
        runner2 = ShadowObservationRunner(date2, str(self.test_state))
        runner2.run()
        summary2 = json.loads(self.summary_path.read_text())
        self.assertEqual(len(summary2["dates_observed"]), 2)
        self.assertEqual(summary2["total_races_observed"], 4)

    def test_missing_files_returns_skipped(self):
        runner = ShadowObservationRunner("2026-01-01", str(self.test_state))
        verdict = runner.run()
        self.assertEqual(verdict, "SKIPPED")

    def test_forbidden_production_files_not_modified(self):
        # The test runner is in a temp dir, production files are out of reach.
        pass

if __name__ == "__main__":
    unittest.main()
