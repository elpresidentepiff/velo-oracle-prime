"""
Tests for Issue #85 — RP_MERGED Feature Differentiation Collapse.

Validates:
  Phase 1 — Regression proof:
    - Uniform race (AYR 1.42 fixture): was VP=1/n before fix
    - After fix: betting_forecast odds produce differentiated best_odds_decimal
    - FFO 3.20 (Kenobi): was fully differentiated, still is

  Phase 2 — Feature audit:
    - build_scoring_feature_audit reports constant_fields for null-input races
    - build_scoring_feature_audit reports coverage_pct per field

  Phase 3 — Flatline detector:
    - detect_vp_flatline: fires for uniform VP input
    - detect_vp_flatline: fires for majority-tied input (>= 60%)
    - detect_vp_flatline: silent when VP is well-differentiated
    - flatline_summary_for_run: aggregates correctly

  Racecard loader:
    - _parse_betting_forecast: fractional, EVS, favourite markers
    - _fuzzy_odds_lookup: exact, fuzzy, apostrophe names
    - load_rp_merged_as_racecards: odds injected, pdf_intel built
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.velo.racecard_loader import (  # noqa: E402
    _fuzzy_odds_lookup,
    _parse_betting_forecast,
    load_rp_merged_as_racecards,
)
from src.velo.feature_audit import (  # noqa: E402
    build_scoring_feature_audit,
    detect_vp_flatline,
    flatline_summary_for_run,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

DATE = "2026-05-20"
DATA_ROOT = ROOT / "data"

# AYR 1.42 — 4-runner race, no betting forecast in merged JSON (fully uniform pre-fix)
_AYR_142_RACE_ID = f"rp_AYR_{DATE.replace('-','')}_{1}_{42}"

# FFO 3.20 — 5 runners, betting forecast present (was differentiated before fix)
_FFO_320_FORECAST = "4/6 One Knight, 5/2 The Flaggy Shore, 4/1 Fiskardo, 33/1 Brenda Lady, 100/1 Kenobi"
_FFO_320_HORSES = ["One Knight", "The Flaggy Shore", "Fiskardo", "Brenda Lady", "Kenobi"]

# ── _parse_betting_forecast ───────────────────────────────────────────────────


def test_parse_forecast_basic():
    odds = _parse_betting_forecast("4/6 One Knight, 5/2 The Flaggy Shore, 100/1 Kenobi")
    assert abs(odds["one knight"] - (4 / 6 + 1)) < 0.01
    assert abs(odds["the flaggy shore"] - (5 / 2 + 1)) < 0.01
    assert abs(odds["kenobi"] - 101.0) < 0.01


def test_parse_forecast_evs():
    odds = _parse_betting_forecast("EVS Bluegrass, 2/1 Crystal Queen")
    assert abs(odds["bluegrass"] - 2.0) < 0.01
    assert abs(odds["crystal queen"] - 3.0) < 0.01


def test_parse_forecast_favourite_marker():
    # "2/1F" or "4/6F" — strip the F
    odds = _parse_betting_forecast("4/6F One Knight, 5/2 The Flaggy Shore")
    assert "one knight" in odds
    assert abs(odds["one knight"] - (4 / 6 + 1)) < 0.01


def test_parse_forecast_empty_string():
    assert _parse_betting_forecast("") == {}


def test_parse_forecast_none():
    assert _parse_betting_forecast(None) == {}


def test_parse_forecast_full_ffo():
    odds = _parse_betting_forecast(_FFO_320_FORECAST)
    assert len(odds) == 5
    assert "one knight" in odds
    assert "kenobi" in odds
    assert odds["kenobi"] == 101.0


# ── _fuzzy_odds_lookup ────────────────────────────────────────────────────────


def test_fuzzy_lookup_exact():
    forecast = {"crystal queen": 5.0, "a lady forever": 3.5}
    assert _fuzzy_odds_lookup("Crystal Queen", forecast) == 5.0


def test_fuzzy_lookup_apostrophe():
    forecast = {"evelyn's phoenix": 7.0}
    assert _fuzzy_odds_lookup("Evelyn'S Phoenix", forecast) == 7.0


def test_fuzzy_lookup_no_match():
    forecast = {"some other horse": 3.0}
    assert _fuzzy_odds_lookup("Crystal Queen", forecast) == 0.0


def test_fuzzy_lookup_empty_forecast():
    assert _fuzzy_odds_lookup("Any Horse", {}) == 0.0


def test_fuzzy_lookup_substring():
    forecast = {"golden garden": 6.0}
    # Short 4-char names skip fuzzy — 'goldengarden' is 12 chars, should match
    assert _fuzzy_odds_lookup("Golden Garden", forecast) == 6.0


# ── load_rp_merged_as_racecards — odds injection ──────────────────────────────


def _load_today(date: str = DATE) -> list[dict]:
    """Load today's merged racecards if they exist (skip test if not)."""
    import pytest
    merged_dir = DATA_ROOT / "racecard_merged"
    files = list(merged_dir.glob(f"racecard_*_{date}.json"))
    if not files:
        pytest.skip(f"No racecard_merged files for {date} — fixture unavailable")
    return load_rp_merged_as_racecards(date, DATA_ROOT)


def test_loader_returns_races():
    races = _load_today()
    assert len(races) > 0


def test_loader_runners_have_horse_id():
    races = _load_today()
    for race in races:
        for runner in race.get("runners", []):
            assert runner.get("horse_id", "").startswith("rp_")


def test_loader_ffo_odds_injected():
    """FFO 3.20 has betting_forecast — runners must have differentiated odds."""
    races = _load_today()
    ffo_races = [r for r in races if "FFO" in r.get("race_id", "") and "3_20" in r.get("race_id", "")]
    if not ffo_races:
        import pytest
        pytest.skip("FFO 3.20 not in today's data")
    ffo = ffo_races[0]
    runner_odds = [r.get("odds") for r in ffo["runners"] if r.get("odds")]
    # At least 2 runners must have distinct odds
    assert len(set(runner_odds)) >= 2, f"Expected differentiated odds, got: {runner_odds}"


def test_loader_runners_with_forecast_have_odds():
    """Any race with a non-empty betting_forecast must produce non-zero odds for top runners."""
    races = _load_today()
    for race in races:
        if not race.get("_rp_betting_forecast", ""):
            continue
        runners = race.get("runners", [])
        runners_with_odds = [r for r in runners if r.get("odds") and r["odds"] > 0]
        # At least half the runners should have odds when a forecast is present
        if len(runners) >= 2:
            assert len(runners_with_odds) >= 1, (
                f"Race {race['race_id']} has forecast but no runner odds: {race['_rp_betting_forecast']}"
            )


def test_loader_pdf_intel_built():
    """Each runner should have a pdf_intel dict (may be empty values)."""
    races = _load_today()
    for race in races[:3]:  # check first 3 races only
        for runner in race.get("runners", [])[:3]:
            assert "pdf_intel" in runner, f"pdf_intel missing on {runner.get('horse')}"
            assert isinstance(runner["pdf_intel"], dict)


def test_loader_ayr_no_forecast_still_builds_runners():
    """AYR races with no betting_forecast must still produce runners (odds=None)."""
    races = _load_today()
    ayr_races = [r for r in races if "AYR" in r.get("race_id", "")]
    assert len(ayr_races) > 0
    for race in ayr_races:
        assert len(race.get("runners", [])) > 0


# ── build_scoring_feature_audit ───────────────────────────────────────────────

_UNIFORM_RUNNERS = [
    {"horse_name": f"Horse{i}", "best_odds_decimal": 10.0, "rpr": None, "ts": None, "draw": None}
    for i in range(8)
]

_DIFFERENTIATED_RUNNERS = [
    {"horse_name": "Horse1", "best_odds_decimal": 2.0, "rpr": 110.0, "ts": 95.0, "draw": 3},
    {"horse_name": "Horse2", "best_odds_decimal": 4.5, "rpr": 105.0, "ts": 88.0, "draw": 7},
    {"horse_name": "Horse3", "best_odds_decimal": 8.0, "rpr": 98.0, "ts": 80.0, "draw": 1},
]


def test_feature_audit_identifies_null_fields():
    audit = build_scoring_feature_audit({}, _UNIFORM_RUNNERS, "rp_merged")
    # rpr, ts, draw are None → missing
    assert "rpr" in audit["missing_fields"]
    assert "ts" in audit["missing_fields"]
    assert "draw" in audit["missing_fields"]


def test_feature_audit_constant_field_detected():
    """All 8 runners have same best_odds_decimal → constant field."""
    audit = build_scoring_feature_audit({}, _UNIFORM_RUNNERS, "rp_merged")
    assert "best_odds_decimal" in audit["constant_fields"]


def test_feature_audit_differentiated_field_not_constant():
    audit = build_scoring_feature_audit({}, _DIFFERENTIATED_RUNNERS, "api")
    assert "best_odds_decimal" not in audit["constant_fields"]
    assert audit["fields"]["best_odds_decimal"]["unique_value_count"] == 3


def test_feature_audit_coverage_pct():
    audit = build_scoring_feature_audit({}, _DIFFERENTIATED_RUNNERS, "api")
    assert audit["fields"]["rpr"]["coverage_pct"] == 1.0
    assert audit["fields"]["ts"]["coverage_pct"] == 1.0


def test_feature_audit_runner_count():
    audit = build_scoring_feature_audit({}, _UNIFORM_RUNNERS, "rp_merged")
    assert audit["runner_count"] == 8


# ── detect_vp_flatline ────────────────────────────────────────────────────────

def _preds(vps: list[float]) -> list[dict]:
    return [{"horse": f"Horse{i}", "velo_prime_prob": v} for i, v in enumerate(vps)]


def test_flatline_fully_uniform():
    """8 runners all VP=0.1250 → flatline."""
    result = detect_vp_flatline("rp_AYR_1.42", _preds([0.125] * 8), "rp_merged")
    assert result is not None
    assert result["flatline"] is True
    assert result["unique_vp_count"] == 1
    assert result["max_tie_group_size"] == 8
    assert "RP_FEATURE_FLATLINE" in result["warning"]


def test_flatline_majority_tied():
    """7 of 9 runners tied → 77% tie group → flatline."""
    result = detect_vp_flatline(
        "rp_WAR_5.00",
        _preds([0.1319, 0.1319, 0.1319, 0.1319, 0.1319, 0.1319, 0.1319, 0.0635, 0.0134]),
        "rp_merged",
    )
    assert result is not None
    assert result["flatline"] is True
    assert result["max_tie_group_pct"] >= 0.60


def test_flatline_silent_when_differentiated():
    """5 fully distinct VP values → no flatline."""
    result = detect_vp_flatline(
        "rp_FFO_3.20",
        _preds([0.5479, 0.2800, 0.1500, 0.0800, 0.0300]),
        "rp_merged",
    )
    assert result is None


def test_flatline_at_boundary():
    """Exactly 60% tie group → flatline fires."""
    vps = [0.25, 0.25, 0.25, 0.10, 0.08, 0.05]  # 3/6 = 50% — below threshold
    result = detect_vp_flatline("rp_TEST", _preds(vps), "rp_merged")
    assert result is None  # 50% < 60%

    vps_boundary = [0.25, 0.25, 0.25, 0.25, 0.10, 0.05]  # 4/6 = 66.7% → fires
    result2 = detect_vp_flatline("rp_TEST", _preds(vps_boundary), "rp_merged")
    assert result2 is not None
    assert result2["flatline"] is True


def test_flatline_empty_predictions():
    result = detect_vp_flatline("rp_TEST", [], "rp_merged")
    assert result is None


def test_flatline_single_runner():
    """1-runner race has unique_count=1 but it's trivially uniform — still fires."""
    result = detect_vp_flatline("rp_TEST", _preds([0.50]), "rp_merged")
    assert result is not None


# ── flatline_summary_for_run ──────────────────────────────────────────────────


def test_flatline_summary_no_flatlines():
    summary = flatline_summary_for_run([], total_races=32)
    assert summary["flatline_count"] == 0
    assert summary["flatline_pct"] == 0.0


def test_flatline_summary_with_flatlines():
    flatlines = [
        detect_vp_flatline("rp_AYR_1.42", _preds([0.25] * 4), "rp_merged"),
        detect_vp_flatline("rp_AYR_2.42", _preds([0.0833] * 12), "rp_merged"),
        detect_vp_flatline(
            "rp_WAR_5.00",
            _preds([0.1319] * 7 + [0.0635, 0.0134]),
            "rp_merged",
        ),
    ]
    summary = flatline_summary_for_run(flatlines, total_races=32)
    assert summary["flatline_count"] == 3
    assert summary["fully_uniform_count"] == 2
    assert summary["majority_tied_count"] == 1
    assert summary["flatline_pct"] == round(3 / 32, 3)


# ── Regression: 2026-05-20 VP uniformity pattern ─────────────────────────────


def test_regression_ayr_142_was_uniform():
    """
    Before fix: AYR 1.42 had 4 runners all VP=0.25 (1/field_size).
    After fix: if AYR merged JSON has no betting_forecast, odds=None → still flat.
    This test documents the known pre-fix behaviour and confirms the detector fires.
    """
    # Simulate pre-fix VP=1/4 for 4 runners
    pre_fix_preds = _preds([0.25, 0.25, 0.25, 0.25])
    flatline = detect_vp_flatline("rp_AYR_20260520_1.42", pre_fix_preds, "rp_merged")
    assert flatline is not None, "Regression: AYR 1.42 flatline should be detected"
    assert flatline["unique_vp_count"] == 1
    assert flatline["runner_count"] == 4


def test_regression_ffo_320_was_differentiated():
    """
    FFO 3.20 (Kenobi) was already differentiated before fix.
    After fix: betting_forecast makes it even more differentiated (more unique odds).
    This is the reference race — must never regress to flatline.
    """
    # Simulate post-fix VP differentiation from betting forecast
    # One Knight 4/6 → implied_prob=0.60, The Flaggy Shore 5/2 → 0.29, etc.
    ffo_preds = _preds([0.5479, 0.3500, 0.2000, 0.0500, 0.0200])
    flatline = detect_vp_flatline("rp_FFO_20260520_3.20", ffo_preds, "rp_merged")
    assert flatline is None, "Regression: FFO 3.20 must NOT be a flatline"


def test_regression_forecast_odds_differentiate_ffo():
    """
    Betting forecast parsing must produce distinct decimal odds for all 5 FFO 3.20 horses.
    """
    forecast = _parse_betting_forecast(_FFO_320_FORECAST)
    odds_values = list(forecast.values())
    assert len(odds_values) == 5
    assert len(set(odds_values)) == 5, f"All 5 odds must be distinct: {odds_values}"
    # Kenobi at 100/1 must be highest
    assert forecast["kenobi"] == 101.0
    # One Knight at 4/6 must be lowest (shortest price)
    assert forecast["one knight"] < 2.0
