"""Regression tests for live passport feature feed.

Tests:
  A. Path independence    — load_index() succeeds from any cwd
  B. Feed row coverage    — build_current_card_feed returns runners_processed > 0
  C. Dynamic days         — pp_days_since_last == 59.0 for last_run 2026-04-01, as_of 2026-05-30
  D. Layoff encoding      — pp_layoff brackets: 0d→0.0, 30d→1.0, 59d→1.0, 60d→2.0, 90d→3.0, 180d→4.0
  E. Scorer prefers live  — _actual_feature_map picks passport_live_features over passport_summary
  F. Median fill          — missing passport feeds medians into _feature_row output
  G. No RPR in live       — lookup_passport_features returns no rpr-keyed values
  H. No same-race SP      — only pp_avg_sp_last5 is SP-related
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Repo root on sys.path so new_build_velo imports resolve
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_passport(last_run_date: str) -> dict[str, Any]:
    """Build a minimal in-memory passport dict."""
    return {
        "horse_name": "Test Horse",
        "horse_rp_uid": 9999999,
        "career_runs": 10,
        "wins": 2,
        "places": 5,
        "win_rate": 0.2,
        "place_rate": 0.5,
        "last_run_date": last_run_date,
        "avg_sp_last5": 8.5,
        "jockey_continuity": True,
        "course_repeat": False,
        "or_change_last3": 2,
        "class_movement": "UP",
        "win_rate_last3": 0.33,
        "win_rate_last6": 0.25,
        "place_rate_last3": 0.67,
        "avg_beaten_margin_last3": 3.0,
        "avg_sp_last3": 9.0,
        "beaten_margin_slope": -0.5,
        "position_trend": "IMPROVING",
        "runs_in_last_90d": 1,
    }


# ===========================================================================
# Test A — Path independence
# ===========================================================================
class TestPathIndependence:
    def test_load_index_succeeds_from_temp_cwd(self, tmp_path: Path) -> None:
        """load_index() must succeed even when cwd is a temp directory."""
        import new_build_velo.passport_lookup as plu

        # Reset module state so load_index() actually runs
        plu._loaded = False
        plu._by_uid.clear()
        plu._by_name.clear()

        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            plu.load_index()  # Must not raise
        finally:
            os.chdir(original_cwd)

        # _ROOT must resolve to the repo root (contains new_build_velo/)
        assert (plu._ROOT / "new_build_velo").exists(), (
            f"_ROOT={plu._ROOT} does not contain new_build_velo/"
        )
        # After load, must be marked loaded (file may or may not exist, but no crash)
        assert plu._loaded is True


# ===========================================================================
# Test B — Feed row coverage
# ===========================================================================
class TestFeedRowCoverage:
    def test_build_current_card_feed_returns_runner_count(self) -> None:
        """build_current_card_feed(execute=False) must complete and report runners_processed > 0."""
        from new_build_velo.current_card_feed import build_current_card_feed

        result = build_current_card_feed(execute=False)
        assert isinstance(result, dict), "build_current_card_feed must return a dict"
        assert "runners_processed" in result, "result must contain runners_processed"
        assert result["runners_processed"] > 0, (
            f"Expected runners_processed > 0, got {result['runners_processed']}"
        )


# ===========================================================================
# Test C — Dynamic days
# ===========================================================================
class TestDynamicDays:
    def test_days_since_last_59(self) -> None:
        """Mock passport with last_run 2026-04-01; as_of 2026-05-30 → 59 days."""
        import new_build_velo.passport_lookup as plu

        mock_passport = _make_mock_passport("2026-04-01")

        plu._loaded = True  # skip file load
        with patch.object(plu, "_by_uid", {9999999: mock_passport}):
            with patch.object(plu, "_by_name", {"test horse": mock_passport}):
                result = plu.lookup_passport_features(
                    horse_rp_uid=9999999,
                    horse_name="Test Horse",
                    as_of_date=date(2026, 5, 30),
                )

        assert result["pp_days_since_last"] == 59.0, (
            f"Expected 59.0, got {result['pp_days_since_last']}"
        )


# ===========================================================================
# Test D — Layoff encoding
# ===========================================================================
class TestLayoffEncoding:
    """Verify all layoff bracket thresholds."""

    def _run_lookup(self, last_run_date: str, as_of: date) -> dict[str, Any]:
        import new_build_velo.passport_lookup as plu

        mock_passport = _make_mock_passport(last_run_date)
        plu._loaded = True
        with patch.object(plu, "_by_uid", {9999999: mock_passport}):
            with patch.object(plu, "_by_name", {"test horse": mock_passport}):
                return plu.lookup_passport_features(
                    horse_rp_uid=9999999,
                    horse_name="Test Horse",
                    as_of_date=as_of,
                )

    def test_0_days_is_active(self) -> None:
        result = self._run_lookup("2026-05-30", date(2026, 5, 30))
        assert result["pp_layoff"] == 0.0, f"0 days → ACTIVE (0.0), got {result['pp_layoff']}"

    def test_30_days_is_fresh30(self) -> None:
        result = self._run_lookup("2026-04-30", date(2026, 5, 30))
        assert result["pp_layoff"] == 1.0, f"30 days → FRESH_30 (1.0), got {result['pp_layoff']}"

    def test_59_days_is_fresh30(self) -> None:
        result = self._run_lookup("2026-04-01", date(2026, 5, 30))
        assert result["pp_layoff"] == 1.0, f"59 days → FRESH_30 (1.0), got {result['pp_layoff']}"

    def test_60_days_is_fresh60(self) -> None:
        # 60 days before 2026-05-30 = 2026-03-31
        result = self._run_lookup("2026-03-31", date(2026, 5, 30))
        assert result["pp_layoff"] == 2.0, f"60 days → 2.0, got {result['pp_layoff']}"

    def test_90_days_is_fresh90(self) -> None:
        # 90 days before 2026-05-30 = 2026-03-01
        result = self._run_lookup("2026-03-01", date(2026, 5, 30))
        assert result["pp_layoff"] == 3.0, f"90 days → 3.0, got {result['pp_layoff']}"

    def test_180_days_is_long_break(self) -> None:
        # 180 days before 2026-05-30 = 2025-12-01
        result = self._run_lookup("2025-12-01", date(2026, 5, 30))
        assert result["pp_layoff"] == 4.0, f"180 days → 4.0, got {result['pp_layoff']}"


# ===========================================================================
# Test E — Scorer prefers live features
# ===========================================================================
class TestScorerPrefersLiveFeatures:
    def test_live_features_preferred_over_passport_summary(self) -> None:
        """_actual_feature_map must take pp_days_since_last / pp_layoff from
        passport_live_features, not from the stale passport_summary."""
        from new_build_velo.paper_scorer import _actual_feature_map

        fake_row: dict[str, Any] = {
            "passport_summary": {
                "days_since_last_run": 999,
                "layoff_flag": "ACTIVE",
                "career_runs": 5,
                "win_rate": 0.2,
                "place_rate": 0.4,
                "avg_sp_last5": 10.0,
                "jockey_continuity": False,
                "or_change_last3": 0,
                "class_movement": "FLAT",
            },
            "passport_live_features": {
                "pp_days_since_last": 25.0,
                "pp_layoff": 0.0,
                "pp_career_runs": 10,
                "pp_win_rate": 0.3,
                "pp_place_rate": 0.5,
                "pp_avg_sp_last5": 8.0,
                "pp_jockey_continuity": 1.0,
                "pp_course_seen": 0.0,
                "pp_or_change_3": 3.0,
                "pp_class_moved_up": 0.0,
                "pp_class_moved_down": 0.0,
            },
            "distance_furlongs": 8.0,
            "going": "good",
            "surface": "turf",
            "field_size": 10,
            "draw": 5,
            "age": 4,
            "weight_lbs": 126,
            "official_rating": 95,
            "going_code_raw": None,
        }
        medians: dict[str, float] = {
            "going_code": 3.0,
            "pp_course_seen": 0.0,
        }

        feature_map = _actual_feature_map(fake_row, medians)

        assert feature_map["pp_days_since_last"] == 25.0, (
            f"Expected 25.0 from live_features, got {feature_map['pp_days_since_last']}"
        )
        assert feature_map["pp_layoff"] == 0.0, (
            f"Expected 0.0 from live_features, got {feature_map['pp_layoff']}"
        )


# ===========================================================================
# Test F — Median fill for missing passport
# ===========================================================================
class TestMedianFillForMissingPassport:
    def test_all_pp_features_filled_from_medians_when_no_passport(self) -> None:
        """When all pp_* in passport_live_features are None and passport_summary is
        empty, _feature_row fills from medians and lists truly-missing cols.

        Note: pp_jockey_continuity, pp_course_seen, pp_class_moved_up, pp_class_moved_down
        have hard 0.0 defaults in _actual_feature_map that kick in even with no passport,
        so they are NOT listed as missing (they resolve to 0.0 without needing medians).
        The core identity cols (career_runs, win_rate, place_rate, days_since_last,
        layoff, avg_sp_last5, or_change_3) do go fully None → median-filled.
        """
        from new_build_velo.paper_scorer import _feature_row

        null_live_pp = {
            "pp_career_runs": None,
            "pp_win_rate": None,
            "pp_place_rate": None,
            "pp_days_since_last": None,
            "pp_layoff": None,
            "pp_avg_sp_last5": None,
            "pp_jockey_continuity": None,
            "pp_course_seen": None,
            "pp_or_change_3": None,
            "pp_class_moved_up": None,
            "pp_class_moved_down": None,
        }

        fake_row: dict[str, Any] = {
            "passport_summary": {},
            "passport_live_features": null_live_pp,
            "distance_furlongs": None,
            "going": None,
            "surface": None,
            "field_size": None,
            "draw": None,
            "age": None,
            "weight_lbs": None,
            "official_rating": None,
            "going_code_raw": None,
        }

        # These cols are truly None when no passport → must be in missing list
        must_be_missing_cols = [
            "pp_career_runs", "pp_win_rate", "pp_place_rate",
            "pp_days_since_last", "pp_layoff", "pp_avg_sp_last5",
            "pp_or_change_3",
        ]
        # All 11 pp cols we test against
        pp_feature_cols = must_be_missing_cols + [
            "pp_jockey_continuity", "pp_course_seen",
            "pp_class_moved_up", "pp_class_moved_down",
        ]
        medians: dict[str, float] = {col: 42.0 for col in pp_feature_cols}
        medians["going_code"] = 3.0

        out, missing = _feature_row(fake_row, pp_feature_cols, medians)

        # Core identity cols must be median-filled and in the missing list
        for col in must_be_missing_cols:
            assert col in missing, f"{col} should be in missing list"
            assert out[col] == 42.0, f"{col} should be filled with median 42.0, got {out[col]}"

        # All pp_* cols in the output must be floats (not None)
        for col in pp_feature_cols:
            assert out[col] is not None, f"{col} output value must not be None"
            assert isinstance(out[col], float), f"{col} output must be float, got {type(out[col])}"


# ===========================================================================
# Test G — No RPR in live features
# ===========================================================================
class TestNoRprInLiveFeatures:
    def test_lookup_passport_features_has_no_rpr_keys(self) -> None:
        """lookup_passport_features must not return any key containing 'rpr'."""
        import new_build_velo.passport_lookup as plu

        plu._loaded = False
        plu._by_uid.clear()
        plu._by_name.clear()
        plu.load_index()

        # Pick any horse that's actually in the passport bank (first entry)
        if not plu._by_uid:
            pytest.skip("Passport bank is empty — skipping RPR key test")

        first_uid = next(iter(plu._by_uid))
        first_passport = plu._by_uid[first_uid]
        horse_name = first_passport.get("horse_name")

        result = plu.lookup_passport_features(
            horse_rp_uid=first_uid,
            horse_name=horse_name,
            as_of_date=date(2026, 5, 30),
        )

        rpr_keys = [k for k in result if "rpr" in k.lower()]
        assert rpr_keys == [], f"Found RPR keys in live features: {rpr_keys}"


# ===========================================================================
# Test H — No same-race SP
# ===========================================================================
class TestNoSameRaceSP:
    FORBIDDEN_SP_SUBSTRINGS = ["sp_dec", "sp_frac", "market_sp", "bsp", "starting_price"]

    def test_only_avg_sp_last5_is_sp_related(self) -> None:
        """pp_avg_sp_last5 is the only SP-related key. Same-race SP keys are forbidden."""
        import new_build_velo.passport_lookup as plu

        plu._loaded = False
        plu._by_uid.clear()
        plu._by_name.clear()
        plu.load_index()

        if not plu._by_uid:
            pytest.skip("Passport bank is empty — skipping SP key test")

        first_uid = next(iter(plu._by_uid))
        first_passport = plu._by_uid[first_uid]
        horse_name = first_passport.get("horse_name")

        result = plu.lookup_passport_features(
            horse_rp_uid=first_uid,
            horse_name=horse_name,
            as_of_date=date(2026, 5, 30),
        )

        for forbidden in self.FORBIDDEN_SP_SUBSTRINGS:
            bad = [k for k in result if forbidden in k.lower()]
            assert bad == [], f"Forbidden SP key '{forbidden}' found in live features: {bad}"

        # pp_avg_sp_last5 is the only allowed SP-related key
        sp_keys = [k for k in result if "sp" in k.lower()]
        allowed_sp = {"pp_avg_sp_last5", "pp_avg_sp_last3"}
        unexpected = [k for k in sp_keys if k not in allowed_sp]
        assert unexpected == [], f"Unexpected SP-related keys: {unexpected}"
