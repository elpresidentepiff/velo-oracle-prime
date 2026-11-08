"""Load the frozen, fitted Rich Context artifact and score a shadow packet. Fails closed.

Production Prime never imports this. Scoring a packet only sets ``challenger_probability`` /
``challenger_rank`` fields on the packet's own row; it never reads or writes a Prime field, and a scoring
failure (no artifact, corrupt artifact, incomplete packet) is reported, never guessed.
"""

from __future__ import annotations

import json
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


def rank_scored_packets(scored: list[tuple[dict[str, Any], dict[str, Any] | None]]) -> None:
    """Set ``challenger_rank`` in place on every packet in ``scored`` that has a probability.

    ``scored`` is a list of (packet, score_result) pairs for ONE race. Rank 1 = highest probability.
    Packets with no score keep ``challenger_rank = None``: a partial field is an honest result, not a
    guess at the runners the model could not see.
    """
    rankable = [(packet, result["challenger_probability"]) for packet, result in scored if result]
    rankable.sort(key=lambda pair: pair[1], reverse=True)
    for rank, (packet, _prob) in enumerate(rankable, start=1):
        packet["challenger_rank"] = rank
