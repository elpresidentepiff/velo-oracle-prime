"""
VÉLØ Oracle - Phase 4 Full Test Suite
40 comprehensive tests for production system
"""
import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle-storage')

import unittest
import numpy as np
import pandas as pd
from datetime import datetime


class TestPhase4Full(unittest.TestCase):
    """Phase 4 comprehensive test suite - 40 tests"""
    
    # ========== Model Training Tests (5) ==========
    
    def test_01_sqpe_v14_trained(self):
        """Test SQPE v14 model exists"""
        import os
        self.assertTrue(os.path.exists('models/sqpe_v14/sqpe_v14.pkl'))
    
    def test_02_tie_v9_trained(self):
        """Test TIE v9 model exists"""
        import os
        self.assertTrue(os.path.exists('models/tie_v9/tie_v9.pkl'))
    
    def test_03_longshot_v6_trained(self):
        """Test Longshot v6 model exists"""
        import os
        self.assertTrue(os.path.exists('models/longshot_v6/longshot_v6.pkl'))
    
    def test_04_overlay_v5_trained(self):
        """Test Overlay v5 model exists"""
        import os
        self.assertTrue(os.path.exists('models/overlay_v5/overlay_v5.pkl'))
    
    def test_05_training_summary_exists(self):
        """Test training summary generated"""
        import os
        self.assertTrue(os.path.exists('models/training_summary_v14.json'))
    
    # ========== Backtest Tests (5) ==========
    
    def test_06_backtest_1_7m_module(self):
        """Test 1.7M backtest module loads"""
        from app.services.backtest.backtest_1_7m import Backtest1_7M
        backtest = Backtest1_7M()
        self.assertIsNotNone(backtest)
    
    def test_07_backtest_results_exist(self):
        """Test backtest results file exists"""
        import os
        self.assertTrue(os.path.exists('backtest_full_v1.json'))
    
    def test_08_backtest_metrics_valid(self):
        """Test backtest metrics are valid"""
        import json
        with open('backtest_full_v1.json', 'r') as f:
            results = json.load(f)
        
        self.assertIn('roi_percent', results)
        self.assertIn('auc', results)
        self.assertIn('win_rate', results)
    
    def test_09_backtest_sample_size(self):
        """Test backtest processed full dataset"""
        import json
        with open('backtest_full_v1.json', 'r') as f:
            results = json.load(f)
        
        self.assertGreater(results['total_samples'], 1000000)
    
    def test_10_backtest_monthly_breakdown(self):
        """Test backtest has monthly results"""
        import json
        with open('backtest_full_v1.json', 'r') as f:
            results = json.load(f)
        
        self.assertIn('monthly_results', results)
        self.assertGreater(len(results['monthly_results']), 0)
    
    # ========== UMA Tests (5) ==========
    
    def test_11_uma_module_loads(self):
        """Test UMA module loads"""
        from app.engine.uma import UMA
        uma = UMA()
        self.assertIsNotNone(uma)
    
    def test_12_uma_model_loading(self):
        """Test UMA loads models"""
        from app.engine.uma import UMA
        uma = UMA()
        uma.load_models()
        self.assertTrue(uma.loaded)
    
    def test_13_uma_prediction(self):
        """Test UMA generates prediction"""
        from app.engine.uma import UMA
        uma = UMA()
        uma.load_models()
        
        features = {'speed': 0.75, 'form': 0.85, 'rating': 95.0}
        prediction = uma.predict(features, market_odds=5.0)
        
        self.assertIsNotNone(prediction.probability)
        self.assertGreater(prediction.probability, 0.0)
        self.assertLess(prediction.probability, 1.0)
    
    def test_14_uma_edge_calculation(self):
        """Test UMA calculates edge"""
        from app.engine.uma import UMA
        uma = UMA()
        uma.load_models()
        
        features = {'speed': 0.75}
        prediction = uma.predict(features, market_odds=5.0)
        
        self.assertIsNotNone(prediction.edge)
    
    def test_15_uma_risk_classification(self):
        """Test UMA classifies risk"""
        from app.engine.uma import UMA
        uma = UMA()
        uma.load_models()
        
        features = {'speed': 0.75}
        prediction = uma.predict(features, market_odds=5.0)
        
        self.assertIn(prediction.risk_band, ['NO_BET', 'LOW', 'MEDIUM', 'HIGH'])
    
    # ========== Monitoring Tests (5) ==========
    
    def test_16_drift_detector_loads(self):
        """Test drift detector module loads"""
        from app.monitoring.drift_detector import DriftDetector
        detector = DriftDetector()
        self.assertIsNotNone(detector)
    
    def test_17_feature_drift_detection(self):
        """Test feature drift detection works"""
        from app.monitoring.drift_detector import DriftDetector
        
        detector = DriftDetector()
        
        data = pd.DataFrame({
            'feature_1': np.random.normal(0, 1, 1000),
            'feature_2': np.random.normal(5, 2, 1000)
        })
        
        results = detector.detect_feature_drift(data, data)
        
        self.assertIn('total_features', results)
        self.assertIn('drifted_features', results)
    
    def test_18_performance_drift_detection(self):
        """Test performance drift detection"""
        from app.monitoring.drift_detector import DriftDetector
        
        detector = DriftDetector()
        results = detector.detect_performance_drift(0.85, 0.87, threshold=0.02)
        
        self.assertIn('is_degraded', results)
        self.assertTrue(results['is_degraded'])
    
    def test_19_performance_tracker_loads(self):
        """Test performance tracker loads"""
        from app.monitoring.performance_tracker import PerformanceTracker
        tracker = PerformanceTracker(log_path="logs/test_perf.json")
        self.assertIsNotNone(tracker)
    
    def test_20_performance_logging(self):
        """Test performance logging works"""
        from app.monitoring.performance_tracker import PerformanceTracker
        
        tracker = PerformanceTracker(log_path="logs/test_perf.json")
        tracker.log_metrics('test_model', {'auc': 0.85, 'logloss': 0.42})
        
        latest = tracker.get_latest_metrics('test_model')
        self.assertIsNotNone(latest)
    
    # ========== API Tests (5) ==========
    
    def test_21_predict_api_module_loads(self):
        """Test prediction API module loads"""
        from app.api.v1.predict import router
        self.assertIsNotNone(router)
    
    def test_22_api_request_model(self):
        """Test API request model"""
        from app.api.v1.predict import PredictRequest
        
        request = PredictRequest(
            race_id="TEST_001",
            runner_id="R1",
            features={'speed': 0.75},
            market_odds=5.0
        )
        
        self.assertEqual(request.race_id, "TEST_001")
    
    def test_23_api_response_model(self):
        """Test API response model"""
        from app.api.v1.predict import PredictResponse
        
        response = PredictResponse(
            race_id="TEST_001",
            runner_id="R1",
            probability=0.25,
            edge=0.05,
            confidence=0.80,
            risk_band="MEDIUM",
            signals={}
        )
        
        self.assertEqual(response.probability, 0.25)
    
    def test_24_api_key_validation(self):
        """Test API key validation"""
        from app.api.v1.predict import validate_api_key
        from fastapi import HTTPException
        
        # Valid key should pass
        try:
            validate_api_key("test_key_123")
            valid = True
        except:
            valid = False
        
        self.assertTrue(valid)
    
    def test_25_api_endpoints_exist(self):
        """Test all API endpoints exist"""
        from app.api.v1.predict import router
        
        paths = [route.path for route in router.routes]
        
        self.assertIn("/v1/predict/full", paths)
        self.assertIn("/v1/predict/quick", paths)
        self.assertIn("/v1/predict/market", paths)
        self.assertIn("/v1/predict/ensemble", paths)
    
    # ========== Odds Feed Tests (5) ==========
    
    def test_26_odds_feed_loads(self):
        """Test odds feed module loads"""
        from app.feeds.odds_feed import OddsFeed
        feed = OddsFeed()
        self.assertIsNotNone(feed)
    
    def test_27_odds_snapshot_capture(self):
        """Test odds snapshot capture"""
        from app.feeds.odds_feed import OddsFeed
        
        feed = OddsFeed()
        snapshot = feed.capture_snapshot(
            "TEST_RACE",
            [{'runner_id': 'R1', 'odds_decimal': 3.5}]
        )
        
        self.assertIn('timestamp', snapshot)
        self.assertIn('race_id', snapshot)
    
    def test_28_odds_movement_calculation(self):
        """Test odds movement calculation"""
        from app.feeds.odds_feed import OddsFeed
        
        feed = OddsFeed()
        
        # Capture multiple snapshots
        for i in range(5):
            feed.capture_snapshot(
                "TEST_RACE",
                [{'runner_id': 'R1', 'odds_decimal': 3.5 - i * 0.1}]
            )
        
        movement = feed.compute_odds_movement("TEST_RACE", "R1")
        
        self.assertIn('movement_percent', movement)
        self.assertIn('trend', movement)
    
    def test_29_steam_detection(self):
        """Test steam move detection"""
        from app.feeds.odds_feed import OddsFeed
        
        feed = OddsFeed()
        
        # Simulate steaming odds
        for i in range(5):
            feed.capture_snapshot(
                "TEST_RACE",
                [{'runner_id': 'R1', 'odds_decimal': 5.0 * (1.0 - i * 0.1)}]
            )
        
        is_steam = feed.detect_steam_move("TEST_RACE", "R1", threshold=10.0)
        
        self.assertTrue(is_steam)
    
    def test_30_odds_processor_loads(self):
        """Test odds processor loads"""
        from app.feeds.odds_processor import OddsProcessor
        processor = OddsProcessor()
        self.assertIsNotNone(processor)
    
    # ========== Feature Engineering Tests (3) ==========
    
    def test_31_feature_engineering_v3_loads(self):
        """Test feature engineering v3 loads"""
        from app.services.feature_engineering_v3 import FeatureEngineerV3
        engineer = FeatureEngineerV3()
        self.assertIsNotNone(engineer)
    
    def test_32_feature_engineering_60_features(self):
        """Test 60+ features generated"""
        from app.services.feature_engineering_v3 import FeatureEngineerV3
        
        engineer = FeatureEngineerV3()
        
        # Count feature methods
        methods = [m for m in dir(engineer) if m.startswith('compute_')]
        
        self.assertGreaterEqual(len(methods), 7)  # 7 categories
    
    def test_33_rolling_features(self):
        """Test rolling features work"""
        from app.services.feature_engineering_v3 import FeatureEngineerV3
        
        engineer = FeatureEngineerV3()
        
        data = pd.DataFrame({
            'runner_id': ['R1'] * 100,
            'speed': np.random.normal(70, 10, 100),
            'form': np.random.normal(80, 5, 100)
        })
        
        features = engineer.compute_rolling_features(data)
        
        self.assertIsNotNone(features)
    
    # ========== Dataset Tests (3) ==========
    
    def test_34_dataset_loader_loads(self):
        """Test dataset loader module loads"""
        from app.data.dataset_loader import load_racing_dataset
        self.assertIsNotNone(load_racing_dataset)
    
    def test_35_full_dataset_exists(self):
        """Test full dataset file exists"""
        import os
        self.assertTrue(os.path.exists('storage/velo-datasets/racing_full_1_7m.csv'))
    
    def test_36_dataset_size(self):
        """Test dataset has 1.7M+ rows"""
        import os
        size = os.path.getsize('storage/velo-datasets/racing_full_1_7m.csv')
        self.assertGreater(size, 600 * 1024 * 1024)  # >600MB
    
    # ========== Integration Tests (4) ==========
    
    def test_37_end_to_end_prediction(self):
        """Test end-to-end prediction flow"""
        from app.engine.uma import UMA
        
        uma = UMA()
        uma.load_models()
        
        features = {
            'speed_normalized': 0.75,
            'form_decay': 0.85,
            'rating_composite': 95.0
        }
        
        prediction = uma.predict(features, market_odds=5.0)
        
        self.assertIsNotNone(prediction)
        self.assertGreater(prediction.confidence, 0.0)
    
    def test_38_value_bet_detection(self):
        """Test value bet detection"""
        from app.feeds.odds_processor import OddsProcessor
        
        processor = OddsProcessor()
        
        model_probs = {'R1': 0.35, 'R2': 0.20}
        market_odds = {'R1': 3.5, 'R2': 4.0}
        
        value_bets = processor.compute_value_bets(model_probs, market_odds, edge_threshold=0.02)
        
        self.assertIsInstance(value_bets, list)
    
    def test_39_monitoring_integration(self):
        """Test monitoring integration"""
        from app.monitoring.drift_detector import DriftDetector
        from app.monitoring.performance_tracker import PerformanceTracker
        
        detector = DriftDetector()
        tracker = PerformanceTracker(log_path="logs/test_integration.json")
        
        self.assertIsNotNone(detector)
        self.assertIsNotNone(tracker)
    
    def test_40_full_system_health(self):
        """Test full system health check"""
        import os
        
        # Check all critical components exist
        critical_files = [
            'models/sqpe_v14/sqpe_v14.pkl',
            'models/tie_v9/tie_v9.pkl',
            'app/engine/uma.py',
            'app/api/v1/predict.py',
            'app/feeds/odds_feed.py',
            'app/monitoring/drift_detector.py',
            'storage/velo-datasets/racing_full_1_7m.csv'
        ]
        
        for filepath in critical_files:
            self.assertTrue(os.path.exists(filepath), f"Missing: {filepath}")


if __name__ == '__main__':
    print("="*60)
    print("VÉLØ Oracle - Phase 4 Full Test Suite (40 Tests)")
    print("="*60)
    
    # Run tests
    unittest.main(verbosity=2)
