#!/usr/bin/env python3
"""
Hardened Tests for VÉLØ EOD Result Study Layer
"""

import json
import os
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone

# Add root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.audit.eod_result_study_layer import EODStudyLayer

class TestEODResultStudyLayerHardened(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_date = "2026-05-01"
        cls.date_tag = cls.test_date.replace("-", "_")
        cls.date_compact = cls.test_date.replace("-", "")
        
        cls.test_status = ROOT / "data" / f"nightly_eod_learning_status_{cls.date_tag}.json"
        cls.test_council = ROOT / "data" / f"nightly_eod_learning_council_audit_{cls.date_tag}.json"
        cls.test_events = ROOT / "data" / f"nightly_eod_learning_events_{cls.date_tag}.jsonl"
        
        cls.out_json = ROOT / "data" / f"eod_result_study_{cls.date_compact}.json"
        cls.out_md = ROOT / "data" / f"eod_result_study_{cls.date_compact}.md"

    def setUp(self):
        # Clear output files
        for f in [self.out_json, self.out_md]:
            if f.exists(): f.unlink()
            
        # Create mock input data
        self.mock_status = {
            "date": self.test_date,
            "wins": 5,
            "matched_races": 20,
            "prediction_count": 20,
            "result_count": 20,
            "data_error_rate": 0.0,
            "engine_updates_applied_first_run": 20,
            "shadow_state_touched": True,
            "loss_count_by_type": {"WRONG_HORSE": 10, "CALIBRATION_ERROR": 5},
            "live_sentient_state_touched": False,
            "supabase_writes_attempted": False,
            "hfs_features_used": False
        }
        self.mock_council = {"council_verdict": "PASS"}
        
        # Create 10 events for ECE calculation
        self.mock_events = []
        for i in range(10):
            self.mock_events.append({
                "race_id": f"r{i}",
                "prediction_result": "WIN" if i < 5 else "LOSS",
                "prediction_snapshot": {"velo_prime_prob": 0.5, "horse": f"Horse {i}"}
            })
        
        self.test_status.write_text(json.dumps(self.mock_status))
        self.test_council.write_text(json.dumps(self.mock_council))
        with open(self.test_events, "w") as f:
            for e in self.mock_events:
                f.write(json.dumps(e) + "\n")

    def test_missing_nightly_status_blocks(self):
        self.test_status.unlink()
        study = EODStudyLayer(self.test_date)
        verdict = study.run()
        self.assertEqual(verdict, "BLOCKED")
        self.assertEqual(json.loads(self.out_json.read_text())["blocker"], "MISSING_NIGHTLY_STATUS")

    def test_missing_council_audit_blocks(self):
        self.test_council.unlink()
        study = EODStudyLayer(self.test_date)
        verdict = study.run()
        self.assertEqual(verdict, "BLOCKED")
        self.assertEqual(json.loads(self.out_json.read_text())["blocker"], "MISSING_COUNCIL_AUDIT")

    def test_top_3_accuracy_is_null_not_placeholder(self):
        study = EODStudyLayer(self.test_date)
        study.run()
        report = json.loads(self.out_json.read_text())
        self.assertIsNone(report["sigma"]["top_3_accuracy"])
        self.assertEqual(report["sigma"]["top_3_accuracy_status"], "UNAVAILABLE_MISSING_RANKING_DATA")

    def test_calibration_error_calculation(self):
        study = EODStudyLayer(self.test_date)
        study.run()
        report = json.loads(self.out_json.read_text())
        self.assertIsNotNone(report["sigma"]["calibration_error"])
        self.assertEqual(report["sigma"]["calibration_error_status"], "CALCULATED")

    def test_live_state_touched_fails(self):
        self.mock_status["live_sentient_state_touched"] = True
        self.test_status.write_text(json.dumps(self.mock_status))
        study = EODStudyLayer(self.test_date)
        verdict = study.run()
        self.assertEqual(verdict, "FAIL")

    def test_hfs_features_used_fails(self):
        self.mock_status["hfs_features_used"] = True
        self.test_status.write_text(json.dumps(self.mock_status))
        study = EODStudyLayer(self.test_date)
        verdict = study.run()
        self.assertEqual(verdict, "FAIL")

    def test_supabase_writes_attempted_fails(self):
        self.mock_status["supabase_writes_attempted"] = True
        self.test_status.write_text(json.dumps(self.mock_status))
        study = EODStudyLayer(self.test_date)
        verdict = study.run()
        self.assertEqual(verdict, "FAIL")

    def test_sigma_verdict_weak_day(self):
        self.mock_status["wins"] = 1 # 1/20 = 5% strike rate
        self.test_status.write_text(json.dumps(self.mock_status))
        study = EODStudyLayer(self.test_date)
        study.run()
        report = json.loads(self.out_json.read_text())
        self.assertEqual(report["sigma"]["sigma_verdict"], "WEAK_DAY")
        self.assertEqual(report["overall_verdict"], "PASS_WITH_WARNINGS")

    def test_playbook_g_critique_includes_watchlist(self):
        study = EODStudyLayer(self.test_date)
        study.run()
        report = json.loads(self.out_json.read_text())
        self.assertTrue(len(report["playbook_g"]["tomorrow_watchlist"]) > 0)
        self.assertIn("tomorrow_watchlist", report["playbook_g"])

if __name__ == "__main__":
    unittest.main()
