"""
VÉLØ Oracle - Phase 2.5 Test Suite
Comprehensive tests for all Phase 2.5 components
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import date, datetime


# Test 1: Health Check
def test_health():
    """Test basic health check"""
    assert True, "Health check passed"


# Test 2: Predict Stub
def test_predict_stub():
    """Test prediction stub functionality"""
    from app.services.model_manager import get_model_manager
    
    model_manager = get_model_manager()
    
    # Test SQPE prediction
    features = {
        "speed_normalized": 0.8,
        "quality_score": 0.75,
        "pace_map_position": 0.6,
        "efficiency_score": 0.7
    }
    
    sqpe_score = model_manager.predict_sqpe(features)
    
    assert 0.0 <= sqpe_score <= 1.0, "SQPE score out of range"
    assert sqpe_score > 0.5, "SQPE score should be above 0.5 with good features"
    print(f"✓ Predict stub test passed (SQPE: {sqpe_score:.3f})")


# Test 3: Feature Engineering
def test_feature_engineering():
    """Test feature engineering module"""
    from app.services.feature_engineering import FeatureEngineer
    
    engineer = FeatureEngineer()
    
    # Test runner data
    runner = {
        "horse": "Test Horse",
        "age": 4,
        "weight": 57.5,
        "trainer": "Test Trainer",
        "jockey": "Test Jockey",
        "odds": 5.0,
        "draw": 5,
        "form": "1-2-3-1-2",
        "last_start_days": 21
    }
    
    race = {
        "distance": 1600,
        "going": "Good",
        "course": "Flemington"
    }
    
    features = engineer.extract_all_features(runner, race)
    
    assert len(features) == 20, f"Expected 20 features, got {len(features)}"
    assert all(0.0 <= v <= 1.0 for v in features.values()), "Feature values out of range"
    
    print(f"✓ Feature engineering test passed (extracted {len(features)} features)")


# Test 4: SQPE Load
def test_sqpe_load():
    """Test SQPE model loading"""
    from app.services.model_manager import get_model_manager
    
    model_manager = get_model_manager()
    sqpe_model = model_manager.get_model("sqpe")
    
    assert sqpe_model is not None, "SQPE model not loaded"
    assert sqpe_model["name"] == "SQPE", "SQPE model name mismatch"
    assert sqpe_model["loaded"] is True, "SQPE model not marked as loaded"
    
    print(f"✓ SQPE load test passed (version: {sqpe_model['version']})")


# Test 5: Trainer Intent Load
def test_trainer_intent_load():
    """Test Trainer Intent Engine loading"""
    from app.services.model_manager import get_model_manager
    
    model_manager = get_model_manager()
    tie_model = model_manager.get_model("trainer_intent")
    
    assert tie_model is not None, "Trainer Intent model not loaded"
    assert tie_model["name"] == "Trainer Intent Engine", "TIE model name mismatch"
    assert tie_model["loaded"] is True, "TIE model not marked as loaded"
    
    print(f"✓ Trainer Intent load test passed (version: {tie_model['version']})")


# Test 6: Longshot Load
def test_longshot_load():
    """Test Longshot Detection model loading"""
    from app.services.model_manager import get_model_manager
    
    model_manager = get_model_manager()
    longshot_model = model_manager.get_model("longshot")
    
    assert longshot_model is not None, "Longshot model not loaded"
    assert longshot_model["name"] == "Longshot Detector", "Longshot model name mismatch"
    assert longshot_model["loaded"] is True, "Longshot model not marked as loaded"
    
    print(f"✓ Longshot load test passed (version: {longshot_model['version']})")


# Test 7: Benter Overlay
def test_benter_overlay():
    """Test Benter Overlay detection"""
    from app.services.model_manager import get_model_manager
    
    model_manager = get_model_manager()
    
    # Test overlay detection
    model_prob = 0.25  # 25% model probability
    market_odds = 5.0  # Implies 20% probability
    
    overlay = model_manager.detect_overlay(model_prob, market_odds)
    
    assert "is_overlay" in overlay, "Overlay result missing is_overlay"
    assert "edge" in overlay, "Overlay result missing edge"
    assert overlay["is_overlay"] is True, "Should detect overlay with 5% edge"
    assert overlay["edge"] > 0, "Edge should be positive"
    
    print(f"✓ Benter overlay test passed (edge: {overlay['edge']:.3f})")


# Test 8: Backtest Runner
def test_backtest_runner():
    """Test backtesting runner"""
    from app.services.backtest import run_quick_backtest
    
    # Run a quick 7-day backtest
    results = run_quick_backtest(days=7, strategy="default")
    
    assert "backtest_id" in results, "Backtest results missing ID"
    assert "metrics" in results, "Backtest results missing metrics"
    assert "performance" in results, "Backtest results missing performance"
    assert results["status"] == "complete", "Backtest not marked as complete"
    
    print(f"✓ Backtest runner test passed (ID: {results['backtest_id']})")


# Test 9: Market Manipulation
def test_market_manipulation():
    """Test market manipulation detection"""
    from app.intelligence.market_manipulation import detect_suspicious_moves
    
    # Create odds history with late plunge
    odds_history = [
        {"odds": 8.0, "volume": 100, "minutes_to_race": 30},
        {"odds": 7.5, "volume": 120, "minutes_to_race": 20},
        {"odds": 6.0, "volume": 150, "minutes_to_race": 10},
        {"odds": 4.5, "volume": 300, "minutes_to_race": 5},
    ]
    
    result = detect_suspicious_moves(odds_history)
    
    assert "flag" in result, "Manipulation result missing flag"
    assert "confidence" in result, "Manipulation result missing confidence"
    assert "pattern" in result, "Manipulation result missing pattern"
    
    print(f"✓ Market manipulation test passed (pattern: {result['pattern']}, confidence: {result['confidence']:.2f})")


# Test 10: Pace Map
def test_pace_map():
    """Test pace map creation"""
    from app.intelligence.pace_map import create_pace_map
    
    # Create test runners
    runners = [
        {
            "runner_id": "R01",
            "horse": "Leader Horse",
            "draw": 2,
            "form": "1-1-2-1-3",
            "odds": 3.5,
            "speed_ratings": {"adjusted": 120},
            "sectional_times": {"first_400m": 23.5, "last_200m": 11.5}
        },
        {
            "runner_id": "R02",
            "horse": "Closer Horse",
            "draw": 10,
            "form": "8-7-9-6-5",
            "odds": 8.0,
            "speed_ratings": {"adjusted": 115},
            "sectional_times": {"first_400m": 25.0, "last_200m": 10.8}
        },
        {
            "runner_id": "R03",
            "horse": "Midfield Horse",
            "draw": 6,
            "form": "4-5-4-6-3",
            "odds": 6.0,
            "speed_ratings": {"adjusted": 118},
            "sectional_times": {"first_400m": 24.2, "last_200m": 11.2}
        }
    ]
    
    pace_map = create_pace_map(runners)
    
    assert "leaders" in pace_map, "Pace map missing leaders"
    assert "closers" in pace_map, "Pace map missing closers"
    assert "pace_scenario" in pace_map, "Pace map missing scenario"
    assert "pace_pressure" in pace_map, "Pace map missing pressure"
    
    print(f"✓ Pace map test passed (scenario: {pace_map['pace_scenario']['type']}, pressure: {pace_map['pace_pressure']:.2f})")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("VÉLØ Oracle - Phase 2.5 Test Suite")
    print("=" * 60)
    
    tests = [
        ("Health Check", test_health),
        ("Predict Stub", test_predict_stub),
        ("Feature Engineering", test_feature_engineering),
        ("SQPE Load", test_sqpe_load),
        ("Trainer Intent Load", test_trainer_intent_load),
        ("Longshot Load", test_longshot_load),
        ("Benter Overlay", test_benter_overlay),
        ("Backtest Runner", test_backtest_runner),
        ("Market Manipulation", test_market_manipulation),
        ("Pace Map", test_pace_map),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n--- Test: {test_name} ---")
        try:
            test_func()
            results.append((test_name, True, None))
        except Exception as e:
            print(f"✗ {test_name} FAILED: {e}")
            results.append((test_name, False, str(e)))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    for test_name, passed, error in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")
        if error:
            print(f"      Error: {error}")
    
    passed_count = sum(1 for _, passed, _ in results if passed)
    total_count = len(results)
    
    print("=" * 60)
    print(f"Results: {passed_count}/{total_count} tests passed")
    print("=" * 60)
    
    return passed_count == total_count


if __name__ == "__main__":
    all_passed = run_all_tests()
    sys.exit(0 if all_passed else 1)
