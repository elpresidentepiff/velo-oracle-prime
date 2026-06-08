"""Tests for Horse Passport V1 builder."""
from datetime import date
from new_build_velo.horse_passport import HorsePassportBuilder, TRUST_POLICY, VELO_SCORING_ALLOWED


def _make_run(race_date, position, field_size, sp_raw, jockey="J Doe", course="Newmarket", beaten_margin=None, or_rating=None):
    return {
        "horse_name": "Test Horse",
        "horse_rp_uid": 12345,
        "race_date": race_date,
        "position": position,
        "field_size": field_size,
        "sp_raw": sp_raw,
        "jockey_name": jockey,
        "course_name": course,
        "beaten_margin": beaten_margin,
        "or_rating": or_rating,
        "distance": "6f",
        "going": "Good",
    }


SAMPLE_RUNS = [
    _make_run("2026-05-01", 6, 12, "9/2", beaten_margin=4.0, or_rating=80),
    _make_run("2026-04-15", 2, 10, "5/2", beaten_margin=1.0, or_rating=79),
    _make_run("2026-03-20", 1, 8,  "2/1", beaten_margin=0.0, or_rating=77),
    _make_run("2026-02-10", 5, 11, "4/1", beaten_margin=6.0, or_rating=75),
]


def test_passport_builds_from_minimal_runs():
    p = HorsePassportBuilder().build(SAMPLE_RUNS)
    assert p.horse_name == "Test Horse"
    assert p.horse_rp_uid == 12345
    assert p.career_runs == 4
    assert p.wins == 1
    assert p.places == 2


def test_layoff_flag_active():
    # last run 2026-05-01 vs AS_OF_DATE 2026-05-25 = 24 days → ACTIVE
    p = HorsePassportBuilder().build(SAMPLE_RUNS)
    assert p.layoff_flag == "ACTIVE"
    assert p.days_since_last_run == 24


def test_layoff_flag_fresh_90():
    runs = [_make_run("2025-10-01", 1, 8, "2/1")]
    p = HorsePassportBuilder().build(runs)
    assert p.layoff_flag in ("FRESH_90", "FRESH_180")


def test_sp_trajectory_shortening():
    # Recent SPs 2.5, 3.0 — older 6.0, 7.0, 8.0 → SHORTENING
    runs = [
        _make_run("2026-05-01", 1, 8, "3/2"),   # sp=2.5
        _make_run("2026-04-01", 2, 9, "2/1"),   # sp=3.0
        _make_run("2026-03-01", 3, 10, "5/1"),  # sp=6.0
        _make_run("2026-02-01", 4, 11, "6/1"),  # sp=7.0
        _make_run("2026-01-01", 5, 12, "7/1"),  # sp=8.0
    ]
    p = HorsePassportBuilder().build(runs)
    assert p.sp_trajectory == "SHORTENING"


def test_cash_run_candidate():
    # Last run: SP=2/1 (3.0 dec), finished 7th in 10 → past top half
    runs = [
        _make_run("2026-05-01", 7, 10, "2/1"),
        _make_run("2026-04-01", 1, 8,  "4/1"),
    ]
    p = HorsePassportBuilder().build(runs)
    assert p.cash_run_candidate is True


def test_cash_run_candidate_false_when_placed():
    # Last run: SP=2/1 (3.0), finished 2nd → NOT past top half
    runs = [_make_run("2026-05-01", 2, 10, "2/1")]
    p = HorsePassportBuilder().build(runs)
    assert p.cash_run_candidate is False


def test_velo_scoring_allowed_always_false():
    p = HorsePassportBuilder().build(SAMPLE_RUNS)
    assert p.velo_scoring_allowed is False


def test_trust_policy_always_archive():
    p = HorsePassportBuilder().build(SAMPLE_RUNS)
    assert p.trust_policy == TRUST_POLICY == "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"


def test_or_trajectory_rising():
    runs = [
        _make_run("2026-05-01", 1, 8, "2/1", or_rating=90),
        _make_run("2026-04-01", 2, 9, "3/1", or_rating=85),
        _make_run("2026-03-01", 1, 7, "4/1", or_rating=82),
    ]
    p = HorsePassportBuilder().build(runs)
    assert p.or_trajectory == "RISING"
    assert p.or_change_last3 == 8
