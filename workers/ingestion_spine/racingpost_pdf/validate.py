"""
Racing Post PDF Parser - Hard Validation Gates
Enforce data quality rules. NO MERCY.
"""

from typing import List, Tuple

from .normalize import is_placeholder_name
from .types import Meeting, Race, Runner


def validate_meeting(meeting: Meeting) -> Tuple[bool, List[str]]:
    """
    Apply hard validation gates to meeting data.
    
    Args:
        meeting: Parsed meeting data
        
    Returns:
        Tuple of (is_valid, errors)
        If not valid -> batch status = rejected_bad_output
        
    Hard Gates:
        1. No placeholder names (TBD, RUNNER A, etc.)
        2. Impossible ages (not 2-15 for Flat/AW)
        3. Runner count consistency
        4. Distance must be mapped
        5. Distance consistency check (yards vs furlongs)
        6. No all-zero predictions (if predictions exist)
    """
    errors = []
    
    # Gate 1: No placeholder names
    for race in meeting.races:
        for runner in race.runners:
            if is_placeholder_name(runner.name):
                errors.append(
                    f"Placeholder name in {race.race_id}: {runner.name}"
                )
    
    # Gate 2: Impossible ages (Flat/AW)
    for race in meeting.races:
        for runner in race.runners:
            if runner.age is not None:
                if not (2 <= runner.age <= 15):
                    errors.append(
                        f"Impossible age in {race.race_id}: "
                        f"{runner.name} age={runner.age}"
                    )
    
    # Gate 3: Runner count consistency
    for race in meeting.races:
        declared = race.runners_count
        actual = len(race.runners)
        
        if declared != actual:
            # Allow declared-1 only if Non-Runner marker found
            if not (declared - 1 == actual and race.has_non_runners):
                errors.append(
                    f"Runner count mismatch in {race.race_id}: "
                    f"declared={declared}, actual={actual}"
                )
    
    # Gate 4: Distance must be mapped
    for race in meeting.races:
        if race.distance_yards is None:
            errors.append(
                f"Distance not mapped in {race.race_id}: "
                f"{race.distance_text}"
            )
    
    # Gate 5: Distance consistency check
    for race in meeting.races:
        if race.distance_yards and race.distance_furlongs:
            expected_f = race.distance_yards / 220.0
            if abs(race.distance_furlongs - expected_f) > 0.1:
                errors.append(
                    f"Distance mismatch in {race.race_id}: "
                    f"{race.distance_yards}y != {race.distance_furlongs}f"
                )
    
    # Gate 6: No all-zero predictions (if predictions exist)
    for race in meeting.races:
        if race.top_4_predictions:
            scores = [p.score for p in race.top_4_predictions]
            if all(s == 0 for s in scores):
                errors.append(
                    f"All-zero predictions in {race.race_id}"
                )
    
    return (len(errors) == 0, errors)


def block_bad_output(batch_id: str, errors: List[str]) -> None:
    """
    Set batch status to rejected_bad_output.
    Log errors. Refuse Supabase insert.
    
    Args:
        batch_id: Batch UUID
        errors: List of validation errors
        
    Raises:
        ValidationError: Always raised to block insert
    """
    from pydantic import ValidationError as PydanticValidationError
    
    # Log errors (would use proper logger in production)
    print(f"❌ Batch {batch_id} REJECTED: {len(errors)} validation errors")
    for error in errors:
        print(f"  - {error}")
    
    # Raise validation error to block insert
    raise PydanticValidationError(
        f"Batch {batch_id} rejected. "
        f"{len(errors)} hard gate violations. NO INSERT."
    )
