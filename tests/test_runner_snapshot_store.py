"""
Tests for Issue #80 — VÉLØ Runner Snapshot Store.

Validates:
  - JSONL file created with correct row count per runner
  - All required fields present in each row
  - Rank 0 = top pick, rank N = Nth runner
  - prob_gap = 0.0 for rank 0, top_vp - runner_vp for rank > 0
  - live_scoring_changed and write_execution_allowed always False
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

from src.velo.runner_snapshot_store import write_runner_snapshots  # noqa: E402

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


# ── Row count and file creation ────────────────────────────────────────────────


def test_creates_jsonl_file(tmp_path):
    scored = _scored_1race_2runners()
    n = write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    assert n == 2
    assert (tmp_path / "runner_snapshots_2026_05_20.jsonl").exists()


def test_row_count_matches_total_runners(tmp_path):
    race1 = _race("rac_001")
    race2 = _race("rac_002", course="Newmarket", off_time="15:00")
    scored = [
        (race1, [_pred("A1"), _pred("A2"), _pred("A3")], "A", []),
        (race2, [_pred("B1"), _pred("B2")], "B", []),
    ]
    n = write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    assert n == 5
    assert len((tmp_path / "runner_snapshots_2026_05_20.jsonl").read_text().splitlines()) == 5


def test_each_line_is_valid_json(tmp_path):
    scored = _scored_1race_2runners()
    write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    for line in (tmp_path / "runner_snapshots_2026_05_20.jsonl").read_text().splitlines():
        assert isinstance(json.loads(line), dict)


# ── Rank and prob_gap ──────────────────────────────────────────────────────────


def test_rank_0_is_top_pick(tmp_path):
    scored = _scored_1race_2runners()
    write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    rows = _read_rows(tmp_path / "runner_snapshots_2026_05_20.jsonl")
    rank0 = next(r for r in rows if r["rank"] == 0)
    assert rank0["horse"] == "Horse A"


def test_rank_1_is_second_runner(tmp_path):
    scored = _scored_1race_2runners()
    write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    rows = _read_rows(tmp_path / "runner_snapshots_2026_05_20.jsonl")
    rank1 = next(r for r in rows if r["rank"] == 1)
    assert rank1["horse"] == "Horse B"


def test_prob_gap_zero_for_rank_0(tmp_path):
    scored = _scored_1race_2runners()
    write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    rows = _read_rows(tmp_path / "runner_snapshots_2026_05_20.jsonl")
    rank0 = next(r for r in rows if r["rank"] == 0)
    assert rank0["prob_gap"] == 0.0


def test_prob_gap_correct_for_rank_1(tmp_path):
    scored = _scored_1race_2runners()
    write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    rows = _read_rows(tmp_path / "runner_snapshots_2026_05_20.jsonl")
    rank1 = next(r for r in rows if r["rank"] == 1)
    # top_vp=0.45, runner_vp=0.30 → gap=0.15
    assert abs(rank1["prob_gap"] - 0.15) < 1e-5


# ── Required fields ────────────────────────────────────────────────────────────


def test_required_context_fields_present(tmp_path):
    scored = _scored_1race_2runners()
    write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    rows = _read_rows(tmp_path / "runner_snapshots_2026_05_20.jsonl")
    required = {
        "created_at", "race_date", "race_id", "course", "off_time", "tier",
        "rank", "horse", "horse_id", "velo_prime_prob", "market_deception_score",
        "improvement_score", "top_pick_name", "top_pick_vp", "prob_gap",
        "live_scoring_changed", "write_execution_allowed",
    }
    for row in rows:
        for field in required:
            assert field in row, f"Missing field: {field}"


# ── Safety invariants ─────────────────────────────────────────────────────────


def test_live_scoring_changed_always_false(tmp_path):
    scored = _scored_1race_2runners()
    write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    rows = _read_rows(tmp_path / "runner_snapshots_2026_05_20.jsonl")
    for row in rows:
        assert row["live_scoring_changed"] is False


def test_write_execution_allowed_always_false(tmp_path):
    scored = _scored_1race_2runners()
    write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    rows = _read_rows(tmp_path / "runner_snapshots_2026_05_20.jsonl")
    for row in rows:
        assert row["write_execution_allowed"] is False


# ── Failure safety (write failure cannot affect caller) ───────────────────────


def test_unwritable_dir_does_not_raise():
    scored = _scored_1race_2runners()
    result = write_runner_snapshots(
        scored, "2026-05-20", "2026_05_20", snapshot_dir=Path("/dev/null/nonexistent")
    )
    assert result == 0


def test_supabase_failure_does_not_raise(tmp_path):
    bad_client = MagicMock()
    bad_client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB down")
    scored = _scored_1race_2runners()
    n = write_runner_snapshots(
        scored, "2026-05-20", "2026_05_20",
        snapshot_dir=tmp_path,
        supabase_client=bad_client,
    )
    assert n == 2


def test_empty_preds_race_is_skipped_gracefully(tmp_path):
    scored = [(_race(), [], "B", [])]
    n = write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    assert n == 0


def test_empty_scored_list_returns_zero(tmp_path):
    n = write_runner_snapshots([], "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    assert n == 0


# ── Race context propagated correctly ─────────────────────────────────────────


def test_race_context_fields_written_to_all_rows(tmp_path):
    race = _race(race_id="rac_specific", course="Cheltenham", off_time="16:45")
    scored = [(race, [_pred("X"), _pred("Y")], "A", [])]
    write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    rows = _read_rows(tmp_path / "runner_snapshots_2026_05_20.jsonl")
    for row in rows:
        assert row["race_id"] == "rac_specific"
        assert row["course"] == "Cheltenham"
        assert row["off_time"] == "16:45"
        assert row["race_date"] == "2026-05-20"
        assert row["tier"] == "A"


def test_top_pick_name_written_to_all_rows(tmp_path):
    race = _race()
    scored = [(race, [_pred("Top Horse", velo_prime_prob=0.50), _pred("Second Horse", velo_prime_prob=0.25)], "A", [])]
    write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    rows = _read_rows(tmp_path / "runner_snapshots_2026_05_20.jsonl")
    for row in rows:
        assert row["top_pick_name"] == "Top Horse"
        assert abs(row["top_pick_vp"] - 0.50) < 1e-6


# ── Supabase happy path ────────────────────────────────────────────────────────


def test_supabase_called_when_client_provided(tmp_path):
    mock_client = MagicMock()
    mock_execute = MagicMock()
    mock_client.table.return_value.insert.return_value.execute = mock_execute
    scored = _scored_1race_2runners()
    write_runner_snapshots(
        scored, "2026-05-20", "2026_05_20",
        snapshot_dir=tmp_path,
        supabase_client=mock_client,
    )
    mock_client.table.assert_called_once_with("runner_prediction_snapshots")
    mock_execute.assert_called_once()


def test_supabase_not_called_when_no_client(tmp_path):
    scored = _scored_1race_2runners()
    n = write_runner_snapshots(scored, "2026-05-20", "2026_05_20", snapshot_dir=tmp_path)
    assert n == 2
