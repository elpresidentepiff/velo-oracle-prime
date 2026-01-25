#!/usr/bin/env python3
"""
Final MCP Pipeline Test - Demonstrate FAIL and PASS scenarios
"""

import subprocess
import json
import sys
from pathlib import Path

def run_agent(agent_name, args):
    """Run an agent and capture output."""
    cmd = ["python", f"src/agents/{agent_name}"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout), None
    except subprocess.CalledProcessError as e:
        return None, f"Agent {agent_name} failed: {e.stderr}"
    except json.JSONDecodeError as e:
        return None, f"Agent {agent_name} output not valid JSON: {e}"

def test_fail_scenario():
    """Test with incomplete data to produce FAIL log."""
    print("\n=== TEST 1: FAIL SCENARIO (Incomplete Data) ===")
    
    # Run RaceIndexAgent on OR PDF (has 7 races)
    race_index, error = run_agent("race_index_agent.py", ["/a0/tmp/uploads/NCS_20260124_00_00_F_0015_OR_Newcastle.pdf"])
    if error:
        print(f"RaceIndexAgent error: {error}")
        return
    
    print(f"RaceIndexAgent extracted {race_index.get('race_count', 0)} races")
    
    # Run RunnerParserAgent on XX PDF (has runners for 1 race)
    runners, error = run_agent("runner_parser_agent.py", ["/a0/tmp/uploads/NCS_20260124_00_00_F_0012_XX_Newcastle.pdf"])
    if error:
        print(f"RunnerParserAgent error: {error}")
        return
    
    print(f"RunnerParserAgent extracted {len(runners)} runners")
    
    # Create incomplete RacePacket (ratings missing, runners for only 1 race not 7)
    race_packet = {
        "venue": race_index.get("venue", "UNKNOWN"),
        "date": race_index.get("date", "UNKNOWN"),
        "races": race_index.get("races", []),
        "runners": runners,
        "ratings": [],  # Empty ratings to trigger failure
        "spotlight": [],
        "market": {}
    }
    
    # Run IntegrityGateAgent
    print("\nRunning IntegrityGateAgent with incomplete data...")
    cmd = ["python", "src/agents/integrity_gate_agent.py"]
    result = subprocess.run(cmd, input=json.dumps(race_packet), capture_output=True, text=True)
    
    print(f"Exit code: {result.returncode}")
    print(f"Output:\n{result.stdout}")
    if result.stderr:
        print(f"Stderr: {result.stderr}")
    
    return result.returncode != 0  # Should be non-zero for FAIL

def test_pass_scenario():
    """Test with mocked complete data to produce PASS log."""
    print("\n=== TEST 2: PASS SCENARIO (Mocked Complete Data) ===")
    
    # Run RaceIndexAgent
    race_index, error = run_agent("race_index_agent.py", ["/a0/tmp/uploads/NCS_20260124_00_00_F_0015_OR_Newcastle.pdf"])
    if error:
        print(f"RaceIndexAgent error: {error}")
        return False
    
    race_count = race_index.get('race_count', 0)
    print(f"RaceIndexAgent extracted {race_count} races")
    
    # Create mock runners for all races (simulating full meeting)
    mock_runners = []
    for i in range(37):  # 37 runners for Newcastle meeting
        mock_runners.append({
            "horse_name": f"Mock Horse {i+1}",
            "horse_number": i+1,
            "age": 5,
            "weight": "9-0",
            "trainer": f"Trainer {i+1}",
            "jockey": f"Jockey {i+1}"
        })
    
    # Create mock ratings
    mock_ratings = []
    for runner in mock_runners:
        mock_ratings.append({
            "horse_name": runner["horse_name"],
            "horse_number": runner["horse_number"],
            "official_rating": 60,
            "rpr": 65,
            "topspeed": 55
        })
    
    # Create complete RacePacket
    race_packet = {
        "venue": race_index.get("venue", "UNKNOWN"),
        "date": race_index.get("date", "UNKNOWN"),
        "races": race_index.get("races", []),
        "runners": mock_runners,
        "ratings": mock_ratings,
        "spotlight": [],
        "market": {}
    }
    
    # Run IntegrityGateAgent
    print("\nRunning IntegrityGateAgent with mocked complete data...")
    cmd = ["python", "src/agents/integrity_gate_agent.py"]
    result = subprocess.run(cmd, input=json.dumps(race_packet), capture_output=True, text=True)
    
    print(f"Exit code: {result.returncode}")
    print(f"Output:\n{result.stdout}")
    if result.stderr:
        print(f"Stderr: {result.stderr}")
    
    # Generate meeting parse report
    report = {
        "race_count": race_count,
        "runner_count": len(mock_runners),
        "aligned_count": len(mock_ratings),
        "missing_by_race": {},
        "mismatches": [],
        "gate_status": "PASS" if result.returncode == 0 else "FAIL",
        "reasons": []
    }
    
    # Save report
    with open("meeting_parse_report_final.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nGenerated meeting_parse_report_final.json")
    print(json.dumps(report, indent=2))
    
    return result.returncode == 0  # Should be zero for PASS

def main():
    """Main test function."""
    print("MCP Parser Team Final Test Pipeline")
    print("====================================")
    
    # Test FAIL scenario
    fail_passed = test_fail_scenario()
    
    # Test PASS scenario
    pass_passed = test_pass_scenario()
    
    # Summary
    print("\n=== TEST SUMMARY ===")
    print(f"FAIL scenario (should fail): {'PASS' if fail_passed else 'FAIL'}")
    print(f"PASS scenario (should pass): {'PASS' if pass_passed else 'FAIL'}")
    
    if fail_passed and pass_passed:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
