"""Read canonical Racing Post racecards from Supabase for shadow consumers.

This module is deliberately read-only.  It reconstructs the racecard shape
used by VÉLØ's enrichment tools from ``public.races.raw`` and marks every row
as archive context that is not authorised for Prime scoring.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from copy import deepcopy
from typing import Any


class SupabaseRacecardError(RuntimeError):
    """Raised when canonical archived racecards cannot be read truthfully."""


def _credentials() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or ""
    ).strip()
    if not url or not key:
        raise SupabaseRacecardError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
        )
    return url, key


def _normalise_country(value: Any) -> str:
    key = str(value or "").strip().lower()
    return {"uk": "gb", "gb": "gb", "eng": "gb", "ire": "ie", "irl": "ie"}.get(
        key, key
    )


def _normalise_runner(raw: dict[str, Any]) -> dict[str, Any]:
    runner = deepcopy(raw)
    horse = runner.get("horse") or runner.get("horse_name") or runner.get("name")
    if horse:
        runner.setdefault("horse", horse)
        runner.setdefault("horse_name", horse)
    if runner.get("lbs") in (None, "") and runner.get("weight_lbs") not in (None, ""):
        runner["lbs"] = runner["weight_lbs"]
    if runner.get("form") in (None, "") and runner.get("form_figures") not in (None, ""):
        runner["form"] = runner["form_figures"]
    if runner.get("sex") in (None, "") and runner.get("sex_colour") not in (None, ""):
        runner["sex"] = runner["sex_colour"]
    if runner.get("odds") in (None, "", 0, 0.0, []):
        price = runner.get("forecast_odds") or runner.get("rp_morning_price")
        if price not in (None, ""):
            runner["odds"] = price
    return runner


def _row_to_race(row: dict[str, Any], date_str: str) -> dict[str, Any]:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    race = deepcopy(raw)
    race_id = row.get("race_id") or raw.get("race_id")
    course = row.get("course") or raw.get("course") or raw.get("track")
    off_time = raw.get("off_time") or raw.get("race_time") or row.get("time")
    country = _normalise_country(raw.get("country") or raw.get("region"))

    race.update(
        {
            "race_id": race_id,
            "course": course,
            "date": str(row.get("date") or raw.get("date") or date_str)[:10],
            "off_time": str(off_time or "")[:8],
            "race_name": row.get("race_name") or raw.get("race_name") or raw.get("race_title"),
            "race_type": row.get("race_type") or raw.get("race_type") or raw.get("type"),
            "type": row.get("race_type") or raw.get("type") or raw.get("race_type"),
            "distance_f": row.get("distance_f") or raw.get("distance_f") or raw.get("distance_furlongs"),
            "distance": raw.get("distance") or raw.get("distance_furlongs") or row.get("distance_f"),
            "going": row.get("going") or raw.get("going"),
            "race_class": row.get("class") or raw.get("race_class") or raw.get("class"),
            "country": country,
            "region": country,
            "runners": [
                _normalise_runner(runner)
                for runner in (raw.get("runners") or [])
                if isinstance(runner, dict)
            ],
            "_source": {
                "provider": "racing_post",
                "storage": "supabase.public.races.raw",
                "mode": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                "velo_scoring_allowed": False,
            },
        }
    )
    return race


def load_supabase_rp_racecards(date_str: str, *, timeout: int = 60) -> list[dict[str, Any]]:
    """Return canonical RP cards for ``date_str`` from ``public.races``.

    Only rows containing a non-empty archived runner payload are accepted.
    A missing/empty archive is an explicit failure rather than an empty card.
    """
    url, key = _credentials()
    params = urllib.parse.urlencode(
        {
            "select": (
                "race_id,course,date,time,race_type,distance_f,going,class,"
                "prize_money,runners_count,race_name,raw"
            ),
            "date": f"eq.{date_str}",
            "order": "time.asc",
            "limit": "1000",
        },
        safe=".,",
    )
    request = urllib.request.Request(
        f"{url}/rest/v1/races?{params}",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "VELO-Oracle-Prime/formfav-shadow",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise SupabaseRacecardError(
            f"Supabase canonical racecard read failed: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(payload, list):
        raise SupabaseRacecardError("Supabase races endpoint returned a non-list payload")

    races = [_row_to_race(row, date_str) for row in payload if isinstance(row, dict)]
    races = [race for race in races if race.get("race_id") and race.get("runners")]
    if not races:
        raise SupabaseRacecardError(
            f"No canonical RP racecards with runners were archived for {date_str}"
        )
    return races
