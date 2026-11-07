"""Append-only persistence for time-safe FormFav factual evidence.

This store never accepts provider predictions, prices or outcomes.  The live
worker freezes positive-allowlisted factual packets before the off; the UK
shadow job later binds those captures to canonical RP identities and appends
an auditable Rich Context manifest.
"""
from __future__ import annotations

import json
import subprocess
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from src.velo.formfav_feature_contract import (
    SCHEMA_VERSION,
    build_manifest,
    content_hash,
    project_allowed_features,
)

PARSER_VERSION = "formfav-factual-writer-v1"


def factual_packet(runner: Mapping[str, Any], race_form: Mapping[str, Any]) -> dict[str, Any]:
    """Return only explicitly allowed facts; aliases are normalised here."""
    candidate = {
        "number": runner.get("number"),
        "name": runner.get("name"),
        "scratched": bool(runner.get("scratched")),
        "jockey": runner.get("jockey"),
        "trainer": runner.get("trainer"),
        "weightKg": runner.get("weightKg", runner.get("weight")),
        "claimKg": runner.get("claimKg", runner.get("claim")),
        "barrier": runner.get("barrier"),
        "age": runner.get("age"),
        "sex": runner.get("sex"),
        "sire": runner.get("sire"),
        "dam": runner.get("dam"),
        "country": runner.get("country"),
        "form": runner.get("form"),
        "last20Starts": runner.get("last20Starts"),
        "stats": runner.get("stats"),
        "speedMap": runner.get("speedMap"),
        "classProfile": runner.get("classProfile"),
        "raceClassFit": runner.get("raceClassFit"),
        "paceScenario": race_form.get("paceScenario"),
        "trackBias": runner.get("trackBias"),
    }
    packet = {key: value for key, value in candidate.items() if value is not None}
    # Defensive recursive scan: this raises if a provider ever nests a banned
    # prediction/outcome key inside an otherwise allowed object such as stats.
    project_allowed_features(packet)
    return packet


def build_capture_rows(
    *, provider_race_key: str, form: Mapping[str, Any], captured_at: datetime,
    off_time_utc: datetime, source_endpoint: str = "formfav:/form",
) -> list[dict[str, Any]]:
    """Build immutable rows only when the capture is strictly pre-off."""
    captured = captured_at.astimezone(UTC)
    off = off_time_utc.astimezone(UTC)
    if captured >= off:
        return []
    rows: list[dict[str, Any]] = []
    for runner in form.get("runners") or []:
        if not isinstance(runner, Mapping) or runner.get("number") is None or not runner.get("name"):
            continue
        packet = factual_packet(runner, form)
        rows.append({
            "provider_race_key": provider_race_key,
            "provider_runner_number": int(runner["number"]),
            "provider_runner_name": str(runner["name"]),
            "captured_at": captured.isoformat(),
            "off_time_utc": off.isoformat(),
            "source_endpoint": source_endpoint,
            "source_payload": packet,
            "source_payload_sha256": content_hash(packet),
            "capture_schema_version": SCHEMA_VERSION,
        })
    return rows


def persist_capture_rows(
    rows: list[dict[str, Any]], *, request: Callable[..., bytes],
) -> list[dict[str, Any]]:
    if not rows:
        return []
    conflict = (
        "provider_race_key,provider_runner_number,captured_at,source_payload_sha256"
    )
    path = "formfav_factual_captures?" + urllib.parse.urlencode({"on_conflict": conflict})
    body = request(
        "POST",
        path,
        rows,
        "resolution=ignore-duplicates,return=representation",
    )
    decoded = json.loads(body.decode("utf-8") or "[]")
    inserted = decoded if isinstance(decoded, list) else []
    by_key = {_capture_key(row): row for row in inserted if row.get("id") is not None}
    # An ignored duplicate returns no representation. Recover its immutable ID
    # through the exact deployed four-column unique key so retries can still
    # bind manifests to the original capture.
    for row in rows:
        key = _capture_key(row)
        if key in by_key:
            continue
        filters = urllib.parse.urlencode({
            "provider_race_key": f"eq.{row['provider_race_key']}",
            "provider_runner_number": f"eq.{row['provider_runner_number']}",
            "captured_at": f"eq.{row['captured_at']}",
            "source_payload_sha256": f"eq.{row['source_payload_sha256']}",
            "select": "id,provider_race_key,provider_runner_number,provider_runner_name,captured_at,off_time_utc,source_endpoint,source_payload,source_payload_sha256,capture_schema_version",
            "limit": "1",
        })
        recovered_body = request("GET", f"formfav_factual_captures?{filters}")
        recovered = json.loads(recovered_body.decode("utf-8") or "[]")
        if not isinstance(recovered, list) or len(recovered) != 1:
            raise RuntimeError("immutable FormFav capture ID recovery failed")
        by_key[key] = recovered[0]
    return [by_key[_capture_key(row)] for row in rows]


def _capture_key(row: Mapping[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        row.get("provider_race_key"),
        row.get("provider_runner_number"),
        row.get("captured_at"),
        row.get("source_payload_sha256"),
    )


def code_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, timeout=5
        ).strip()
    except Exception:
        return "unknown"


def build_manifest_rows(enriched_races: list[dict[str, Any]], *, sha: str | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    stats = {"eligible": 0, "ineligible": 0, "skipped_no_capture": 0, "skipped_identity": 0}
    for race in enriched_races:
        race_ff = race.get("_formfav") or {}
        canonical_race_id = str(race.get("race_id") or "").strip()
        for runner in race.get("runners") or []:
            ff = runner.get("_formfav") or {}
            provenance = ff.get("provenance") or {}
            capture_id = provenance.get("capture_id")
            if not capture_id:
                stats["skipped_no_capture"] += 1
                continue
            canonical_runner_id = str(runner.get("horse_id") or "").strip()
            if not canonical_race_id or not canonical_runner_id:
                stats["skipped_identity"] += 1
                continue
            raw = {key: value for key, value in ff.items() if key not in {"market", "identity_match_method", "provenance"}}
            if race_ff.get("paceScenario") is not None:
                raw["paceScenario"] = race_ff["paceScenario"]
            if race_ff.get("trackBias") is not None:
                raw["trackBias"] = race_ff["trackBias"]
            manifest = build_manifest(
                raw_payload=raw,
                provider_race_key=str(provenance.get("provider_race_key") or ""),
                provider_runner_number=int(ff.get("number")),
                canonical_race_id=canonical_race_id,
                canonical_runner_id=canonical_runner_id,
                captured_at=provenance.get("captured_at"),
                off_time_utc=provenance.get("off_time_utc"),
                race_match_method=str(race_ff.get("identity_match_method") or ""),
                runner_match_method=str(ff.get("identity_match_method") or ""),
                parser_version=PARSER_VERSION,
                source_is_immutable=bool(provenance.get("source_is_immutable")),
            )
            rows.append({
                "capture_id": int(capture_id),
                "canonical_race_id": canonical_race_id,
                "canonical_runner_id": canonical_runner_id,
                "race_match_method": manifest["race_match_method"],
                "runner_match_method": manifest["runner_match_method"],
                "off_time_utc": manifest["off_time_utc"],
                "captured_before_off": manifest["captured_before_off"],
                "temporal_eligibility": manifest["temporal_eligibility"],
                "identity_conflicts": [],
                "feature_schema_version": manifest["feature_schema_version"],
                "parser_version": manifest["parser_version"],
                "feature_families": manifest["families"],
                "family_coverage": manifest["family_coverage"],
                "missingness": manifest["missingness"],
                "banned_field_paths": manifest["banned_field_paths"],
                "derived_vector_sha256": manifest["derived_vector_hash"],
                "training_eligible": manifest["training_eligible"],
                "eligibility_reason": manifest["eligibility_reason"],
                "code_sha": sha or code_sha(),
            })
            stats["eligible" if manifest["training_eligible"] else "ineligible"] += 1
    return rows, stats


def persist_manifest_rows(
    rows: list[dict[str, Any]], *, request: Callable[..., bytes],
) -> dict[str, int]:
    report = {"attempted": len(rows), "inserted": 0, "existing": 0}
    if not rows:
        return report
    conflict = (
        "capture_id,canonical_race_id,canonical_runner_id,"
        "feature_schema_version,parser_version"
    )
    path = "formfav_rich_context_manifests?" + urllib.parse.urlencode({"on_conflict": conflict})
    body = request(
        "POST",
        path,
        rows,
        "resolution=ignore-duplicates,return=representation",
    )
    decoded = json.loads(body.decode("utf-8") or "[]")
    report["inserted"] = len(decoded) if isinstance(decoded, list) else 0
    report["existing"] = report["attempted"] - report["inserted"]
    return report
