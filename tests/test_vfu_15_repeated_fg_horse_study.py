#!/usr/bin/env python3
"""
Tests for VFU-15: Repeated False-GREEN Horse Study.
Run with: source venv/bin/activate && python -m pytest tests/test_vfu_15_repeated_fg_horse_study.py -v
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_15_repeated_fg_horse_study import (
    build_horse_profiles,
    load_fg_cases,
    _horse_key,
    _severity_score,
    REPEAT_THRESHOLD,
    VFU15_VERSION,
)
import scripts.ops.vfu_15_repeated_fg_horse_study as _mod


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _case(
    horse_name="Test Horse",
    horse_id=None,
    race_id="race_001",
    race_date="2026-05-01",
    vp=0.45,
    outcome="MISS",
    is_miss=True,
    is_placed_not_won=False,
    pick_sp=4.0,
    failure_class="HIGH_VP_SHORT_PRICE_FAILURE",
    false_green_severity="HIGH",
    price_attribution_status="PRICED_SETTLED",
    course="Ascot",
) -> dict:
    return {
        "case_id": f"VFU13_FG_TEST_{race_id}",
        "horse_name": horse_name,
        "horse_id": horse_id,
        "race_date": race_date,
        "race_id": race_id,
        "course": course,
        "vp": vp,
        "outcome": outcome,
        "is_miss": is_miss,
        "is_placed_not_won": is_placed_not_won,
        "pick_sp": pick_sp,
        "failure_class": failure_class,
        "false_green_severity": false_green_severity,
        "price_attribution_status": price_attribution_status,
        "blocked_from_live_use": True,
        "human_approval_required": True,
    }


def _two_case_set() -> list[dict]:
    return [
        _case("Repeat Offender", race_id="race_001", race_date="2026-05-01"),
        _case("Repeat Offender", race_id="race_002", race_date="2026-05-15"),
        _case("One Time Failure", race_id="race_003", race_date="2026-05-10"),
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_01_repeater_identified():
    """Horse with 2 FG cases must appear in repeaters list."""
    repeaters, singles, _ = build_horse_profiles(_two_case_set())
    names = [p["horse_name"] for p in repeaters]
    assert "Repeat Offender" in names


def test_02_single_event_excluded_from_repeaters():
    """Horse with 1 FG case must be in singles, not repeaters."""
    repeaters, singles, _ = build_horse_profiles(_two_case_set())
    repeater_names = [p["horse_name"] for p in repeaters]
    assert "One Time Failure" not in repeater_names
    single_names = [p["horse_name"] for p in singles]
    assert "One Time Failure" in single_names


def test_03_repeater_profile_has_required_fields():
    """Each repeater profile must include all required fields."""
    required = [
        "horse_key", "horse_name", "fg_count", "repeater_class",
        "is_repeater", "vp_min", "vp_max", "sp_min", "outcome_counts",
        "top_failure_class", "failure_classes", "blocked_from_live_use",
        "human_review_required",
    ]
    repeaters, _, _ = build_horse_profiles(_two_case_set())
    assert repeaters
    for field in required:
        assert field in repeaters[0], f"Missing field: {field}"


def test_04_repeater_is_repeater_flag():
    """Repeater profile must have is_repeater=True."""
    repeaters, _, _ = build_horse_profiles(_two_case_set())
    assert all(p["is_repeater"] for p in repeaters)


def test_05_single_is_not_repeater():
    """Single-event profile must have is_repeater=False."""
    _, singles, _ = build_horse_profiles(_two_case_set())
    assert all(not p["is_repeater"] for p in singles)


def test_06_blocked_from_live_use_on_profiles():
    """All repeater profiles must have blocked_from_live_use=True."""
    repeaters, _, _ = build_horse_profiles(_two_case_set())
    for p in repeaters:
        assert p["blocked_from_live_use"] is True


def test_07_human_review_required_on_profiles():
    """All repeater profiles must have human_review_required=True."""
    repeaters, _, _ = build_horse_profiles(_two_case_set())
    for p in repeaters:
        assert p["human_review_required"] is True


def test_08_stats_totals_consistent():
    """Stats must sum correctly: repeaters + singles = total_unique_horses."""
    cases = _two_case_set()
    repeaters, singles, stats = build_horse_profiles(cases)
    assert stats["total_unique_horses"] == len(repeaters) + len(singles)


def test_09_horse_id_based_deduplication():
    """Horses with same horse_id are grouped even if names differ slightly."""
    cases = [
        _case("Test Horse", horse_id=99999, race_id="r1", race_date="2026-05-01"),
        _case("Test Horse (IRE)", horse_id=99999, race_id="r2", race_date="2026-05-10"),
    ]
    repeaters, _, _ = build_horse_profiles(cases)
    assert len(repeaters) == 1
    assert repeaters[0]["fg_count"] == 2


def test_10_name_fallback_when_no_horse_id():
    """Horses with horse_id=None are grouped by name."""
    cases = [
        _case("No ID Horse", horse_id=None, race_id="r1"),
        _case("No ID Horse", horse_id=None, race_id="r2"),
    ]
    repeaters, _, _ = build_horse_profiles(cases)
    assert any(p["horse_name"] == "No ID Horse" for p in repeaters)


def test_11_structural_repeater_class_for_3_plus():
    """Horse with 3+ FG cases gets STRUCTURAL_REPEATER class."""
    cases = [
        _case("Triple Fail", race_id=f"r{i}", race_date=f"2026-05-0{i+1}") for i in range(3)
    ]
    repeaters, _, _ = build_horse_profiles(cases)
    assert repeaters[0]["repeater_class"] == "STRUCTURAL_REPEATER"


def test_12_consistent_cause_repeater_for_matching_failure_class():
    """Horse with 2 FG cases sharing same failure_class gets CONSISTENT_CAUSE_REPEATER."""
    cases = [
        _case("Same Cause", race_id="r1", failure_class="HIGH_VP_SHORT_PRICE_FAILURE"),
        _case("Same Cause", race_id="r2", failure_class="HIGH_VP_SHORT_PRICE_FAILURE"),
    ]
    repeaters, _, _ = build_horse_profiles(cases)
    assert repeaters[0]["repeater_class"] == "CONSISTENT_CAUSE_REPEATER"


def test_13_no_supabase_in_module():
    """VFU-15 module must not import or call Supabase."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "create_client" not in src
    assert "from supabase" not in src
    assert "import supabase" not in src


def test_14_no_telegram_in_module():
    """VFU-15 module must not contain Telegram send logic."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "bot.send" not in src
    assert "telegram.Bot" not in src
    assert "sendMessage" not in src


def test_15_no_live_scoring_in_module():
    """VFU-15 must not invoke the live scoring pipeline."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "run_prime_today" not in src
    assert "SQPEEngine" not in src
    assert "VeloPrimeEnsemble" not in src


def test_16_vp_range_computed_correctly():
    """VP min/max computed from cases."""
    cases = [
        _case("VP Range Horse", race_id="r1", vp=0.41),
        _case("VP Range Horse", race_id="r2", vp=0.58),
    ]
    repeaters, _, _ = build_horse_profiles(cases)
    assert abs(repeaters[0]["vp_min"] - 0.41) < 0.001
    assert abs(repeaters[0]["vp_max"] - 0.58) < 0.001


def test_17_severity_scores_correct():
    """_severity_score returns expected values per label."""
    assert _severity_score({"false_green_severity": "LOW"}) == 1.0
    assert _severity_score({"false_green_severity": "MEDIUM"}) == 2.0
    assert _severity_score({"false_green_severity": "HIGH"}) == 3.0
    assert _severity_score({"false_green_severity": "CRITICAL"}) == 4.0


def test_18_repeaters_sorted_by_count_desc():
    """Repeater list must be ordered highest FG count first."""
    cases = (
        [_case("Two Timer", race_id=f"r{i}") for i in range(2)] +
        [_case("Three Timer", race_id=f"q{i}") for i in range(3)]
    )
    repeaters, _, _ = build_horse_profiles(cases)
    counts = [p["fg_count"] for p in repeaters]
    assert counts == sorted(counts, reverse=True)


def test_19_real_data_loads_and_finds_repeaters():
    """Load actual VFU-14 enriched cases; confirm stats output is valid."""
    cases = load_fg_cases()
    assert len(cases) > 100, "Expected 121 FG cases"
    repeaters, singles, stats = build_horse_profiles(cases)
    assert stats["total_fg_cases"] == len(cases)
    assert stats["total_unique_horses"] >= 1
    assert isinstance(stats["repeater_horses"], int)
    assert stats["repeater_horses"] + stats["single_event_horses"] == stats["total_unique_horses"]


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = sorted(
        [(k, v) for k, v in globals().items() if k.startswith("test_")],
        key=lambda x: x[0],
    )
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            failed += 1
    print(f"\n{passed + failed} tests  |  {passed} passed  |  {failed} failed")
    sys.exit(1 if failed else 0)
