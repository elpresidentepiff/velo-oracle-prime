"""
V12 Integration Test
End-to-end test of V12 Market-Intent Stack
"""

import json
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.v10_entrypoint import run_velo_v10, EngineMode
from app.logging.csv_logger import log_engine_result as log_csv
from app.logging.sheets_logger import log_engine_result as log_sheets

def test_v12_engine_full():
    """Test ENGINE_FULL mode with test fixture."""
    print("="*80)
    print("V12 INTEGRATION TEST")
    print("="*80)
    
    # Load test fixture
    fixture_path = Path(__file__).parent / "fixtures" / "test_race_v12.json"
    with open(fixture_path, 'r') as f:
        race_data = json.load(f)
    
    print(f"\nLoaded test fixture: {fixture_path}")
    print(f"Race: {race_data['race_id']} | {race_data['track']} | {race_data['date']}")
    print(f"Runners: {race_data['field_size']}")
    
    # Run engine
    print("\n" + "-"*80)
    print("Running ENGINE_FULL mode...")
    print("-"*80)
    
    result = run_velo_v10(race_data, mode=EngineMode.ENGINE_FULL, bankroll=10000.0)
    
    # Print result
    print("\n" + "="*80)
    print("RESULT")
    print("="*80)
    print(json.dumps(result, indent=2))
    
    # Validate result structure
    print("\n" + "-"*80)
    print("VALIDATION")
    print("-"*80)
    
    assert "race_details" in result, "Missing race_details"
    assert "audit" in result, "Missing audit"
    assert "signals" in result, "Missing signals"
    assert "decision" in result, "Missing decision"
    
    audit = result["audit"]
    signals = result["signals"]
    decision = result["decision"]
    
    assert audit["mode"] == "ENGINE_FULL", f"Wrong mode: {audit['mode']}"
    assert audit["data_version"] == "v12-alpha", f"Wrong version: {audit['data_version']}"
    
    assert "chaos_score" in signals, "Missing chaos_score"
    assert "structure_class" in signals, "Missing structure_class"
    assert "ICM" in signals, "Missing ICM"
    assert "MOF" in signals, "Missing MOF"
    assert "entropy" in signals, "Missing entropy"
    
    assert "top4_chassis" in decision, "Missing top4_chassis"
    assert "status" in decision, "Missing status"
    assert "stake_cap" in decision, "Missing stake_cap"
    
    print("✅ Result structure valid")
    
    # Print key signals
    print("\n" + "-"*80)
    print("KEY SIGNALS")
    print("-"*80)
    print(f"Chaos Score: {signals['chaos_score']:.3f}")
    print(f"Structure Class: {signals['structure_class']}")
    print(f"MOF State: {signals['MOF']['mof_state']}")
    print(f"MOF Confidence: {signals['MOF']['mof_confidence']:.3f}")
    print(f"Entropy: {signals['entropy']['entropy_score']:.3f}")
    print(f"Confidence Ceiling: {signals['entropy']['confidence_ceiling']:.3f}")
    
    # Print decision
    print("\n" + "-"*80)
    print("DECISION")
    print("-"*80)
    print(f"Status: {decision['status']}")
    print(f"Top-4 Chassis: {', '.join(decision['top4_chassis'])}")
    print(f"Win Candidate: {decision['win_candidate']}")
    print(f"Win Overlay: {decision['win_overlay']}")
    print(f"Stake Cap: £{decision['stake_cap']:.2f}")
    print(f"Stake Used: £{decision['stake_used']:.2f}")
    if decision['kill_list_triggers']:
        print(f"Kill List: {', '.join(decision['kill_list_triggers'])}")
    
    # Log to CSV
    print("\n" + "-"*80)
    print("LOGGING")
    print("-"*80)
    
    try:
        log_csv(result)
        print("✅ Logged to CSV")
    except Exception as e:
        print(f"⚠️  CSV logging failed: {e}")
    
    try:
        log_sheets(result)
        print("✅ Logged to Google Sheets (if enabled)")
    except Exception as e:
        print(f"⚠️  Google Sheets logging failed: {e}")
    
    # Final summary
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print(f"Run ID: {audit['run_id']}")
    print(f"Race ID: {result['race_details']['race_id']}")
    print(f"Status: {decision['status']}")
    print(f"Mode: {audit['mode']}")
    print(f"Data Version: {audit['data_version']}")
    
    return result

if __name__ == "__main__":
    try:
        result = test_v12_engine_full()
        print("\n✅ All tests passed")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
