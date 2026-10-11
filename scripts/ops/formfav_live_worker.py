#!/usr/bin/env python3
"""24/7 FormFav ingestion worker for VÉLØ.

Purpose:
- continuously discover international race meetings;
- refresh race form / scratchings / conditions;
- poll Premium win+place markets as races approach;
- capture Pro/Premium results after the off;
- persist all provider truth to Supabase without altering canonical VÉLØ
  scoring tables.

The worker is deliberately additive. It never writes velo_verdicts,
pipeline_runs, selections or model weights.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

from src.velo.formfav_client import FormFavClient, FormFavError, best_live_prices

POLL_SECONDS = max(20, int(os.getenv("FORMFAV_WORKER_TICK_SECONDS", "30")))
MEETINGS_REFRESH_SECONDS = max(120, int(os.getenv("FORMFAV_MEETINGS_REFRESH_SECONDS", "600")))
FORM_REFRESH_SECONDS = max(300, int(os.getenv("FORMFAV_FORM_REFRESH_SECONDS", "1800")))
RESULT_REFRESH_SECONDS = max(30, int(os.getenv("FORMFAV_RESULT_REFRESH_SECONDS", "60")))
COUNTRIES = {
    c.strip().lower()
    for c in os.getenv("FORMFAV_LIVE_COUNTRIES", "gb,ie,us,ca,fr,au,hk,jp").split(",")
    if c.strip()
}
QUERY_TIMEZONE = os.getenv("FORMFAV_LIVE_QUERY_TIMEZONE", "UTC")
PRICE_LOOKAHEAD_MIN = max(15, int(os.getenv("FORMFAV_PRICE_LOOKAHEAD_MIN", "120")))
RESULT_LOOKBACK_MIN = max(30, int(os.getenv("FORMFAV_RESULT_LOOKBACK_MIN", "180")))

_last_meetings_fetch: float = 0.0
_meeting_cache: dict[str, list[dict[str, Any]]] = {}
_last_form: dict[str, float] = {}
_last_prediction: dict[str, float] = {}
_last_price: dict[str, float] = {}
_last_result: dict[str, float] = {}
_price_forbidden_until: float = 0.0


def _sb_env() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or ""
    )
    if not url or not key:
        raise RuntimeError("Supabase service credentials are missing")
    return url, key


def _sb_request(method: str, path: str, data: Any = None, prefer: str | None = None) -> bytes:
    url, key = _sb_env()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    body = json.dumps(data, default=str).encode("utf-8") if data is not None else None
    req = urllib.request.Request(f"{url}/rest/v1/{path}", data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Supabase HTTP {exc.code}: {detail}") from exc


def _upsert(table: str, rows: list[dict[str, Any]], conflict: str) -> None:
    if not rows:
        return
    qs = urllib.parse.urlencode({"on_conflict": conflict})
    _sb_request(
        "POST",
        f"{table}?{qs}",
        rows,
        prefer="resolution=merge-duplicates,return=minimal",
    )


def _insert(table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    _sb_request("POST", table, rows, prefer="return=minimal")


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def _race_key(date_str: str, country: str, slug: str, race_no: int) -> str:
    safe_slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in slug).strip("_")
    return f"formfav:{country}:{date_str}:{safe_slug}:r{race_no}"


def _meeting_dates(now: datetime) -> list[str]:
    # Query yesterday/today/tomorrow in UTC so evening US and early Asian/AUS
    # cards remain visible across timezone boundaries.
    return [(now.date() + timedelta(days=d)).isoformat() for d in (-1, 0, 1)]


def _refresh_meetings(client: FormFavClient, now: datetime) -> None:
    global _last_meetings_fetch, _meeting_cache
    if time.time() - _last_meetings_fetch < MEETINGS_REFRESH_SECONDS:
        return
    fresh: dict[str, list[dict[str, Any]]] = {}
    for date_str in _meeting_dates(now):
        try:
            payload = client.meetings(date_str, timezone=QUERY_TIMEZONE)
            meetings = [
                m for m in (payload.get("meetings") or [])
                if isinstance(m, dict)
                and str(m.get("country") or "").lower() in COUNTRIES
                and not m.get("abandoned")
            ]
            fresh[date_str] = meetings
            print(f"[FORMFAV-LIVE] meetings date={date_str} in_scope={len(meetings)}", flush=True)
        except Exception as exc:
            print(f"[FORMFAV-LIVE] meetings ERROR date={date_str}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            fresh[date_str] = _meeting_cache.get(date_str, [])
    _meeting_cache = fresh
    _last_meetings_fetch = time.time()


def _price_interval_seconds(minutes_to_off: float) -> int | None:
    if minutes_to_off > PRICE_LOOKAHEAD_MIN or minutes_to_off < -10:
        return None
    if minutes_to_off > 60:
        return 300
    if minutes_to_off > 20:
        return 120
    if minutes_to_off > 5:
        return 60
    return 30


def _looks_final(result: dict[str, Any]) -> bool:
    stage = str(
        result.get("resultStage")
        or result.get("stage")
        or result.get("status")
        or result.get("resultStatus")
        or ""
    ).lower()
    if any(token in stage for token in ("correct weight", "final", "official", "settled")):
        return True
    return bool(result.get("correctWeight") is True or result.get("final") is True)


def _persist_form(race_key: str, race_row: dict[str, Any], form: dict[str, Any]) -> None:
    _upsert("formfav_races", [race_row], "provider_race_key")
    # Providers can occasionally emit duplicate saddlecloth numbers in the
    # same payload (e.g. coupled entries / correction rows). De-duplicate the
    # batch before Postgres ON CONFLICT so one insert command never targets the
    # same primary key twice. Preserve the last provider row as freshest truth.
    runners_by_number: dict[int, dict[str, Any]] = {}
    for rr in form.get("runners") or []:
        if not isinstance(rr, dict):
            continue
        number = rr.get("number")
        name = rr.get("name")
        if number is None or not name:
            continue
        n = int(number)
        runners_by_number[n] = {
            "provider_race_key": race_key,
            "runner_number": n,
            "horse_name": str(name),
            "scratched": bool(rr.get("scratched")),
            "form_payload": rr,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    _upsert("formfav_runner_form", list(runners_by_number.values()), "provider_race_key,runner_number")


def _persist_predictions(race_key: str, payload: dict[str, Any]) -> None:
    model_version = payload.get("modelVersion") or payload.get("model_version")
    confidence = payload.get("confidence") or payload.get("confidenceLevel")
    _upsert(
        "formfav_predictions",
        [{
            "provider_race_key": race_key,
            "model_version": str(model_version) if model_version is not None else None,
            "confidence": str(confidence) if confidence is not None else None,
            "predictions_payload": payload,
            "captured_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }],
        "provider_race_key",
    )


def _persist_prices(race_key: str, prices: dict[str, Any]) -> int:
    rows_by_number: dict[int, dict[str, Any]] = {}
    captured = datetime.now(UTC).isoformat()
    for rr in prices.get("runners") or []:
        if not isinstance(rr, dict) or rr.get("number") is None or not rr.get("name"):
            continue
        summary = best_live_prices(rr)
        n = int(rr["number"])
        rows_by_number[n] = {
            "provider_race_key": race_key,
            "captured_at": captured,
            "runner_number": n,
            "horse_name": str(rr["name"]),
            "best_win": summary.get("best_win"),
            "best_place": summary.get("best_place"),
            "shortest_win": summary.get("shortest_win"),
            "quote_count": summary.get("fresh_quote_count") or 0,
            "market_payload": rr,
        }
    rows = list(rows_by_number.values())
    _insert("formfav_market_snapshots", rows)
    return len(rows)


def _persist_result(race_key: str, payload: dict[str, Any]) -> None:
    final = _looks_final(payload)
    stage = (
        payload.get("resultStage")
        or payload.get("stage")
        or payload.get("status")
        or payload.get("resultStatus")
    )
    _upsert(
        "formfav_results",
        [{
            "provider_race_key": race_key,
            "result_stage": str(stage) if stage is not None else None,
            "interim": not final,
            "results_payload": payload,
            "settled_at": datetime.now(UTC).isoformat() if final else None,
            "updated_at": datetime.now(UTC).isoformat(),
        }],
        "provider_race_key",
    )


def _process_race(client: FormFavClient, date_str: str, meeting: dict[str, Any], mrace: dict[str, Any], now: datetime) -> None:
    global _price_forbidden_until
    country = str(meeting.get("country") or "").lower()
    track = str(meeting.get("track") or "")
    slug = str(meeting.get("slug") or track)
    race_no = mrace.get("raceNumber")
    if race_no is None:
        return
    race_no = int(race_no)
    start = _parse_dt(mrace.get("startTime"))
    if start is None:
        return
    mins_to_off = (start - now).total_seconds() / 60.0
    race_key = _race_key(date_str, country, slug, race_no)

    # Ignore races long outside the live window.
    if mins_to_off > 24 * 60 or mins_to_off < -RESULT_LOOKBACK_MIN:
        return

    base_race = {
        "provider_race_key": race_key,
        "race_date": date_str,
        "country": country,
        "track": track,
        "race_number": race_no,
        "race_code": str(mrace.get("raceCode") or "gallops"),
        "start_time": start.isoformat(),
        "timezone": mrace.get("timezone"),
        "status": "abandoned" if mrace.get("abandoned") else "scheduled",
        "meeting_slug": slug,
        "metadata": mrace,
        "updated_at": now.isoformat(),
    }
    _upsert("formfav_races", [base_race], "provider_race_key")

    # Form is comparatively static; refresh periodically for scratchings,
    # track-condition changes and richer Pro analytics.
    last_form = _last_form.get(race_key, 0.0)
    if time.time() - last_form >= FORM_REFRESH_SECONDS and mins_to_off > -30:
        try:
            form = client.race_form(
                date=date_str,
                track=slug,
                race=race_no,
                country=country,
                timezone=mrace.get("timezone") or QUERY_TIMEZONE,
            )
            race_row = dict(base_race)
            race_row["metadata"] = {"meeting_race": mrace, "form_meta": {k: v for k, v in form.items() if k != "runners"}}
            _persist_form(race_key, race_row, form)
            _last_form[race_key] = time.time()
            print(f"[FORMFAV-LIVE] form OK {country}:{track} R{race_no}", flush=True)

            # Pro's own probability model is captured as an independent benchmark.
            # It never replaces or directly drives VÉLØ's rankings.
            if time.time() - _last_prediction.get(race_key, 0.0) >= 21600:
                try:
                    pred = client.predictions(
                        date=date_str,
                        track=slug,
                        race=race_no,
                        country=country,
                        timezone=mrace.get("timezone") or QUERY_TIMEZONE,
                    )
                    _persist_predictions(race_key, pred)
                    _last_prediction[race_key] = time.time()
                    print(f"[FORMFAV-LIVE] predictions OK {country}:{track} R{race_no}", flush=True)
                except Exception as pred_exc:
                    print(
                        f"[FORMFAV-LIVE] predictions ERROR {country}:{track} R{race_no}: {pred_exc}",
                        file=sys.stderr,
                        flush=True,
                    )
        except Exception as exc:
            print(f"[FORMFAV-LIVE] form ERROR {country}:{track} R{race_no}: {exc}", file=sys.stderr, flush=True)

    # Premium market polling. A Pro trial legitimately returns 403; back off
    # globally for one hour rather than hammering a tier-gated endpoint.
    interval = _price_interval_seconds(mins_to_off)
    if interval is not None and time.time() >= _price_forbidden_until:
        last = _last_price.get(race_key, 0.0)
        if time.time() - last >= interval:
            try:
                prices = client.prices(
                    date=date_str,
                    track=slug,
                    race=race_no,
                    country=country,
                    timezone=mrace.get("timezone") or QUERY_TIMEZONE,
                )
                n = _persist_prices(race_key, prices)
                _last_price[race_key] = time.time()
                print(f"[FORMFAV-LIVE] prices OK {country}:{track} R{race_no} runners={n} tto={mins_to_off:.1f}m", flush=True)
            except FormFavError as exc:
                if "403" in str(exc):
                    _price_forbidden_until = time.time() + 3600
                    print("[FORMFAV-LIVE] prices tier-gated (403); backing off 60m", flush=True)
                else:
                    print(f"[FORMFAV-LIVE] prices ERROR {country}:{track} R{race_no}: {exc}", file=sys.stderr, flush=True)
            except Exception as exc:
                print(f"[FORMFAV-LIVE] prices ERROR {country}:{track} R{race_no}: {exc}", file=sys.stderr, flush=True)

    # Result polling starts just after the scheduled off and continues until
    # final/correct-weight or the live lookback window expires.
    if -RESULT_LOOKBACK_MIN <= mins_to_off <= 0:
        last = _last_result.get(race_key, 0.0)
        if time.time() - last >= RESULT_REFRESH_SECONDS:
            try:
                result = client.results(
                    date=date_str,
                    track=slug,
                    race=race_no,
                    country=country,
                    timezone=mrace.get("timezone") or QUERY_TIMEZONE,
                )
                _persist_result(race_key, result)
                _last_result[race_key] = time.time()
                print(
                    f"[FORMFAV-LIVE] result OK {country}:{track} R{race_no} final={_looks_final(result)}",
                    flush=True,
                )
                if _looks_final(result):
                    # Final races no longer need repeated result calls in-memory.
                    _last_result[race_key] = time.time() + 10**9
            except FormFavError as exc:
                # A not-yet-resulted race may legitimately 404/empty.
                if "404" not in str(exc):
                    print(f"[FORMFAV-LIVE] result ERROR {country}:{track} R{race_no}: {exc}", file=sys.stderr, flush=True)
                _last_result[race_key] = time.time()
            except Exception as exc:
                print(f"[FORMFAV-LIVE] result ERROR {country}:{track} R{race_no}: {exc}", file=sys.stderr, flush=True)
                _last_result[race_key] = time.time()


def main() -> int:
    client = FormFavClient()
    _sb_env()  # fail fast on durable-storage misconfiguration
    print(
        "[FORMFAV-LIVE] online "
        f"countries={','.join(sorted(COUNTRIES))} tick={POLL_SECONDS}s "
        f"price_window={PRICE_LOOKAHEAD_MIN}m results_window={RESULT_LOOKBACK_MIN}m",
        flush=True,
    )
    while True:
        now = datetime.now(UTC)
        try:
            _refresh_meetings(client, now)
            processed = 0
            for date_str, meetings in list(_meeting_cache.items()):
                for meeting in meetings:
                    for mrace in meeting.get("races") or []:
                        if not isinstance(mrace, dict) or mrace.get("abandoned"):
                            continue
                        _process_race(client, date_str, meeting, mrace, now)
                        processed += 1
            print(f"[FORMFAV-LIVE] heartbeat processed={processed} utc={now.isoformat()}", flush=True)
        except Exception as exc:
            print(f"[FORMFAV-LIVE] LOOP ERROR {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
