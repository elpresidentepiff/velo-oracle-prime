"""
Tests for the racecard cache completeness gate.

Covers the four required scenarios:
  - 8-race bad cache must fail
  - 48-race corrected card must pass
  - date mismatch must fail
  - missing course must fail
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.velo.racecard_cache_gate import validate_racecard  # noqa: E402

DATE = "2026-05-26"

# ── Fixture helpers ────────────────────────────────────────────────────────────

def _runner(horse: str = "Test Horse", idx: int = 0) -> dict:
    return {
        "horse": horse,
        "horse_id": f"id_{idx}",
        "jockey": "J Rider",
        "jockey_id": f"j_{idx}",
        "trainer": "T Coach",
        "trainer_id": f"t_{idx}",
        "rp_rpr_archive_only": 95,
        "rp_rpr_velo_allowed": False,
    }


def _race(race_id: str, course: str, runners: int = 8, region: str = "GB") -> dict:
    return {
        "race_id": race_id,
        "course": course,
        "date": DATE,
        "region": region,
        "runners": [_runner(f"Horse {i}", i) for i in range(runners)],
    }


def _full_card() -> list[dict]:
    """48-race card matching today's real structure: 7 meetings."""
    meetings = [
        ("Leicester", 7),
        ("Redcar", 7),
        ("Bath", 6),
        ("Ballinrobe", 8),
        ("Dundalk (AW)", 7),
        ("Plumpton", 7),
        ("Lingfield", 6),
    ]
    races = []
    rid = 900000
    for course, n_races in meetings:
        region = "IRE" if course in ("Ballinrobe", "Dundalk (AW)") else "GB"
        for i in range(n_races):
            races.append(_race(str(rid), course, runners=8, region=region))
            rid += 1
    return races


def _bad_cache_card() -> list[dict]:
    """8-race card — the bad cache from 2026-05-26."""
    return [
        _race("918928", "Leicester"),
        _race("918943", "Redcar"),
        _race("918942", "Redcar"),
        _race("918944", "Redcar"),
        _race("918941", "Redcar"),
        _race("918947", "Redcar"),
        _race("918946", "Redcar"),
        _race("918945", "Redcar"),
    ]


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_bad_cache_fails(tmp_path):
    """8-race bad cache must be blocked — race_count and course_coverage fail."""
    result = validate_racecard(_bad_cache_card(), DATE, racecard_source="cache")
    assert not result.passed, "Expected gate to BLOCK an 8-race card"

    failed_names = {c.name for c in result.failed_blocking()}
    assert "race_count" in failed_names, "race_count check must fire on 8-race card"


def test_full_card_passes(tmp_path):
    """48-race corrected card must pass all blocking checks."""
    result = validate_racecard(_full_card(), DATE, racecard_source="rp_merged")
    failed = result.failed_blocking()
    assert result.passed, (
        f"Expected full card to PASS. Failing checks: {[c.name + ': ' + c.message for c in failed]}"
    )


def test_date_mismatch_fails():
    """A card loaded for the wrong date must be blocked."""
    wrong_date_races = [
        {**_race("r1", "Ascot"), "date": "2026-05-20"},
        {**_race("r2", "Newbury"), "date": "2026-05-20"},
        {**_race("r3", "Sandown"), "date": "2026-05-20"},
    ] * 6  # 18 races — passes count check but wrong date
    result = validate_racecard(wrong_date_races, DATE, racecard_source="cache")
    assert not result.passed, "Expected gate to BLOCK a date-mismatched card"

    failed_names = {c.name for c in result.failed_blocking()}
    assert "date_match" in failed_names, "date_match check must fire on wrong-date card"


def test_missing_course_fails():
    """A card with too few unique courses (only 1 meeting) must be blocked."""
    single_course = [_race(f"r{i}", "Ascot") for i in range(20)]
    result = validate_racecard(single_course, DATE, racecard_source="cache")
    assert not result.passed, "Expected gate to BLOCK a single-course card"

    failed_names = {c.name for c in result.failed_blocking()}
    assert "course_coverage" in failed_names, "course_coverage check must fire on single-course card"


def test_rpr_live_leak_fails():
    """A card where runners expose bare 'rpr' field must be blocked."""
    races = _full_card()
    # Inject a live RPR leak into the first runner of the first race
    races[0]["runners"][0]["rpr"] = 105
    result = validate_racecard(races, DATE, racecard_source="api")
    assert not result.passed
    failed_names = {c.name for c in result.failed_blocking()}
    assert "rpr_live_leak" in failed_names


def test_low_runner_count_fails():
    """A card with suspiciously low total runners must be blocked."""
    thin_races = [_race(f"r{i}", f"Course{i}", runners=2) for i in range(20)]
    # 20 races * 2 runners = 40 total < MIN_RUNNERS_TOTAL (80)
    result = validate_racecard(thin_races, DATE, racecard_source="cache")
    assert not result.passed
    failed_names = {c.name for c in result.failed_blocking()}
    assert "runner_count" in failed_names


def test_checks_present_in_result():
    """Gate result always contains all seven check names."""
    expected = {
        "date_match", "race_count", "course_coverage", "runner_count",
        "metadata_coverage", "rpr_live_leak", "sidecar_date_match",
    }
    result = validate_racecard(_full_card(), DATE)
    found = {c.name for c in result.checks}
    assert found == expected, f"Missing checks: {expected - found}"


def test_sidecar_check_is_non_blocking():
    """sidecar_date_match is a soft warn-only check and must never block alone."""
    result = validate_racecard(_full_card(), DATE)
    sidecar = next(c for c in result.checks if c.name == "sidecar_date_match")
    assert not sidecar.blocking, "sidecar_date_match must be warn-only"
