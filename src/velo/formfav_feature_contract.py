"""Time-safe FormFav factual feature contract for Rich Context challengers.

This module deliberately does not score a horse.  It separates provider facts
and provider-derived context from FormFav's predictions and refuses any packet
whose identity or capture time cannot be proven before the race off.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Mapping

SCHEMA_VERSION = "FORMFAV_FACTUAL_V1"

RAW_FACT_FIELDS = frozenset({
    "number", "name", "scratched", "jockey", "trainer", "weightKg",
    "claimKg", "barrier", "age", "sex", "sire", "dam", "country",
    "form", "last20Starts", "stats",
})

DERIVED_CONTEXT_FIELDS = frozenset({
    "speedMap", "classProfile", "raceClassFit", "paceScenario",
    "trackBias",
})

BANNED_KEY_TOKENS = frozenset({
    "prediction", "predictions", "probability", "winprobability",
    "placeprobability", "modelrank", "selected", "selection", "tophorse",
    "confidence", "recommendation", "recommendedbet", "predictedorder",
    "edge", "fairprice", "fairprobability", "pricerank", "modelversion",
    "decorator", "decorators", "badge", "badges", "result", "results",
    "placing", "placings", "margin", "margins", "officialsp", "sp",
})


def _normalise_key(value: Any) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def scan_banned_fields(value: Any, path: str = "$") -> list[str]:
    """Return every recursively banned key path in a provider packet."""
    hits: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            child = f"{path}.{key}"
            normalised = _normalise_key(key)
            if normalised in BANNED_KEY_TOKENS or any(
                len(token) > 3 and normalised.startswith(token) for token in BANNED_KEY_TOKENS
            ):
                hits.append(child)
            hits.extend(scan_banned_fields(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            hits.extend(scan_banned_fields(nested, f"{path}[{index}]"))
    return sorted(set(hits))


def project_allowed_features(packet: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Positive-allowlist a packet into raw and provider-derived families."""
    banned = scan_banned_fields(packet)
    if banned:
        raise ValueError("FormFav predictive/outcome fields are forbidden: " + ", ".join(banned))
    return {
        "raw_facts": {key: packet.get(key) for key in sorted(RAW_FACT_FIELDS) if key in packet},
        "provider_derived_context": {
            key: packet.get(key) for key in sorted(DERIVED_CONTEXT_FIELDS) if key in packet
        },
    }


def temporal_verdict(captured_at: Any, off_time_utc: Any) -> dict[str, Any]:
    captured = parse_timestamp(captured_at)
    off = parse_timestamp(off_time_utc)
    eligible = bool(captured and off and captured < off)
    reason = (
        "captured_before_off" if eligible else
        "missing_capture_time" if captured is None else
        "missing_off_time" if off is None else
        "captured_at_or_after_off"
    )
    return {
        "captured_at": captured.isoformat() if captured else None,
        "off_time_utc": off.isoformat() if off else None,
        "captured_before_off": eligible,
        "temporal_eligibility": "ELIGIBLE" if eligible else "INELIGIBLE",
        "temporal_reason": reason,
    }


def build_manifest(
    *, raw_payload: Mapping[str, Any], provider_race_key: str,
    provider_runner_number: int, canonical_race_id: str,
    canonical_runner_id: str | None, captured_at: Any, off_time_utc: Any,
    race_match_method: str, runner_match_method: str, parser_version: str,
    source_is_immutable: bool,
) -> dict[str, Any]:
    """Build a deterministic eligibility manifest; never infer missing proof."""
    families = project_allowed_features(raw_payload)
    temporal = temporal_verdict(captured_at, off_time_utc)
    banned = scan_banned_fields(raw_payload)
    identity_ok = bool(
        provider_race_key and canonical_race_id and canonical_runner_id
        and race_match_method and runner_match_method
    )
    eligible = bool(source_is_immutable and identity_ok and temporal["captured_before_off"] and not banned)
    missingness = {
        family: sorted(key for key, value in values.items() if value in (None, "", [], {}))
        for family, values in families.items()
    }
    vector_hash = content_hash(families)
    return {
        "feature_schema_version": SCHEMA_VERSION,
        "parser_version": parser_version,
        "provider": "formfav",
        "provider_race_key": provider_race_key,
        "provider_runner_number": provider_runner_number,
        "canonical_race_id": canonical_race_id,
        "canonical_runner_id": canonical_runner_id,
        "race_match_method": race_match_method,
        "runner_match_method": runner_match_method,
        "source_is_immutable": source_is_immutable,
        "raw_payload_hash": content_hash(raw_payload),
        "derived_vector_hash": vector_hash,
        "families": families,
        "family_coverage": {name: len(values) for name, values in families.items()},
        "missingness": missingness,
        "banned_field_paths": banned,
        **temporal,
        "training_eligible": eligible,
        "eligibility_reason": "eligible" if eligible else "provenance_identity_or_time_gate_failed",
    }
