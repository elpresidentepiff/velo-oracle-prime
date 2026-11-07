"""Frozen Rich Context shadow packets and fail-closed challenger scoring.

Production Prime never imports this module. It assembles auditable pre-off
evidence for a separately versioned challenger. Until a model artifact is fit
under the frozen protocol and its hashes are verified, it emits no probability
or rank: coverage is evidence, not a selection.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.velo.formfav_feature_contract import scan_banned_fields

PACKET_SCHEMA_VERSION = "rich_context_shadow_packet_v1"
CHALLENGER_VERSION = "rich_context_challenger_v1_unfitted"
MODEL_STATUS = "AWAITING_FROZEN_MODEL_FIT"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _eligible(packet: Mapping[str, Any] | None, key: str = "training_eligible") -> bool:
    return bool(packet and packet.get(key) is True)


def _formfav_families(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    if not _eligible(manifest):
        return {}
    families = manifest.get("families") or {}
    if not isinstance(families, Mapping):
        return {}
    banned = scan_banned_fields(families)
    if banned:
        raise ValueError("provider prediction/output leakage in FormFav manifest: " + ", ".join(banned))
    raw = families.get("raw_facts") if isinstance(families.get("raw_facts"), Mapping) else {}
    derived = families.get("provider_derived_context")
    derived = derived if isinstance(derived, Mapping) else {}
    return {
        "formfav_raw_facts": dict(raw),
        "formfav_pace_context": {
            key: derived[key] for key in ("speedMap", "paceScenario") if key in derived
        },
        "formfav_class_context": {
            key: derived[key] for key in ("classProfile", "raceClassFit") if key in derived
        },
        "formfav_track_bias_context": {
            key: derived[key] for key in ("trackBias",) if key in derived
        },
    }


def build_runner_shadow_packet(
    *,
    race_id: str,
    horse_id: str,
    race_date: str,
    prime_snapshot: Mapping[str, Any],
    formfav_manifest: Mapping[str, Any] | None,
    history_packet: Mapping[str, Any] | None,
    comment_packet: Mapping[str, Any] | None,
    connections_passport: Mapping[str, Any] | None = None,
    market_facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble one immutable-in-shape shadow packet using exact identities."""
    identity_ok = bool(str(race_id).strip() and str(horse_id).strip())
    reasons: list[str] = []
    if not identity_ok:
        reasons.append("UNPROVEN_CANONICAL_IDENTITY")

    families: dict[str, Any] = {
        "prime_baseline_snapshot": {
            key: prime_snapshot.get(key)
            for key in ("velo_prime_prob", "place_prob", "longshot_prob", "sp_dec", "is_fav")
            if key in prime_snapshot
        }
    }
    families.update(_formfav_families(formfav_manifest))
    if history_packet and history_packet.get("eligible") is True:
        families["canonical_history"] = dict(history_packet.get("features") or {})
    if _eligible(comment_packet):
        families["rp_spotlight_facts"] = {
            "feature_families": list(comment_packet.get("feature_families") or []),
            "family_counts": dict(comment_packet.get("family_counts") or {}),
        }
    if connections_passport:
        families["connections_passports"] = dict(connections_passport)
    if market_facts:
        families["market_facts"] = dict(market_facts)

    family_coverage = {name: bool(payload) for name, payload in families.items()}
    required = ("prime_baseline_snapshot", "canonical_history")
    missing_required = [name for name in required if not family_coverage.get(name)]
    reasons.extend(f"MISSING_REQUIRED_FAMILY:{name}" for name in missing_required)

    provenance = {
        "formfav_manifest_hash": formfav_manifest.get("derived_vector_hash") if formfav_manifest else None,
        "history_source_row_ids": list(history_packet.get("source_row_ids") or []) if history_packet else [],
        "comment_normalized_text_sha256": comment_packet.get("normalized_text_sha256") if comment_packet else None,
        "comment_raw_text_sha256": comment_packet.get("raw_text_sha256") if comment_packet else None,
    }
    input_hash = _hash({"identity": [race_id, horse_id, race_date], "families": families, "provenance": provenance})
    return {
        "packet_schema_version": PACKET_SCHEMA_VERSION,
        "challenger_version": CHALLENGER_VERSION,
        "model_status": MODEL_STATUS,
        "race_id": str(race_id),
        "horse_id": str(horse_id),
        "race_date": str(race_date),
        "families": families,
        "family_coverage": family_coverage,
        "provenance": provenance,
        "input_hash": input_hash,
        "feature_vector_hash": _hash(families),
        "eligible_for_future_fit": identity_ok and not missing_required,
        "ineligibility_reasons": reasons,
        "challenger_probability": None,
        "challenger_rank": None,
        "production_prime_consumed_rich_context": False,
        "production_influence": False,
        "paper_sim_only": True,
        "provider_predictions_consumed": False,
    }


def assert_prime_invariant(before: list[Mapping[str, Any]], after: list[Mapping[str, Any]]) -> None:
    """Prove Rich Context attachment did not alter Prime ranking/probabilities."""
    fields = ("horse_id", "horse", "velo_prime_prob", "place_prob", "longshot_prob")
    left = [{key: row.get(key) for key in fields} for row in before]
    right = [{key: row.get(key) for key in fields} for row in after]
    if left != right:
        raise AssertionError("Rich Context shadow changed production Prime output")


@dataclass(frozen=True)
class FrozenModelArtifact:
    model_version: str
    protocol_hash: str
    feature_schema_hash: str
    artifact_hash: str


def score_with_frozen_artifact(packet: Mapping[str, Any], artifact: FrozenModelArtifact | None) -> dict[str, Any]:
    """Fail closed until a separately fitted, hash-verified artifact exists."""
    if artifact is None:
        return {**dict(packet), "model_status": MODEL_STATUS, "challenger_probability": None}
    raise NotImplementedError(
        "No Rich Context model artifact has been fitted or approved; scoring remains shadow-unfitted"
    )
