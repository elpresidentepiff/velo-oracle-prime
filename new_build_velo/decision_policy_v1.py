"""
New Build Decision Policy V1

A lane classifier that sits on top of Champion V1 predictions.
Does NOT change the champion model — applies operator decision rules only.

Lanes:
  WIN_TRUST   — high probability, good passport, velocity consistent
  FRAME_TRUST — moderate probability, form velocity suggests place/frame
  NO_EDGE     — scored, no actionable signal (hold)
  LOW_DATA    — insufficient passport/profile data to trust signal
  SUPPRESS    — actively suppress (low probability, weak profile)

Usage:
  from new_build_velo.decision_policy_v1 import classify_predictions
  rows = classify_predictions(pred_rows, v3_lookup_path=..., race_date="2026-06-03")
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V3_TR_PATH = ROOT / "data" / "new_build" / "training" / "v3_velocity_candidates_train.parquet"
V3_TE_PATH = ROOT / "data" / "new_build" / "training" / "v3_velocity_candidates_test.parquet"

# ── Thresholds (v1 — calibrated against historical sigma) ──────────────────
WIN_TRUST_VP_MIN = 0.22
WIN_TRUST_PP_MIN = 1.0

FRAME_TRUST_VP_MIN = 0.17
FRAME_TRUST_PLACE_RATE_MIN = 0.50

SUPPRESS_VP_MAX = 0.10
SUPPRESS_PP_MAX = 0.0

LOW_DATA_PP_FLOOR = 0.0  # passport_strength_score below this = low data


def _build_v3_lookup() -> dict[tuple, dict]:
    """Build (race_id, horse) → {win_rate_last3, place_rate_last3, win_rate_last6} lookup."""
    frames = []
    for p in [V3_TR_PATH, V3_TE_PATH]:
        if p.exists():
            frames.append(pd.read_parquet(p))
    if not frames:
        return {}
    df = pd.concat(frames, ignore_index=True)
    out: dict[tuple, dict] = {}
    for _, row in df.iterrows():
        key = (str(row["race_id"]), str(row["horse"]))
        out[key] = {
            "win_rate_last3": row.get("win_rate_last3"),
            "place_rate_last3": row.get("place_rate_last3"),
            "win_rate_last6": row.get("win_rate_last6"),
        }
    return out


_V3_CACHE: dict[tuple, dict] | None = None


def _get_v3_lookup() -> dict[tuple, dict]:
    global _V3_CACHE
    if _V3_CACHE is None:
        _V3_CACHE = _build_v3_lookup()
    return _V3_CACHE


def _classify_row(row: dict, v3: dict[tuple, dict]) -> str:
    prob = float(row.get("champion_probability") or 0.0)
    pp_str = row.get("passport_strength_score")
    pp_found = bool(row.get("passport_found"))
    pp_score = float(pp_str) if pp_str is not None else None

    v3_key = (str(row.get("race_id") or ""), str(row.get("horse") or ""))
    v3_row = v3.get(v3_key, {})
    place_rate = v3_row.get("place_rate_last3")

    # LOW_DATA: no passport or profile too weak to trust
    if not pp_found or (pp_score is not None and pp_score < LOW_DATA_PP_FLOOR):
        return "LOW_DATA"

    # SUPPRESS: very low probability or very weak profile
    if prob <= SUPPRESS_VP_MAX:
        return "SUPPRESS"
    if pp_score is not None and pp_score <= SUPPRESS_PP_MAX:
        return "SUPPRESS"

    # WIN_TRUST: high conviction
    if prob >= WIN_TRUST_VP_MIN:
        pp_ok = pp_score is None or pp_score >= WIN_TRUST_PP_MIN
        if pp_ok:
            return "WIN_TRUST"

    # FRAME_TRUST: velocity + moderate probability
    if prob >= FRAME_TRUST_VP_MIN:
        if place_rate is not None and place_rate >= FRAME_TRUST_PLACE_RATE_MIN:
            return "FRAME_TRUST"
        # High passport strength alone is a frame signal at moderate VP
        if pp_score is not None and pp_score >= 2.0:
            return "FRAME_TRUST"

    return "NO_EDGE"


def classify_predictions(
    pred_rows: list[dict],
    use_v3_sidecar: bool = True,
) -> list[dict]:
    """Return pred_rows with `decision_lane` and sidecar fields added."""
    v3 = _get_v3_lookup() if use_v3_sidecar else {}

    out = []
    for row in pred_rows:
        lane = _classify_row(row, v3)
        v3_key = (str(row.get("race_id") or ""), str(row.get("horse") or ""))
        v3_data = v3.get(v3_key, {})
        out.append({
            **row,
            "decision_lane": lane,
            "v3_place_rate_last3": v3_data.get("place_rate_last3"),
            "v3_win_rate_last3": v3_data.get("win_rate_last3"),
            "v3_win_rate_last6": v3_data.get("win_rate_last6"),
            "v3_sidecar_source": "V3_VELOCITY_PAPER_ONLY",
        })
    return out


def lane_summary(classified_rows: list[dict]) -> dict:
    lanes = ["WIN_TRUST", "FRAME_TRUST", "NO_EDGE", "LOW_DATA", "SUPPRESS"]
    counts = {lane: 0 for lane in lanes}
    for r in classified_rows:
        lane = r.get("decision_lane", "NO_EDGE")
        counts[lane] = counts.get(lane, 0) + 1

    return {
        "total": len(classified_rows),
        "lane_counts": counts,
        "win_trust_picks": [
            {"horse": r["horse"], "course": r.get("course"), "off_time": r.get("off_time"),
             "prob": round(float(r["champion_probability"]), 3),
             "pp_strength": r.get("passport_strength_score"),
             "rank": r.get("champion_rank")}
            for r in classified_rows if r.get("decision_lane") == "WIN_TRUST"
        ],
        "frame_trust_picks": [
            {"horse": r["horse"], "course": r.get("course"), "off_time": r.get("off_time"),
             "prob": round(float(r["champion_probability"]), 3),
             "place_rate_last3": r.get("v3_place_rate_last3"),
             "pp_strength": r.get("passport_strength_score"),
             "rank": r.get("champion_rank")}
            for r in classified_rows if r.get("decision_lane") == "FRAME_TRUST"
        ],
    }
