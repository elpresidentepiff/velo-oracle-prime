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


def test_manual_recovery_allows_shadow_learning_but_blocks_promotion(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "velo_daily_run_truth_2026_06_07.json").write_text(
        json.dumps(
            {
                "status": "MANUAL_RECOVERY_ONLY",
                "alert_required": True,
                "issues": ["MANUAL_RUN_ONLY"],
                "cron_truth_status": "FAIL_OR_UNPROVEN",
            }
        )
    )
    (data_dir / "velo_run_observability_2026_06_07_clean.json").write_text(
        json.dumps(
            {
                "source_truth": "RP_MERGED_CLEAN",
                "timestamp": "2026-06-07T12:00:00+00:00",
            }
        )
    )
    council_dir = data_dir / "council_runs"
    council_dir.mkdir()
    (council_dir / "council_run_2026-06-07.json").write_text(
        json.dumps({"council_verdict": "PASS_TO_LEARNING"})
    )
    monkeypatch.setattr(update_mission_control, "ROOT", tmp_path)

    result = update_mission_control.build_mission_control("2026-06-07")

    assert result["learning_gate_status"] == "OPEN"
    assert result["promotion_gate_status"] == "BLOCKED"
    assert "GATE_PIPELINE_TRUTH_MANUAL_RECOVERY_ONLY" in result["gate_reasons"]
