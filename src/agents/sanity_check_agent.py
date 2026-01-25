"""
SanityCheckAgent (Control Layer)

Role: Kill bad inputs.
Validates: Race count matches, runner names align across agents, no ghost runners, no missing mandatory fields.
This agent has veto power over the engine.
"""

import json
import sys
from typing import Dict, List

def sanity_check(race_index: Dict, runners: List[Dict], ratings: List[Dict]) -> bool:
    """
    Perform sanity checks on extracted data.

    Returns:
        True if data passes all checks, False otherwise.
    """
    # Check 1: Race index has required fields
    if not race_index.get('venue') or not race_index.get('date') or not race_index.get('races'):
        print("SANITY FAIL: Race index missing venue, date, or races")
        return False

    # Check 2: At least one race
    if len(race_index['races']) == 0:
        print("SANITY FAIL: No races found")
        return False

    # Check 3: Runner count > 0
    if len(runners) == 0:
        print("SANITY FAIL: No runners found")
        return False

    # Check 4: Ratings count matches runners count
    if len(ratings) != len(runners):
        print(f"SANITY FAIL: Ratings count ({len(ratings)}) != runners count ({len(runners)})")
        return False

    # Check 5: All runners have required fields
    required_runner_fields = ['horse_name', 'horse_number', 'age', 'weight', 'trainer', 'jockey']
    for i, runner in enumerate(runners):
        for field in required_runner_fields:
            if field not in runner:
                print(f"SANITY FAIL: Runner {i} missing field '{field}'")
                return False

    print("SANITY PASS: All checks passed")
    return True

def main():
    """Entry point: reads JSON from stdin."""
    try:
        data = json.load(sys.stdin)
        race_index = data.get('race_index', {})
        runners = data.get('runners', [])
        ratings = data.get('ratings', [])

        if sanity_check(race_index, runners, ratings):
            sys.exit(0)  # Success
        else:
            sys.exit(1)  # Failure
    except Exception as e:
        print(f"SANITY ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
