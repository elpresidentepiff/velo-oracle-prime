#!/usr/bin/env python3
"""
Test MCP Pipeline - Demonstrate FAIL and PASS scenarios
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
    
    # Run RaceIndexAgent
    race_index, error = run_agent("race_index_agent.py", ["/a0/tmp/uploads/NCS_20260124_00_00_F_0012_XX_Newcastle.pdf"])
    if error:
        print(f"RaceIndexAgent error: {error}")
        return
    
    # Run RunnerParserAgent
    runners, error = run_agent("runner_parser_agent.py", ["/a0/tmp/uploads/NCS_20260124_00_00_F_0012_XX_Newcastle.pdf"])
    if error:
        print(f"RunnerParserAgent error: {error}")
        return
    
    # Create incomplete RacePacket (missing ratings)
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
    """Test with full data to produce PASS log."""
    print("\n=== TEST 2: PASS SCENARIO (Full Meeting) ===")
    
    # Run RaceIndexAgent
    race_index, error = run_agent("race_index_agent.py", ["/a0/tmp/uploads/NCS_20260124_00_00_F_0012_XX_Newcastle.pdf"])
    if error:
        print(f"RaceIndexAgent error: {error}")
        return False
    
    # Run RunnerParserAgent
    runners, error = run_agent("runner_parser_agent.py", ["/a0/tmp/uploads/NCS_20260124_00_00_F_0012_XX_Newcastle.pdf"])
    if error:
        print(f"RunnerParserAgent error: {error}")
        return False
    
    # Create mock ratings (in production would parse TS/RPR PDFs)
    ratings = []
    for runner in runners:
        ratings.append({
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
        "runners": runners,
        "ratings": ratings,
        "spotlight": [],
        "market": {}
    }
    
    # Run IntegrityGateAgent
    print("\nRunning IntegrityGateAgent with complete data...")
    cmd = ["python", "src/agents/integrity_gate_agent.py"]
    result = subprocess.run(cmd, input=json.dumps(race_packet), capture_output=True, text=True)
    
    print(f"Exit code: {result.returncode}")
    print(f"Output:\n{result.stdout}")
    if result.stderr:
        print(f"Stderr: {result.stderr}")
    
    # Generate meeting parse report
    report = {
        "race_count": len(race_packet.get("races", [])),
        "runner_count": len(race_packet.get("runners", [])),
        "aligned_count": len(race_packet.get("ratings", [])),
        "missing_by_race": {},
        "mismatches": [],
        "gate_status": "PASS" if result.returncode == 0 else "FAIL",
        "reasons": []
    }
    
    # Save report
    with open("meeting_parse_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nGenerated meeting_parse_report.json")
    print(json.dumps(report, indent=2))
    
    return result.returncode == 0  # Should be zero for PASS

def main():
    """Main test function."""
    print("MCP Parser Team Test Pipeline")
    print("=============================")
    
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
