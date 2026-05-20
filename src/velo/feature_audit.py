"""
VÉLØ Feature Audit + Flatline Detector — Issue #85.

build_scoring_feature_audit(): per-race field-level coverage report.
detect_vp_flatline():           post-scoring flatline check per race.

Hard constraints: read-only, no scoring changes, no routing changes.
"""

from __future__ import annotations

import re
from typing import Any


_AUDITED_FIELDS = (
    "official_rating",
    "rpr",
    "ts",
    "draw",
    "best_odds_decimal",
    "postdata_score",
    "or_compression_score",
    "mark_compression_score",
    "spotlight_score",
    "market_deception_score",
    "improvement_score",
    "place_prob",
    "release_day_prob",
    "comment_intel_score",
    "rpdc_release_score",
    "rpdc_primary_tag",
    "plot_conviction",
    "trainer_form_signal",
    "ts_trend_signal",
    "or_trend_signal",
)

# Flatline thresholds — see CLAUDE.md / THREE_HUNDRED_RUNNER_REVIEW_2026_05_20.md
_FLATLINE_MAX_UNIQUE = 2        # <= 2 distinct VP values → flatline
_FLATLINE_TIE_GROUP_PCT = 0.60  # top tie group covers >= 60% of field → flatline


def build_scoring_feature_audit(
    race: dict[str, Any],
    runners: list[dict[str, Any]],
    source_label: str = "",
) -> dict[str, Any]:
    """
    Produce a per-race field-level coverage audit for RP_MERGED diagnostics.

    For each audited field, reports:
        coverage_pct          : fraction of runners where field is non-None, non-zero
        unique_value_count    : distinct non-null values seen
        null_count            : runners where field is None or 0
        constant_value        : the single value if all runners share one (else None)

    Returns a summary dict suitable for logging and dashboard persistence.
    """
    n = max(len(runners), 1)
    field_reports: dict[str, dict] = {}

    for field in _AUDITED_FIELDS:
        values = []
        for r in runners:
            # Check runner dict first, then pdf_intel sub-dict
            v = r.get(field)
            if v is None:
                pdf = r.get("pdf_intel") or {}
                v = pdf.get(field)
            values.append(v)

        non_null = [v for v in values if v is not None and v != 0 and v != 0.0 and v != ""]
        unique_vals = set(str(v) for v in non_null)

        field_reports[field] = {
            "coverage_pct": round(len(non_null) / n, 3),
            "unique_value_count": len(unique_vals),
            "null_count": n - len(non_null),
            "constant_value": list(unique_vals)[0] if len(unique_vals) == 1 else None,
        }

    # Compute constant-feature count: fields where all runners share the same value
    constant_fields = [f for f, r in field_reports.items() if r["unique_value_count"] <= 1]
    missing_fields = [f for f, r in field_reports.items() if r["coverage_pct"] == 0.0]

    return {
        "race_id": race.get("race_id", ""),
        "course": race.get("course", ""),
        "off_time": race.get("off_time", ""),
        "source_label": source_label,
        "runner_count": n,
        "constant_feature_count": len(constant_fields),
        "missing_feature_count": len(missing_fields),
        "constant_fields": constant_fields,
        "missing_fields": missing_fields,
        "fields": field_reports,
    }


def detect_vp_flatline(
    race_id: str,
    predictions: list[dict[str, Any]],
    source_label: str = "",
) -> dict[str, Any] | None:
    """
    Post-scoring flatline check. Call after score_race_velo_prime() returns.

    Returns a flatline descriptor dict when the race scores collapse:
        {
            "race_id": ...,
            "flatline": True,
            "unique_vp_count": N,
            "runner_count": N,
            "max_tie_group_size": N,
            "max_tie_group_pct": 0.xx,
            "max_vp": 0.xxxx,
            "source_label": ...,
            "warning": "RP_FEATURE_FLATLINE: ...",
        }

    Returns None when the race is well-differentiated (no flatline).
    """
    if not predictions:
        return None

    vps = [float(p.get("velo_prime_prob") or 0) for p in predictions]
    n = len(vps)

    # Count occurrences per VP bucket (6 decimal places — same as storage precision)
    from collections import Counter
    vp_counts = Counter(round(v, 6) for v in vps)
    unique_count = len(vp_counts)
    max_tie_group = max(vp_counts.values())
    tie_group_pct = max_tie_group / n
    max_vp = max(vps) if vps else 0.0

    is_flatline = (unique_count <= _FLATLINE_MAX_UNIQUE) or (tie_group_pct >= _FLATLINE_TIE_GROUP_PCT)

    if not is_flatline:
        return None

    if unique_count == 1:
        msg = (
            f"RP_FEATURE_FLATLINE: {n}/{n} runners tied at VP={max_vp:.4f}. "
            f"Source features not differentiating. Treat selection as VISION_ONLY."
        )
    else:
        msg = (
            f"RP_FEATURE_FLATLINE: {max_tie_group}/{n} runners in top tie group "
            f"({tie_group_pct:.0%}). Unique VP groups={unique_count}. "
            f"Selection reliability degraded."
        )

    return {
        "race_id": race_id,
        "flatline": True,
        "unique_vp_count": unique_count,
        "runner_count": n,
        "max_tie_group_size": max_tie_group,
        "max_tie_group_pct": round(tie_group_pct, 3),
        "max_vp": round(max_vp, 4),
        "source_label": source_label,
        "warning": msg,
    }


def flatline_summary_for_run(
    flatlines: list[dict[str, Any]],
    total_races: int,
) -> dict[str, Any]:
    """
    Aggregate flatline stats for a full scoring run.

    Returns a summary for Telegram / timing audit / local JSON.
    """
    if not flatlines:
        return {
            "flatline_count": 0,
            "total_races": total_races,
            "flatline_pct": 0.0,
            "fully_uniform_count": 0,
            "majority_tied_count": 0,
            "races": [],
        }

    fully_uniform = [f for f in flatlines if f["unique_vp_count"] == 1]
    majority_tied = [f for f in flatlines if f["unique_vp_count"] > 1]

    return {
        "flatline_count": len(flatlines),
        "total_races": total_races,
        "flatline_pct": round(len(flatlines) / max(total_races, 1), 3),
        "fully_uniform_count": len(fully_uniform),
        "majority_tied_count": len(majority_tied),
        "races": [
            {
                "race_id": f["race_id"],
                "unique_vp_count": f["unique_vp_count"],
                "runner_count": f["runner_count"],
                "max_tie_pct": f["max_tie_group_pct"],
            }
            for f in flatlines
        ],
    }
