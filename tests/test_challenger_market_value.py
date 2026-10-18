from __future__ import annotations

import pytest

from src.intelligence.challenger_lab import MarketObservation, evaluate_market_value


def _race(race_id: str, winner: str) -> list[MarketObservation]:
    return [
        MarketObservation(
            race_id=race_id,
            runner_id=runner,
            race_time="2026-06-20T14:00:00Z",
            prediction_time="2026-06-20T12:00:00Z",
            outcome=int(runner == winner),
            baseline_prob=baseline,
            challenger_prob=challenger,
            decimal_price=price,
        )
        for runner, baseline, challenger, price in (
            ("a", 0.6, 0.4, 2.0),
            ("b", 0.4, 0.6, 4.0),
        )
    ]


def test_market_value_uses_paired_races_and_flat_stakes() -> None:
    result = evaluate_market_value(_race("r1", "a") + _race("r2", "b"), min_races=2)
    assert result["race_count"] == 2
    assert result["baseline"]["stake_units"] == 2
    assert result["baseline"]["return_units"] == 2
    assert result["challenger"]["return_units"] == 4
    assert result["roi_delta_challenger_minus_baseline"] == 1
    assert result["uncertainty"]["roi_delta_95pct_ci"] is not None
    assert result["promotion"] == "NOT_AUTHORISED"


def test_market_value_rejects_late_price() -> None:
    rows = _race("r1", "a")
    rows[0] = MarketObservation(**{**rows[0].__dict__, "prediction_time": rows[0].race_time})
    with pytest.raises(ValueError, match="not strictly pre-race"):
        evaluate_market_value(rows, min_races=1)
