"""
VÉLØ Oracle - Phase 5 Operational Test Suite v2.0
Complete production readiness validation
"""
import unittest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPhase5Operational(unittest.TestCase):
    """Phase 5 operational tests"""
    
    def test_01_model_training_v15_exists(self):
        """Test Model Training Stack v15 files exist"""
        self.assertTrue(Path("app/ml/trainers/train_sqpe_v15.py").exists())
        self.assertTrue(Path("app/ml/trainers/train_all_v15_xgboost.py").exists())
        self.assertTrue(Path("requirements_production.txt").exists())
        print("✅ Model Training Stack v15 files exist")
    
    def test_02_parquet_conversion_exists(self):
        """Test Parquet conversion module exists"""
        self.assertTrue(Path("scripts/convert_to_parquet_v2.py").exists())
        self.assertTrue(Path("app/data/dataset_loader_parquet.py").exists())
        print("✅ Parquet conversion module exists")
    
    def test_03_live_odds_sync_exists(self):
        """Test live odds sync layer exists"""
        self.assertTrue(Path("app/feeds/live_odds_sync.py").exists())
        print("✅ Live odds sync layer exists")
    
    def test_04_supabase_telemetry_exists(self):
        """Test Supabase telemetry exists"""
        self.assertTrue(Path("app/telemetry/supabase_telemetry.py").exists())
        print("✅ Supabase telemetry exists")
    
    def test_05_continuous_retraining_exists(self):
        """Test continuous retraining exists"""
        self.assertTrue(Path("app/governance/continuous_retraining.py").exists())
        print("✅ Continuous retraining exists")
    
    def test_06_deployment_config_exists(self):
        """Test deployment configuration exists"""
        self.assertTrue(Path("deployment/production_config.py").exists())
        self.assertTrue(Path("railway.toml").exists())
        self.assertTrue(Path("Dockerfile").exists())
        self.assertTrue(Path("deployment/cloudflare_worker.js").exists())
        self.assertTrue(Path("deployment/DEPLOYMENT.md").exists())
        print("✅ Deployment configuration exists")
    
    def test_07_production_config_loads(self):
        """Test production config loads"""
        try:
            from deployment.production_config import ProductionConfig
            config = ProductionConfig()
            self.assertIsNotNone(config.API_TITLE)
            self.assertEqual(config.PORT, 8000)
            print(f"✅ Production config loads: {config.API_TITLE}")
        except Exception as e:
            self.fail(f"Production config failed: {e}")
    
    def test_08_supabase_telemetry_loads(self):
        """Test Supabase telemetry loads"""
        try:
            from app.telemetry.supabase_telemetry import SupabaseTelemetry
            telemetry = SupabaseTelemetry()
            self.assertIsNotNone(telemetry)
            print("✅ Supabase telemetry loads")
        except Exception as e:
            self.fail(f"Supabase telemetry failed: {e}")
    
    def test_09_continuous_retraining_loads(self):
        """Test continuous retraining loads"""
        try:
            from app.governance.continuous_retraining import ContinuousRetraining
            retrainer = ContinuousRetraining()
            self.assertIsNotNone(retrainer)
            self.assertEqual(retrainer.auc_threshold, 0.02)
            print("✅ Continuous retraining loads")
        except Exception as e:
            self.fail(f"Continuous retraining failed: {e}")
    
    def test_10_dataset_loader_loads(self):
        """Test dataset loader loads"""
        try:
            from app.data.dataset_loader import load_racing_dataset
            self.assertIsNotNone(load_racing_dataset)
            print("✅ Dataset loader loads")
        except Exception as e:
            self.fail(f"Dataset loader failed: {e}")
    
    def test_11_feature_engineering_v3_loads(self):
        """Test feature engineering v3 loads"""
        try:
            from app.services.feature_engineering_v3 import engineer_features_v3
            self.assertIsNotNone(engineer_features_v3)
            print("✅ Feature engineering v3 loads")
        except Exception as e:
            self.fail(f"Feature engineering v3 failed: {e}")
    
    def test_12_uma_loads(self):
        """Test UMA loads"""
        try:
            from app.engine.uma import UMA
            uma = UMA()
            self.assertIsNotNone(uma)
            print("✅ UMA loads")
        except Exception as e:
            self.fail(f"UMA failed: {e}")
    
    def test_13_backtest_1_7m_loads(self):
        """Test 1.7M backtest engine loads"""
        try:
            from app.services.backtest.backtest_1_7m import Backtest1_7M
            self.assertIsNotNone(Backtest1_7M)
            print("✅ 1.7M backtest engine loads")
        except Exception as e:
            self.fail(f"1.7M backtest failed: {e}")
    
    def test_14_model_ops_loads(self):
        """Test model ops loads"""
        try:
            from app.ml.model_ops.loader import load_model_by_name
            from app.ml.model_ops.validator import validate_model_schema
            from app.ml.model_ops.registry_manager import register_model_run
            self.assertIsNotNone(load_model_by_name)
            self.assertIsNotNone(validate_model_schema)
            self.assertIsNotNone(register_model_run)
            print("✅ Model ops loads")
        except Exception as e:
            self.fail(f"Model ops failed: {e}")
    
    def test_15_intelligence_chains_load(self):
        """Test intelligence chains load"""
        try:
            from app.intelligence.chains.prediction_chain import run_prediction_chain
            from app.intelligence.chains.narrative_chain import run_narrative_chain
            from app.intelligence.chains.market_chain import run_market_chain
            from app.intelligence.chains.pace_chain import run_pace_chain
            self.assertIsNotNone(run_prediction_chain)
            self.assertIsNotNone(run_narrative_chain)
            self.assertIsNotNone(run_market_chain)
            self.assertIsNotNone(run_pace_chain)
            print("✅ Intelligence chains load")
        except Exception as e:
            self.fail(f"Intelligence chains failed: {e}")
    
    def test_16_observatory_loads(self):
        """Test observatory loads"""
        try:
            from app.observatory.volatility_index import compute_volatility_index
            from app.observatory.stability_index import compute_stability_index
            from app.observatory.manipulation_radar import compute_manipulation_radar
            self.assertIsNotNone(compute_volatility_index)
            self.assertIsNotNone(compute_stability_index)
            self.assertIsNotNone(compute_manipulation_radar)
            print("✅ Observatory loads")
        except Exception as e:
            self.fail(f"Observatory failed: {e}")
    
    def test_17_monitoring_loads(self):
        """Test monitoring loads"""
        try:
            from app.monitoring.drift_detector import DriftDetector
            from app.monitoring.performance_tracker import PerformanceTracker
            self.assertIsNotNone(DriftDetector)
            self.assertIsNotNone(PerformanceTracker)
            print("✅ Monitoring loads")
        except Exception as e:
            self.fail(f"Monitoring failed: {e}")
    
    def test_18_risk_layer_loads(self):
        """Test risk layer loads"""
        try:
            from app.services.risk_layer import compute_edge, classify_risk
            self.assertIsNotNone(compute_edge)
            self.assertIsNotNone(classify_risk)
            print("✅ Risk layer loads")
        except Exception as e:
            self.fail(f"Risk layer failed: {e}")
    
    def test_19_advanced_metrics_load(self):
        """Test advanced metrics load"""
        try:
            from app.metrics.advanced import calibration_error, brier_score
            self.assertIsNotNone(calibration_error)
            self.assertIsNotNone(brier_score)
            print("✅ Advanced metrics load")
        except Exception as e:
            self.fail(f"Advanced metrics failed: {e}")
    
    def test_20_api_endpoints_exist(self):
        """Test API endpoints exist"""
        self.assertTrue(Path("app/api/v1/predict.py").exists())
        self.assertTrue(Path("app/api/v1/intel.py").exists())
        self.assertTrue(Path("app/api/v1/system.py").exists())
        print("✅ API endpoints exist")
    
    def test_21_dockerfile_valid(self):
        """Test Dockerfile is valid"""
        with open("Dockerfile") as f:
            content = f.read()
            self.assertIn("FROM python:3.11-slim", content)
            self.assertIn("gunicorn", content)
            self.assertIn("HEALTHCHECK", content)
            print("✅ Dockerfile valid")
    
    def test_22_railway_config_valid(self):
        """Test railway.toml is valid"""
        with open("railway.toml") as f:
            content = f.read()
            self.assertIn("[build]", content)
            self.assertIn("[deploy]", content)
            self.assertIn("[healthcheck]", content)
            print("✅ Railway config valid")
    
    def test_23_requirements_production_valid(self):
        """Test requirements_production.txt is valid"""
        with open("requirements_production.txt") as f:
            content = f.read()
            self.assertIn("scikit-learn", content)
            self.assertIn("xgboost", content)
            self.assertIn("fastapi", content)
            self.assertIn("supabase", content)
            self.assertIn("pyarrow", content)
            print("✅ Requirements production valid")
    
    def test_24_deployment_docs_complete(self):
        """Test deployment documentation is complete"""
        with open("deployment/DEPLOYMENT.md") as f:
            content = f.read()
            self.assertIn("Supabase Setup", content)
            self.assertIn("Railway Deployment", content)
            self.assertIn("Cloudflare Setup", content)
            self.assertIn("Production Checklist", content)
            print("✅ Deployment documentation complete")
    
    def test_25_cloudflare_worker_valid(self):
        """Test Cloudflare Worker is valid"""
        with open("deployment/cloudflare_worker.js") as f:
            content = f.read()
            self.assertIn("export default", content)
            self.assertIn("fetch", content)
            self.assertIn("CORS", content)
            self.assertIn("rate_limit", content)
            print("✅ Cloudflare Worker valid")


def run_tests():
    """Run all tests"""
    print("="*60)
    print("VÉLØ Oracle - Phase 5 Operational Test Suite v2.0")
    print("="*60)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPhase5Operational)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    # Summary
    print()
    print("="*60)
    print("Test Summary")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
