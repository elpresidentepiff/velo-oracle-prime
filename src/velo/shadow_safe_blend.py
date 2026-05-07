"""
shadow_safe_blend.py

V3 SHADOW_SAFE_BLEND — SQPE 70% / MDS 30%

Formula:
  safe_blend_v3_score = 0.70 * sqpe_v17_prob + 0.30 * market_deception_score

This module is SHADOW ONLY.

Hard constraints:
- Does NOT modify live velo_prime_prob
- Does NOT affect candidate_execution_allowed
- Does NOT affect router decisions
- Does NOT trigger staking or Telegram betting alerts
- Zero production scoring side effect

Evidence basis (2026-05-07 simulation, n=321 at VP>=0.25):
  V0 current blend: SR=26.48%  ROI=-24.38%
  V3 SQPE+MDS only: SR=27.10%  ROI=-7.79%  (+16.59pp ROI)
"""
from __future__ import annotations

import csv
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

V3_VERSION     = "v1_sqpe70_mds30"
V3_STATUS      = "SHADOW_ONLY"
_SQPE_WEIGHT   = 0.70
_MDS_WEIGHT    = 0.30

ROOT       = Path(__file__).resolve().parents[2]
LEDGER_CSV = ROOT / "data" / "safe_blend_v3_shadow_ledger.csv"

_LEDGER_COLS = [
    "date", "race_id", "course", "off_time", "race_name",
    "live_top_horse", "live_top_horse_id", "live_top_vp",
    "safe_v3_top_horse", "safe_v3_top_horse_id", "safe_v3_score",
    "changed_top_selection", "live_top_tier", "safe_v3_status",
    "result_position_live_top", "result_position_safe_v3",
    "won_live_top", "won_safe_v3",
    "placed_live_top", "placed_safe_v3",
    "sp_live_top", "sp_safe_v3",
    "profit_loss_live_top", "profit_loss_safe_v3",
]


def compute_safe_blend_v3(predictions: list[dict]) -> dict:
    """
    Score a race's runners under V3 and return a shadow annotation dict.

    Args:
        predictions: list of runner prediction dicts (from score_race_velo_prime).
                     Each must have: horse, horse_id (or race_id), sqpe_v17_prob,
                     market_deception_score, velo_prime_prob.

    Returns dict with:
        safe_blend_v3_score            float
        safe_blend_v3_rank             int  (1 = top)
        safe_blend_v3_top_pick         str  horse name
        safe_blend_v3_top_horse_id     str
        safe_blend_v3_delta_vs_live_vp float
        safe_blend_v3_changes_top_selection bool
        safe_blend_v3_status           str  always SHADOW_ONLY
        safe_blend_v3_version          str
    """
    if not predictions:
        return _empty_annotation()

    scored = []
    for i, p in enumerate(predictions):
        try:
            sqpe = float(p.get("sqpe_v17_prob") or 0)
        except (ValueError, TypeError):
            sqpe = 0.0
        try:
            mds = float(p.get("market_deception_score") or 0)
        except (ValueError, TypeError):
            mds = 0.0
        v3 = _SQPE_WEIGHT * sqpe + _MDS_WEIGHT * mds
        scored.append((v3, i, p))

    scored.sort(key=lambda x: -x[0])
    top_score, _, top_pred = scored[0]

    live_top = predictions[0]
    try:
        live_vp = float(live_top.get("velo_prime_prob") or 0)
    except (ValueError, TypeError):
        live_vp = 0.0

    changed = top_pred.get("horse", "") != live_top.get("horse", "")

    return {
        "safe_blend_v3_score":               round(top_score, 6),
        "safe_blend_v3_rank":                1,
        "safe_blend_v3_top_pick":            top_pred.get("horse", ""),
        "safe_blend_v3_top_horse_id":        top_pred.get("horse_id", ""),
        "safe_blend_v3_delta_vs_live_vp":    round(top_score - live_vp, 6),
        "safe_blend_v3_changes_top_selection": changed,
        "safe_blend_v3_status":              V3_STATUS,
        "safe_blend_v3_version":             V3_VERSION,
    }


def _empty_annotation() -> dict:
    return {
        "safe_blend_v3_score": 0.0,
        "safe_blend_v3_rank": 0,
        "safe_blend_v3_top_pick": "",
        "safe_blend_v3_top_horse_id": "",
        "safe_blend_v3_delta_vs_live_vp": 0.0,
        "safe_blend_v3_changes_top_selection": False,
        "safe_blend_v3_status": V3_STATUS,
        "safe_blend_v3_version": V3_VERSION,
    }


def append_to_shadow_ledger(
    *,
    date_str: str,
    race_id: str,
    course: str,
    off_time: str,
    race_name: str,
    live_top_horse: str,
    live_top_horse_id: str,
    live_top_vp: float,
    live_top_tier: str,
    safe_v3_top_horse: str,
    safe_v3_top_horse_id: str,
    safe_v3_score: float,
    changed_top_selection: bool,
    ledger_path: Path | None = None,
) -> None:
    """
    Append (or update) one row in the V3 shadow ledger.

    Idempotency key: (date, race_id, safe_blend_v3_version).
    If a row for this key exists, it is updated in-place.
    Result columns (won_live_top, sp_*, etc.) are left blank until sigma fills them.
    """
    path = ledger_path or LEDGER_CSV
    path.parent.mkdir(parents=True, exist_ok=True)

    idem_key = (date_str, race_id, V3_VERSION)

    existing: list[dict] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))

    new_row = {
        "date":                    date_str,
        "race_id":                 race_id,
        "course":                  course,
        "off_time":                off_time,
        "race_name":               race_name,
        "live_top_horse":          live_top_horse,
        "live_top_horse_id":       live_top_horse_id,
        "live_top_vp":             str(round(live_top_vp, 6)),
        "safe_v3_top_horse":       safe_v3_top_horse,
        "safe_v3_top_horse_id":    safe_v3_top_horse_id,
        "safe_v3_score":           str(round(safe_v3_score, 6)),
        "changed_top_selection":   str(changed_top_selection),
        "live_top_tier":           live_top_tier,
        "safe_v3_status":          V3_STATUS,
        # result columns — filled by sigma close
        "result_position_live_top":  "",
        "result_position_safe_v3":   "",
        "won_live_top":              "",
        "won_safe_v3":               "",
        "placed_live_top":           "",
        "placed_safe_v3":            "",
        "sp_live_top":               "",
        "sp_safe_v3":                "",
        "profit_loss_live_top":      "",
        "profit_loss_safe_v3":       "",
    }

    # Update existing row if idempotency key matches
    matched = False
    for row in existing:
        if (row.get("date"), row.get("race_id"), row.get("safe_v3_status", "")) == idem_key[:2] + (V3_STATUS,):
            # More precise: match date + race_id
            if row.get("date") == date_str and row.get("race_id") == race_id:
                for k, v in new_row.items():
                    if v != "":  # don't overwrite filled result columns
                        row[k] = v
                matched = True
                break

    if not matched:
        existing.append(new_row)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_LEDGER_COLS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existing)
