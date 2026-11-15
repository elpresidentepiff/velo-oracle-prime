"""Returns must be measured at a price that existed before the off, never at one seen after it."""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from src.velo import formfav_head_to_head as h2h
from src.velo import obtainable_prices as op

OFF = datetime(2026, 11, 14, 15, 30, tzinfo=UTC)


def _snap(minutes_before: float, price: float | None, horse: str = "Alpha") -> dict:
    return {"provider_race_key": "ff-1", "captured_at": (OFF - timedelta(minutes=minutes_before)).isoformat(),
            "horse_name": horse, "best_win": price}


def test_open_decision_and_close_are_taken_from_the_right_moments() -> None:
    rows = [_snap(118, 6.0), _snap(61, 5.5), _snap(40, 5.0), _snap(11, 4.5), _snap(9, 4.2), _snap(1, 4.0)]
    assert op.runner_prices(rows, OFF) == {"open": 6.0, "t10": 4.5, "close": 4.0}


def test_a_price_seen_at_or_after_the_off_is_never_used() -> None:
    rows = [_snap(90, 6.0), _snap(12, 5.0), _snap(0, 2.0), _snap(-5, 1.5)]
    assert op.runner_prices(rows, OFF) == {"open": 6.0, "t10": 5.0, "close": 5.0}


def test_a_runner_without_an_early_or_a_decision_price_is_left_out() -> None:
    assert op.runner_prices([_snap(30, 5.0), _snap(5, 4.0)], OFF) is None  # nothing 60 minutes out
    assert op.runner_prices([_snap(90, 5.0), _snap(5, 4.0)], OFF) == {"open": 5.0, "t10": 5.0, "close": 4.0}
    assert op.runner_prices([_snap(5, 4.0)], OFF) is None
    assert op.runner_prices([_snap(90, None), _snap(20, 1.0)], OFF) is None  # no usable price
    assert op.runner_prices([{"captured_at": "2026-11-14T13:00:00", "best_win": 5.0}], OFF) is None  # no timezone


def test_a_pick_is_settled_at_the_decision_price_and_scored_against_the_close() -> None:
    steamer = op.pick_outcome(True, {"open": 6.0, "t10": 5.0, "close": 4.0})
    assert steamer["profit_at_t10"] == 4.0
    assert math.isclose(steamer["beat_close"], math.log(5.0 / 4.0)) and steamer["beat_close"] > 0
    drifter = op.pick_outcome(False, {"open": 4.0, "t10": 5.0, "close": 6.5})
    assert drifter["profit_at_t10"] == -1.0 and drifter["beat_close"] < 0


def test_summary_reports_the_sample_size_and_both_signals() -> None:
    picks = [op.pick_outcome(True, {"open": 6.0, "t10": 5.0, "close": 4.0}),
             op.pick_outcome(False, {"open": 4.0, "t10": 4.0, "close": 5.0}),
             op.pick_outcome(False, {"open": 3.0, "t10": 3.0, "close": 3.0})]
    out = op.summarise(picks)
    assert out["picks"] == 3
    assert out["roi_at_t10_pct"] == round(100 * (4.0 - 1 - 1) / 3, 1)
    assert out["beat_close_share_pct"] == 33.3 and out["worse_than_close_share_pct"] == 33.3
    assert op.summarise([])["picks"] == 0 and op.summarise([])["roi_at_t10_pct"] is None


def test_the_book_shows_the_bookmakers_margin() -> None:
    prices = {"a": {"t10": 2.0}, "b": {"t10": 4.0}, "c": {"t10": 4.0}}
    assert op.book(prices) == 1.0
    assert op.book({"a": {"t10": 1.8}, "b": {"t10": 3.5}, "c": {"t10": 3.5}}) > 1.1


# ── through the head-to-head ─────────────────────────────────────────────────

VELO_RACES = [{"race_id": "100", "course": "Cheltenham", "date": "2026-11-14", "time": "15:30:00"}]
FF_RACES = [{"provider_race_key": "ff-1", "race_date": "2026-11-14", "track": "Cheltenham", "start_time": "2026-11-14T15:30:00Z"}]
RESULTS = [{"race_id": "100", "horse": "Alpha (IRE)", "position_int": 1, "sp_dec": 3.0},
           {"race_id": "100", "horse": "Bravo", "position_int": 2, "sp_dec": 2.5},
           {"race_id": "100", "horse": "Charlie", "position_int": 3, "sp_dec": 9.0}]
VERDICT = {"race_id": "100", "generated_at": "2026-11-14T07:25:00Z", "full_analysis": {"predictions": [
    {"horse": "Alpha", "velo_prime_prob": 0.5}, {"horse": "Bravo", "velo_prime_prob": 0.3}, {"horse": "Charlie", "velo_prime_prob": 0.2}]}}
PREDICTION = {"provider_race_key": "ff-1", "predictions_payload": {"predictedAt": "2026-11-14T09:00:00Z", "predictions": [
    {"name": "Alpha (IRE)", "winProb": 0.3}, {"name": "Bravo", "winProb": 0.5}, {"name": "Charlie", "winProb": 0.2}]}}


def _market(alpha=(5.0, 4.0, 3.2), bravo=(2.4, 2.6, 2.5), charlie=(9.0, 9.0, 9.5), names=("Alpha (IRE)", "Bravo", "Charlie")) -> list[dict]:
    rows = []
    for name, (opening, decision, close) in zip(names, (alpha, bravo, charlie), strict=True):
        rows += [_snap(100, opening, name), _snap(12, decision, name), _snap(1, close, name)]
    return rows


def test_each_source_is_measured_at_the_decision_price_on_the_same_races() -> None:
    report = h2h.evaluate(VELO_RACES, FF_RACES, [VERDICT], [PREDICTION], RESULTS, _market())
    priced = report["obtainable_prices"]
    assert priced["races_with_full_prices"] == 1
    assert priced["PRIME"]["roi_at_t10_pct"] == 300.0  # Alpha won, taken at 4.0 ten minutes out
    assert priced["PRIME"]["roi_at_sp_pct_same_races"] == 200.0  # the same pick at its SP of 3.0
    assert priced["PRIME"]["avg_beat_close_pct"] == 25.0  # 4.0 against a close of 3.2
    assert priced["FORMFAV"]["roi_at_t10_pct"] == -100.0  # Bravo lost
    assert priced["FORMFAV"]["avg_beat_close_pct"] == 4.0  # 2.6 against 2.5


def test_a_race_with_one_unpriced_runner_is_left_out_of_the_price_comparison_only() -> None:
    partial = [row for row in _market() if row["horse_name"] != "Charlie"]
    report = h2h.evaluate(VELO_RACES, FF_RACES, [VERDICT], [PREDICTION], RESULTS, partial)
    assert report["coverage"]["eligible"] == 1  # still counted at SP
    assert report["obtainable_prices"]["races_with_full_prices"] == 0
    assert report["obtainable_prices"]["PRIME"]["picks"] == 0


def test_without_snapshots_the_price_section_is_absent_not_invented() -> None:
    assert h2h.evaluate(VELO_RACES, FF_RACES, [VERDICT], [PREDICTION], RESULTS)["obtainable_prices"] is None
