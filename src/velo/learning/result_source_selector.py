"""
Result-source selection adapter — LEARNING-LOOP-01A Phase 2, corrected per
PR #147 REQUEST CHANGES (P0-2, P1 source-selector strengthening).

Deliberately separate from identity resolution (see identity_resolver.py).
This module answers only "which result rows are we allowed to trust for
this date, and how complete are they" — it never resolves an individual
race or horse.

Selection is evidence-based, not a hardcoded date boundary. Supabase is
consulted only as an evidence-checked fallback, and its result rows are
classified SUPABASE_CANONICAL_RESULT vs SUPABASE_LEGACY_RESULT by
observing the race_id scheme actually present in the returned rows.
Local and Supabase data are never silently merged into an apparently
complete race — if both exist and disagree, that is reported as
RESULT_SOURCE_CONFLICT, not resolved automatically.

Correction (P0-2): "the file contains at least one runner per race it
happens to contain" is NOT completeness proof. A result is only complete
when the caller's expected race/runner universe (from the prediction
side) is passed in and every expected runner is accounted for as a
numeric finishing position, a terminal starter outcome (F/PU/UR/BD/RO/
DSQ), or an explicit non-runner/withdrawn marker. A blank position alone
is UNKNOWN, never automatically NR. A file with only winner/top-three
data is RESULT_SOURCE_PARTIAL, never primary-complete.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

RESULTS_DIR_DEFAULT = Path("data/results")

SOURCE_RP_LOCAL_JSON = "RP_LOCAL_JSON"
SOURCE_SUPABASE_CANONICAL = "SUPABASE_CANONICAL_RESULT"
SOURCE_SUPABASE_LEGACY = "SUPABASE_LEGACY_RESULT"
SOURCE_SUPABASE_MIXED = "SUPABASE_MIXED_SCHEME_RESULT"
SOURCE_UNAVAILABLE = "RESULT_SOURCE_UNAVAILABLE"

CLASS_RP_LOCAL_PRIMARY = "RESULT_SOURCE_RP_LOCAL_PRIMARY"
CLASS_SUPABASE_LEGACY = "RESULT_SOURCE_SUPABASE_LEGACY"
CLASS_PARTIAL = "RESULT_SOURCE_PARTIAL"
CLASS_MISSING = "RESULT_SOURCE_MISSING"
CLASS_CONFLICT = "RESULT_SOURCE_CONFLICT"
CLASS_FALLBACK_VERIFIED = "RESULT_SOURCE_FALLBACK_VERIFIED"

_NUMERIC_POSITION_RE = re.compile(r"^\d+$")
_TERMINAL_STARTER_CODES = {"F", "PU", "UR", "BD", "RO", "DSQ"}
_EXPLICIT_NON_RUNNER_CODES = {"NR", "WD"}

OUTCOME_FINISHED = "FINISHED"
OUTCOME_TERMINAL = "TERMINAL"
OUTCOME_NON_RUNNER = "NON_RUNNER"
OUTCOME_UNKNOWN = "UNKNOWN"

RACE_STATUS_ABANDONED = "ABANDONED"
RACE_STATUS_VOID = "VOID"
_RACE_VOID_STATUSES = {RACE_STATUS_ABANDONED, RACE_STATUS_VOID}
_REQUIRED_RACE_STATUS_EVIDENCE = {"source_name", "source_url", "observed_at"}
_RACE_STATUS_CONTRACT = "GOVERNED_RACE_STATUS_V1"


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def runner_outcome_status(position_value: str | None) -> str:
    v = str(position_value or "").strip().upper()
    if _NUMERIC_POSITION_RE.match(v):
        return OUTCOME_FINISHED
    if v in _TERMINAL_STARTER_CODES:
        return OUTCOME_TERMINAL
    if v in _EXPLICIT_NON_RUNNER_CODES:
        return OUTCOME_NON_RUNNER
    return OUTCOME_UNKNOWN  # blank or unrecognised -- never automatically NR


def authoritative_race_void(race: dict | None) -> bool:
    """Recognise only explicitly evidenced whole-race abandonments/voids."""
    if not isinstance(race, dict):
        return False
    status = str(race.get("race_status") or "").strip().upper()
    evidence = race.get("race_status_evidence")
    if status not in _RACE_VOID_STATUSES or not isinstance(evidence, dict):
        return False
    if set(evidence) != _REQUIRED_RACE_STATUS_EVIDENCE:
        return False
    if not all(str(evidence.get(field) or "").strip() for field in _REQUIRED_RACE_STATUS_EVIDENCE):
        return False
    parsed_url = urlparse(str(evidence["source_url"]).strip())
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return False
    try:
        observed = datetime.fromisoformat(str(evidence["observed_at"]).strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return observed.tzinfo is not None and observed.utcoffset() is not None


def load_race_status_evidence(date: str, results_dir: Path = RESULTS_DIR_DEFAULT) -> list[dict]:
    """Load governed race-status evidence; malformed claims fail closed."""
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid requested race date: {date!r}") from exc
    if parsed_date.strftime("%Y-%m-%d") != date:
        raise ValueError(f"invalid requested race date: {date!r}")
    path = results_dir / f"race_status_{date.replace('-', '_')}.json"
    if not path.exists():
        path = Path(__file__).resolve().parents[3] / "config" / "race_status" / path.name
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) - {"date", "contract", "races", "corroboration"}:
        raise ValueError(f"invalid race-status document shape in {path}")
    if payload.get("date") != date or payload.get("contract") != _RACE_STATUS_CONTRACT:
        raise ValueError(f"race-status contract/date mismatch in {path}")
    rows = payload.get("races")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"race-status races must be a non-empty list in {path}")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"invalid race-status row in {path}")
        race_id = str(row.get("race_id") or "").strip()
        if not race_id or race_id in seen or row.get("race_id") != race_id:
            raise ValueError(f"blank, non-canonical, or duplicate race_id in {path}")
        seen.add(race_id)
        if set(row) - {"race_id", "course", "off", "race_status", "race_status_evidence"}:
            raise ValueError(f"unexpected race-status row fields in {path}")
        if row.get("race_status") not in _RACE_VOID_STATUSES or not authoritative_race_void(row):
            raise ValueError(f"invalid or unauthoritative race-status evidence in {path}")
    return rows


def merge_result_and_status_rows(result_rows: list[dict], status_rows: list[dict]) -> list[dict]:
    """Merge independent status truth while refusing result/status collisions."""
    result_ids = [str(row.get("race_id") or "").strip() for row in result_rows if isinstance(row, dict)]
    status_ids = [str(row.get("race_id") or "").strip() for row in status_rows]
    if len(result_ids) != len(set(result_ids)):
        raise ValueError("duplicate race_id in parsed results")
    collisions = sorted(set(result_ids) & set(status_ids))
    if collisions:
        raise ValueError(f"race status/result collision for race_id(s): {', '.join(collisions)}")
    return list(result_rows) + list(status_rows)


@dataclass
class RaceCompleteness:
    race_id: str
    accounted: bool
    missing_from_result: tuple[str, ...] = field(default_factory=tuple)
    unknown_status_horses: tuple[str, ...] = field(default_factory=tuple)


def _race_completeness(race: dict, expected_horse_ids: set[str] | None) -> RaceCompleteness:
    if authoritative_race_void(race):
        return RaceCompleteness(race_id=race.get("race_id", ""), accounted=True)
    runners = race.get("runners", [])
    non_runner_names = {_norm(n) for n in race.get("non_runners", []) if isinstance(n, str)}

    statuses: dict[str, str] = {}
    for r in runners:
        hid = r.get("horse_id")
        if not hid:
            continue
        status = runner_outcome_status(r.get("position") or r.get("position_text"))
        if status == OUTCOME_UNKNOWN and _norm(r.get("horse")) in non_runner_names:
            status = OUTCOME_NON_RUNNER
        statuses[hid] = status

    if expected_horse_ids is None:
        accounted = len(statuses) > 0 and all(s != OUTCOME_UNKNOWN for s in statuses.values())
        missing: set[str] = set()
    else:
        missing = expected_horse_ids - set(statuses)
        accounted = not missing and all(
            statuses.get(hid) != OUTCOME_UNKNOWN for hid in expected_horse_ids if hid in statuses
        )

    unknown = [hid for hid, s in statuses.items() if s == OUTCOME_UNKNOWN]
    return RaceCompleteness(
        race_id=race.get("race_id", ""),
        accounted=accounted,
        missing_from_result=tuple(sorted(missing)),
        unknown_status_horses=tuple(sorted(unknown)),
    )


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


def _sha256_of_rows(rows: list[dict]) -> str:
    """Deterministic hash of ordered canonical rows -- used for Supabase
    result snapshots, which have no file to hash directly."""
    canonical = sorted(
        ({"race_id": r.get("race_id"), "runners": r.get("runners", [])} for r in rows),
        key=lambda r: str(r["race_id"]),
    )
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _local_file_path(date: str, results_dir: Path) -> Path:
    return results_dir / f"rp_results_{date.replace('-', '_')}.json"


def _load_local_rp_file(date: str, results_dir: Path) -> tuple[list[dict], str | None, dict]:
    path = _local_file_path(date, results_dir)
    if not path.exists():
        return [], None, {"exists": False, "races_parsed": 0, "races_with_runners": 0, "races_total": 0}
    raw = path.read_text(encoding="utf-8")
    status_rows = load_race_status_evidence(date, results_dir)
    status_raw = json.dumps(status_rows, sort_keys=True, ensure_ascii=False)
    source_hash = _sha256_of_text(raw + "\n--RACE-STATUS-EVIDENCE--\n" + status_raw)
    data = json.loads(raw)
    result_rows = list(data.get("results", []) if isinstance(data, dict) else data)
    if not all(isinstance(row, dict) for row in result_rows):
        raise ValueError(f"invalid result row in {path}")
    races = merge_result_and_status_rows(result_rows, status_rows)
    status = data.get("status") if isinstance(data, dict) else None
    races_parsed = data.get("races_parsed", len(result_rows)) if isinstance(data, dict) else len(result_rows)
    if isinstance(races_parsed, bool) or not isinstance(races_parsed, int) or races_parsed != len(result_rows):
        raise ValueError(f"impossible races_parsed count in {path}")
    parse_errors = data.get("parse_errors", 0) if isinstance(data, dict) else 0
    html_files_seen = data.get("html_files_seen") if isinstance(data, dict) else None
    if isinstance(parse_errors, bool) or not isinstance(parse_errors, int) or parse_errors < 0:
        raise ValueError(f"impossible parse_errors count in {path}")
    if html_files_seen is not None:
        if isinstance(html_files_seen, bool) or not isinstance(html_files_seen, int) or html_files_seen < 0:
            raise ValueError(f"impossible html_files_seen count in {path}")
        if races_parsed + parse_errors > html_files_seen:
            raise ValueError(f"impossible result coverage counts in {path}")
    races_with_runners = [r for r in races if r.get("runners") or authoritative_race_void(r)]
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


def _evaluate_completeness(
    races: list[dict],
    expected_race_ids: set[str] | None,
    expected_runners_by_race: dict[str, set[str]] | None,
) -> dict[str, Any]:
    """Compare the observed races against the caller's expected
    prediction-side universe. Returns a report; `full_universe_complete`
    is only True when every expected race is present AND every expected
    runner in every expected race is accounted for."""
    present_race_ids = {r.get("race_id") for r in races if r.get("race_id")}
    expected_race_ids = expected_race_ids or set()
    missing_races = sorted(expected_race_ids - present_race_ids)

    race_reports = []
    for race in races:
        rid = race.get("race_id")
        expected_horses = (expected_runners_by_race or {}).get(rid)
        race_reports.append(_race_completeness(race, expected_horses))

    fully_accounted_races = [rc.race_id for rc in race_reports if rc.accounted]
    partial_races = [rc.race_id for rc in race_reports if not rc.accounted]

    expectation_provided = bool(expected_race_ids or expected_runners_by_race)
    full_universe_complete = (
        expectation_provided
        and not missing_races
        and all(rc.accounted for rc in race_reports)
        and len(race_reports) > 0
    )

    return {
        "expectation_provided": expectation_provided,
        "expected_races": len(expected_race_ids),
        "missing_races": missing_races,
        "races_present": len(races),
        "races_fully_accounted": len(fully_accounted_races),
        "races_partial": len(partial_races),
        "partial_race_ids": partial_races,
        "full_universe_complete": full_universe_complete,
        "race_completeness_by_id": {rc.race_id: rc.accounted for rc in race_reports},
    }


def select_result_source(
    date: str,
    *,
    results_dir: Path = RESULTS_DIR_DEFAULT,
    supabase_fetch: Callable[[str], list[dict]] | None = None,
    expected_race_ids: set[str] | None = None,
    expected_runners_by_race: dict[str, set[str]] | None = None,
) -> ResultSourceSelection:
    """
    date: "YYYY-MM-DD"
    supabase_fetch: injected callable date -> list[race rows], so this
        stays testable without a live Supabase connection.
    expected_race_ids / expected_runners_by_race: the prediction-side
        universe to check completeness against. Without these, this
        function falls back to a weaker "does this file look internally
        populated" heuristic and flags `expectation_provided: False` so
        callers know the completeness claim is unproven against the real
        expected universe -- it can never be silently treated as strong.
    """
    local_races, local_hash, local_file_stats = _load_local_rp_file(date, results_dir)
    local_completeness = _evaluate_completeness(local_races, expected_race_ids, expected_runners_by_race)
    local_completeness.update(local_file_stats)

    if local_completeness["expectation_provided"]:
        local_complete = local_file_stats["exists"] and local_completeness["full_universe_complete"]
    else:
        # Weak fallback heuristic only used when the caller supplied no
        # expected universe to check against -- a file that looks like it
        # only carries winner/top-three data (<=3 runners, no non-runner
        # accounting at all) is never treated as primary-complete even
        # under this weaker heuristic.
        only_winner_data = local_races and all(
            len(r.get("runners", [])) <= 3 and not r.get("non_runners") for r in local_races
        )
        local_complete = (
            local_file_stats["exists"]
            and not only_winner_data
            and local_file_stats["races_with_runners"] > 0
            and local_file_stats["races_with_runners"] == local_file_stats["races_total"]
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
        if local_file_stats["exists"]:
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
    # not by the date. A mixed scheme (some rp_, some not) is reported
    # honestly rather than being called canonical off a single rp_ row.
    race_id_prefixes = Counter("rp_" if str(r.get("race_id", "")).startswith("rp_") else "other" for r in supa_races)
    if race_id_prefixes["rp_"] > 0 and race_id_prefixes["other"] > 0:
        source = SOURCE_SUPABASE_MIXED
    elif race_id_prefixes["rp_"] > 0:
        source = SOURCE_SUPABASE_CANONICAL
    else:
        source = SOURCE_SUPABASE_LEGACY

    supa_race_ids = [r.get("race_id") for r in supa_races if r.get("race_id")]
    duplicate_supa_ids = sorted({rid for rid, c in Counter(supa_race_ids).items() if c > 1})

    supa_completeness = _evaluate_completeness(supa_races, expected_race_ids, expected_runners_by_race)
    supa_completeness["duplicate_race_ids"] = duplicate_supa_ids
    supa_hash = _sha256_of_rows(supa_races)

    if local_file_stats["exists"] and local_races:
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
                completeness={"local": local_completeness, "supabase": supa_completeness},
                races=[],
                conflict_detail={"conflicts": conflicts},
            )

    if duplicate_supa_ids:
        classification = CLASS_PARTIAL  # cannot trust a source with duplicate race identities
    elif source == SOURCE_SUPABASE_CANONICAL and supa_completeness.get("full_universe_complete", False):
        classification = CLASS_FALLBACK_VERIFIED
    elif source == SOURCE_SUPABASE_CANONICAL:
        classification = CLASS_PARTIAL
    else:
        classification = CLASS_SUPABASE_LEGACY

    return ResultSourceSelection(
        date=date,
        source=source,
        classification=classification,
        path_or_table="supabase:races/runner_results",
        source_hash=supa_hash,
        completeness=supa_completeness,
        races=supa_races,
    )
