"""Read-only adapter contract tests using synthetic exports."""
import json

import pytest

from src.intelligence.challenger_lab import evaluate
from src.intelligence.challenger_readonly_adapter import load_verified_export


def valid():
    return {
        "result_source_complete": True, "holdout_frozen": True,
        "official_result_reference": "fixture-official-hash",
        "prediction_run_id": "fixture-run", "baseline_commit": "sha-1",
        "challenger_commit": "sha-2",
        "runners": [
            {"race_id": "r1", "runner_id": str(i), "race_time": "2026-10-17T15:00:00Z",
             "prediction_time": "2026-10-17T14:00:00Z", "official_evaluation_eligible": True,
             "result_source_complete": True, "non_runner": False,
             "win": int(i == 1), "baseline_prob": 0.5,
             "challenger_prob": 0.7 if i == 1 else 0.3}
            for i in (1, 2)
        ],
    }


def load(tmp_path, data):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data))
    return load_verified_export(path)


def test_readonly_export_can_be_evaluated(tmp_path):
    observations, metadata = load(tmp_path, valid())
    report = evaluate(observations, min_runners=2)
    assert report["challenger_brier"] < report["baseline_brier"]
    assert report["promotion"] == "NOT_AUTHORISED"
    assert metadata["evaluation_status"] == "PENDING_INDEPENDENT_REVIEW"


@pytest.mark.parametrize("field,bad", [
    ("result_source_complete", False), ("holdout_frozen", False),
    ("official_result_reference", ""), ("baseline_commit", ""),
])
def test_missing_export_verification_fails(tmp_path, field, bad):
    data = valid()
    data[field] = bad
    with pytest.raises(ValueError):
        load(tmp_path, data)


@pytest.mark.parametrize("field,bad", [
    ("official_evaluation_eligible", False),
    ("result_source_complete", False),
    ("non_runner", True), ("non_runner", None),
])
def test_runner_verification_fails(tmp_path, field, bad):
    data = valid()
    data["runners"][0][field] = bad
    with pytest.raises(ValueError):
        load(tmp_path, data)
