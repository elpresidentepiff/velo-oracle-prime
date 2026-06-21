"""Passport feed attachment for Radical Velo shadow packets."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def normalize_name(value: Any) -> str:
    text = str(value or "").lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def load_passport_feed(data_dir: Path, date: str) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    slug = date.replace("-", "_")
    feed_dir = data_dir / "new_build" / "current_cards"
    dated_path = feed_dir / f"current_card_passport_feed_{slug}.jsonl"
    latest_path = feed_dir / "current_card_passport_feed_latest.jsonl"

    selected = dated_path if dated_path.exists() and dated_path.stat().st_size > 0 else latest_path
    status = {
        "requested_date": date,
        "dated_path": str(dated_path),
        "latest_path": str(latest_path),
        "selected_path": str(selected),
        "selected_kind": "dated" if selected == dated_path else "latest",
        "rows": 0,
        "available_rows": 0,
        "loaded": False,
        "error": None,
    }
    if not selected.exists() or selected.stat().st_size == 0:
        status["error"] = "NO_NON_EMPTY_PASSPORT_FEED"
        return {}, status

    out: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        for line in selected.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (str(row.get("race_id") or ""), normalize_name(row.get("horse")))
            if key[0] and key[1]:
                out[key] = row
                status["rows"] += 1
                if row.get("passport_available") or row.get("passport_found"):
                    status["available_rows"] += 1
        status["loaded"] = True
    except Exception as exc:  # pragma: no cover - runtime reporting only
        status["error"] = str(exc)
        return {}, status
    return out, status


def passport_snapshot(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "matched": False,
            "passport_available": False,
            "passport_strength_score": None,
            "reason_codes": [],
            "passport_live_features": {},
        }
    features = row.get("passport_live_features") or {}
    return {
        "matched": True,
        "passport_available": bool(row.get("passport_available") or row.get("passport_found")),
        "passport_strength_score": row.get("passport_strength_score"),
        "weak_profile_runner": row.get("weak_profile_runner"),
        "reason_codes": row.get("reason_codes") or [],
        "horse": row.get("horse"),
        "rp_uid": row.get("rp_uid"),
        "race_class": row.get("race_class"),
        "race_type": row.get("race_type"),
        "distance_furlongs": row.get("distance_furlongs"),
        "going": row.get("going"),
        "forecast_odds": row.get("forecast_odds"),
        "passport_live_features": {
            key: features.get(key)
            for key in [
                "pp_career_runs",
                "pp_win_rate",
                "pp_place_rate",
                "pp_days_since_last",
                "pp_avg_sp_last5",
                "pp_jockey_continuity",
                "pp_or_change_3",
                "pp_class_moved_up",
                "pp_class_moved_down",
            ]
        },
    }
