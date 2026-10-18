"""Offline-only challenger evaluation primitives. No production imports or network calls."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import log, isfinite


@dataclass(frozen=True)
class Observation:
    race_id: str
    runner_id: str
    race_time: str
    prediction_time: str
    outcome: int
    baseline_prob: float
    challenger_prob: float


def _as_utc(value: str) -> datetime:
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return t.astimezone(timezone.utc)


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
        for p, baseline in ((row.baseline_prob, True), (row.challenger_prob, False)):
            safe = max(1e-12, min(1 - 1e-12, p))
            loss = -(y * log(safe) + (1-y) * log(1-safe))
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
        "promotion": "NOT_AUTHORISED",
        "mode": "offline_shadow_research",
    }
