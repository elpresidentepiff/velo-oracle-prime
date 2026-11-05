"""Durable, immutable persistence for Velo World PAPER/SHADOW scorecards."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any


def _key(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def build_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    generated_at = payload["generated_at"]
    generated_dt = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
    model_name = payload.get("scoring_engine") or "VELO_WORLD_PRIME_SHADOW_V1"
    rows: list[dict[str, Any]] = []
    for race in payload.get("races") or []:
        provider_key = race.get("provider_race_key")
        scheduled_off = race.get("scheduled_off")
        country = str(race.get("country") or "").lower()
        if not provider_key or not scheduled_off or country in {"gb", "ie"}:
            continue
        off_dt = datetime.fromisoformat(str(scheduled_off).replace("Z", "+00:00"))
        if generated_dt >= off_dt:
            continue
        for pred in race.get("scorecard") or []:
            horse_key = pred.get("horse_id")
            horse_name = pred.get("horse")
            if not horse_key or not horse_name:
                continue
            rows.append({
                "scorecard_key": _key(provider_key, model_name, "FIRST_COMPLETE", horse_key),
                "provider_race_key": provider_key,
                "race_date": payload["date"],
                "country": country,
                "track": race.get("course") or "",
                "race_number": race.get("race_number"),
                "scheduled_off": scheduled_off,
                "model_name": model_name,
                "freeze_stage": "FIRST_COMPLETE",
                "runner_rank": pred.get("rank"),
                "horse_key": horse_key,
                "horse_name": horse_name,
                "score": pred.get("velo_prime_prob"),
                "place_prob": pred.get("place_prob"),
                "longshot_prob": pred.get("longshot_prob"),
                "captured_price": pred.get("sp_dec"),
                "generated_at": generated_at,
                "generated_pre_off": generated_dt < off_dt,
                "provider_predictions_consumed": False,
                "identity_grade": "D_NAME_COUNTRY_ONLY",
                "feature_payload": {
                    "improvement_score": pred.get("improvement_score"),
                    "market_deception_score": pred.get("market_deception_score"),
                    "confidence_level": pred.get("confidence_level"),
                },
            })
    return rows


def persist_rows(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("Supabase service credentials are required for world scorecard persistence")
    query = urllib.parse.urlencode({"on_conflict": "scorecard_key"})
    req = urllib.request.Request(
        f"{url}/rest/v1/world_model_scorecards?{query}",
        data=json.dumps(rows).encode(),
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        },
    )
    with urllib.request.urlopen(req, timeout=60):
        pass
    return len(rows)
