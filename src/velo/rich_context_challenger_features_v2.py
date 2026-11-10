"""Rich Context challenger v2 feature vector: the full ``canonical_history`` family, not a subset.

v1 (``rich_context_challenger_features.py``) used 7 of the ~20 fields ``CanonicalHistoryProvider``
already computes for every eligible packet — a feature-utilization gap, not a capture gap: no new
provenance, no new family, nothing requiring fresh history to accumulate. v2 adds the remaining
distance/going/course-place/jockey-pairing/trainer-continuity/rating/margin/recency fields from the
exact same family, so it is still trainable and holdout-testable on the identical frozen chronological
windows declared for v1 in ``scripts/research/fit_rich_context_challenger_v1.py``.

``rp_spotlight_facts``, ``formfav_*`` and ``connections_passports`` remain excluded here for the same
reason v1 excluded them: no pre-2026-11-06 history exists yet to fit or validate a family of them on.
This module is the family-utilization half of that work only.

Same missingness contract as v1: a missing value gets an explicit ``*_missing`` flag and a neutral
placeholder, never a favourable guess.
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
    "runs_30d",
    "runs_90d",
    "runs_365d",
    "win_rate",
    "win_rate_missing",
    "place_rate",
    "place_rate_missing",
    "average_position",
    "average_position_missing",
    "course_win_rate",
    "course_win_rate_missing",
    "course_place_rate",
    "course_place_rate_missing",
    "distance_win_rate",
    "distance_win_rate_missing",
    "distance_place_rate",
    "distance_place_rate_missing",
    "going_win_rate",
    "going_win_rate_missing",
    "class_win_rate",
    "class_win_rate_missing",
    "current_jockey_pair_win_rate",
    "current_jockey_pair_win_rate_missing",
    "current_trainer_win_rate",
    "current_trainer_win_rate_missing",
    "jockey_changed_from_last_run",
    "jockey_changed_from_last_run_missing",
    "trainer_changed_from_last_run",
    "trainer_changed_from_last_run_missing",
    "best_official_rating_norm",
    "best_official_rating_missing",
    "average_beaten_margin_norm",
    "average_beaten_margin_missing",
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
    """Return the v2 model input, or None when the two required families are not both present.

    Same packet shapes as v1's ``extract_feature_vector``: ``prime_baseline`` is
    ``families["prime_baseline_snapshot"]`` and ``history_features`` is ``families["canonical_history"]``.
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

    def _count(key: str) -> float:
        value = _num(hf.get(key)) if history_eligible else None
        return float(value) if value is not None else 0.0

    def _flag(key: str) -> tuple[float, float]:
        value = hf.get(key) if history_eligible else None
        if value is None:
            return (0.0, 1.0)
        return (1.0 if bool(value) else 0.0, 0.0)

    win_rate, win_missing = _rate("win_rate")
    place_rate, place_missing = _rate("place_rate")
    course_rate, course_missing = _rate("course_win_rate")
    course_place_rate, course_place_missing = _rate("course_place_rate")
    distance_rate, distance_missing = _rate("distance_win_rate")
    distance_place_rate, distance_place_missing = _rate("distance_place_rate")
    going_rate, going_missing = _rate("going_win_rate")
    class_rate, class_missing = _rate("class_win_rate")
    jockey_pair_rate, jockey_pair_missing = _rate("current_jockey_pair_win_rate")
    trainer_rate, trainer_missing = _rate("current_trainer_win_rate")
    jockey_changed, jockey_changed_missing = _flag("jockey_changed_from_last_run")
    trainer_changed, trainer_changed_missing = _flag("trainer_changed_from_last_run")

    avg_pos = _num(hf.get("average_position")) if history_eligible else None
    avg_pos_missing = 1.0 if avg_pos is None else 0.0
    avg_pos_value = avg_pos if avg_pos is not None else 10.0  # neutral mid-field placeholder, flagged above

    days_since = _num(hf.get("days_since_last_run")) if history_eligible else None
    days_since_value = min(days_since, 365.0) if days_since is not None else 365.0

    best_or = _num(hf.get("best_official_rating")) if history_eligible else None
    best_or_missing = 1.0 if best_or is None else 0.0
    best_or_value = (best_or / 100.0) if best_or is not None else 0.0  # ratings are ~0-140; scale down

    margin = _num(hf.get("average_beaten_margin")) if history_eligible else None
    margin_missing = 1.0 if margin is None else 0.0
    margin_value = (margin / 10.0) if margin is not None else 0.0  # lengths beaten; scale down

    import math

    return [
        vp,
        1.0 / sp,
        math.log(sp),
        has_history,
        days_since_value,
        _count("runs_30d"),
        _count("runs_90d"),
        _count("runs_365d"),
        win_rate,
        win_missing,
        place_rate,
        place_missing,
        avg_pos_value,
        avg_pos_missing,
        course_rate,
        course_missing,
        course_place_rate,
        course_place_missing,
        distance_rate,
        distance_missing,
        distance_place_rate,
        distance_place_missing,
        going_rate,
        going_missing,
        class_rate,
        class_missing,
        jockey_pair_rate,
        jockey_pair_missing,
        trainer_rate,
        trainer_missing,
        jockey_changed,
        jockey_changed_missing,
        trainer_changed,
        trainer_changed_missing,
        best_or_value,
        best_or_missing,
        margin_value,
        margin_missing,
    ]


def vector_from_packet_families(families: Mapping[str, Any]) -> list[float] | None:
    """Convenience wrapper over a packet's ``families`` dict, as stored in Supabase."""
    history = families.get("canonical_history")
    return extract_feature_vector(
        prime_baseline=families.get("prime_baseline_snapshot"),
        history_eligible=isinstance(history, Mapping) and bool(history),
        history_features=history if isinstance(history, Mapping) else None,
    )
