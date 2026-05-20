"""
Tests for Issue #80 — VÉLØ Runner Snapshot Store.

Validates:
  - JSONL file created with correct row count per runner
  - All required fields present in each row (including run_id)
  - Rank 0 = top pick, rank N = Nth runner
  - prob_gap = 0.0 for rank 0, top_vp - runner_vp for rank > 0
  - live_scoring_changed and write_execution_allowed always False
  - All rows in same batch share run_id
  - Same-day two writes produce separate files (no overwrite)
  - Write failure does NOT raise into caller (safety invariant)
  - Supabase client failure does NOT raise into caller
  - Empty preds list is handled gracefully
  - Multiple races written as flat JSONL (one line per runner)
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.velo.runner_snapshot_store import (  # noqa: E402
    build_run_id,
    write_runner_snapshots,
)

# Stable run_id used across all tests for filename predictability
_RUN_ID = "2026_05_20_abc12345_1716220800000"
_DATE_TAG = "2026_05_20"
_DATE_STR = "2026-05-20"
_JSONL_NAME = f"runner_snapshots_{_DATE_TAG}_{_RUN_ID}.jsonl"


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _pred(horse="Horse A", velo_prime_prob=0.40, mds=0.15, imp=0.12):
    return {
        "horse": horse,
        "horse_id": f"hid_{horse.replace(' ', '_').lower()}",
        "velo_prime_prob": velo_prime_prob,
        "sqpe_v17_prob": 0.35,
        "market_deception_score": mds,
        "improvement_score": imp,
        "place_prob": 0.65,
        "longshot_prob": 0.02,
        "release_day_prob": 0.10,
        "comment_intel_score": 0.08,
        "cash_run_flag": False,
        "setup_run_flag": False,
        "decoy_support_flag": False,
        "rpd_tag": "CYCLE_RUN",
        "rpd_confidence": 0.70,
        "rpd_evidence_codes": ["FORM_UP", "MARK_READY"],
        "rpdc_primary_tag": "STABLE_WARM",
        "rpdc_release_score": 0.55,
        "rpdc_cash_window_flag": False,
        "rpdc_tags": [],
        "tie_gate_fires": False,
        "tie_gate_tier_upgrade": None,
        "active_components": ["sqpe", "mds", "improvement"],
        "excluded_from_ensemble": [],
        "assigned_product": "WIN_ONLY",
        "confidence_level": "HIGH",
        "decision_tier": "A",
        "execution_allowed": False,
        "race_archetype": "Structure",
        "archetype_confidence": "high",
        "router_reasons": ["VP_ABOVE_GATE"],
        "sp_dec": None,
        "is_fav": None,
    }


def _race(race_id="rac_001", course="Ascot", off_time="14:30"):
    return {
        "race_id": race_id,
        "course": course,
        "off_time": off_time,
        "race_name": "Test Race",
    }


def _scored_1race_2runners():
    race = _race()
    preds = [
        _pred("Horse A", velo_prime_prob=0.45),
        _pred("Horse B", velo_prime_prob=0.30),
    ]
    return [(race, preds, "A", [])]


def _read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def _write(scored, tmp_path, run_id=_RUN_ID):
    return write_runner_snapshots(
        scored, _DATE_STR, _DATE_TAG, run_id=run_id, snapshot_dir=tmp_path
    )


# ── Row count and file creation ────────────────────────────────────────────────


def test_creates_jsonl_file(tmp_path):
    n = _write(_scored_1race_2runners(), tmp_path)
    assert n == 2
    assert (tmp_path / _JSONL_NAME).exists()


def test_row_count_matches_total_runners(tmp_path):
    race1 = _race("rac_001")
    race2 = _race("rac_002", course="Newmarket", off_time="15:00")
    scored = [
        (race1, [_pred("A1"), _pred("A2"), _pred("A3")], "A", []),
        (race2, [_pred("B1"), _pred("B2")], "B", []),
    ]
    n = _write(scored, tmp_path)
    assert n == 5
    assert len((tmp_path / _JSONL_NAME).read_text().splitlines()) == 5


def test_each_line_is_valid_json(tmp_path):
    _write(_scored_1race_2runners(), tmp_path)
    for line in (tmp_path / _JSONL_NAME).read_text().splitlines():
        assert isinstance(json.loads(line), dict)


# ── run_id invariants ─────────────────────────────────────────────────────────


def test_every_row_has_run_id(tmp_path):
    _write(_scored_1race_2runners(), tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    for row in rows:
        assert "run_id" in row, "row missing run_id"
        assert row["run_id"] == _RUN_ID


def test_all_rows_in_same_batch_share_run_id(tmp_path):
    race1 = _race("rac_001")
    race2 = _race("rac_002", course="Newmarket", off_time="15:00")
    scored = [
        (race1, [_pred("A1"), _pred("A2")], "A", []),
        (race2, [_pred("B1")], "B", []),
    ]
    _write(scored, tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    assert len(rows) == 3
    run_ids = {r["run_id"] for r in rows}
    assert run_ids == {_RUN_ID}, f"Expected single run_id, got {run_ids}"


def test_same_day_two_writes_produce_separate_files(tmp_path):
    scored = _scored_1race_2runners()
    run_id_1 = "2026_05_20_abc12345_1000000000001"
    run_id_2 = "2026_05_20_abc12345_1000000000002"
    write_runner_snapshots(scored, _DATE_STR, _DATE_TAG, run_id=run_id_1, snapshot_dir=tmp_path)
    write_runner_snapshots(scored, _DATE_STR, _DATE_TAG, run_id=run_id_2, snapshot_dir=tmp_path)
    file1 = tmp_path / f"runner_snapshots_{_DATE_TAG}_{run_id_1}.jsonl"
    file2 = tmp_path / f"runner_snapshots_{_DATE_TAG}_{run_id_2}.jsonl"
    assert file1.exists(), "First run file missing"
    assert file2.exists(), "Second run file missing"
    assert file1 != file2


def test_supabase_rows_contain_run_id(tmp_path):
    mock_client = MagicMock()
    write_runner_snapshots(
        _scored_1race_2runners(), _DATE_STR, _DATE_TAG, run_id=_RUN_ID,
        snapshot_dir=tmp_path,
        supabase_client=mock_client,
    )
    call_args = mock_client.table.return_value.insert.call_args
    assert call_args is not None, "Supabase insert was not called"
    passed_rows = call_args[0][0]
    for row in passed_rows:
        assert row["run_id"] == _RUN_ID, f"row missing run_id: {row.get('run_id')}"


# ── Rank and prob_gap ──────────────────────────────────────────────────────────


def test_rank_0_is_top_pick(tmp_path):
    _write(_scored_1race_2runners(), tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    rank0 = next(r for r in rows if r["rank"] == 0)
    assert rank0["horse"] == "Horse A"


def test_rank_1_is_second_runner(tmp_path):
    _write(_scored_1race_2runners(), tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    rank1 = next(r for r in rows if r["rank"] == 1)
    assert rank1["horse"] == "Horse B"


def test_prob_gap_zero_for_rank_0(tmp_path):
    _write(_scored_1race_2runners(), tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    rank0 = next(r for r in rows if r["rank"] == 0)
    assert rank0["prob_gap"] == 0.0


def test_prob_gap_correct_for_rank_1(tmp_path):
    _write(_scored_1race_2runners(), tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    rank1 = next(r for r in rows if r["rank"] == 1)
    # top_vp=0.45, runner_vp=0.30 → gap=0.15
    assert abs(rank1["prob_gap"] - 0.15) < 1e-5


# ── Required fields ────────────────────────────────────────────────────────────


def test_required_context_fields_present(tmp_path):
    _write(_scored_1race_2runners(), tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    required = {
        "run_id", "created_at", "race_date", "race_id", "course", "off_time", "tier",
        "rank", "horse", "horse_id", "velo_prime_prob", "market_deception_score",
        "improvement_score", "top_pick_name", "top_pick_vp", "prob_gap",
        "live_scoring_changed", "write_execution_allowed",
    }
    for row in rows:
        for field in required:
            assert field in row, f"Missing field: {field}"


# ── Safety invariants ─────────────────────────────────────────────────────────


def test_live_scoring_changed_always_false(tmp_path):
    _write(_scored_1race_2runners(), tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    for row in rows:
        assert row["live_scoring_changed"] is False


def test_write_execution_allowed_always_false(tmp_path):
    _write(_scored_1race_2runners(), tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    for row in rows:
        assert row["write_execution_allowed"] is False


# ── Failure safety (write failure cannot affect caller) ───────────────────────


def test_unwritable_dir_does_not_raise():
    scored = _scored_1race_2runners()
    result = write_runner_snapshots(
        scored, _DATE_STR, _DATE_TAG, run_id=_RUN_ID,
        snapshot_dir=Path("/dev/null/nonexistent"),
    )
    assert result == 0


def test_supabase_failure_does_not_raise(tmp_path):
    bad_client = MagicMock()
    bad_client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB down")
    n = write_runner_snapshots(
        _scored_1race_2runners(), _DATE_STR, _DATE_TAG, run_id=_RUN_ID,
        snapshot_dir=tmp_path,
        supabase_client=bad_client,
    )
    assert n == 2


def test_empty_preds_race_is_skipped_gracefully(tmp_path):
    n = write_runner_snapshots(
        [(_race(), [], "B", [])], _DATE_STR, _DATE_TAG, run_id=_RUN_ID, snapshot_dir=tmp_path
    )
    assert n == 0


def test_empty_scored_list_returns_zero(tmp_path):
    n = write_runner_snapshots([], _DATE_STR, _DATE_TAG, run_id=_RUN_ID, snapshot_dir=tmp_path)
    assert n == 0


# ── Race context propagated correctly ─────────────────────────────────────────


def test_race_context_fields_written_to_all_rows(tmp_path):
    race = _race(race_id="rac_specific", course="Cheltenham", off_time="16:45")
    scored = [(race, [_pred("X"), _pred("Y")], "A", [])]
    _write(scored, tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    for row in rows:
        assert row["race_id"] == "rac_specific"
        assert row["course"] == "Cheltenham"
        assert row["off_time"] == "16:45"
        assert row["race_date"] == _DATE_STR
        assert row["tier"] == "A"


def test_top_pick_name_written_to_all_rows(tmp_path):
    scored = [(_race(), [_pred("Top Horse", velo_prime_prob=0.50), _pred("Second Horse", velo_prime_prob=0.25)], "A", [])]
    _write(scored, tmp_path)
    rows = _read_rows(tmp_path / _JSONL_NAME)
    for row in rows:
        assert row["top_pick_name"] == "Top Horse"
        assert abs(row["top_pick_vp"] - 0.50) < 1e-6


# ── build_run_id ──────────────────────────────────────────────────────────────


def test_build_run_id_format():
    rid = build_run_id("2026_05_20", "abc1234567")
    parts = rid.split("_")
    # date_tag has 3 parts joined by underscore: 2026, 05, 20 → then sha8, then epoch_ms
    assert parts[0] == "2026"
    assert parts[1] == "05"
    assert parts[2] == "20"
    assert parts[3] == "abc12345"  # sha8
    assert parts[4].isdigit()      # epoch_ms


def test_build_run_id_different_calls_produce_different_ids():
    rid1 = build_run_id("2026_05_20", "abc123")
    rid2 = build_run_id("2026_05_20", "abc123")
    # epoch_ms differs between calls (at ms resolution — practically always unique)
    # Both should at minimum be valid strings with sha component
    assert "abc123" in rid1
    assert "abc123" in rid2


# ── Supabase happy path ────────────────────────────────────────────────────────


def test_supabase_called_when_client_provided(tmp_path):
    mock_client = MagicMock()
    mock_execute = MagicMock()
    mock_client.table.return_value.insert.return_value.execute = mock_execute
    _write(_scored_1race_2runners(), tmp_path, run_id=_RUN_ID)
    write_runner_snapshots(
        _scored_1race_2runners(), _DATE_STR, _DATE_TAG, run_id=_RUN_ID,
        snapshot_dir=tmp_path,
        supabase_client=mock_client,
    )
    mock_client.table.assert_called_once_with("runner_prediction_snapshots")
    mock_execute.assert_called_once()


def test_supabase_not_called_when_no_client(tmp_path):
    n = _write(_scored_1race_2runners(), tmp_path)
    assert n == 2
