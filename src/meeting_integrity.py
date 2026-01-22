#!/usr/bin/env python3
"""
VÉLØ PRIME Meeting Integrity Gate
Prevents bad data from producing decisions
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime

@dataclass
class MeetingIntegrityResult:
    """Result of meeting integrity check."""
    meeting_status: str  # "VALID" or "QUARANTINED"
    quarantine_reasons: List[str]
    bad_races: List[Tuple[int, str, int]]  # (race_id, time, runner_count)
    can_proceed: bool


def parse_race_time(time_str: str, date_str: str = "2026-01-22") -> datetime:
    """
    Parse race time from HH.MM format to datetime.
    Handles ambiguous times (1.10 could be 01:10 or 13:10).
    
    Racing convention: 
    - Times < 10.00 are PM (e.g., 1.10 = 13:10)
    - Times >= 10.00 are AM/PM based on context (12.40 = 12:40)
    """
    try:
        parts = str(time_str).split(".")
        if len(parts) != 2:
            # Try colon format
            parts = str(time_str).split(":")
        
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        
        # Racing convention: single-digit hours are PM
        if hour < 10:
            hour += 12
        
        return datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")
    except Exception as e:
        # Return a default time if parsing fails
        return datetime.strptime(f"{date_str} 00:00", "%Y-%m-%d %H:%M")


def meeting_integrity_gate(races: List[Dict], min_runners: int = 6) -> MeetingIntegrityResult:
    """
    Check meeting integrity before any verdict generation.
    
    Rules:
    - If any race has < min_runners (unless match/walkover), flag it
    - If multiple races have bad data, quarantine meeting
    """
    bad_races = []
    quarantine_reasons = []
    
    for race in races:
        race_id = race.get('id', 0)
        time_str = race.get('race_time', '0.00')
        runner_count = race.get('runner_count', 0)
        race_type = race.get('race_type', '').lower()
        
        # Check for walkovers (1 runner is valid for walkover)
        is_walkover = runner_count == 1 or 'walkover' in race_type or 'match' in race_type
        
        if runner_count < min_runners and not is_walkover:
            bad_races.append((race_id, time_str, runner_count))
        elif runner_count == 0:
            bad_races.append((race_id, time_str, runner_count))
            quarantine_reasons.append("DATA_CORRUPT_ZERO_RUNNERS")
    
    # Determine meeting status
    if len(bad_races) >= 3:
        quarantine_reasons.append("DATA_CORRUPT_MULTIPLE_SMALL_FIELDS")
    
    if "DATA_CORRUPT_ZERO_RUNNERS" in quarantine_reasons:
        meeting_status = "QUARANTINED"
        can_proceed = False
    elif len(bad_races) >= 3:
        meeting_status = "QUARANTINED"
        can_proceed = False
    else:
        meeting_status = "VALID"
        can_proceed = True
    
    return MeetingIntegrityResult(
        meeting_status=meeting_status,
        quarantine_reasons=quarantine_reasons,
        bad_races=bad_races,
        can_proceed=can_proceed
    )


if __name__ == "__main__":
    # Test time parsing
    print("=== TIME PARSING TEST ===")
    test_times = ["12.40", "1.10", "1.45", "2.20", "2.55", "3.30"]
    for t in test_times:
        parsed = parse_race_time(t)
        print(f"{t} -> {parsed.strftime('%H:%M')}")
