"""
Unit tests for proposal fingerprinting.
"""

import pytest
from .fingerprint import fingerprint_proposal, fingerprint_from_dict


def test_fingerprint_identical_proposals():
    """Identical proposals should produce identical fingerprints."""
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    fp2 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    assert fp1 == fp2


def test_fingerprint_different_changes():
    """Different proposed changes should produce different fingerprints."""
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    fp2 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "reject_future"})
    assert fp1 != fp2


def test_fingerprint_different_critics():
    """Different critic types should produce different fingerprints."""
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    fp2 = fingerprint_proposal("BIAS", "FUTURE_MARKET", {"rule": "validate_time"})
    assert fp1 != fp2


def test_fingerprint_different_finding_types():
    """Different finding types should produce different fingerprints."""
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    fp2 = fingerprint_proposal("LEAKAGE", "FUTURE_OUTCOME", {"rule": "validate_time"})
    assert fp1 != fp2


def test_fingerprint_json_normalization():
    """Fingerprint should normalize JSON (key order irrelevant)."""
    change1 = {"rule": "validate", "severity": "CRITICAL"}
    change2 = {"severity": "CRITICAL", "rule": "validate"}
    
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", change1)
    fp2 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", change2)
    
    assert fp1 == fp2


def test_fingerprint_nested_json():
    """Fingerprint should handle nested JSON structures."""
    change = {
        "rule": "validate_time",
        "conditions": {
            "field": "market_snapshot.timestamp",
            "operator": "<=",
            "value": "decision_time"
        },
        "action": "reject_snapshot"
    }
    
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", change)
    fp2 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", change)
    
    assert fp1 == fp2


def test_fingerprint_from_dict():
    """Convenience wrapper should produce same result."""
    proposal = {
        "critic_type": "LEAKAGE",
        "finding_type": "FUTURE_MARKET",
        "proposed_change": {"rule": "validate_time"}
    }
    
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    fp2 = fingerprint_from_dict(proposal)
    
    assert fp1 == fp2


def test_fingerprint_is_sha256():
    """Fingerprint should be a valid SHA256 hex digest (64 characters)."""
    fp = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
    
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_fingerprint_deterministic():
    """Fingerprint should be deterministic across multiple calls."""
    fingerprints = [
        fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
        for _ in range(10)
    ]
    
    assert len(set(fingerprints)) == 1  # All identical


def test_fingerprint_empty_change():
    """Fingerprint should handle empty proposed change."""
    fp = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {})
    assert len(fp) == 64


def test_fingerprint_complex_change():
    """Fingerprint should handle complex nested structures."""
    change = {
        "rule_type": "temporal_validation",
        "conditions": [
            {"field": "market_snapshot.timestamp", "operator": "<=", "value": "decision_time"},
            {"field": "outcome.timestamp", "operator": ">", "value": "decision_time"}
        ],
        "actions": {
            "on_violation": "reject_snapshot",
            "on_success": "accept_snapshot"
        },
        "severity": "CRITICAL",
        "metadata": {
            "version": "1.0",
            "author": "leakage_detector"
        }
    }
    
    fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET_LEAKAGE", change)
    fp2 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET_LEAKAGE", change)
    
    assert fp1 == fp2
