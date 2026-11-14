"""Live history fetch for the horse-history shadow. Reads Supabase over REST with the
service key. Read-only. Never raises into scoring: callers get (frame, status)."""
from __future__ import annotations

import os
import urllib.parse
from typing import Iterable

import pandas as pd

from app.services.horse_history_features import normalise_name

_BATCH = 40
_RACEFORM_COLS = "horse,date,course,dist,going,class_raw,type,pos,or_rating,ran,draw,age,wgt,sp,jockey,trainer"
_RHR_COLS = "horse,run_date,course,distance_f,going,race_class,position,sp,race_type,jockey,trainer"


def _clean(name: str) -> str:
    return str(name or "").replace('"', "").replace(",", " ").replace("(", " ").replace(")", " ").strip()


def _get(table: str, params: dict) -> list[dict]:
    import requests

    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not base or not key:
        raise RuntimeError("SUPABASE_URL / service key not set")
    url = f"{base}/rest/v1/{table}?" + urllib.parse.urlencode(params, safe="(),.*\"")
    r = requests.get(url, headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=60)
    r.raise_for_status()
    return r.json()


def _batches(names: list[str]) -> Iterable[list[str]]:
    for i in range(0, len(names), _BATCH):
        yield names[i:i + _BATCH]


def fetch_history(names: list[str], since: str = "2017-01-01") -> pd.DataFrame:
    """History rows for these horses, from raceform (2017-2025) and racing_horse_runs (2026+).

    Returns columns: horse, date, course, dist, going, class_raw, type, pos, or_rating,
    ran, draw, age, wgt, sp, source. Matching is by normalised name."""
    wanted = {normalise_name(n) for n in names if n}
    rows: list[dict] = []
    for batch in _batches(sorted({_clean(n) for n in names if n})):
        # raceform horse names carry a country suffix, so match on prefix then filter.
        orf = ",".join(f"horse.ilike.{n}*" for n in batch)
        for r in _get("raceform", {"select": _RACEFORM_COLS, "or": f"({orf})",
                                   "date": f"gte.{since}", "limit": 100000}):
            if normalise_name(r.get("horse")) in wanted:
                r["source"] = "raceform"
                rows.append(r)
        inlist = ",".join(f'"{n}"' for n in batch)
        for r in _get("racing_horse_runs", {"select": _RHR_COLS, "horse": f"in.({inlist})",
                                            "run_date": f"gte.{since}", "limit": 100000}):
            if normalise_name(r.get("horse")) in wanted:
                rows.append({
                    "horse": r.get("horse"), "date": r.get("run_date"), "course": r.get("course"),
                    "dist": None, "going": r.get("going"), "class_raw": r.get("race_class"),
                    "type": r.get("race_type"), "pos": r.get("position"),
                    "or_rating": None, "ran": None, "draw": None, "age": None, "wgt": None,
                    "sp": r.get("sp"), "dist_f": r.get("distance_f"), "source": "racing_horse_runs",
                    "jockey": r.get("jockey"), "trainer": r.get("trainer"),
                })
    return pd.DataFrame(rows)
