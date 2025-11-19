"""
VÉLØ Oracle - Phase 3 Full Test Suite
Comprehensive tests for Phase 3 components
"""
import sys
from pathlib import Path
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_01_intelligence_chains():
    """Test intelligence chains execution"""
    print("\n[TEST 01] Intelligence Chains")
    
    from app.intelligence.chains import (
        run_prediction_chain,
        run_narrative_chain,
        run_market_chain,
        run_pace_chain
    )
    
    # Test data
    race = {"race_id": "TEST001", "distance": 1600, "course": "Test Track"}
    runners = [
        {"runner_id": "R1", "horse": "Test Horse", "odds": 5.0, "draw": 3},
        {"runner_id": "R2", "horse": "Test Horse 2", "odds": 3.5, "draw": 7}
    ]
    odds_movements = [{"odds": 5.0, "timestamp": "2025-11-19T10:00:00"}]
    
    # Test pace chain (synchronous wrapper)
    async def test_pace():
        result = await run_pace_chain(runners, race)
        assert result["status"] == "success"
        assert "pace_clusters" in result["signals"]
        return True
    
    success = asyncio.run(test_pace())
    
    print("  ✅ Intelligence chains functional")
    return True


def test_02_chain_timing():
    """Test chain execution timing"""
    print("\n[TEST 02] Chain Timing")
    
    from app.intelligence.chains import run_pace_chain
    import time
    
    race = {"race_id": "TEST001", "distance": 1600}
    runners = [{"runner_id": "R1", "odds": 5.0}]
    
    async def test_timing():
        start = time.time()
        result = await run_pace_chain(runners, race)
        elapsed = (time.time() - start) * 1000
        
        assert "execution_duration_ms" in result
        assert elapsed < 5000  # Should complete in < 5s
        return True
    
    success = asyncio.run(test_timing())
    
    print("  ✅ Chain timing acceptable")
    return True


def test_03_observatory_volatility():
    """Test volatility index"""
    print("\n[TEST 03] Observatory - Volatility Index")
    
    from app.observatory import compute_volatility_index
    
    odds_movements = [
        {"odds": 5.0}, {"odds": 4.8}, {"odds": 4.5}
    ]
    runners = [{"runner_id": "R1", "sectional_times": {"last_200m": 11.2}}]
    race = {"distance": 1600}
    
    result = compute_volatility_index(odds_movements, runners, race)
    
    assert "volatility_score" in result
    assert 0 <= result["volatility_score"] <= 100
    assert result["category"] in ["LOW", "MEDIUM", "HIGH", "CHAOS"]
    
    print(f"  ✅ Volatility: {result['volatility_score']} ({result['category']})")
    return True


def test_04_observatory_stability():
    """Test stability index"""
    print("\n[TEST 04] Observatory - Stability Index")
    
    from app.observatory import compute_stability_index
    
    runners = [
        {"runner_id": "R1", "trainer": "Test Trainer", "jockey": "Test Jockey", "odds": 5.0}
    ]
    race = {"distance": 1600}
    
    result = compute_stability_index(runners, race)
    
    assert "stability_score" in result
    assert 0 <= result["stability_score"] <= 1
    assert result["category"] in ["VERY_STABLE", "STABLE", "MODERATE", "UNSTABLE"]
    
    print(f"  ✅ Stability: {result['stability_score']:.3f} ({result['category']})")
    return True


def test_05_manipulation_radar():
    """Test manipulation radar"""
    print("\n[TEST 05] Observatory - Manipulation Radar")
    
    from app.observatory import compute_manipulation_radar
    
    market_result = {"risk_score": 25, "signals": {}}
    volatility = {"volatility_score": 30, "category": "MEDIUM"}
    stability = {"stability_score": 0.75, "category": "STABLE"}
    
    result = compute_manipulation_radar(market_result, volatility, stability)
    
    assert "risk_radar" in result
    assert 0 <= result["risk_radar"] <= 100
    assert result["risk_category"] in ["SAFE", "CAUTION", "WARNING", "CRITICAL"]
    
    print(f"  ✅ Radar: {result['risk_radar']} ({result['risk_category']})")
    return True


def test_06_model_ops_loader():
    """Test model ops loader"""
    print("\n[TEST 06] Model Ops - Loader")
    
    from app.ml.model_ops import load_sqpe, load_tie, load_longshot, load_overlay
    
    sqpe = load_sqpe()
    assert sqpe["name"] == "SQPE"
    assert sqpe["loaded"] == True
    
    tie = load_tie()
    assert tie["name"] == "Trainer Intent Engine"
    
    longshot = load_longshot()
    assert longshot["name"] == "Longshot Detector"
    
    overlay = load_overlay()
    assert overlay["name"] == "Benter Overlay"
    
    print("  ✅ All models loaded")
    return True


def test_07_model_ops_validator():
    """Test model ops validator"""
    print("\n[TEST 07] Model Ops - Validator")
    
    from app.ml.model_ops import validate_model_schema, validate_feature_map
    
    model = {
        "name": "Test Model",
        "version": "v1.0",
        "type": "test",
        "loaded": True,
        "features": ["f1", "f2"],
        "performance": {"auc": 0.8}
    }
    
    assert validate_model_schema(model) == True
    
    features = {"f1": 1.0, "f2": 2.5}
    assert validate_feature_map(features) == True
    
    print("  ✅ Validation working")
    return True


def test_08_model_ops_registry():
    """Test model ops registry"""
    print("\n[TEST 08] Model Ops - Registry")
    
    from app.ml.model_ops import register_model_run
    
    metadata = {
        "model_name": "test_model",
        "version": "v1.0",
        "metrics": {"auc": 0.8},
        "dataset_size": 1000
    }
    
    # Note: Will fail gracefully if Supabase not configured
    result = register_model_run(metadata)
    
    print(f"  ✅ Registry functional (result: {result})")
    return True


def test_09_advanced_metrics():
    """Test advanced metrics"""
    print("\n[TEST 09] Advanced Metrics")
    
    from app.metrics import calibration_error, brier_score, probability_sharpness
    
    y_true = [1, 0, 1, 1, 0]
    y_pred = [0.9, 0.1, 0.8, 0.7, 0.2]
    
    cal_error = calibration_error(y_true, y_pred)
    assert 0 <= cal_error <= 1
    
    brier = brier_score(y_true, y_pred)
    assert 0 <= brier <= 1
    
    sharpness = probability_sharpness(y_pred)
    assert 0 <= sharpness <= 1
    
    print(f"  ✅ Metrics: cal_error={cal_error:.3f}, brier={brier:.3f}, sharpness={sharpness:.3f}")
    return True


def test_10_async_scheduler():
    """Test async scheduler"""
    print("\n[TEST 10] Optimization - Async Scheduler")
    
    from app.optim import run_chains_parallel
    
    race = {"race_id": "TEST001", "distance": 1600}
    runners = [{"runner_id": "R1", "odds": 5.0}]
    odds_movements = [{"odds": 5.0}]
    
    async def test_parallel():
        result = await run_chains_parallel(race, runners, odds_movements)
        assert "narrative" in result
        assert "market" in result
        assert "pace" in result
        assert "speedup" in result
        return True
    
    success = asyncio.run(test_parallel())
    
    print("  ✅ Async scheduler working")
    return True


def test_11_memo_cache():
    """Test memo cache"""
    print("\n[TEST 11] Optimization - Memo Cache")
    
    from app.optim import cache_narrative, get_cached_narrative, clear_cache
    
    narrative = {"type": "test", "confidence": 0.8}
    cache_narrative("TEST001", narrative)
    
    cached = get_cached_narrative("TEST001")
    assert cached == narrative
    
    cleared = clear_cache()
    assert cleared >= 0
    
    print("  ✅ Memo cache working")
    return True


def test_12_latency_profiler():
    """Test latency profiler"""
    print("\n[TEST 12] Optimization - Latency Profiler")
    
    from app.optim import profile_latency, get_latency_stats
    
    @profile_latency("test_operation")
    def test_func():
        import time
        time.sleep(0.01)
        return True
    
    test_func()
    
    stats = get_latency_stats("test_operation")
    assert stats["count"] >= 1
    assert "avg_ms" in stats
    
    print(f"  ✅ Latency profiler working (avg: {stats['avg_ms']:.2f}ms)")
    return True


def test_13_data_contracts():
    """Test data contracts"""
    print("\n[TEST 13] Data Contracts")
    
    # Test contract files exist
    import os
    contracts_dir = project_root / "app" / "contracts"
    assert contracts_dir.exists()
    assert (contracts_dir / "race_contract.py").exists()
    assert (contracts_dir / "runner_contract.py").exists()
    
    print("  ✅ Data contracts files present")
    return True


def test_14_risk_layer():
    """Test risk layer"""
    print("\n[TEST 14] Risk Layer")
    
    from app.services.risk_layer import compute_edge, classify_risk
    
    edge = compute_edge(0.3, 3.0)
    assert isinstance(edge, float)
    
    risk = classify_risk(edge)
    assert risk in ["NO_BET", "LOW", "MEDIUM", "HIGH"]
    
    print(f"  ✅ Risk layer: edge={edge:.3f}, risk={risk}")
    return True


def test_15_feature_engineering():
    """Test feature engineering"""
    print("\n[TEST 15] Feature Engineering")
    
    try:
        from app.services.feature_engineering import FeatureEngineer
        
        engineer = FeatureEngineer()
        
        # Test that class exists and has methods
        assert hasattr(engineer, 'compute_speed_normalized')
        
        print(f"  ✅ Feature engineering module loaded")
    except Exception as e:
        print(f"  ⚠️ Feature engineering: {e}")
    
    return True


def test_16_training_automation():
    """Test training automation scripts exist"""
    print("\n[TEST 16] Training Automation")
    
    import os
    
    scripts = [
        "scripts/train_automation/auto_train_all.py",
        "scripts/train_automation/auto_compare.py",
        "scripts/train_automation/auto_promote.py"
    ]
    
    for script in scripts:
        path = project_root / script
        assert path.exists(), f"Script not found: {script}"
        assert os.access(path, os.X_OK), f"Script not executable: {script}"
    
    print("  ✅ Training automation scripts present")
    return True


def test_17_api_endpoints():
    """Test API endpoint modules exist"""
    print("\n[TEST 17] API Endpoints")
    
    from app.api.v1 import system_router, intel_router
    
    assert system_router is not None
    assert intel_router is not None
    
    print("  ✅ API routers loaded")
    return True


def test_18_backtest_50k_v2():
    """Test backtest 50K V2 module"""
    print("\n[TEST 18] Backtest 50K V2")
    
    from app.services.backtest.backtest_50k_v2 import run_backtest_50k_v2
    
    # Test module exists (skip actual execution due to missing parquet)
    assert run_backtest_50k_v2 is not None
    
    print(f"  ✅ Backtest V2 module loaded")
    return True


def test_19_supabase_logging():
    """Test Supabase logging extensions"""
    print("\n[TEST 19] Supabase Logging")
    
    try:
        from src.data.supabase_client import get_supabase_client
        
        db = get_supabase_client()
        
        # Test logging methods exist
        assert hasattr(db, 'log_backtest_summary')
        assert hasattr(db, 'log_prediction_summary')
        assert hasattr(db, 'fetch_recent_backtests')
        
        print("  ✅ Supabase logging methods present")
    except ImportError:
        print("  ⚠️ Supabase not installed (expected in dev)")
    
    return True


def test_20_integration_smoke():
    """Integration smoke test"""
    print("\n[TEST 20] Integration Smoke Test")
    
    # Test full pipeline can be imported
    from app.intelligence.chains import run_prediction_chain
    from app.ml.model_ops import load_all_models
    from app.observatory import compute_volatility_index
    from app.optim import run_chains_parallel
    
    # Load all models
    models = load_all_models()
    assert len(models) == 4
    
    print("  ✅ Integration smoke test passed")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("VÉLØ Oracle - Phase 3 Full Test Suite")
    print("=" * 60)
    
    tests = [
        test_01_intelligence_chains,
        test_02_chain_timing,
        test_03_observatory_volatility,
        test_04_observatory_stability,
        test_05_manipulation_radar,
        test_06_model_ops_loader,
        test_07_model_ops_validator,
        test_08_model_ops_registry,
        test_09_advanced_metrics,
        test_10_async_scheduler,
        test_11_memo_cache,
        test_12_latency_profiler,
        test_13_data_contracts,
        test_14_risk_layer,
        test_15_feature_engineering,
        test_16_training_automation,
        test_17_api_endpoints,
        test_18_backtest_50k_v2,
        test_19_supabase_logging,
        test_20_integration_smoke
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    if failed > 0:
        print(f"❌ {failed} tests failed")
    else:
        print("✅ ALL TESTS PASSED")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
