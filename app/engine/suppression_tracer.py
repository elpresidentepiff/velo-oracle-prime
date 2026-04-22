"""
VÉLØ Suppression Tracer
========================
Records exactly which layer blocked or passed each bet for every race.

Written to:  logs/suppression_trace_YYYY-MM-DD.jsonl
Also written to Supabase table `suppression_trace` when available.

Each record:
  race_id, runner_id, horse_name, engine_mode,
  sqpe_prob, layer_blocked, block_reason,
  would_have_won (filled in post-race by sigma)
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LOG_DIR = Path("logs")


def _trace_path() -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    return LOG_DIR / f"suppression_trace_{datetime.now():%Y-%m-%d}.jsonl"


def record(
    race_id: str,
    runner_id: str,
    horse_name: str,
    engine_mode: str,
    sqpe_prob: float,
    layer_blocked: str | None,       # None = not blocked (bet fired)
    block_reason: str = "",
    prod_chassis: str = "",
    direct_chassis: str = "",
    extra: dict[str, Any] | None = None,
) -> dict:
    """Write one suppression trace record."""
    record = {
        "ts": datetime.now().isoformat(),
        "race_id": race_id,
        "runner_id": runner_id,
        "horse_name": horse_name,
        "engine_mode": engine_mode,
        "sqpe_prob": round(sqpe_prob, 4),
        "layer_blocked": layer_blocked,
        "block_reason": block_reason,
        "prod_chassis": prod_chassis,
        "direct_chassis": direct_chassis,
        "would_have_won": None,   # filled post-race by sigma
        **(extra or {}),
    }

    try:
        with open(_trace_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.warning(f"[tracer] Failed to write trace record: {e}")

    return record


def load_traces(date: str | None = None) -> list[dict]:
    """Load all trace records for a given date (default: today)."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    path = LOG_DIR / f"suppression_trace_{date}.jsonl"
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def summarise(date: str | None = None) -> dict:
    """Quick summary of suppression for a given date."""
    traces = load_traces(date)
    if not traces:
        return {"date": date, "total": 0}

    total = len(traces)
    blocked = [t for t in traces if t.get("layer_blocked")]
    passed  = [t for t in traces if not t.get("layer_blocked")]

    layer_counts: dict[str, int] = {}
    for t in blocked:
        layer = t.get("layer_blocked", "unknown")
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    return {
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "total_runners_evaluated": total,
        "bets_fired": len(passed),
        "bets_suppressed": len(blocked),
        "suppression_rate": round(len(blocked) / total, 3) if total else 0,
        "suppression_by_layer": layer_counts,
        "avg_sqpe_prob_blocked": round(
            sum(t["sqpe_prob"] for t in blocked) / len(blocked), 4
        ) if blocked else 0,
        "avg_sqpe_prob_passed": round(
            sum(t["sqpe_prob"] for t in passed) / len(passed), 4
        ) if passed else 0,
    }
