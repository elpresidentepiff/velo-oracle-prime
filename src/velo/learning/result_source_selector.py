"""
Result-source selection adapter — LEARNING-LOOP-01A Phase 2.

Deliberately separate from identity resolution (see identity_resolver.py).
This module answers only "which result rows are we allowed to trust for
this date, and how complete are they" — it never resolves an individual
race or horse.

Selection is evidence-based, not a hardcoded date boundary. The RP-era
vs-legacy split observed in Phase 1 (Supabase races/runner_results stop
2026-05-06, runner_prediction_snapshots start 2026-05-20) is a *fact about
current data*, not a rule wired into this selector. The selector always
tries the local RP JSON first; Supabase is consulted only as an
evidence-checked fallback, and its result rows are classified
SUPABASE_CANONICAL_RESULT vs SUPABASE_LEGACY_RESULT by observing the
race_id scheme actually present in the returned rows (rp_ prefix vs
not), not by comparing against a fixed date.

Local and Supabase data are never silently merged into an apparently
complete race — if both exist and disagree, that is reported as
RESULT_SOURCE_CONFLICT, not resolved automatically.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RESULTS_DIR_DEFAULT = Path("data/results")

SOURCE_RP_LOCAL_JSON = "RP_LOCAL_JSON"
SOURCE_SUPABASE_CANONICAL = "SUPABASE_CANONICAL_RESULT"
SOURCE_SUPABASE_LEGACY = "SUPABASE_LEGACY_RESULT"
SOURCE_UNAVAILABLE = "RESULT_SOURCE_UNAVAILABLE"

CLASS_RP_LOCAL_PRIMARY = "RESULT_SOURCE_RP_LOCAL_PRIMARY"
CLASS_SUPABASE_LEGACY = "RESULT_SOURCE_SUPABASE_LEGACY"
CLASS_PARTIAL = "RESULT_SOURCE_PARTIAL"
CLASS_MISSING = "RESULT_SOURCE_MISSING"
CLASS_CONFLICT = "RESULT_SOURCE_CONFLICT"
CLASS_FALLBACK_VERIFIED = "RESULT_SOURCE_FALLBACK_VERIFIED"


@dataclass
class ResultSourceSelection:
    date: str
    source: str  # one of SOURCE_*
    classification: str  # one of CLASS_*
    path_or_table: str | None
    source_hash: str | None
    completeness: dict[str, Any]
    races: list[dict]  # normalised race rows from the selected source
    conflict_detail: dict[str, Any] | None = None


def _sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _local_file_path(date: str, results_dir: Path) -> Path:
    return results_dir / f"rp_results_{date.replace('-', '_')}.json"


def _load_local_rp_file(date: str, results_dir: Path) -> tuple[list[dict], str | None, dict]:
    path = _local_file_path(date, results_dir)
    if not path.exists():
        return [], None, {"exists": False, "races_parsed": 0, "races_with_runners": 0, "races_total": 0}
    raw = path.read_text(encoding="utf-8")
    source_hash = _sha256_of_text(raw)
    data = json.loads(raw)
    races = data.get("results", []) if isinstance(data, dict) else data
    status = data.get("status") if isinstance(data, dict) else None
    races_parsed = data.get("races_parsed") if isinstance(data, dict) else len(races)
    races_with_runners = [r for r in races if r.get("runners")]
    completeness = {
        "exists": True,
        "status": status,
        "races_parsed": races_parsed,
        "races_with_runners": len(races_with_runners),
        "races_total": len(races),
    }
    return races, source_hash, completeness


def _winner_of(race: dict) -> str | None:
    for r in race.get("runners", []):
        pos = str(r.get("position") or r.get("position_text") or "")
        if pos == "1" or r.get("is_winner"):
            return r.get("horse_id") or r.get("horse_name") or r.get("horse")
    return None


def select_result_source(
    date: str,
    *,
    results_dir: Path = RESULTS_DIR_DEFAULT,
    supabase_fetch: Callable[[str], list[dict]] | None = None,
) -> ResultSourceSelection:
    """
    date: "YYYY-MM-DD"
    supabase_fetch: injected callable date -> list[race rows], so this
        stays testable without a live Supabase connection. Each returned
        race row must carry "race_id", "course", a date field, a time
        field, and "runners": [...].
    """
    local_races, local_hash, local_completeness = _load_local_rp_file(date, results_dir)
    local_complete = (
        local_completeness["exists"]
        and local_completeness["races_with_runners"] > 0
        and local_completeness["races_with_runners"] == local_completeness["races_total"]
    )

    if local_complete:
        return ResultSourceSelection(
            date=date,
            source=SOURCE_RP_LOCAL_JSON,
            classification=CLASS_RP_LOCAL_PRIMARY,
            path_or_table=str(_local_file_path(date, results_dir)),
            source_hash=local_hash,
            completeness=local_completeness,
            races=local_races,
        )

    supa_races = list(supabase_fetch(date)) if supabase_fetch else []

    if not supa_races:
        if local_completeness["exists"]:
            # partial local file, nothing to verify a fallback against --
            # do not fabricate completeness, do not invent a fallback.
            return ResultSourceSelection(
                date=date,
                source=SOURCE_RP_LOCAL_JSON,
                classification=CLASS_PARTIAL,
                path_or_table=str(_local_file_path(date, results_dir)),
                source_hash=local_hash,
                completeness=local_completeness,
                races=local_races,
            )
        return ResultSourceSelection(
            date=date,
            source=SOURCE_UNAVAILABLE,
            classification=CLASS_MISSING,
            path_or_table=None,
            source_hash=None,
            completeness=local_completeness,
            races=[],
        )

    # Supabase returned rows -- classify by the evidence in those rows,
    # not by the date. rp_ scheme rows mean a supplementary write from
    # the same RP pipeline that also produced the local file (rare, but
    # possible); anything else is the pre-RP-era legacy corpus.
    rp_scheme_present = any(str(r.get("race_id", "")).startswith("rp_") for r in supa_races)
    source = SOURCE_SUPABASE_CANONICAL if rp_scheme_present else SOURCE_SUPABASE_LEGACY

    if local_completeness["exists"] and local_races:
        local_by_id = {r.get("race_id"): r for r in local_races}
        conflicts = []
        for sr in supa_races:
            lr = local_by_id.get(sr.get("race_id"))
            if not lr:
                continue
            lw, sw = _winner_of(lr), _winner_of(sr)
            if lw and sw and lw != sw:
                conflicts.append({"race_id": sr.get("race_id"), "local_winner": lw, "supabase_winner": sw})
        if conflicts:
            return ResultSourceSelection(
                date=date,
                source=source,
                classification=CLASS_CONFLICT,
                path_or_table="supabase:races/runner_results",
                source_hash=None,
                completeness={"local": local_completeness, "supabase_races": len(supa_races)},
                races=[],
                conflict_detail={"conflicts": conflicts},
            )

    classification = CLASS_FALLBACK_VERIFIED if source == SOURCE_SUPABASE_CANONICAL else CLASS_SUPABASE_LEGACY
    return ResultSourceSelection(
        date=date,
        source=source,
        classification=classification,
        path_or_table="supabase:races/runner_results",
        source_hash=None,
        completeness={"supabase_races": len(supa_races)},
        races=supa_races,
    )
