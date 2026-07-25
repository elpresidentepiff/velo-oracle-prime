"""
Canonical verdict-loading module for VELO daily scripts.

THE BUG THIS MODULE EXISTS TO KILL
-----------------------------------
`velo_verdicts.generated_at` is write-time, not race-date. VELO's normal
operating pattern scores race day N the evening of day N-1 (manual, no cron),
so any query that filters `generated_at` by the target calendar day silently
returns zero rows for every card scored the night before -- which is most of
them. `race_id` reliably correlates to the actual race date instead, via the
locally cached RP racecard for that date.

This exact bug was independently hand-copied into 12+ scripts across this
codebase (dashboard endpoints, operator cards, sigma variants, audit tools,
the truth watchdog whose entire job is proving whether a day scored) before
this module existed -- see commit history and project memory for the week of
2026-07-23/24. Each copy had to be found and fixed one at a time because
there was no shared code to fix once.

New code that needs "today's verdicts" MUST use `load_verdicts()` below
instead of writing a fresh Supabase query. If you are about to write
`.gte("generated_at", ...)` or `generated_at.startswith(date_str)`, stop --
that is the bug signature. Use this module.

Usage
-----
    from src.velo.verdict_loader import load_verdicts

    rows, method = load_verdicts(
        "2026-07-24",
        select="race_id,velo_prime_prob,decision_tier,full_analysis",
    )
    # method is "race_id" (normal path), "generated_at" (fallback used --
    # something is wrong with the local racecard cache, worth investigating),
    # or "local_file" (Supabase had nothing at all; last-resort local backup).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]

_CHUNK_SIZE = 50  # PostgREST `in.(...)` URL-length safety margin, matches prior precedent in this codebase.


def _supabase_url() -> str:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not url:
        raise RuntimeError("SUPABASE_URL not set in environment")
    return url


def _supabase_headers() -> dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY) not set in environment")
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def _get(table: str, params: dict[str, str]) -> list[dict]:
    resp = requests.get(
        f"{_supabase_url()}/rest/v1/{table}",
        headers=_supabase_headers(),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        raise RuntimeError(f"Supabase error querying {table}: {data}")
    return data


def known_race_ids_for_date(date_str: str, root: Path | None = None) -> list[str]:
    """race_ids from the locally cached standard racecard for this date, if it exists.

    Handles both racecard cache shapes seen in this repo: a bare list of race
    dicts (the modern format), and an older {"racecards": [...]} wrapper.
    Returns [] if no cache exists for this date -- callers should fall back
    to generated_at filtering in that case, since it's the only option left.
    """
    root = root or ROOT
    path = root / "data" / f"racecards_{date_str.replace('-', '_')}_standard.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    races = payload.get("racecards", []) if isinstance(payload, dict) else payload
    if not isinstance(races, list):
        return []
    return [str(r["race_id"]) for r in races if isinstance(r, dict) and r.get("race_id")]


def _load_verdicts_by_race_id(select: str, race_ids: list[str]) -> list[dict]:
    rows: list[dict] = []
    for offset in range(0, len(race_ids), _CHUNK_SIZE):
        chunk = race_ids[offset : offset + _CHUNK_SIZE]
        rows.extend(
            _get(
                "velo_verdicts",
                {"select": select, "race_id": f"in.({','.join(chunk)})"},
            )
        )
    return rows


def _load_verdicts_by_generated_at(select: str, date_str: str) -> list[dict]:
    rows = _get(
        "velo_verdicts",
        {
            "select": select,
            "generated_at": f"gte.{date_str}T00:00:00",
            "order": "generated_at.asc",
        },
    )
    end = f"{date_str}T23:59:59"
    return [row for row in rows if str(row.get("generated_at", "")) <= end]


def _load_verdicts_local_file(date_str: str, root: Path) -> list[dict]:
    date_under = date_str.replace("-", "_")
    for candidate in (
        root / "data" / f"velo_prime_verdicts_{date_under}.json",
        root / "data" / f"velo_prime_verdicts_{date_str}.json",
    ):
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("verdicts"), list):
            return payload["verdicts"]
        if isinstance(payload, list):
            return payload
    return []


def load_verdicts(
    date_str: str,
    select: str = "*",
    root: Path | None = None,
    local_fallback: bool = True,
    race_ids: list[str] | None = None,
) -> tuple[list[dict], str]:
    """Load velo_verdicts rows for a given race date, the correct way.

    Tries, in order:
      1. race_id membership -- against `race_ids` if the caller already has a
         reliable race-id list for this date (e.g. from verdicts it already
         loaded some other way), otherwise against the locally cached
         racecard for date_str. Correct regardless of when scoring actually
         happened.
      2. generated_at date-range filtering (only reached if no race_ids are
         available from either source -- this is the degraded, bug-prone
         path; treat a run that falls back to it as a signal worth
         investigating, not as a normal outcome).
      3. local JSON backup file, if local_fallback is True.

    Returns (rows, method) where method is one of "race_id", "generated_at",
    "local_file", or "none" (nothing found anywhere).
    """
    root = root or ROOT

    race_ids = race_ids or known_race_ids_for_date(date_str, root=root)
    if race_ids:
        rows = _load_verdicts_by_race_id(select, race_ids)
        if rows:
            return rows, "race_id"

    rows = _load_verdicts_by_generated_at(select, date_str)
    if rows:
        return rows, "generated_at"

    if local_fallback:
        rows = _load_verdicts_local_file(date_str, root)
        if rows:
            return rows, "local_file"

    return [], "none"
