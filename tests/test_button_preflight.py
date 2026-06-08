"""
Tests for velo_race_day_button preflight guards.

Covers:
  1. _best_capture_label: prefers refresh2 over refresh over base label
  2. _preflight_injection_gate: blocks on null off_time, missing injection, low course count
  3. Integration: gate passes on valid injection, blocks on partial data
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.velo_race_day_button import _best_capture_label, _preflight_injection_gate  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_race(course: str, off_time: str | None = "14:30") -> dict:
    return {"race_id": f"r_{course}", "course": course, "off_time": off_time}


def _write_injection(tmp_dir: Path, races: list[dict]) -> Path:
    inj_dir = tmp_dir / "racing_post_account_parsed" / "live-full-racepages-2026-01-01"
    inj_dir.mkdir(parents=True, exist_ok=True)
    inj_path = inj_dir / "racecard_injection.json"
    inj_path.write_text(json.dumps({"races": races}), encoding="utf-8")
    return inj_path


# ── _best_capture_label ────────────────────────────────────────────────────────

class TestBestCaptureLabel:
    def test_returns_base_when_no_raw_root(self, monkeypatch, tmp_path):
        """When raw root doesn't exist, return base label."""
        import scripts.ops.velo_race_day_button as btn
        monkeypatch.setattr(btn, "RAW_ROOT", tmp_path / "nonexistent")
        assert btn._best_capture_label("2026-01-01") == "live-full-racepages-2026-01-01"

    def test_returns_base_when_only_base_exists(self, monkeypatch, tmp_path):
        raw_root = tmp_path / "raw"
        (raw_root / "live-full-racepages-2026-01-01").mkdir(parents=True)
        import scripts.ops.velo_race_day_button as btn
        monkeypatch.setattr(btn, "RAW_ROOT", raw_root)
        assert btn._best_capture_label("2026-01-01") == "live-full-racepages-2026-01-01"

    def test_prefers_refresh_over_base(self, monkeypatch, tmp_path):
        raw_root = tmp_path / "raw"
        (raw_root / "live-full-racepages-2026-01-01").mkdir(parents=True)
        (raw_root / "live-full-racepages-2026-01-01-refresh").mkdir(parents=True)
        import scripts.ops.velo_race_day_button as btn
        monkeypatch.setattr(btn, "RAW_ROOT", raw_root)
        assert btn._best_capture_label("2026-01-01") == "live-full-racepages-2026-01-01-refresh"

    def test_prefers_refresh2_over_refresh(self, monkeypatch, tmp_path):
        """refresh2 label is longer than refresh so it wins."""
        raw_root = tmp_path / "raw"
        (raw_root / "live-full-racepages-2026-01-01").mkdir(parents=True)
        (raw_root / "live-full-racepages-2026-01-01-refresh").mkdir(parents=True)
        (raw_root / "live-full-racepages-2026-01-01-refresh2").mkdir(parents=True)
        import scripts.ops.velo_race_day_button as btn
        monkeypatch.setattr(btn, "RAW_ROOT", raw_root)
        assert btn._best_capture_label("2026-01-01") == "live-full-racepages-2026-01-01-refresh2"

    def test_ignores_other_dates(self, monkeypatch, tmp_path):
        """Folders from other dates must not affect label selection for target date."""
        raw_root = tmp_path / "raw"
        (raw_root / "live-full-racepages-2026-01-01").mkdir(parents=True)
        (raw_root / "live-full-racepages-2026-01-02-refresh2").mkdir(parents=True)
        import scripts.ops.velo_race_day_button as btn
        monkeypatch.setattr(btn, "RAW_ROOT", raw_root)
        assert btn._best_capture_label("2026-01-01") == "live-full-racepages-2026-01-01"


# ── _preflight_injection_gate ──────────────────────────────────────────────────

class TestPreflightInjectionGate:
    def test_passes_on_valid_injection(self, tmp_path):
        courses = ["Ascot", "Chepstow", "Newbury", "York"]
        races = [_make_race(c, "14:30") for c in courses]
        inj = _write_injection(tmp_path, races)
        fails = _preflight_injection_gate(inj, "2026-01-01")
        assert fails == [], f"Expected no failures, got: {fails}"

    def test_blocks_on_missing_injection(self, tmp_path):
        missing = tmp_path / "does_not_exist.json"
        fails = _preflight_injection_gate(missing, "2026-01-01")
        assert any("INJECTION_MISSING" in f for f in fails)

    def test_blocks_on_empty_injection(self, tmp_path):
        inj_path = tmp_path / "racecard_injection.json"
        inj_path.write_text(json.dumps({"races": []}), encoding="utf-8")
        fails = _preflight_injection_gate(inj_path, "2026-01-01")
        assert any("INJECTION_EMPTY" in f for f in fails)

    def test_blocks_on_null_off_time(self, tmp_path):
        """A single race with null off_time must trigger the gate."""
        races = [
            _make_race("Ascot", "14:30"),
            _make_race("Chepstow", None),   # This is the bug from 2026-06-06
            _make_race("Newbury", "15:00"),
            _make_race("York", "15:30"),
        ]
        inj = _write_injection(tmp_path, races)
        fails = _preflight_injection_gate(inj, "2026-01-01")
        assert any("OFF_TIME_NULL" in f for f in fails), f"Expected OFF_TIME_NULL, got: {fails}"
        assert any("Chepstow" in f for f in fails)

    def test_blocks_on_low_course_count(self, tmp_path):
        """Two courses is suspicious — partial capture."""
        races = [_make_race("Ascot", "14:30"), _make_race("Ascot", "15:00")]
        inj = _write_injection(tmp_path, races)
        fails = _preflight_injection_gate(inj, "2026-01-01")
        assert any("COURSE_COUNT_LOW" in f for f in fails)

    def test_allows_exactly_three_courses(self, tmp_path):
        """3 courses is the minimum acceptable — should not trigger COURSE_COUNT_LOW."""
        races = [
            _make_race("Ascot", "14:30"),
            _make_race("Chepstow", "14:45"),
            _make_race("Newbury", "15:00"),
        ]
        inj = _write_injection(tmp_path, races)
        fails = _preflight_injection_gate(inj, "2026-01-01")
        course_fails = [f for f in fails if "COURSE_COUNT_LOW" in f]
        assert course_fails == [], f"3 courses should pass: {fails}"

    def test_blocks_on_corrupt_json(self, tmp_path):
        inj_path = tmp_path / "racecard_injection.json"
        inj_path.write_text("not valid json{{{", encoding="utf-8")
        fails = _preflight_injection_gate(inj_path, "2026-01-01")
        assert any("INJECTION_PARSE_ERROR" in f for f in fails)

    def test_multiple_races_per_course_allowed(self, tmp_path):
        """Multiple races per course (normal day) must not cause false positives."""
        races = []
        for course in ["Ascot", "Chepstow", "Newbury", "York"]:
            for hh in range(14, 20):
                races.append(_make_race(course, f"{hh:02d}:00"))
        inj = _write_injection(tmp_path, races)
        fails = _preflight_injection_gate(inj, "2026-01-01")
        assert fails == []

    def test_blocks_when_all_off_times_null(self, tmp_path):
        """Full null off_time scenario — the bug pattern from today."""
        races = [_make_race(c, None) for c in ["Ascot", "Chepstow", "Newbury", "York"]]
        inj = _write_injection(tmp_path, races)
        fails = _preflight_injection_gate(inj, "2026-01-01")
        assert any("OFF_TIME_NULL" in f for f in fails)
        assert "4 race(s)" in "\n".join(fails)
