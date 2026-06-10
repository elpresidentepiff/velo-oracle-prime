"""
RPDC attach resolution — deterministic, never inventive.
=========================================================
Born from the June 9 failure: PDF-bypass cards mint synthetic
rp_{VENUE}_* race/horse IDs while runner_release_candidates carries real
RP numeric IDs, so the exact race_id join returns nothing and RPDC
silently attaches no_data.

Fallback order (deterministic only — no fuzzy matching):
  1. exact race_id + horse_id        -> "race_id_exact"
  2. run_date + normalized horse name, UNIQUE match only
                                     -> "date_name_fallback"
  ambiguous name (2+ candidates)     -> None, "ambiguous_blocked"
  no candidate                       -> None, "no_candidate"

Ambiguity returns no data — never invented data. The attach method is
returned so callers can log it per runner.

Pure functions only: no I/O, no Supabase, no scoring imports.
Tests: tests/test_rpdc_attach_fallback.py
"""
from __future__ import annotations

import re
from typing import Any

AMBIGUOUS = "__AMBIGUOUS__"


def normalize_horse_name(name: str) -> str:
    """Deterministic name key: country suffix dropped, lowercase alphanumerics."""
    name = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", name or "")
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_name_map(candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Map normalized horse name -> candidate row, or AMBIGUOUS sentinel when
    two or more candidates share the same normalized name on the date."""
    name_map: dict[str, Any] = {}
    for row in candidate_rows or []:
        key = normalize_horse_name(row.get("horse", ""))
        if not key:
            continue
        if key in name_map:
            name_map[key] = AMBIGUOUS
        else:
            name_map[key] = row
    return name_map


def resolve_runner_rpdc(
    race_rpdc: dict[str, dict],
    name_map: dict[str, Any] | None,
    horse_id: str | None,
    horse_name: str | None,
) -> tuple[dict | None, str]:
    """Resolve one runner's RPDC row.

    Args:
        race_rpdc: {horse_id: row} from the exact race_id query (may be empty).
        name_map:  output of build_name_map for the run_date, or None when the
                   day-level fallback has not been loaded.
        horse_id / horse_name: the runner as scoring sees it.

    Returns:
        (row | None, attach_method)
    """
    if horse_id and race_rpdc:
        row = race_rpdc.get(horse_id)
        if row is not None:
            return row, "race_id_exact"

    if name_map:
        key = normalize_horse_name(horse_name or "")
        if key:
            hit = name_map.get(key)
            if hit is AMBIGUOUS:
                return None, "ambiguous_blocked"
            if hit is not None:
                return hit, "date_name_fallback"

    return None, "no_candidate"
