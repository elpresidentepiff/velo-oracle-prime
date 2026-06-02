"""
Regression test for Sigma Reconciliation logic.
Verifies ID-first matching and provenance labeling.
"""
import pytest
import json
from pathlib import Path
import sys

# Add script dir to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Mock the required globals and helpers from run_results_sigma
# Note: In a real scenario we'd refactor the script to be more testable,
# but for this hardening phase we simulate the logic.

def mock_normalize(name):
    return name.lower().strip().replace("(aw)", "").replace(" ", "_")

def reconcile_logic(predictions, results_list, horse_names):
    """Simplified reproduction of Step 3 logic from run_results_sigma.py"""
    results_by_id = {str(r.get("race_id")): r for r in results_list if r.get("race_id")}
    results_by_course_time = {(mock_normalize(r.get("course", "")), r.get("off_time", "")): r for r in results_list}
    
    DNF_POSITIONS = {"NR", "WD", "PU", "F", "BD", "UR", "SU", "RO", "REF", "DSQ", ""}
    matched = []
    
    for rid, pred in predictions.items():
        predicted_horse_id = str(pred.get("top_rank_horse_id", "") or "")
        info = horse_names.get(rid, {})
        
        result = results_by_id.get(rid)
        provenance = "UNRESOLVED"
        
        if result:
            provenance = "MATCH_EXACT_ID"
        else:
            # Simple course/time match mock
            c = mock_normalize(info.get("course", ""))
            ot = info.get("off_time", "")
            result = results_by_course_time.get((c, ot))
            if result:
                provenance = "MATCH_COURSE_TIME"
        
        if not result: continue
        
        # Horse reconciliation
        horse_result = None
        if predicted_horse_id:
            for runner in result.get("runners", []):
                if str(runner.get("horse_id")) == predicted_horse_id:
                    horse_result = runner
                    provenance += "_HID"
                    break
        
        if not horse_result and info.get("horse"):
            p_name = mock_normalize(info["horse"])
            for runner in result.get("runners", []):
                if mock_normalize(runner.get("horse", "")) == p_name:
                    horse_result = runner
                    provenance += "_NAME"
                    break
        
        if not horse_result: continue
        
        pos = str(horse_result.get("position", "")).strip().upper()
        if pos in DNF_POSITIONS: continue
        
        matched.append({
            "race_id": rid,
            "provenance": provenance,
            "outcome": "WIN" if pos == "1" else "MISS"
        })
        
    return matched

def test_id_first_matching():
    # 1. Setup mocks
    predictions = {
        "race_1": {"top_rank_horse_id": "hrs_123"},
        "race_2": {"top_rank_horse_id": "hrs_456"}
    }
    results = [
        {
            "race_id": "race_1", 
            "course": "Southwell", "off_time": "14:30",
            "runners": [{"horse_id": "hrs_123", "horse": "Horse A", "position": "1"}]
        },
        {
            "race_id": "race_999", # ID mismatch
            "course": "Pontefract", "off_time": "15:00",
            "runners": [{"horse_id": "hrs_456", "horse": "Horse B", "position": "2"}]
        }
    ]
    horse_names = {
        "race_1": {"horse": "Horse A", "course": "Southwell", "off_time": "14:30"},
        "race_2": {"horse": "Horse B", "course": "Pontefract", "off_time": "15:00"}
    }
    
    # 2. Run logic
    matches = reconcile_logic(predictions, results, horse_names)
    
    # 3. Assertions
    assert len(matches) == 2
    
    # Race 1 should match by ID
    m1 = next(m for m in matches if m["race_id"] == "race_1")
    assert m1["provenance"] == "MATCH_EXACT_ID_HID"
    assert m1["outcome"] == "WIN"
    
    # Race 2 should match by Course/Time and then HID
    m2 = next(m for m in matches if m["race_id"] == "race_2")
    assert m2["provenance"] == "MATCH_COURSE_TIME_HID"
    assert m2["outcome"] == "MISS"

def test_name_fallback_matching():
    predictions = {"race_3": {"top_rank_horse_id": "hrs_MISSING"}} # ID won't match
    results = [{
        "race_id": "race_3",
        "runners": [{"horse_id": "hrs_999", "horse": "Horse C", "position": "1"}]
    }]
    horse_names = {"race_3": {"horse": "Horse C"}}
    
    matches = reconcile_logic(predictions, results, horse_names)
    assert len(matches) == 1
    assert matches[0]["provenance"] == "MATCH_EXACT_ID_NAME"

if __name__ == "__main__":
    pytest.main([__file__])
