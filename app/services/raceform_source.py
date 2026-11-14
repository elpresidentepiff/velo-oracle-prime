"""Read the historical raceform table from Supabase, one page at a time (no local files).

Used by the candidate training script so training never depends on a laptop copy.
Read-only. Pages by id, so every row is read once and the order is stable.
"""
from __future__ import annotations

import os
import urllib.parse
from typing import Callable, Iterator

import pandas as pd

COLUMNS = ["id", "race_id", "date", "course", "off", "dist", "going", "class_raw", "type",
           "ran", "num", "pos", "draw", "horse", "age", "wgt", "or_rating", "sp", "jockey", "trainer"]
PAGE = 1000


def _default_get(path: str) -> list[dict]:
    import requests

    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not base or not key:
        raise RuntimeError("SUPABASE_URL / service key not set")
    r = requests.get(f"{base}/rest/v1/{path}",
                     headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=120)
    r.raise_for_status()
    return r.json()


def iter_pages(get: Callable[[str], list[dict]] = _default_get,
               date_from: str = "2017-01-01") -> Iterator[list[dict]]:
    """Yield raceform rows in id order, PAGE rows at a time, until a short page."""
    last_id = 0
    while True:
        q = {
            "select": ",".join(COLUMNS),
            "id": f"gt.{last_id}",
            "order": "id.asc",
            "limit": str(PAGE),
            "date": f"gte.{date_from}",
        }
        path = "raceform?" + urllib.parse.urlencode(q, safe="(),.*")
        rows = get(path)
        if not rows:
            return
        yield rows
        last_id = rows[-1]["id"]
        if len(rows) < PAGE:
            return


def load_raceform(get: Callable[[str], list[dict]] = _default_get,
                  date_from: str = "2017-01-01") -> pd.DataFrame:
    """Whole raceform history from Supabase as one DataFrame with the COLUMNS above."""
    frames = [pd.DataFrame(page) for page in iter_pages(get, date_from=date_from)]
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    return df[COLUMNS].copy()
