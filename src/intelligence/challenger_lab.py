"""Offline-only challenger evaluation primitives. No production imports or network calls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite, log, sqrt


@dataclass(frozen=True)
class Observation:
    race_id: str
    runner_id: str
    race_time: str
    prediction_time: str
    outcome: int
    baseline_prob: float
    challenger_prob: float


@dataclass(frozen=True)
class MarketObservation:
    race_id: str
    runner_id: str
    race_time: str
    prediction_time: str
    outcome: int
    baseline_prob: float
    challenger_prob: float
    decimal_price: float


def _as_utc(value: str) -> datetime:
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return t.astimezone(UTC)


def _mean_ci(values: list[float]) -> list[float] | None:
    """Normal-approximation 95% CI over independent race-level summaries."""
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    margin = 1.96 * sqrt(variance / len(values))
    return [mean - margin, mean + margin]


def _expected_calibration_error(rows: list[tuple[float, int]], bins: int = 10) -> float:
    total = len(rows)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        bucket = [row for row in rows if lower <= row[0] < upper or (index == bins - 1 and row[0] == 1)]
        if bucket:
            confidence = sum(row[0] for row in bucket) / len(bucket)
            accuracy = sum(row[1] for row in bucket) / len(bucket)
            error += (len(bucket) / total) * abs(confidence - accuracy)
    return error


def evaluate(observations: list[Observation], *, min_runners: int = 300) -> dict:
    """Paired win-probability comparison; raises on unsafe or incomplete evidence.

    Caller must supply an independent time-ordered holdout. This deliberately
    performs no Supabase I/O, model training, promotion or live scoring.
    """
    if min_runners < 1:
        raise ValueError("min_runners must be positive")
    if len(observations) < min_runners:
        raise ValueError("insufficient runner count for review")
    seen = set()
    baseline_brier = challenger_brier = 0.0
    baseline_log = challenger_log = 0.0
    race_outcomes = {}
    calibration_rows: dict[str, list[tuple[float, int]]] = {"baseline": [], "challenger": []}
    race_loss_deltas: dict[str, list[float]] = {}
    for row in observations:
        if not row.race_id or not row.runner_id:
            raise ValueError("missing race or runner identity")
        key = (row.race_id, row.runner_id)
        if key in seen:
            raise ValueError("duplicate runner identity")
        seen.add(key)
        if _as_utc(row.prediction_time) >= _as_utc(row.race_time):
            raise ValueError("prediction not strictly pre-race")
        if type(row.outcome) is not int or row.outcome not in (0, 1):
            raise ValueError("outcome must be binary 0 or 1")
        for p in (row.baseline_prob, row.challenger_prob):
            if not isfinite(p) or not 0 <= p <= 1:
                raise ValueError("probability outside [0,1]")
        race_outcomes[row.race_id] = race_outcomes.get(row.race_id, 0) + row.outcome
        y = row.outcome
        baseline_brier += (row.baseline_prob - y) ** 2
        challenger_brier += (row.challenger_prob - y) ** 2
        calibration_rows["baseline"].append((row.baseline_prob, y))
        calibration_rows["challenger"].append((row.challenger_prob, y))
        race_loss_deltas.setdefault(row.race_id, []).append(
            (row.challenger_prob - y) ** 2 - (row.baseline_prob - y) ** 2
        )
        for p, baseline in ((row.baseline_prob, True), (row.challenger_prob, False)):
            safe = max(1e-12, min(1 - 1e-12, p))
            loss = -(y * log(safe) + (1 - y) * log(1 - safe))
            if baseline:
                baseline_log += loss
            else:
                challenger_log += loss
    if any(n != 1 for n in race_outcomes.values()):
        raise ValueError("each evaluated race must have exactly one winner")
    n = len(observations)
    return {
        "runner_count": n,
        "race_count": len(race_outcomes),
        "baseline_brier": baseline_brier / n,
        "challenger_brier": challenger_brier / n,
        "baseline_log_loss": baseline_log / n,
        "challenger_log_loss": challenger_log / n,
        "brier_delta_challenger_minus_baseline": (challenger_brier - baseline_brier) / n,
        "log_loss_delta_challenger_minus_baseline": (challenger_log - baseline_log) / n,
        "baseline_expected_calibration_error_10_bin": _expected_calibration_error(calibration_rows["baseline"]),
        "challenger_expected_calibration_error_10_bin": _expected_calibration_error(calibration_rows["challenger"]),
        "uncertainty": {
            "unit": "RACE_LEVEL_MEAN_BRIER_DELTA",
            "method": "NORMAL_APPROXIMATION_95_PERCENT_CI",
            "race_count": len(race_loss_deltas),
            "brier_delta_95pct_ci": _mean_ci([sum(values) / len(values) for values in race_loss_deltas.values()]),
        },
        "promotion": "NOT_AUTHORISED",
        "mode": "offline_shadow_research",
    }


def evaluate_market_value(observations: list[MarketObservation], *, min_races: int = 30) -> dict:
    """Compare one flat-stake top pick per race at captured pre-race prices.

    This is descriptive offline evidence, not a staking recommendation. Every
    runner in an admitted race must have a valid price so model selection is
    compared on the same complete race cohort.
    """
    if min_races < 1:
        raise ValueError("min_races must be positive")
    races: dict[str, list[MarketObservation]] = {}
    seen: set[tuple[str, str]] = set()
    for row in observations:
        key = (row.race_id, row.runner_id)
        if not row.race_id or not row.runner_id or key in seen:
            raise ValueError("missing or duplicate runner identity")
        seen.add(key)
        if _as_utc(row.prediction_time) >= _as_utc(row.race_time):
            raise ValueError("price observation not strictly pre-race")
        if type(row.outcome) is not int or row.outcome not in (0, 1):
            raise ValueError("outcome must be binary 0 or 1")
        if not isfinite(row.decimal_price) or row.decimal_price <= 1:
            raise ValueError("decimal price must be finite and greater than one")
        for probability in (row.baseline_prob, row.challenger_prob):
            if not isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError("probability outside [0,1]")
        races.setdefault(row.race_id, []).append(row)
    if len(races) < min_races:
        raise ValueError("insufficient race count for value review")
    if any(sum(row.outcome for row in rows) != 1 for rows in races.values()):
        raise ValueError("each evaluated race must have exactly one winner")

    def summary(probability_field: str) -> dict:
        picks = [max(rows, key=lambda row: getattr(row, probability_field)) for rows in races.values()]
        returns = sum(row.decimal_price if row.outcome else 0.0 for row in picks)
        stake = float(len(picks))
        expected_wins = sum(1.0 / row.decimal_price for row in picks)
        actual_wins = sum(row.outcome for row in picks)
        return {
            "bets": len(picks),
            "wins": actual_wins,
            "strike_rate": actual_wins / stake,
            "stake_units": stake,
            "return_units": returns,
            "profit_units": returns - stake,
            "roi": (returns - stake) / stake,
            "actual_to_market_expected": actual_wins / expected_wins if expected_wins else None,
            "mean_captured_decimal_price": sum(row.decimal_price for row in picks) / stake,
            "mean_model_edge": sum(getattr(row, probability_field) - (1.0 / row.decimal_price) for row in picks)
            / stake,
        }

    baseline = summary("baseline_prob")
    challenger = summary("challenger_prob")
    race_return_deltas = []
    for rows in races.values():
        baseline_pick = max(rows, key=lambda row: row.baseline_prob)
        challenger_pick = max(rows, key=lambda row: row.challenger_prob)
        race_return_deltas.append(
            (challenger_pick.decimal_price if challenger_pick.outcome else 0.0)
            - (baseline_pick.decimal_price if baseline_pick.outcome else 0.0)
        )
    return {
        "race_count": len(races),
        "runner_count": len(observations),
        "selection_policy": "ONE_HIGHEST_PROBABILITY_PICK_PER_RACE_FLAT_ONE_UNIT",
        "price_contract": "CAPTURED_IN_STRICTLY_PRE_RACE_PREDICTION_RECORD",
        "baseline": baseline,
        "challenger": challenger,
        "roi_delta_challenger_minus_baseline": challenger["roi"] - baseline["roi"],
        "uncertainty": {
            "unit": "PAIRED_RACE_RETURN_DELTA_UNITS",
            "method": "NORMAL_APPROXIMATION_95_PERCENT_CI",
            "roi_delta_95pct_ci": _mean_ci(race_return_deltas),
        },
        "promotion": "NOT_AUTHORISED",
        "mode": "offline_shadow_research",
    }
