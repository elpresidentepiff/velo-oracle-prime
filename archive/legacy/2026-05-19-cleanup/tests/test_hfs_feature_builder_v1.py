import unittest
import math
from datetime import datetime, UTC, timedelta
from unittest.mock import MagicMock
from app.services.velo_prime_service import compute_market_intelligence, _build_live_features, score_race_velo_prime

class TestHFSFeatureBuilderV1(unittest.TestCase):

    def test_mpi_normalization(self):
        """MPI must normalize to 1.0 across the field."""
        runners = [
            {"best_odds_decimal": 2.0},  # p=0.5
            {"best_odds_decimal": 4.0},  # p=0.25
            {"best_odds_decimal": 4.0},  # p=0.25
        ]
        mpis, chaos = compute_market_intelligence(runners)
        self.assertAlmostEqual(sum(mpis), 1.0, places=5)
        self.assertAlmostEqual(mpis[0], 0.5, places=2)
        self.assertAlmostEqual(mpis[1], 0.25, places=2)

    def test_chaos_bloom_mathematical_integrity(self):
        """Chaos Bloom must reflect market uncertainty correctly."""
        # 1. High certainty market (dominant favourite)
        runners_certain = [{"best_odds_decimal": 1.1}, {"best_odds_decimal": 20.0}, {"best_odds_decimal": 20.0}]
        _, chaos_low = compute_market_intelligence(runners_certain)
        
        # 2. Low certainty market (balanced field)
        runners_uncertain = [{"best_odds_decimal": 3.0}, {"best_odds_decimal": 3.0}, {"best_odds_decimal": 3.0}]
        _, chaos_high = compute_market_intelligence(runners_uncertain)
        
        self.assertTrue(chaos_low < chaos_high, f"Entropy {chaos_low} should be lower than {chaos_high} for dominant favourite")
        self.assertTrue(0 <= chaos_low <= 1.0)
        self.assertTrue(0 <= chaos_high <= 1.0)

    def test_leakage_safety_gate(self):
        """Rows with odds_timestamp >= prediction_timestamp must be marked LEAKAGE_RISK."""
        race = {
            "race_id": "leak_race",
            "prediction_timestamp": "2026-05-05T12:00:00Z"
        }
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {"runs_since_win": 1} # Complete

        # 1. Safe row
        runner_safe = {
            "horse_id": "h1",
            "best_odds_decimal": 5.0,
            "odds_timestamp": "2026-05-05T11:59:59Z"
        }
        feats_safe = _build_live_features(runner_safe, race, [], [], extractor=mock_extractor, is_training=True)
        self.assertEqual(feats_safe["_meta"]["leakage_status"], "CLEAN")
        self.assertTrue(feats_safe["_meta"]["training_safe"])

        # 2. Leaked row (odds same as prediction)
        runner_leaked = {
            "horse_id": "h2",
            "best_odds_decimal": 5.0,
            "odds_timestamp": "2026-05-05T12:00:00Z"
        }
        feats_leaked = _build_live_features(runner_leaked, race, [], [], extractor=mock_extractor, is_training=True)
        self.assertEqual(feats_leaked["_meta"]["leakage_status"], "LEAKAGE_RISK")
        self.assertFalse(feats_leaked["_meta"]["training_safe"])

        # 3. Missing timestamp
        runner_no_ts = {
            "horse_id": "h3",
            "best_odds_decimal": 5.0
        }
        feats_no_ts = _build_live_features(runner_no_ts, race, [], [], extractor=mock_extractor, is_training=True)
        self.assertEqual(feats_no_ts["_meta"]["leakage_status"], "LEAKAGE_RISK")
        self.assertFalse(feats_no_ts["_meta"]["training_safe"])

    def test_no_defaults_in_training_rows(self):
        """Training rows must have NULLs and FEATURE_INCOMPLETE on empty extractor result."""
        from app.services.v17_feature_extractor import DEFAULTS
        
        race = {"race_id": "test"}
        runner = {"horse_id": "h1"}
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {} # Empty result
        
        feats = _build_live_features(runner, race, [], [], extractor=mock_extractor, is_training=True)
        
        for k in DEFAULTS:
            self.assertIsNone(feats.get(k), f"Feature {k} should be None in training row for incomplete extraction")
        
        self.assertFalse(feats["_meta"]["training_safe"])
        self.assertEqual(feats["_meta"]["feature_status"], "FEATURE_INCOMPLETE")
        self.assertEqual(feats["_meta"]["feature_quality"], "DEGRADED")

    def test_feature_error_marks_unsafe(self):
        """Extraction error must mark the row as training_safe=false."""
        mock_extractor = MagicMock()
        mock_extractor.extract.side_effect = Exception("API Timeout")
        
        race = {"race_id": "test"}
        runner = {"horse_id": "h1"}
        
        feats = _build_live_features(runner, race, [], [], extractor=mock_extractor, is_training=True)
        self.assertFalse(feats["_meta"]["training_safe"])
        self.assertEqual(feats["_meta"]["feature_status"], "FEATURE_ERROR")

if __name__ == "__main__":
    unittest.main()
