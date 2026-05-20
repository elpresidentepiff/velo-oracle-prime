"""
VÉLØ Runner Snapshot Store — Issue #80.

Persists full per-runner prediction snapshots for every scored race.
Storage only — never modifies scoring, routing, or execution.

Output:
  - Local JSONL: data/runner_snapshots_YYYY_MM_DD.jsonl  (primary)
  - Supabase: runner_prediction_snapshots table          (best-effort, fails silently)

Hard constraints (permanent — never override):
  live_scoring_changed = False  always
  execution_allowed    = False  always
  write failure        = warning only, never raises into scoring path
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_SNAPSHOT_DIR = Path("data")

# Fields extracted from each runner pred dict
_PRED_FIELDS = [
    "horse",
    "horse_id",
    "velo_prime_prob",
    "sqpe_v17_prob",
    "market_deception_score",
    "improvement_score",
    "place_prob",
    "longshot_prob",
    "release_day_prob",
    "comment_intel_score",
    "mark_compression_score",
    "spotlight_score",
    "postdata_score",
    "plot_conviction",
    "cash_run_flag",
    "setup_run_flag",
    "decoy_support_flag",
    "rpd_tag",
    "rpd_confidence",
    "rpd_evidence_codes",
    "rpdc_primary_tag",
    "rpdc_release_score",
    "rpdc_cash_window_flag",
    "rpdc_tags",
    "tie_gate_fires",
    "tie_gate_tier_upgrade",
    "active_components",
    "excluded_from_ensemble",
    "assigned_product",
    "confidence_level",
    "decision_tier",
    "execution_allowed",
    "race_archetype",
    "archetype_confidence",
    "router_reasons",
    "sp_dec",
    "is_fav",
]

# Safety invariants written on every snapshot row
_LIVE_SCORING_CHANGED = False
_WRITE_EXECUTION_ALLOWED = False


def _build_snapshot_row(
    pred: dict[str, Any],
    rank: int,
    race_id: str,
    race_date: str,
    course: str,
    off_time: str,
    tier: str,
    top_pick_name: str,
    top_pick_vp: float | None,
    created_at: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "created_at": created_at,
        "race_date": race_date,
        "race_id": race_id,
        "course": course,
        "off_time": off_time,
        "tier": tier,
        "rank": rank,
        "top_pick_name": top_pick_name,
        "top_pick_vp": top_pick_vp,
        "prob_gap": (
            round((top_pick_vp or 0.0) - float(pred.get("velo_prime_prob") or 0.0), 6)
            if rank > 0
            else 0.0
        ),
        "live_scoring_changed": _LIVE_SCORING_CHANGED,
        "write_execution_allowed": _WRITE_EXECUTION_ALLOWED,
    }
    for field in _PRED_FIELDS:
        row[field] = pred.get(field)
    return row


def write_runner_snapshots(
    scored: list[tuple[dict, list[dict], str, list]],
    date_str: str,
    date_tag: str,
    snapshot_dir: Path | str | None = None,
    supabase_client: Any | None = None,
) -> int:
    """
    Batch-write full per-runner prediction snapshots for all scored races.

    Args:
        scored: list of (race, preds, tier, reasons) tuples from the scoring loop.
        date_str: ISO date string e.g. "2026-05-20".
        date_tag: underscore date tag e.g. "2026_05_20" for filenames.
        snapshot_dir: override for data/ directory path.
        supabase_client: optional live Supabase client for DB write.

    Returns:
        Number of runner rows written to local JSONL. 0 on total failure.

    Never raises — all errors are logged as warnings.
    """
    created_at = datetime.now(tz=UTC).isoformat()
    rows: list[dict[str, Any]] = []

    for race, preds, tier, _reasons in scored:
        if not preds:
            continue
        race_id = race.get("race_id", "")
        course = race.get("course", "")
        off_time = race.get("off_time", "")
        top = preds[0]
        top_pick_name: str = top.get("horse", "")
        top_pick_vp: float | None = top.get("velo_prime_prob")

        for rank, pred in enumerate(preds):
            rows.append(
                _build_snapshot_row(
                    pred=pred,
                    rank=rank,
                    race_id=race_id,
                    race_date=date_str,
                    course=course,
                    off_time=off_time,
                    tier=tier,
                    top_pick_name=top_pick_name,
                    top_pick_vp=top_pick_vp,
                    created_at=created_at,
                )
            )

    if not rows:
        log.warning("runner_snapshot_store: no rows to write")
        return 0

    written = _write_local_jsonl(rows, date_tag, snapshot_dir)
    _write_supabase(rows, supabase_client)
    return written


def _write_local_jsonl(
    rows: list[dict[str, Any]],
    date_tag: str,
    snapshot_dir: Path | str | None,
) -> int:
    try:
        base = Path(snapshot_dir or _DEFAULT_SNAPSHOT_DIR)
        base.mkdir(parents=True, exist_ok=True)
        out_path = base / f"runner_snapshots_{date_tag}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, default=str) + "\n")
        log.info("runner_snapshot_store: wrote %d rows → %s", len(rows), out_path.name)
        return len(rows)
    except Exception as exc:
        log.warning("runner_snapshot_store: local JSONL write failed: %s", exc)
        return 0


def _write_supabase(
    rows: list[dict[str, Any]],
    supabase_client: Any | None,
) -> None:
    if supabase_client is None:
        return
    try:
        supabase_client.table("runner_prediction_snapshots").insert(rows).execute()
        log.info("runner_snapshot_store: upserted %d rows to Supabase", len(rows))
    except Exception as exc:
        log.warning("runner_snapshot_store: Supabase write failed (non-fatal): %s", exc)
