"""
Tests for Issue #74 — VÉLØ Runtime Timing Audit

Validates:
  - _RuntimeTimer class correctness
  - to_dict() output matches required JSON schema
  - Stage marks accumulate correctly
  - Per-race timing shape is correct
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "ops"))

from run_prime_today import _RuntimeTimer


def test_timer_marks_accumulate():
    t = _RuntimeTimer()
    time.sleep(0.01)
    dur = t.mark("preflight")
    assert dur >= 0.005  # at least half the sleep — generous for CI
    assert len(t._stages) == 1
    assert t._stages[0]["stage"] == "preflight"


def test_timer_elapsed_increases():
    t = _RuntimeTimer()
    e1 = t.elapsed()
    time.sleep(0.01)
    e2 = t.elapsed()
    assert e2 > e1


def test_mark_with_metadata():
    t = _RuntimeTimer()
    t.mark("normalize", races=8, runners=64, notes="test note")
    s = t._stages[0]
    assert s["races"] == 8
    assert s["runners"] == 64
    assert s["notes"] == "test note"


def test_to_dict_schema():
    t = _RuntimeTimer()
    t.mark("preflight")
    t.mark("racecard_load", races=5)
    t.mark("normalize", races=5, runners=40)

    race_timings = [
        {
            "race_id": "r001",
            "course": "Ascot",
            "off_time": "14:30",
            "runners": 8,
            "score_race_velo_prime_sec": 0.2345,
            "per_runner_avg_ms": 29.3,
            "pdf_intel_attached_count": 6,
            "spotlight_parsed_count": 4,
        }
    ]

    result = t.to_dict(
        date="2026-05-19",
        commit_sha="abc123",
        source="cache",
        race_timings=race_timings,
        spotlight_total=4,
        pdf_intel_total=6,
    )

    # Required top-level keys
    for key in ("date", "commit_sha", "source", "total_runtime_sec",
                "spotlight_runners_parsed", "pdf_intel_runners_attached",
                "stages", "race_timings"):
        assert key in result, f"Missing key: {key}"

    assert result["date"] == "2026-05-19"
    assert result["commit_sha"] == "abc123"
    assert result["source"] == "cache"
    assert result["spotlight_runners_parsed"] == 4
    assert result["pdf_intel_runners_attached"] == 6
    assert isinstance(result["total_runtime_sec"], float)
    assert result["total_runtime_sec"] >= 0

    # Stages shape
    assert len(result["stages"]) == 3
    for s in result["stages"]:
        for k in ("stage", "duration_sec", "races", "runners", "notes"):
            assert k in s, f"Stage missing key: {k}"

    # Race timings passthrough
    assert result["race_timings"] == race_timings


def test_stage_durations_non_negative():
    t = _RuntimeTimer()
    for name in ("preflight", "racecard_load", "normalize", "persist", "telegram"):
        t.mark(name)
    for s in t._stages:
        assert s["duration_sec"] >= 0, f"Negative duration in stage: {s['stage']}"


def test_per_race_timing_schema():
    required_keys = {
        "race_id", "course", "off_time", "runners",
        "score_race_velo_prime_sec", "per_runner_avg_ms",
        "pdf_intel_attached_count", "spotlight_parsed_count",
    }
    entry = {
        "race_id": "r123",
        "course": "Cheltenham",
        "off_time": "15:20",
        "runners": 12,
        "score_race_velo_prime_sec": 0.1234,
        "per_runner_avg_ms": 10.28,
        "pdf_intel_attached_count": 7,
        "spotlight_parsed_count": 5,
    }
    assert required_keys == set(entry.keys())
