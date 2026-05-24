"""
load_rpdc_memory.py
---------------------
Read-only local RPDC memory adapter.

Loads data/rpdc_backfill/rpdc_tags_historical.jsonl and provides
lookup functions for scoring context. NO Supabase. NO writes.
NO scoring formula changes. Read-only bridge only.

The horse_id formats differ between systems:
  - RPDC JSONL: hrs_XXXXXXXX  (Racing API origin)
  - Racecard/snapshots: rp_COURSE_horse_name  (RP origin)

Matching strategy: normalised horse name (primary), horse_id (secondary).
Name normalisation: strip country code suffix, lowercase, collapse whitespace.

Intended usage (Option B):
  memory = load_rpdc_memory()
  ctx = get_memory_summary_for_runner(
      horse_id="rp_CUR_sun_goddess",
      horse_name="Sun Goddess",
      as_of_date="2026-05-25",
      memory=memory,
  )
  # ctx["rpdc_tag_count"], ctx["rpdc_primary_tag"], ctx["provenance_status"], ...
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSONL = ROOT / "data" / "rpdc_backfill" / "rpdc_tags_historical.jsonl"

_COUNTRY_RE = re.compile(r"\s*\([A-Z]{2,3}\)\s*$")


def _normalise_name(name: str) -> str:
    """Strip country suffix and normalise to lowercase for fuzzy matching."""
    if not name:
        return ""
    n = _COUNTRY_RE.sub("", name).strip().lower()
    n = re.sub(r"\s+", " ", n)
    return n


def _rp_id_to_name(horse_id: str) -> str | None:
    """
    Extract a hint name from RP-format horse_id like 'rp_CUR_sun_goddess'.
    Returns normalised slug ('sun goddess') or None if not RP-format.
    """
    if not horse_id or not horse_id.startswith("rp_"):
        return None
    parts = horse_id.split("_", 2)
    if len(parts) < 3:
        return None
    return parts[2].replace("_", " ").replace("'", "").strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_rpdc_memory(path: Path | str | None = None) -> dict:
    """
    Load RPDC JSONL into an in-memory index.

    Returns a dict with two lookup keys:
      memory["by_name"][normalised_name] → list[dict] (sorted newest-date first)
      memory["by_horse_id"][horse_id]    → list[dict] (sorted newest-date first)
      memory["_total_rows"]              → int
      memory["_date_range"]              → {"first": ..., "last": ...}
      memory["_path"]                    → str
    """
    p = Path(path) if path else DEFAULT_JSONL
    if not p.exists():
        return {
            "by_name": {},
            "by_horse_id": {},
            "_total_rows": 0,
            "_date_range": {"first": None, "last": None},
            "_path": str(p),
            "_loaded": False,
        }

    by_name: dict[str, list[dict]] = {}
    by_horse_id: dict[str, list[dict]] = {}
    total = 0
    all_dates: list[str] = []

    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue

            horse_id = row.get("horse_id", "")
            horse_name = row.get("horse", "")
            key = _normalise_name(horse_name)

            if key:
                by_name.setdefault(key, []).append(row)
            if horse_id:
                by_horse_id.setdefault(horse_id, []).append(row)
            rd = row.get("race_date")
            if rd:
                all_dates.append(rd)
            total += 1

    # Sort each list newest-first
    for k in by_name:
        by_name[k].sort(key=lambda r: r.get("race_date", ""), reverse=True)
    for k in by_horse_id:
        by_horse_id[k].sort(key=lambda r: r.get("race_date", ""), reverse=True)

    all_dates_sorted = sorted(all_dates)
    return {
        "by_name": by_name,
        "by_horse_id": by_horse_id,
        "_total_rows": total,
        "_date_range": {
            "first": all_dates_sorted[0] if all_dates_sorted else None,
            "last": all_dates_sorted[-1] if all_dates_sorted else None,
        },
        "_path": str(p),
        "_loaded": True,
    }


def lookup_horse_memory(
    horse_id: str,
    horse_name: str,
    as_of_date: str,
    memory: dict,
) -> dict | None:
    """
    Return the most recent RPDC memory row for this horse that is
    STRICTLY before as_of_date.

    Matching priority:
      1. horse_id exact match (hrs_ format)
      2. normalised horse name match
      3. name extracted from RP-format horse_id slug

    Returns None if no match found.
    """
    candidates: list[dict] = []

    # 1. horse_id exact match (hrs_ format only)
    if horse_id and horse_id.startswith("hrs_"):
        candidates = memory.get("by_horse_id", {}).get(horse_id, [])

    # 2. Normalised name match
    if not candidates and horse_name:
        key = _normalise_name(horse_name)
        candidates = memory.get("by_name", {}).get(key, [])

    # 3. Name from RP-format horse_id slug
    if not candidates and horse_id:
        slug = _rp_id_to_name(horse_id)
        if slug:
            candidates = memory.get("by_name", {}).get(slug, [])

    # Filter to strictly before as_of_date, take newest
    for row in candidates:
        if row.get("race_date", "") < as_of_date:
            return row

    return None


def get_prior_tags(
    horse_id: str,
    horse_name: str,
    as_of_date: str,
    memory: dict,
) -> list[str]:
    """Return RPDC tags from the most recent memory row, or empty list."""
    row = lookup_horse_memory(horse_id, horse_name, as_of_date, memory)
    return row.get("rpdc_tags", []) if row else []


def get_memory_summary_for_runner(
    horse_id: str,
    horse_name: str,
    as_of_date: str,
    memory: dict,
) -> dict:
    """
    Return a structured RPDC memory context dict for a single runner.

    Fields returned:
      horse_id, horse_name, as_of_date,
      memory_found, match_method,
      memory_date, memory_race_id,
      prior_runs_count, days_since_run, campaign_run_no,
      or_delta_to_win, curr_or_minus_last_win_or,
      runs_since_win_proxy, runs_since_place_proxy,
      rpdc_tags, rpdc_tag_count, rpdc_primary_tag,
      rpdc_release_score, rpdc_cash_window_flag,
      provenance_status,
    """
    row = lookup_horse_memory(horse_id, horse_name, as_of_date, memory)

    if row is None:
        return {
            "horse_id": horse_id,
            "horse_name": horse_name,
            "as_of_date": as_of_date,
            "memory_found": False,
            "match_method": None,
            "memory_date": None,
            "memory_race_id": None,
            "prior_runs_count": None,
            "days_since_run": None,
            "campaign_run_no": None,
            "or_delta_to_win": None,
            "curr_or_minus_last_win_or": None,
            "rpdc_tags": [],
            "rpdc_tag_count": 0,
            "rpdc_primary_tag": None,
            "rpdc_release_score": 0.0,
            "rpdc_cash_window_flag": False,
            "provenance_status": "NO_MEMORY",
        }

    # Determine match method
    match_method = "name"
    if horse_id.startswith("hrs_") and horse_id == row.get("horse_id"):
        match_method = "horse_id"
    elif _rp_id_to_name(horse_id) == _normalise_name(row.get("horse", "")):
        match_method = "rp_slug"

    return {
        "horse_id": horse_id,
        "horse_name": horse_name,
        "as_of_date": as_of_date,
        "memory_found": True,
        "match_method": match_method,
        "memory_date": row.get("race_date"),
        "memory_race_id": row.get("race_id"),
        "prior_runs_count": row.get("prior_runs_count"),
        "days_since_run": row.get("days_since_run"),
        "campaign_run_no": row.get("campaign_run_no"),
        "or_delta_to_win": row.get("or_delta_to_win"),
        "curr_or_minus_last_win_or": row.get("or_delta_to_win"),  # alias for improvement model
        "rpdc_tags": row.get("rpdc_tags", []),
        "rpdc_tag_count": row.get("rpdc_tag_count", 0),
        "rpdc_primary_tag": row.get("rpdc_primary_tag"),
        "rpdc_release_score": row.get("rpdc_release_score", 0.0),
        "rpdc_cash_window_flag": row.get("rpdc_cash_window_flag", False),
        "provenance_status": row.get("provenance_status", "LOCAL_HISTORY_ONLY"),
    }


if __name__ == "__main__":
    import sys
    mem = load_rpdc_memory()
    if not mem["_loaded"]:
        print(f"RPDC memory not found at {mem['_path']}")
        sys.exit(1)
    print(f"RPDC memory loaded: {mem['_total_rows']} rows")
    print(f"  Date range: {mem['_date_range']['first']} → {mem['_date_range']['last']}")
    print(f"  Unique horse names: {len(mem['by_name'])}")
    print(f"  Unique horse_ids: {len(mem['by_horse_id'])}")

    # Sample lookup
    sample_name = list(mem["by_name"].keys())[0]
    sample_row = mem["by_name"][sample_name][0]
    print(f"\nSample: {sample_name}")
    ctx = get_memory_summary_for_runner(
        horse_id=sample_row.get("horse_id", ""),
        horse_name=sample_row.get("horse", ""),
        as_of_date="2026-05-25",
        memory=mem,
    )
    print(f"  Memory found: {ctx['memory_found']}, match: {ctx['match_method']}")
    print(f"  Memory date: {ctx['memory_date']}, tags: {ctx['rpdc_tags']}")
