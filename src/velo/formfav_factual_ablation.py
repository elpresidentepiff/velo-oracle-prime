"""Truthful FormFav factual-lane readiness reports.

This module does not score, fit, rank, or blend horses.  It converts the
already immutable Rich Context packet evidence into separate factual-family
cohorts so that a later, chronologically fitted challenger can be evaluated
family by family.  Provider predictions and outcomes are rejected here rather
than merely omitted from a dashboard label.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from src.velo.formfav_feature_contract import scan_banned_fields

LANES: tuple[tuple[str, str], ...] = (
    ("formfav_raw_facts", "FormFav runner facts"),
    ("formfav_pace_context", "FormFav pace context"),
    ("formfav_class_context", "FormFav class context"),
    ("formfav_track_bias_context", "FormFav track-bias context"),
)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def build_factual_ablation_report(
    *, date: str, packets: Sequence[Mapping[str, Any]], minimum_forward_races: int = 500
) -> dict[str, Any]:
    """Build a capture/readiness report without deriving a horse selection.

    A row contributes only when it is an immutable, pre-off packet marked
    eligible for a future fit.  Any banned provider field makes the relevant
    lane ineligible and is recorded explicitly.  It never enters a model.
    """
    total = len(packets)
    eligible_packets = [p for p in packets if p.get("eligible_for_future_fit") is True]
    unique_races = {str(p.get("race_id")) for p in packets if p.get("race_id")}
    eligible_races = {str(p.get("race_id")) for p in eligible_packets if p.get("race_id")}
    lanes: list[dict[str, Any]] = []
    all_banned: set[str] = set()

    for family, label in LANES:
        captured = 0
        eligible = 0
        banned_packets = 0
        fields_seen: set[str] = set()
        for packet in packets:
            families = _mapping(packet.get("feature_families") or packet.get("families"))
            factual = _mapping(families.get(family))
            if not factual:
                continue
            captured += 1
            fields_seen.update(str(k) for k in factual)
            banned = scan_banned_fields(factual)
            if banned:
                banned_packets += 1
                all_banned.update(f"{family}:{path}" for path in banned)
                continue
            if packet.get("eligible_for_future_fit") is True:
                eligible += 1
        coverage = round(100.0 * captured / total, 1) if total else None
        eligible_coverage = round(100.0 * eligible / total, 1) if total else None
        lanes.append({
            "family": family,
            "label": label,
            "captured_runners": captured,
            "eligible_runners": eligible,
            "total_runners": total,
            "coverage_pct": coverage,
            "eligible_coverage_pct": eligible_coverage,
            "field_names": sorted(fields_seen),
            "banned_provider_field_packets": banned_packets,
            "state": (
                "REJECTED_PROVIDER_OUTPUT_PRESENT" if banned_packets else
                "FORWARD_EVIDENCE_COLLECTING" if eligible else
                "NO_ELIGIBLE_PRE_OFF_EVIDENCE"
            ),
            "active_shadow_use": "NOT_FITTED_SEPARATE_ABLATION",
        })

    return {
        "schema_version": "FORMFAV_FACTUAL_ABLATION_V1",
        "date": date,
        "generated_at": datetime.now(UTC).isoformat(),
        "classification": "SHADOW_ONLY",
        "production_influence": False,
        "paper_sim_only": True,
        "provider_predictions_consumed": False,
        "provider_outcomes_consumed": False,
        "model_fit_performed": False,
        "summary": {
            "captured_packets": total,
            "eligible_pre_off_packets": len(eligible_packets),
            "captured_races": len(unique_races),
            "eligible_pre_off_races": len(eligible_races),
            "minimum_forward_races_before_fit": minimum_forward_races,
            "fit_state": "FORWARD_COLLECTION_ONLY",
            "banned_provider_field_paths": sorted(all_banned),
        },
        "lanes": lanes,
        "next_gate": (
            "Collect immutable, identity-matched pre-off factual packets and settle them. "
            "Do not fit, rank, blend, or promote before the separate protocol's chronological evidence gate."
        ),
    }
