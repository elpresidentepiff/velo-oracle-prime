"""Offline evaluation acceptance tests; no credentials or remote services."""
from dataclasses import replace

import pytest

from src.intelligence.challenger_lab import Observation, evaluate


def sample():
    return [
        Observation("race-1", "a", "2026-10-18T15:00:00Z", "2026-10-18T14:00:00Z", 1, 0.55, 0.70),
        Observation("race-1", "b", "2026-10-18T15:00:00Z", "2026-10-18T14:00:00Z", 0, 0.45, 0.30),
    ]


def test_paired_metrics_and_explicit_no_promotion():
    result = evaluate(sample(), min_runners=2)
    assert result["challenger_brier"] < result["baseline_brier"]
    assert result["challenger_log_loss"] < result["baseline_log_loss"]
    assert result["promotion"] == "NOT_AUTHORISED"


@pytest.mark.parametrize("field,value", [
    ("prediction_time", "2026-10-18T15:00:00Z"),
    ("baseline_prob", 1.2),
    ("challenger_prob", float("nan")),
    ("outcome", 2),
    ("runner_id", ""),
    ("race_time", "2026-10-18T15:00:00"),
])
def test_invalid_evidence_rejected(field, value):
    rows = sample()
    rows[0] = replace(rows[0], **{field: value})
    with pytest.raises(ValueError):
        evaluate(rows, min_runners=2)


def test_duplicate_identity_rejected():
    rows = sample()
    with pytest.raises(ValueError, match="duplicate"):
        evaluate([rows[0], rows[0]], min_runners=2)


def test_incomplete_race_rejected():
    with pytest.raises(ValueError, match="exactly one winner"):
        evaluate([sample()[1]], min_runners=1)


def test_insufficient_review_evidence_rejected():
    with pytest.raises(ValueError, match="insufficient"):
        evaluate(sample())  # existing 300-runner minimum
