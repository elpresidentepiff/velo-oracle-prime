"""
IntegrityGateAgent (Control Layer) - HARD STOP

Role: Validate RacePacket against schema.
Outputs PASS/FAIL with reasons.
This agent has veto power over the engine.
"""

import json
import sys
from typing import Dict, List

def integrity_check(race_packet: Dict) -> tuple[bool, List[str]]:
    """
    Perform integrity checks on RacePacket.

    Returns:
        Tuple of (pass_status, reasons_list)
    """
    reasons = []
    
    # Check 1: RacePacket has required top-level fields
    required_fields = ['venue', 'date', 'races', 'runners', 'ratings']
    for field in required_fields:
        if field not in race_packet:
            reasons.append(f"Missing required field: {field}")
    
    # Check 2: At least one race
    races = race_packet.get('races', [])
    if len(races) == 0:
        reasons.append("No races found")
    
    # Check 3: Runners count > 0
    runners = race_packet.get('runners', [])
    if len(runners) == 0:
        reasons.append("No runners found")
    
    # Check 4: Ratings count matches runners count
    ratings = race_packet.get('ratings', [])
    if len(ratings) != len(runners):
        reasons.append(f"Ratings count ({len(ratings)}) != runners count ({len(runners)})")
    
    # Check 5: All runners have required fields
    required_runner_fields = ['horse_name', 'horse_number', 'age', 'weight', 'trainer', 'jockey']
    for i, runner in enumerate(runners):
        for field in required_runner_fields:
            if field not in runner:
                reasons.append(f"Runner {i} missing field '{field}'")
                break
    
    # Check 6: Meeting completeness (at least 5 races for standard meeting)
    if len(races) < 5 and len(races) > 0:
        reasons.append(f"Meeting has only {len(races)} races (expected at least 5)")
    
    # Check 7: No UNKNOWN values in critical fields
    for i, runner in enumerate(runners):
        if runner.get('trainer') == 'UNKNOWN' or runner.get('jockey') == 'UNKNOWN':
            reasons.append(f"Runner {i} ({runner.get('horse_name')}) has UNKNOWN trainer/jockey")
    
    pass_status = len(reasons) == 0
    return pass_status, reasons

def main():
    """Entry point: reads JSON from stdin."""
    try:
        race_packet = json.load(sys.stdin)
        pass_status, reasons = integrity_check(race_packet)
        
        if pass_status:
            print("IntegrityGate: PASS")
            sys.exit(0)
        else:
            print("IntegrityGate: FAIL")
            for reason in reasons:
                print(f"  - {reason}")
            sys.exit(1)
    except Exception as e:
        print(f"IntegrityGate ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
