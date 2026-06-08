from __future__ import annotations

import json

from scripts.ops import update_mission_control


def test_missing_run_truth_blocks_learning_and_promotion(monkeypatch, tmp_path):
    monkeypatch.setattr(update_mission_control, "ROOT", tmp_path)

    result = update_mission_control.build_mission_control("2026-06-07")

    assert result["run_truth"]["status"] == "MISSING"
    assert result["learning_gate_status"] == "BLOCKED"
    assert result["promotion_gate_status"] == "BLOCKED"
    assert "GATE_PIPELINE_TRUTH_MISSING" in result["gate_reasons"]


def test_verdicts_without_pipeline_truth_blocks_false_green(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "velo_daily_run_truth_2026_06_07.json").write_text(
        json.dumps(
            {
                "status": "VERDICTS_WITHOUT_PIPELINE_TRUTH",
                "alert_required": True,
                "issues": ["VERDICTS_WITHOUT_PIPELINE_TRUTH"],
                "cron_truth_status": "FAIL_OR_UNPROVEN",
            }
        )
    )
    monkeypatch.setattr(update_mission_control, "ROOT", tmp_path)

    result = update_mission_control.build_mission_control("2026-06-07")

    assert result["run_truth"]["status"] == "VERDICTS_WITHOUT_PIPELINE_TRUTH"
    assert result["learning_gate_status"] == "BLOCKED"
    assert result["promotion_gate_status"] == "BLOCKED"
