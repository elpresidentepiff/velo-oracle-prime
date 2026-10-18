"""Read-only, offline adapter for independently exported Velo evidence.

No database credentials, network connection, writes or inference side effects.
Input is an operator-exported JSON array of per-runner canonical records.
This adapter is strict by design: missing official result verification fails closed.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.intelligence.challenger_lab import Observation


def load_verified_export(path: Path) -> tuple[list[Observation], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("runners"), list):
        raise ValueError("expected runners array")
    if data.get("result_source_complete") is not True:
        raise ValueError("official result source incomplete")
    if data.get("holdout_frozen") is not True:
        raise ValueError("holdout not frozen")
    if not data.get("official_result_reference") or not data.get("prediction_run_id"):
        raise ValueError("official result reference and prediction run ID required")
    if not data.get("baseline_commit") or not data.get("challenger_commit"):
        raise ValueError("model artifact commits required")
    observations = []
    for record in data["runners"]:
        if record.get("official_evaluation_eligible") is not True:
            raise ValueError("ineligible official outcome")
        if record.get("result_source_complete") is not True:
            raise ValueError("runner result source incomplete")
        if record.get("non_runner") is not False:
            raise ValueError("non-runner or unknown participation")
        observations.append(Observation(
            race_id=str(record["race_id"]), runner_id=str(record["runner_id"]),
            race_time=record["race_time"], prediction_time=record["prediction_time"],
            outcome=record["win"], baseline_prob=record["baseline_prob"],
            challenger_prob=record["challenger_prob"],
        ))
    return observations, {
        "prediction_run_id": data["prediction_run_id"],
        "official_result_reference": data["official_result_reference"],
        "baseline_commit": data["baseline_commit"],
        "challenger_commit": data["challenger_commit"],
        "evaluation_status": "PENDING_INDEPENDENT_REVIEW",
    }
