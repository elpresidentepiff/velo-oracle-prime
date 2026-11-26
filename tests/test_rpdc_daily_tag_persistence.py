"""Daily RPDC tag projection must be a faithful, auditable read model."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_rpdc_daily",
    ROOT / "scripts" / "ops" / "build_rpdc_daily.py",
)
assert SPEC and SPEC.loader
rpdc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rpdc)


def _candidate(**overrides: object) -> dict:
    row = {
        "run_date": "2026-11-26",
        "race_id": "rp_123",
        "horse_id": "456",
        "horse": "Example Runner",
        "rpdc_tags": ["MARK_READY", "CYCLE_RUN_2"],
        "rpdc_release_score": 4.2,
        "rpdc_suppression_score": 0.0,
        "rpdc_cash_window_flag": True,
        "rpdc_trap_flag": False,
        "or_delta_to_win": -2,
        "days_since_run": 18,
        "campaign_run_no": 2,
    }
    row.update(overrides)
    return row


def test_tag_projection_is_one_row_per_existing_tag_and_preserves_identity():
    rows = rpdc.build_tag_rows([_candidate()])

    assert [(r["race_id"], r["horse_id"], r["tag"]) for r in rows] == [
        ("rp_123", "456", "MARK_READY"),
        ("rp_123", "456", "CYCLE_RUN_2"),
    ]
    assert all(r["run_date"] == "2026-11-26" for r in rows)
    assert all(r["horse"] == "Example Runner" for r in rows)


def test_tag_projection_has_auditable_candidate_evidence_not_provider_data():
    row = rpdc.build_tag_rows([_candidate()])[0]

    assert row["tag_value"] == "3.0"
    assert row["tag_strength"] == 1.0
    assert '"source":"runner_release_candidates"' in row["evidence"]
    assert '"release_score":4.2' in row["evidence"]
    assert "winProbability" not in row["evidence"]
    assert "prediction" not in row["evidence"]


def test_tag_projection_handles_untagged_candidate_without_inventing_tag():
    assert rpdc.build_tag_rows([_candidate(rpdc_tags=[])]) == []


def test_tag_projection_blocks_missing_identity():
    with pytest.raises(ValueError, match="RPDC_TAG_IDENTITY_MISSING"):
        rpdc.build_tag_rows([_candidate(horse_id="")])


def test_daily_builder_wires_candidate_projection_and_verification():
    source = (ROOT / "scripts" / "ops" / "build_rpdc_daily.py").read_text(encoding="utf-8")
    assert "build_tag_rows(candidates)" in source
    assert '"/today_rpdc_tags?run_date=eq.{date_str}"' in source
    assert "RPDC_TAG_COUNT_MISMATCH" in source
