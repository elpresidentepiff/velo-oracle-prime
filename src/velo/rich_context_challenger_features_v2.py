"""Stable, leakage-safe feature contract for the fully enriched Velo challenger.

This module does not score or promote anything. It converts every approved
pre-off evidence family in a Rich Context packet into a fixed-length numeric
vector. Unknown provider fields remain preserved in the immutable packet but
cannot silently alter the fitted schema.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from src.velo.formfav_feature_contract import scan_banned_fields

SCHEMA_VERSION = "rich_context_feature_vector_v2"
APPROVED_FAMILIES: tuple[str, ...] = (
    "prime_baseline_snapshot",
    "market_facts",
    "canonical_history",
    "formfav_raw_facts",
    "formfav_pace_context",
    "formfav_class_context",
    "formfav_track_bias_context",
    "rp_spotlight_facts",
    "connections_passports",
)

# Exact, chronological features. Each numeric value is immediately followed by
# its missing flag. Categorical facts use explicit, bounded encodings.
NUMERIC_PATHS: tuple[tuple[str, ...], ...] = (
    ("prime_baseline_snapshot", "velo_prime_prob"),
    ("prime_baseline_snapshot", "place_prob"),
    ("prime_baseline_snapshot", "longshot_prob"),
    ("prime_baseline_snapshot", "sp_dec"),
    ("canonical_history", "days_since_last_run"),
    ("canonical_history", "runs_30d"),
    ("canonical_history", "runs_90d"),
    ("canonical_history", "career_history_rows"),
    ("canonical_history", "win_rate"),
    ("canonical_history", "place_rate"),
    ("canonical_history", "average_position"),
    ("canonical_history", "average_beaten_margin"),
    ("canonical_history", "course_win_rate"),
    ("canonical_history", "course_place_rate"),
    ("canonical_history", "distance_win_rate"),
    ("canonical_history", "distance_place_rate"),
    ("canonical_history", "going_win_rate"),
    ("canonical_history", "class_win_rate"),
    ("canonical_history", "current_jockey_pair_win_rate"),
    ("canonical_history", "current_trainer_win_rate"),
    ("formfav_raw_facts", "weightKg"),
    ("formfav_raw_facts", "claimKg"),
    ("formfav_raw_facts", "barrier"),
    ("formfav_raw_facts", "age"),
    ("formfav_raw_facts", "stats", "overall", "starts"),
    ("formfav_raw_facts", "stats", "overall", "wins"),
    ("formfav_raw_facts", "stats", "overall", "places"),
    ("formfav_pace_context", "speedMap", "earlySpeedIndex"),
    ("formfav_pace_context", "paceScenario", "pressureIndex"),
    ("formfav_class_context", "classProfile", "currentRating"),
    ("formfav_class_context", "raceClassFit", "rating"),
    ("formfav_track_bias_context", "trackBias", "sampleSize"),
    ("connections_passports", "pp_career_runs"),
    ("connections_passports", "pp_win_rate"),
    ("connections_passports", "pp_place_rate"),
    ("connections_passports", "pp_days_since_last"),
    ("connections_passports", "pp_jockey_continuity"),
    ("connections_passports", "pp_course_seen"),
    ("connections_passports", "pp_or_change_3"),
    ("connections_passports", "pp_win_rate_last3"),
    ("connections_passports", "pp_place_rate_last3"),
    ("connections_passports", "pp_avg_beaten_margin_last3"),
)

COUNT_FAMILIES: tuple[str, ...] = (
    "formfav_pace_context",
    "formfav_class_context",
    "formfav_track_bias_context",
    "rp_spotlight_facts",
)

FEATURE_NAMES: tuple[str, ...] = tuple(
    name
    for path in NUMERIC_PATHS
    for name in ("__".join(path), f"{'__'.join(path)}__missing")
) + tuple(
    name
    for family in APPROVED_FAMILIES
    for name in (f"family__{family}__present", f"family__{family}__scalar_count")
) + tuple(f"context__{family}__numeric_leaf_count" for family in COUNT_FAMILIES)

FEATURE_SCHEMA_HASH = hashlib.sha256(
    json.dumps({"version": SCHEMA_VERSION, "features": FEATURE_NAMES}, separators=(",", ":")).encode()
).hexdigest()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _numeric_leaf_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return sum(_numeric_leaf_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(_numeric_leaf_count(item) for item in value)
    return int(_number(value) is not None)


def _scalar_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return sum(_scalar_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(_scalar_count(item) for item in value)
    return int(value not in (None, ""))


def _at_path(families: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = families
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def build_enriched_vector(families: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic model-ready vector plus complete coverage truth."""
    approved = {name: families.get(name) for name in APPROVED_FAMILIES}
    provider = {key: approved[key] for key in approved if key.startswith("formfav_")}
    banned = scan_banned_fields(provider)
    if banned:
        raise ValueError("provider prediction/output leakage in enriched vector: " + ", ".join(banned))

    vector: list[float] = []
    for path in NUMERIC_PATHS:
        value = _number(_at_path(approved, path))
        vector.extend((value if value is not None else 0.0, 0.0 if value is not None else 1.0))
    for family in APPROVED_FAMILIES:
        payload = approved.get(family)
        present = isinstance(payload, Mapping) and bool(payload)
        vector.extend((1.0 if present else 0.0, float(_scalar_count(payload)) if present else 0.0))
    for family in COUNT_FAMILIES:
        vector.append(float(_numeric_leaf_count(approved.get(family))))

    coverage = {family: isinstance(approved.get(family), Mapping) and bool(approved.get(family)) for family in APPROVED_FAMILIES}
    return {
        "schema_version": SCHEMA_VERSION,
        "feature_schema_hash": FEATURE_SCHEMA_HASH,
        "feature_names": FEATURE_NAMES,
        "vector": vector,
        "family_coverage": coverage,
        "covered_family_count": sum(coverage.values()),
        "expected_family_count": len(APPROVED_FAMILIES),
        "fully_enriched": all(coverage.values()),
        "missing_families": [name for name, present in coverage.items() if not present],
    }
