"""Contracts for Horse Arrival Snapshot evidence collection."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "ops" / "build_arrival_snapshot_packets.py"
SPEC = importlib.util.spec_from_file_location("arrival_snapshot_packets", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_requires_durable_rp_source_timestamp_not_file_mtime() -> None:
    assert MODULE._captured_at_from_race({}) is None
    assert MODULE._captured_at_from_race({"source_parsed_at": "not-a-time"}) is None
    assert MODULE._captured_at_from_race({"source_parsed_at": "2026-11-22T09:00:00"}) is None


def test_accepts_only_timezone_aware_rp_source_timestamp() -> None:
    assert MODULE._captured_at_from_race({"source_parsed_at": "2026-11-22T09:00:00Z"}) == datetime(
        2026, 11, 22, 9, 0, tzinfo=UTC
    )


def test_no_merged_cards_returns_complete_zero_coverage_shape(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(MODULE, "MERGED_DIR", tmp_path)

    assert MODULE.build_packets_for_date("2026-11-22", dry_run=True) == {
        "date": "2026-11-22",
        "total_runners": 0,
        "runners_with_spotlight": 0,
        "training_eligible": 0,
        "files": 0,
    }
