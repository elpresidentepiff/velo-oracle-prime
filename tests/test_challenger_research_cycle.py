"""Proposer/Reflector fixture tests (no API, credentials or production state)."""
import pytest

from src.intelligence.challenger_lab import Observation
from src.intelligence.challenger_research_cycle import (
    Proposal,
    propose_calibration_review,
    reflect,
)


def _rows(challenger_winner=0.7):
    return [
        Observation("r1", "horse1", "2026-10-18T14:00:00Z", "2026-10-18T13:00:00Z", 1, 0.5, challenger_winner),
        Observation("r1", "horse2", "2026-10-18T14:00:00Z", "2026-10-18T13:00:00Z", 0, 0.5, 1 - challenger_winner),
    ]


def test_proposal_is_deterministic_and_independent_of_results():
    a = propose_calibration_review(baseline_ref="commit123")
    assert a == propose_calibration_review(baseline_ref="commit123")
    assert a.candidate_id != propose_calibration_review(baseline_ref="commit456").candidate_id


def test_reflector_requires_manual_review_even_if_better():
    p = propose_calibration_review(baseline_ref="commit123")
    result = reflect(p, _rows(), min_runners=2)
    assert result["reflector_decision"] == "REVIEW_REQUIRED"
    assert result["production_authority"] is False
    assert len(result["artifact_sha256"]) == 64
    assert result == reflect(p, _rows(), min_runners=2)


def test_reflector_rejects_nonimprovement():
    p = propose_calibration_review(baseline_ref="commit123")
    assert reflect(p, _rows(challenger_winner=0.3), min_runners=2)["reflector_decision"] == "REJECT"


def test_unsafe_proposal_blocked():
    with pytest.raises(ValueError, match="research-only"):
        reflect(Proposal("x", "unsafe", "commit123", research_only=False), _rows(), min_runners=2)


def test_no_bypass_of_runner_threshold():
    with pytest.raises(ValueError, match="insufficient"):
        reflect(propose_calibration_review(baseline_ref="commit123"), _rows())


def test_missing_baseline_reference_blocked():
    with pytest.raises(ValueError, match="baseline_ref"):
        propose_calibration_review(baseline_ref="  ")
