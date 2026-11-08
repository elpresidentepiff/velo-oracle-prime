"""The one feature vector both training and live scoring use, so they can never drift apart.

Reads only the two families every eligible shadow packet already carries (`prime_baseline_snapshot`,
`canonical_history`) plus `market_facts`/`sp_dec`. No post-off field, no provider prediction, no field this
module invents: a missing value gets an explicit ``*_missing`` flag and a neutral placeholder, never a
favourable guess (the same rule ``_build_live_features`` applies to Prime's own ratings).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

FEATURE_NAMES: tuple[str, ...] = (
    "velo_prime_prob",
    "implied_prob",
    "log_sp",
    "has_history",
    "days_since_last_run",
    "runs_90d",
    "win_rate",
    "win_rate_missing",
    "place_rate",
    "place_rate_missing",
    "average_position",
    "average_position_missing",
    "course_win_rate",
    "course_win_rate_missing",
    "class_win_rate",
    "class_win_rate_missing",
)


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def extract_feature_vector(
    *,
    prime_baseline: Mapping[str, Any] | None,
    history_eligible: bool,
    history_features: Mapping[str, Any] | None,
) -> list[float] | None:
    """Return the model input, or None when the two required families are not both present.

    ``prime_baseline`` is ``families["prime_baseline_snapshot"]`` and ``history_features`` is
    ``families["canonical_history"]`` as stored on every ``rich_context_shadow_packets`` row — the exact
    shapes ``build_runner_shadow_packet`` writes and ``CanonicalHistoryProvider.build()`` returns.
    """
    prime_baseline = prime_baseline or {}
    vp = _num(prime_baseline.get("velo_prime_prob"))
    sp = _num(prime_baseline.get("sp_dec"))
    if vp is None or sp is None or sp <= 1.0:
        return None  # the baseline family itself is required and incomplete
    hf: Mapping[str, Any] = history_features or {}
    has_history = 1.0 if history_eligible else 0.0

    def _rate(key: str) -> tuple[float, float]:
        value = _num(hf.get(key)) if history_eligible else None
        return (value, 0.0) if value is not None else (0.0, 1.0)

    win_rate, win_missing = _rate("win_rate")
    place_rate, place_missing = _rate("place_rate")
    course_rate, course_missing = _rate("course_win_rate")
    class_rate, class_missing = _rate("class_win_rate")
    avg_pos = _num(hf.get("average_position")) if history_eligible else None
    avg_pos_missing = 1.0 if avg_pos is None else 0.0
    avg_pos_value = avg_pos if avg_pos is not None else 10.0  # a neutral mid-field placeholder, flagged above
    days_since = _num(hf.get("days_since_last_run")) if history_eligible else None
    days_since_value = min(days_since, 365.0) if days_since is not None else 365.0
    runs_90d = _num(hf.get("runs_90d")) if history_eligible else None

    import math

    return [
        vp,
        1.0 / sp,
        math.log(sp),
        has_history,
        days_since_value,
        float(runs_90d) if runs_90d is not None else 0.0,
        win_rate,
        win_missing,
        place_rate,
        place_missing,
        avg_pos_value,
        avg_pos_missing,
        course_rate,
        course_missing,
        class_rate,
        class_missing,
    ]


def vector_from_packet_families(families: Mapping[str, Any]) -> list[float] | None:
    """Convenience wrapper over a packet's ``families`` dict, as stored in Supabase."""
    history = families.get("canonical_history")
    return extract_feature_vector(
        prime_baseline=families.get("prime_baseline_snapshot"),
        history_eligible=isinstance(history, Mapping) and bool(history),
        history_features=history if isinstance(history, Mapping) else None,
    )
