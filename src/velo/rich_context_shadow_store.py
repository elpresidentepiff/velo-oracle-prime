"""Append-only persistence for Rich Context shadow evidence packets."""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def packet_row(packet: Mapping[str, Any], *, code_sha: str) -> dict[str, Any]:
    return {
        "race_date": packet["race_date"],
        "race_id": packet["race_id"],
        "horse_id": packet["horse_id"],
        "packet_schema_version": packet["packet_schema_version"],
        "challenger_version": packet["challenger_version"],
        "model_status": packet["model_status"],
        "input_sha256": packet["input_hash"],
        "feature_vector_sha256": packet["feature_vector_hash"],
        "family_coverage": packet["family_coverage"],
        "provenance": packet["provenance"],
        "feature_families": packet["families"],
        "eligible_for_future_fit": packet["eligible_for_future_fit"],
        "ineligibility_reasons": packet["ineligibility_reasons"],
        "challenger_probability": packet["challenger_probability"],
        "challenger_rank": packet["challenger_rank"],
        "production_influence": False,
        "provider_predictions_consumed": False,
        "paper_sim_only": True,
        "code_sha": code_sha or "unknown",
    }


def write_local_jsonl(
    packets: Iterable[Mapping[str, Any]], *, output_path: Path, code_sha: str
) -> int:
    rows = [packet_row(packet, code_sha=code_sha) for packet in packets]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return len(rows)


def persist_supabase_rows(
    packets: Iterable[Mapping[str, Any]], *, client: Any, code_sha: str
) -> dict[str, int]:
    rows = [packet_row(packet, code_sha=code_sha) for packet in packets]
    if not rows:
        return {"attempted": 0, "inserted": 0, "existing": 0}
    response = (
        client.table("rich_context_shadow_packets")
        .upsert(rows, on_conflict="race_id,horse_id,input_sha256", ignore_duplicates=True)
        .execute()
    )
    inserted = len(getattr(response, "data", None) or [])
    return {"attempted": len(rows), "inserted": inserted, "existing": len(rows) - inserted}
