"""Durable, immutable persistence for Velo World PAPER/SHADOW scorecards.

Everything here is pure except the ``persist_*`` functions:

* ``usable_price``   - a price counts only if it is dated and was captured before the off
* ``decide_freeze``  - when a race's scorecard may become the immutable one
* ``build_rows``     - frozen scorecard rows, each carrying its own price provenance
* ``build_run_rows`` - one ledger row per country per run (``world_pipeline_runs``)
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

# velo_prime_service.py scores a runner with no price as ``sp_dec = 10.0``. That value is a
# model default, never a market price, so it must never be stored as one.
PRICE_PLACEHOLDER = 10.0
MIN_PRICED_SHARE = 0.5
# The shadow job runs hourly. A race is deferred only while at least one more run is still
# guaranteed to happen before the off; after that it is frozen with whatever it has.
DEFER_UNTIL_MINUTES = 75


def _key(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def usable_price(
    market: dict[str, Any] | None, off_dt: datetime, generated_at: datetime
) -> tuple[float | None, str | None]:
    """Return ``(best_win_price, captured_at_iso)`` or ``(None, None)``.

    A price with no capture time cannot be shown to be pre-off, so it is rejected, as is a
    quote captured at or after the off or after this run started.
    """
    if not isinstance(market, dict):
        return None, None
    try:
        best = float(market.get("best_win"))
    except (TypeError, ValueError):
        return None, None
    if best <= 1.0:
        return None, None
    times = [
        t for q in market.get("quotes") or []
        if isinstance(q, dict) and not q.get("stale") and q.get("win") not in (None, "")
        and (t := _parse_dt(q.get("capturedAt"))) is not None
    ]
    if not times:
        return None, None
    latest = max(times)
    if latest >= off_dt or latest > generated_at:
        return None, None
    return best, latest.isoformat()


def top_tie_size(scorecard: list[dict[str, Any]]) -> int:
    """How many runners share the rank-1 score. More than 1 means rank 1 was list order."""
    scores = [
        round(float(p["velo_prime_prob"]), 6)
        for p in scorecard if p.get("velo_prime_prob") is not None
    ]
    if not scores:
        return 0
    top = max(scores)
    return sum(1 for s in scores if s == top)


def decide_freeze(
    priced: int, runners: int, feed_live: bool, minutes_to_off: float
) -> tuple[bool, str]:
    """Decide whether a race may be frozen now. Returns ``(freeze, state)``.

    PRICED          at least half the field has a dated pre-off price
    AWAITING_PRICES the country's price feed is live but this race has none yet, and another
                    hourly run will still happen before the off: wait
    PARTIAL_MARKET  frozen with some prices (time ran out)
    NO_MARKET       frozen with none (the feed does not cover this country, or time ran out)
    """
    share = priced / runners if runners else 0.0
    if share >= MIN_PRICED_SHARE:
        return True, "PRICED"
    if feed_live and minutes_to_off > DEFER_UNTIL_MINUTES:
        return False, "AWAITING_PRICES"
    return True, "PARTIAL_MARKET" if priced else "NO_MARKET"


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
        if race.get("freeze_state") == "AWAITING_PRICES":
            continue
        off_dt = datetime.fromisoformat(str(scheduled_off).replace("Z", "+00:00"))
        if generated_dt >= off_dt:
            continue
        for pred in race.get("scorecard") or []:
            horse_key = pred.get("horse_id")
            horse_name = pred.get("horse")
            if not horse_key or not horse_name:
                continue
            real = pred.get("price_state") == "REAL"
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
                # NULL unless a dated pre-off market price existed. Never the model default.
                "captured_price": pred.get("captured_price") if real else None,
                "generated_at": generated_at,
                "generated_pre_off": generated_dt < off_dt,
                "provider_predictions_consumed": False,
                "identity_grade": "D_NAME_COUNTRY_ONLY",
                "feature_payload": {
                    "improvement_score": pred.get("improvement_score"),
                    "market_deception_score": pred.get("market_deception_score"),
                    "confidence_level": pred.get("confidence_level"),
                    "price_state": "REAL" if real else "MISSING",
                    "price_captured_at": pred.get("price_captured_at") if real else None,
                    "race_price_state": race.get("freeze_state"),
                    "priced_runners": race.get("priced_runners"),
                    "field_size": race.get("field_size"),
                    "top_tie_size": race.get("top_tie_size"),
                    "code_commit": payload.get("code_commit"),
                },
            })
    return rows


def build_run_rows(
    payload: dict[str, Any],
    attempted_by_country: dict[str, int] | None = None,
    inserted_by_country: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """One ``world_pipeline_runs`` row per country for this run. History is kept: every run
    gets its own ``run_key``, so coverage defects are never overwritten by the next hour."""
    generated_at = payload["generated_at"]
    model = payload.get("scoring_engine") or "VELO_WORLD_PRIME_SHADOW_V1"
    details_all = (payload.get("fetch_report") or {}).get("error_detail") or []
    out: list[dict[str, Any]] = []
    for cc, st in sorted((payload.get("by_country") or {}).items()):
        errs = [e for e in details_all if str(e.get("country") or "").lower() == cc]
        # A country with no rows in the dict means zero, not "unknown": only a missing dict is unknown.
        attempted = None if attempted_by_country is None else attempted_by_country.get(cc, 0)
        inserted = None if inserted_by_country is None else inserted_by_country.get(cc, 0)
        out.append({
            "run_key": _key("run", payload["date"], cc, model, generated_at),
            "race_date": payload["date"],
            "country": cc,
            "model_name": model,
            "status": "PASS" if not errs and not st.get("deferred") else "PARTIAL",
            "races_seen": st.get("seen", 0),
            "races_scored": st.get("scored", 0),
            "races_skipped_post_off": st.get("skipped_post_off", 0),
            "runners_scored": st.get("runners_scored", 0),
            "provider_predictions_consumed": False,
            "generated_at": generated_at,
            "details": {
                "code_commit": payload.get("code_commit"),
                "freeze_states": st.get("freeze_states", {}),
                "deferred": st.get("deferred", 0),
                "deferred_keys": (st.get("deferred_keys") or [])[:50],
                "unscorable": st.get("unscorable", 0),
                "tied_top_races": st.get("tied_top_races", 0),
                "error_count": len(errs),
                "errors": errs[:25],
                "rows_attempted": attempted,
                "rows_inserted": inserted,
                "rows_ignored_duplicates": (
                    attempted - inserted if attempted is not None and inserted is not None else None
                ),
            },
        })
    return out


def _credentials() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("Supabase service credentials are required for world scorecard persistence")
    return url, key


def _post(table: str, rows: list[dict[str, Any]], on_conflict: str, prefer: str) -> list[dict[str, Any]]:
    url, key = _credentials()
    query = urllib.parse.urlencode({"on_conflict": on_conflict})
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}?{query}",
        data=json.dumps(rows).encode(),
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
    return json.loads(body.decode()) if body else []


def persist_rows_detailed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Insert frozen scorecard rows; return only the rows actually inserted.

    ``ignore-duplicates`` keeps the first scorecard immutable, and ``return=representation``
    makes PostgREST hand back just the new rows, so ignored duplicates are countable."""
    if not rows:
        return []
    return _post(
        "world_model_scorecards", rows, "scorecard_key",
        "resolution=ignore-duplicates,return=representation",
    )


def persist_rows(rows: list[dict[str, Any]]) -> int:
    """Number of rows actually inserted (duplicates ignored by the first-wins rule are not)."""
    return len(persist_rows_detailed(rows))


def persist_run_rows(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    _post("world_pipeline_runs", rows, "run_key", "resolution=merge-duplicates,return=minimal")
    return len(rows)
