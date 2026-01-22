#!/usr/bin/env python3
"""
VÉLØ PRIME Output Integrity Gate
Enforces the output contract - NO VERDICT WITHOUT CONTEXT

If any required field is missing, the run is INVALID.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any


@dataclass
class OutputContract:
    """Required fields for a valid VÉLØ output."""
    top4: List[str]  # Exactly 4 runners
    strike_decision: Optional[str]  # STRIKE name or None if quarantined
    strike_confidence: Optional[float]
    gate_results: List[str]  # Quarantine reasons (can be empty)
    suppression_signals: List[Dict]  # S1-S7 signals detected
    rationale_block: str  # Why this decision was made
    is_quarantined: bool


@dataclass
class IntegrityResult:
    """Result of output integrity check."""
    is_valid: bool
    missing_fields: List[str]
    error_message: Optional[str]


def validate_race_output(output: Dict[str, Any]) -> IntegrityResult:
    """
    Validate that a race output meets the contract.
    
    MANDATORY FIELDS:
    - top4: List of exactly 4 runner names
    - strike_decision: String or None (if quarantined)
    - gate_results: List of quarantine codes
    - suppression_signals: List of detected signals
    - rationale_block: Non-empty string explaining the decision
    """
    missing = []
    
    # Check top4
    top4 = output.get('top4', [])
    if not isinstance(top4, list):
        missing.append('top4 (not a list)')
    elif len(top4) != 4:
        missing.append(f'top4 (got {len(top4)}, need exactly 4)')
    
    # Check strike_decision (can be None if quarantined)
    if 'strike_decision' not in output:
        missing.append('strike_decision')
    
    # Check gate_results
    if 'gate_results' not in output:
        missing.append('gate_results')
    elif not isinstance(output['gate_results'], list):
        missing.append('gate_results (not a list)')
    
    # Check suppression_signals
    if 'suppression_signals' not in output:
        missing.append('suppression_signals')
    elif not isinstance(output['suppression_signals'], list):
        missing.append('suppression_signals (not a list)')
    
    # Check rationale_block
    rationale = output.get('rationale_block', '')
    if not rationale or not isinstance(rationale, str) or len(rationale.strip()) < 10:
        missing.append('rationale_block (missing or too short)')
    
    if missing:
        return IntegrityResult(
            is_valid=False,
            missing_fields=missing,
            error_message=f"INVALID OUTPUT: CONTRACT BREACH - Missing: {', '.join(missing)}"
        )
    
    return IntegrityResult(
        is_valid=True,
        missing_fields=[],
        error_message=None
    )


def validate_meeting_output(races: List[Dict[str, Any]]) -> IntegrityResult:
    """
    Validate all races in a meeting output.
    If ANY race fails, the entire meeting output is INVALID.
    """
    all_missing = []
    
    for i, race in enumerate(races):
        result = validate_race_output(race)
        if not result.is_valid:
            all_missing.append(f"Race {i+1}: {', '.join(result.missing_fields)}")
    
    if all_missing:
        return IntegrityResult(
            is_valid=False,
            missing_fields=all_missing,
            error_message=f"INVALID OUTPUT: CONTRACT BREACH\n" + "\n".join(all_missing)
        )
    
    return IntegrityResult(
        is_valid=True,
        missing_fields=[],
        error_message=None
    )


def build_valid_output(
    top4: List[str],
    strike_decision: Optional[str],
    strike_confidence: Optional[float],
    gate_results: List[str],
    suppression_signals: List[Dict],
    rationale_block: str,
    is_quarantined: bool
) -> Dict[str, Any]:
    """
    Build a valid output that passes the integrity gate.
    Use this instead of manually constructing output dicts.
    """
    output = {
        'top4': top4[:4] if len(top4) >= 4 else top4 + [''] * (4 - len(top4)),
        'strike_decision': strike_decision,
        'strike_confidence': strike_confidence,
        'gate_results': gate_results,
        'suppression_signals': suppression_signals,
        'rationale_block': rationale_block,
        'is_quarantined': is_quarantined
    }
    
    # Validate before returning
    result = validate_race_output(output)
    if not result.is_valid:
        raise ValueError(result.error_message)
    
    return output


if __name__ == "__main__":
    # Test the integrity gate
    print("=== OUTPUT INTEGRITY GATE TEST ===\n")
    
    # Valid output
    valid = {
        'top4': ['Horse A', 'Horse B', 'Horse C', 'Horse D'],
        'strike_decision': 'Horse A',
        'strike_confidence': 0.65,
        'gate_results': [],
        'suppression_signals': [{'signal': 'S4', 'runner': 'Horse B'}],
        'rationale_block': 'Horse A selected due to rating convergence and expert consensus.'
    }
    
    result = validate_race_output(valid)
    print(f"Valid output: {result.is_valid}")
    
    # Invalid output (missing top4)
    invalid = {
        'strike_decision': 'Horse A',
        'gate_results': [],
        'suppression_signals': [],
        'rationale_block': 'Some reason'
    }
    
    result = validate_race_output(invalid)
    print(f"Invalid output: {result.is_valid}")
    print(f"Error: {result.error_message}")
