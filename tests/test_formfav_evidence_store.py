from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.velo.formfav_evidence_store import (
    build_capture_rows,
    build_manifest_rows,
    factual_packet,
    persist_capture_rows,
    persist_manifest_rows,
)


def test_capture_writer_positive_allowlists_and_freezes_preoff() -> None:
    form = {
        "paceScenario": "FAST",
        "predictions": [{"name": "Never persist me"}],
        "runners": [{
            "number": 4, "name": "Example", "weight": 56.5, "form": "321",
            "stats": {"overall": {"starts": 8, "wins": 2}},
            "speedMap": {"runningStyle": "L"},
        }],
    }
    rows = build_capture_rows(
        provider_race_key="formfav:gb:2026-11-07:test:r1",
        form=form,
        captured_at=datetime(2026, 11, 7, 11, tzinfo=UTC),
        off_time_utc=datetime(2026, 11, 7, 12, tzinfo=UTC),
    )
    assert len(rows) == 1
    packet = rows[0]["source_payload"]
    assert packet["weightKg"] == 56.5 and packet["paceScenario"] == "FAST"
    assert "predictions" not in packet
    assert len(rows[0]["source_payload_sha256"]) == 64


def test_capture_writer_refuses_nested_prediction_and_postoff() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        factual_packet(
            {"number": 1, "name": "A", "stats": {"winProbability": 0.9}},
            {},
        )
    assert build_capture_rows(
        provider_race_key="ff:r1",
        form={"runners": [{"number": 1, "name": "A"}]},
        captured_at=datetime(2026, 11, 7, 12, tzinfo=UTC),
        off_time_utc=datetime(2026, 11, 7, 12, tzinfo=UTC),
    ) == []


def test_capture_persistence_requests_representation() -> None:
    calls = []
    row = {
        "provider_race_key": "ff:r1", "provider_runner_number": 1,
        "captured_at": "2026-11-07T11:00:00+00:00", "source_payload_sha256": "a" * 64,
    }
    def request(method, path, data=None, prefer=None):
        calls.append((method, path, data, prefer))
        return json.dumps([{"id": 77, **data[0]}]).encode()
    frozen = persist_capture_rows([row], request=request)
    assert frozen[0]["id"] == 77
    assert calls[0][0] == "POST" and calls[0][1].startswith("formfav_factual_captures?on_conflict=")
    assert calls[0][3] == "resolution=ignore-duplicates,return=representation"


def test_capture_exact_retry_recovers_original_id() -> None:
    row = {
        "provider_race_key": "ff:r1", "provider_runner_number": 1,
        "captured_at": "2026-11-07T11:00:00+00:00", "source_payload_sha256": "b" * 64,
    }
    calls = []
    def request(method, path, data=None, prefer=None):
        calls.append((method, path, data, prefer))
        if method == "POST":
            return b"[]"  # unique conflict ignored on exact retry
        assert "provider_race_key=eq.ff%3Ar1" in path
        assert "source_payload_sha256=eq." + ("b" * 64) in path
        return json.dumps([{"id": 91, **row}]).encode()
    recovered = persist_capture_rows([row], request=request)
    assert recovered == [{"id": 91, **row}]
    assert [call[0] for call in calls] == ["POST", "GET"]


def test_manifest_binding_requires_immutable_capture_and_canonical_ids() -> None:
    race = {
        "race_id": "rp:r1",
        "_formfav": {"identity_match_method": "track_time"},
        "runners": [{
            "horse_id": "rp:h1", "horse": "Example",
            "_formfav": {
                "number": 4, "name": "Example", "form": "321",
                "identity_match_method": "name_exact",
                "provenance": {
                    "capture_id": 77,
                    "provider_race_key": "ff:r1",
                    "captured_at": "2026-11-07T11:00:00+00:00",
                    "off_time_utc": "2026-11-07T12:00:00+00:00",
                    "source_is_immutable": True,
                },
            },
        }],
    }
    rows, stats = build_manifest_rows([race], sha="abc123")
    assert len(rows) == 1 and rows[0]["training_eligible"] is True
    assert rows[0]["capture_id"] == 77 and rows[0]["code_sha"] == "abc123"
    assert stats["eligible"] == 1


def test_manifest_duplicate_rerun_reports_existing_truthfully() -> None:
    row = {"capture_id": 77, "canonical_race_id": "rp:r1", "canonical_runner_id": "rp:h1",
           "feature_schema_version": "FORMFAV_FACTUAL_V1", "parser_version": "v1"}
    responses = iter([json.dumps([{"id": 1}]).encode(), b"[]"])
    def request(method, path, data=None, prefer=None):
        assert method == "POST" and "on_conflict=" in path
        assert prefer == "resolution=ignore-duplicates,return=representation"
        return next(responses)
    assert persist_manifest_rows([row], request=request) == {
        "attempted": 1, "inserted": 1, "existing": 0,
    }
    assert persist_manifest_rows([row], request=request) == {
        "attempted": 1, "inserted": 0, "existing": 1,
    }
