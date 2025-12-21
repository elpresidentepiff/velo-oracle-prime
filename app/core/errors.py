"""
VÉLØ V12 Error Codes

Explicit error codes for fail-fast validation.
No silent fallbacks allowed.
"""

class V12Error(Exception):
    """Base exception for V12 engine errors."""
    def __init__(self, code: str, message: str, context: dict = None):
        self.code = code
        self.message = message
        self.context = context or {}
        super().__init__(f"[{code}] {message}")


class V12ErrorCode:
    """Error code constants."""
    MISSING_ODDS = "E001_MISSING_ODDS"
    ZERO_ODDS = "E002_ZERO_ODDS"
    INVALID_PROFILE = "E003_INVALID_PROFILE"
    MISSING_SCORE = "E004_MISSING_SCORE"
    INVALID_TOP4 = "E005_INVALID_TOP4"
    MISSING_RUNNER_ID = "E006_MISSING_RUNNER_ID"
    INVALID_FIELD_SIZE = "E007_INVALID_FIELD_SIZE"


def validate_odds(runner: dict) -> None:
    """
    Validate runner odds.
    Fail-fast on missing or zero odds.
    
    Args:
        runner: Runner dictionary
        
    Raises:
        V12Error: If odds are missing or zero
    """
    runner_id = runner.get('runner_id', 'UNKNOWN')
    horse_name = runner.get('horse_name', 'UNKNOWN')
    
    if 'odds_decimal' not in runner:
        raise V12Error(
            V12ErrorCode.MISSING_ODDS,
            f"Runner {runner_id} ({horse_name}) has no odds_decimal field",
            {'runner_id': runner_id, 'horse_name': horse_name}
        )
    
    odds = runner['odds_decimal']
    if odds is None or odds <= 0:
        raise V12Error(
            V12ErrorCode.ZERO_ODDS,
            f"Runner {runner_id} ({horse_name}) has invalid odds: {odds}",
            {'runner_id': runner_id, 'horse_name': horse_name, 'odds': odds}
        )


def validate_runner_profile(profile) -> None:
    """
    Validate opponent profile.
    Fail-fast on missing required fields.
    
    Args:
        profile: OpponentProfile object or dict
        
    Raises:
        V12Error: If profile is invalid
    """
    # Check if profile has required fields
    required_fields = ['runner_id', 'horse_name', 'market_role']
    
    for field in required_fields:
        if not hasattr(profile, field) and field not in profile:
            raise V12Error(
                V12ErrorCode.INVALID_PROFILE,
                f"Profile missing required field: {field}",
                {'missing_field': field}
            )


def validate_scores(score_breakdowns: dict, field_size: int) -> None:
    """
    Validate score contract.
    All runners must have scores.
    
    Args:
        score_breakdowns: Dict of runner_id -> ScoreBreakdown
        field_size: Number of runners
        
    Raises:
        V12Error: If scores are incomplete
    """
    if len(score_breakdowns) != field_size:
        raise V12Error(
            V12ErrorCode.MISSING_SCORE,
            f"Score count mismatch: {len(score_breakdowns)} scores for {field_size} runners",
            {'score_count': len(score_breakdowns), 'field_size': field_size}
        )
    
    for runner_id, breakdown in score_breakdowns.items():
        if breakdown.total is None:
            raise V12Error(
                V12ErrorCode.MISSING_SCORE,
                f"Runner {runner_id} has no total score",
                {'runner_id': runner_id}
            )
        
        if not breakdown.components:
            raise V12Error(
                V12ErrorCode.MISSING_SCORE,
                f"Runner {runner_id} has no score components",
                {'runner_id': runner_id}
            )


def validate_top4(top_4_ids: list, field_size: int) -> None:
    """
    Validate Top-4 output.
    Must have min(4, field_size) runners.
    
    Args:
        top_4_ids: List of runner IDs in Top-4
        field_size: Number of runners
        
    Raises:
        V12Error: If Top-4 is invalid
    """
    expected_count = min(4, field_size)
    if len(top_4_ids) != expected_count:
        raise V12Error(
            V12ErrorCode.INVALID_TOP4,
            f"Top-4 count mismatch: {len(top_4_ids)} runners, expected {expected_count}",
            {'top4_count': len(top_4_ids), 'expected': expected_count, 'field_size': field_size}
        )
