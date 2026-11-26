"""Feature contract for the future Full Factual Context challenger.

This module deliberately does *not* score a horse and is not imported by Prime.
It converts only the factual families frozen in a Rich Context packet into a
fixed numerical vector suitable for a separately fitted V3 shadow challenger.

The contract is intentionally strict: a V3 vector is absent until every
declared factual family is present.  Missing data must remain visible as a
coverage failure rather than being converted into a flattering "full context"
score.  Provider predictions are scanned again at this final boundary.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from src.velo.formfav_feature_contract import scan_banned_fields

FEATURE_SCHEMA_VERSION = "RICH_CONTEXT_FACTUAL_V3"
REQUIRED_FAMILIES: tuple[str, ...] = (
    "prime_baseline_snapshot",
    "canonical_history",
    "market_facts",
    "formfav_raw_facts",
    "formfav_pace_context",
    "formfav_class_context",
    "formfav_track_bias_context",
    "rp_spotlight_facts",
    "connections_passports",
)

# The vector contains source facts, evidence counts and explicit missingness;
# it intentionally excludes provider predictions, ranks, badges and outcomes.
FEATURE_NAMES: tuple[str, ...] = (
    "velo_prime_prob",
    "market_implied_prob",
    "market_log_price",
    "history_win_rate",
    "history_place_rate",
    "history_days_since_last_run_capped",
    "history_course_win_rate",
    "history_distance_win_rate",
    "formfav_barrier_norm",
    "formfav_age_norm",
    "formfav_weight_norm",
    "formfav_form_observed_runs_norm",
    "formfav_early_speed_norm",
    "formfav_settling_position_norm",
    "formfav_style_leader",
    "formfav_style_presser",
    "formfav_pace_fast_or_very_fast",
    "formfav_class_difference_norm",
    "formfav_within_optimal_class",
    "formfav_track_bias_strength",
    "formfav_barrier_advantage",
    "spotlight_fact_count_norm",
    "spotlight_has_pace_fact",
    "connections_career_runs_norm",
    "connections_win_rate",
    "connections_place_rate",
    "formfav_raw_missing",
    "formfav_pace_missing",
    "formfav_class_missing",
    "formfav_track_bias_missing",
    "spotlight_missing",
    "connections_missing",
)


def _number(value: Any) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _value(source: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        converted = _number(source.get(key))
        if converted is not None:
            return converted
    return None


def _bounded(value: float | None, divisor: float, ceiling: float = 1.0) -> float:
    if value is None or divisor <= 0:
        return 0.0
    return min(max(value / divisor, 0.0), ceiling)


def _rate(value: Any) -> float:
    number = _number(value)
    if number is None:
        return 0.0
    if number > 1.0:
        number /= 100.0
    return min(max(number, 0.0), 1.0)


def missing_required_families(families: Mapping[str, Any]) -> list[str]:
    """Return declared factual families that were absent or empty in one packet."""
    return [name for name in REQUIRED_FAMILIES if not isinstance(families.get(name), Mapping) or not families[name]]


def vector_from_packet_families(families: Mapping[str, Any]) -> list[float] | None:
    """Return a V3 factual vector, or ``None`` if the full contract is incomplete.

    No default-filled partial V3 score is permitted. The caller should preserve
    the missing-family reasons and continue running Prime normally.
    """
    missing = missing_required_families(families)
    if missing:
        return None

    formfav_families = {
        name: families[name]
        for name in (
            "formfav_raw_facts",
            "formfav_pace_context",
            "formfav_class_context",
            "formfav_track_bias_context",
        )
    }
    banned = scan_banned_fields(formfav_families)
    if banned:
        raise ValueError("provider prediction/output leakage in V3 factual vector: " + ", ".join(banned))

    prime = families["prime_baseline_snapshot"]
    history = families["canonical_history"]
    market = families["market_facts"]
    raw = families["formfav_raw_facts"]
    pace = families["formfav_pace_context"]
    klass = families["formfav_class_context"]
    bias = families["formfav_track_bias_context"]
    spotlight = families["rp_spotlight_facts"]
    connections = families["connections_passports"]

    price = _value(market, "decimal_price", "sp_dec", "price")
    if price is None:
        price = _value(prime, "sp_dec")
    probability = _value(prime, "velo_prime_prob")
    if probability is None or price is None or price <= 1.0:
        return None

    speed_map = pace.get("speedMap") if isinstance(pace.get("speedMap"), Mapping) else {}
    class_profile = klass.get("classProfile") if isinstance(klass.get("classProfile"), Mapping) else {}
    class_fit = klass.get("raceClassFit") if isinstance(klass.get("raceClassFit"), Mapping) else {}
    track_bias = bias.get("trackBias") if isinstance(bias.get("trackBias"), Mapping) else {}
    family_counts = spotlight.get("family_counts") if isinstance(spotlight.get("family_counts"), Mapping) else {}

    style = str(speed_map.get("runningStyle") or speed_map.get("style") or "").upper()
    scenario = str(pace.get("paceScenario") or "").upper()
    fact_names = {str(name).lower() for name in (spotlight.get("feature_families") or [])}
    career_runs = _value(connections, "career_runs", "runs", "starts")
    wins = _value(connections, "wins")
    places = _value(connections, "places")

    return [
        probability,
        1.0 / price,
        math.log(price),
        _rate(history.get("win_rate")),
        _rate(history.get("place_rate")),
        _bounded(_value(history, "days_since_last_run"), 365.0),
        _rate(history.get("course_win_rate")),
        _rate(history.get("distance_win_rate")),
        _bounded(_value(raw, "barrier", "draw"), 30.0),
        _bounded(_value(raw, "age"), 15.0),
        _bounded(_value(raw, "weight", "weight_lbs"), 180.0),
        _bounded(_value(raw, "form_observed_runs", "last20StartsCount"), 20.0),
        _bounded(_value(speed_map, "earlySpeedIndex"), 10.0),
        _bounded(_value(speed_map, "settlingPosition"), 30.0),
        1.0 if style in {"L", "LEADER"} else 0.0,
        1.0 if style in {"P", "PRESSER"} else 0.0,
        1.0 if scenario in {"FAST", "VERY_FAST"} else 0.0,
        _bounded(abs(_value(class_fit, "classDifference") or 0.0), 10.0),
        1.0 if class_fit.get("withinOptimalRange") is True else 0.0,
        _rate(track_bias.get("biasStrengthScore", track_bias.get("biasStrength"))),
        _rate(track_bias.get("barrierAdvantage", track_bias.get("advantage"))),
        _bounded(sum(_number(count) or 0.0 for count in family_counts.values()), 10.0),
        1.0 if "pace_and_running_style" in fact_names else 0.0,
        _bounded(career_runs, 100.0),
        _rate((wins / career_runs) if wins is not None and career_runs and career_runs > 0 else None),
        _rate((places / career_runs) if places is not None and career_runs and career_runs > 0 else None),
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
