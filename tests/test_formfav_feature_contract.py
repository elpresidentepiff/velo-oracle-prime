from __future__ import annotations

import pytest
from pathlib import Path

from src.velo.formfav_feature_contract import (
    build_manifest,
    content_hash,
    project_allowed_features,
    scan_banned_fields,
    temporal_verdict,
)


def factual_packet() -> dict:
    return {
        "number": 4,
        "name": "Example Horse",
        "jockey": "A Rider",
        "trainer": "A Trainer",
        "form": "321",
        "stats": {"overall": {"starts": 10, "wins": 2, "places": 6}},
        "speedMap": {"runningStyle": "L", "earlySpeedIndex": 8},
        "classProfile": {"currentRating": 82},
    }


@pytest.mark.parametrize("payload,path", [
    ({"winProbability": 0.4}, "$.winProbability"),
    ({"nested": {"fairPrice": 2.5}}, "$.nested.fairPrice"),
    ({"rows": [{"modelRank": 1}]}, "$.rows[0].modelRank"),
    ({"decorators": [{"label": "Track specialist"}]}, "$.decorators"),
    ({"result": {"placing": 1}}, "$.result"),
])
def test_recursive_banned_fields(payload: dict, path: str) -> None:
    assert path in scan_banned_fields(payload)
    with pytest.raises(ValueError):
        project_allowed_features(payload)


def test_positive_allowlist_drops_unknown_non_predictive_fields() -> None:
    packet = {**factual_packet(), "providerInternalNote": "ignored"}
    projected = project_allowed_features(packet)
    assert "providerInternalNote" not in projected["raw_facts"]
    assert "providerInternalNote" not in projected["provider_derived_context"]
    assert projected["raw_facts"]["form"] == "321"
    assert projected["provider_derived_context"]["speedMap"]["earlySpeedIndex"] == 8


@pytest.mark.parametrize("captured,off,eligible", [
    ("2026-11-07T12:00:00Z", "2026-11-07T12:00:01Z", True),
    ("2026-11-07T12:00:00Z", "2026-11-07T12:00:00Z", False),
    ("2026-11-07T12:00:01Z", "2026-11-07T12:00:00Z", False),
    (None, "2026-11-07T12:00:00Z", False),
])
def test_temporal_boundary(captured, off, eligible) -> None:
    assert temporal_verdict(captured, off)["captured_before_off"] is eligible


def test_manifest_requires_immutable_identity_and_preoff_proof() -> None:
    manifest = build_manifest(
        raw_payload=factual_packet(),
        provider_race_key="formfav:gb:2026-11-07:test:r1",
        provider_runner_number=4,
        canonical_race_id="rp:123",
        canonical_runner_id="rp-horse:456",
        captured_at="2026-11-07T11:00:00Z",
        off_time_utc="2026-11-07T12:00:00Z",
        race_match_method="track_time_exact",
        runner_match_method="name_exact",
        parser_version="ff-contract-1",
        source_is_immutable=True,
    )
    assert manifest["training_eligible"] is True
    assert manifest["banned_field_paths"] == []
    assert len(manifest["raw_payload_hash"]) == 64
    assert manifest["derived_vector_hash"] == content_hash(manifest["families"])


def test_mutable_current_cache_row_is_evaluation_ineligible() -> None:
    manifest = build_manifest(
        raw_payload=factual_packet(), provider_race_key="ff:r1", provider_runner_number=4,
        canonical_race_id="rp:r1", canonical_runner_id="rp:h1",
        captured_at="2026-11-07T11:00:00Z", off_time_utc="2026-11-07T12:00:00Z",
        race_match_method="exact", runner_match_method="exact",
        parser_version="ff-contract-1", source_is_immutable=False,
    )
    assert manifest["training_eligible"] is False


def test_immutable_migration_is_service_role_only_and_append_only() -> None:
    migration = Path("supabase/migrations/20261107090000_formfav_factual_immutable_captures.sql").read_text()
    lowered = migration.lower()
    assert "enable row level security" in lowered
    assert "revoke all on public.formfav_factual_captures from anon, authenticated" in lowered
    assert "grant select, insert on public.formfav_factual_captures to service_role" in lowered
    assert "before update or delete on public.formfav_factual_captures" in lowered
    assert "before update or delete on public.formfav_rich_context_manifests" in lowered
    assert "revoke all on function public.reject_formfav_evidence_mutation() from public, anon, authenticated" in lowered
    assert "grant update" not in lowered
    assert "grant delete" not in lowered
