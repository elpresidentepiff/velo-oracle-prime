"""Load the frozen, fitted Rich Context artifact and score a shadow packet. Fails closed.

Production Prime never imports this. A score is written to the separate, append-only
``rich_context_challenger_scores`` table (see ``score_row``/``persist_scores``), never onto the packet
itself: ``rich_context_shadow_packets`` has no UPDATE grant, by design, so the packet stays untouched
evidence. A scoring failure (no artifact, corrupt artifact, incomplete packet) is reported, never guessed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.velo.rich_context_challenger_features import vector_from_packet_families

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "models" / "rich_context_challenger_v1"
MODEL_PATH = ARTIFACT_DIR / "model.joblib"
METADATA_PATH = ARTIFACT_DIR / "metadata.json"

_cache: dict[str, Any] = {}


def load_artifact(*, model_path: Path = MODEL_PATH, metadata_path: Path = METADATA_PATH) -> dict[str, Any] | None:
    """Load once and cache. Returns None (never raises) when no fitted artifact exists yet."""
    key = f"{model_path}:{metadata_path}"
    if key in _cache:
        return _cache[key]
    if not model_path.exists() or not metadata_path.exists():
        _cache[key] = None
        return None
    try:
        import joblib

        model = joblib.load(model_path)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - any load failure means "no artifact", never a guess
        _cache[key] = None
        return None
    _cache[key] = {"model": model, "metadata": metadata}
    return _cache[key]


def score_packet(packet: dict[str, Any], *, artifact: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return a scoring result for one packet, or None when the packet or artifact is not ready.

    Never mutates ``packet``; the caller decides whether/how to attach the result.
    """
    resolved = load_artifact() if artifact is None else artifact
    if not resolved or "model" not in resolved:
        return None
    vector = vector_from_packet_families(packet.get("families") or {})
    if vector is None:
        return None
    model = resolved["model"]
    probability = float(model.predict_proba([vector])[0][1])
    metadata = resolved["metadata"]
    return {
        "challenger_probability": probability,
        "model_version": metadata.get("model_version"),
        "scorer_feature_coverage": {
            "has_history": bool(vector[3]),
        },
    }


def score_row(packet: Mapping[str, Any], result: Mapping[str, Any], *, code_sha: str) -> dict[str, Any]:
    """Build one row for ``rich_context_challenger_scores`` from a packet and its ``score_packet`` result."""
    return {
        "race_date": packet["race_date"],
        "race_id": packet["race_id"],
        "horse_id": packet["horse_id"],
        "packet_input_sha256": packet.get("input_hash") or packet.get("input_sha256"),
        "model_version": result["model_version"],
        "challenger_probability": result["challenger_probability"],
        "challenger_rank": result.get("challenger_rank"),
        "production_influence": False,
        "paper_sim_only": True,
        "code_sha": code_sha or "unknown",
    }


def persist_scores(rows: list[dict[str, Any]], *, client: Any, code_sha: str) -> dict[str, int]:
    """Insert-only (unique on packet_input_sha256+model_version): no table write ever rewrites a prior score."""
    if not rows:
        return {"attempted": 0, "inserted": 0, "existing": 0}
    response = (
        client.table("rich_context_challenger_scores")
        .upsert(rows, on_conflict="packet_input_sha256,model_version", ignore_duplicates=True)
        .execute()
    )
    inserted = len(getattr(response, "data", None) or [])
    return {"attempted": len(rows), "inserted": inserted, "existing": len(rows) - inserted}


def rank_scored_packets(scored: list[tuple[Any, dict[str, Any] | None]]) -> None:
    """Set ``challenger_rank`` in place on every *result* dict in ``scored`` that exists.

    ``scored`` is a list of (packet, score_result) pairs for ONE race; only ``score_result`` (never the
    packet, which stays an untouched evidence row) is mutated. Rank 1 = highest probability. A pair with
    no score is left alone: a partial field is an honest result, not a guess at the runners the model
    could not see.
    """
    rankable = [result for _packet, result in scored if result]
    rankable.sort(key=lambda result: result["challenger_probability"], reverse=True)
    for rank, result in enumerate(rankable, start=1):
        result["challenger_rank"] = rank
