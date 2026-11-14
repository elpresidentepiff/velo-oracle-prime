"""E3: missing history inputs are 0.0 (matches training fillna(0)), not Racing-API placeholders.
E4: a runner with no price is distinguishable from a priced runner (no silent 10/1)."""
from app.services.sqpe_v17_service import (
    EXPECTED_FEATURES,
    LIVE_MISSING_HISTORY_VALUE,
    _resolve_decimal_odds,
    _resolve_decimal_odds_or_none,
    build_v17_feature_vector,
)

DOCTRINE = [
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "curr_or_minus_last_win_or", "curr_or_minus_best_or", "mark_compression_score",
    "release_window_score", "course_fit_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "odds_resilience_score", "odds_contraction_score", "decoy_support_flag",
    "setup_run_flag", "cash_run_flag",
]


def test_missing_history_inputs_are_zero():
    runner = {"best_odds_decimal": 4.0, "official_rating": 80, "rpr": None, "ts": None}
    race = {"distance_f": 8.0, "going": "Good", "race_class": "3", "ran": 8, "runners": []}
    feats = build_v17_feature_vector(runner, race)
    assert LIVE_MISSING_HISTORY_VALUE == 0.0
    for f in DOCTRINE:
        assert f in EXPECTED_FEATURES
        assert feats[f] == 0.0, f


def test_supplied_history_value_is_used():
    runner = {"best_odds_decimal": 4.0, "runs_since_win": 7}
    feats = build_v17_feature_vector(runner, {"distance_f": 8.0, "going": "Good", "runners": []})
    assert feats["runs_since_win"] == 7.0


def test_no_price_is_none_not_silent_ten():
    assert _resolve_decimal_odds_or_none({}) is None
    assert _resolve_decimal_odds({}) == 10.0  # legacy caller unchanged
    assert _resolve_decimal_odds_or_none({"best_odds_decimal": 5.0}) == 5.0
    assert _resolve_decimal_odds_or_none({"sp": "5/2"}) == 3.5
