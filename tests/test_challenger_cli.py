"""CLI integration tests; only tmp_path fixtures, zero production connections."""
import json

import pytest

from src.intelligence.challenger_cli import run


def fixture():
    return {
        "result_source_complete": True,
        "holdout_frozen": True,
        "source_ref": "test-only-fixture",
        "run_id": "fixture-001",
        "observations": [
            {"race_id": "r", "runner_id": "1", "race_time": "2026-10-18T12:00:00Z",
             "prediction_time": "2026-10-18T11:00:00Z", "outcome": 1,
             "baseline_prob": 0.5, "challenger_prob": 0.6},
            {"race_id": "r", "runner_id": "2", "race_time": "2026-10-18T12:00:00Z",
             "prediction_time": "2026-10-18T11:00:00Z", "outcome": 0,
             "baseline_prob": 0.5, "challenger_prob": 0.4},
        ],
    }


def test_cli_writes_reproducible_offline_artifact(tmp_path):
    p = tmp_path / "input.json"
    out = tmp_path / "report.json"
    p.write_text(json.dumps(fixture()))
    result = run(p, out, "test-commit", min_runners=2)
    assert out.exists()
    assert json.loads(out.read_text()) == result
    assert result["production_authority"] is False
    assert result["input_provenance"]["certification"] == "SELF_ATTESTED_NOT_INDEPENDENTLY_VERIFIED"
    assert len(result["input_provenance"]["source_file_sha256"]) == 64


@pytest.mark.parametrize("key,value", [
    ("result_source_complete", False),
    ("holdout_frozen", False),
    ("source_ref", ""),
    ("run_id", ""),
])
def test_cli_rejects_unverified_metadata(tmp_path, key, value):
    payload = fixture()
    payload[key] = value
    p = tmp_path / "input.json"
    out = tmp_path / "out.json"
    p.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        run(p, out, "test-commit", min_runners=2)
    assert not out.exists()


def test_cli_rejects_identical_input_output(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps(fixture()))
    with pytest.raises(ValueError, match="must differ"):
        run(p, p, "test-commit", min_runners=2)
