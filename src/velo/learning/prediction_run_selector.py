"""
Canonical prediction-run selector — LEARNING-LOOP-01A correction (P0-1,
P0-8).

`runner_prediction_snapshots` must be grouped by (race_id, run_id), never
by race_id alone. A single race_id can carry many independent scoring
runs — repeated re-scoring passes across a day, sometimes hours apart —
and pooling all of them into one race silently invents a race with 2-4x
the real field, duplicate horses, and a meaningless rank_order/top_three.

Confirmed on real data: race_id 921866 (2026-06-03) has 8 distinct
run_ids, each independently scoring the full 23-horse field, for 184
pooled rows and 8x-duplicated horse identities if grouped by race_id
alone.

This module selects exactly one canonical run per race through a strict,
deterministic rule, or declares the race unresolved if no run qualifies.
It never merges rows across run_ids.

P0-8 correction: race off-times are LOCAL venue times, not UTC. A UK
15:15 race is 14:15 UTC in BST (British Summer Time), not 15:15 UTC --
the previous implementation assumed UTC directly, giving every summer
snapshot a false one-hour pre-race window. Off-times are now localized
via `zoneinfo` using an explicit course->timezone mapping and converted
to UTC before comparison. A race whose venue's jurisdiction is not in
that mapping is TIMEZONE_UNPROVEN -- its runs may still be selected (for
analysis only) but can never be labelled PROVEN_PRE_RACE. And critically:
if every timed candidate run for a race is proven to be AFTER the race's
off-time, no run is selected -- the race is excluded as NO_PRE_RACE_RUN.
A post-race prediction snapshot must never become the canonical
prediction run.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.velo.learning.identity_resolver import normalise_name, parse_time_to_minutes

REASON_NO_COMPLETE_RUN = "NO_COMPLETE_RUN"
REASON_AMBIGUOUS_RUN_SELECTION = "AMBIGUOUS_RUN_SELECTION"
REASON_DUPLICATE_HORSE_IN_RUN = "DUPLICATE_HORSE_IN_RUN"
REASON_DUPLICATE_RANK_IN_RUN = "DUPLICATE_RANK_IN_RUN"
REASON_NO_PRE_RACE_RUN = "NO_PRE_RACE_RUN"

PROOF_PRE_RACE = "PROVEN_PRE_RACE"
PROOF_POST_RACE = "PROVEN_POST_RACE"
PROOF_TIMEZONE_UNPROVEN = "TIMEZONE_UNPROVEN"
PROOF_UNPROVEN = "UNPROVEN"

# Explicit course -> IANA timezone mapping. Deliberately NOT a default --
# an unmapped course is TIMEZONE_UNPROVEN, never silently assumed to be
# UK. Keys are normalised (lowercase, alnum-only) via identity_resolver's
# normalise_name, covering both 3-letter RP codes and full course names
# seen across runner_prediction_snapshots / racecard_merged.
_GB_TZ = "Europe/London"
_IRE_TZ = "Europe/Dublin"

_IRE_COURSES = [
    "dundalk",
    "dun",
    "sligo",
    "sli",
    "curragh",
    "cur",
    "leopardstown",
    "leo",
    "naas",
    "navan",
    "nav",
    "fairyhouse",
    "fai",
    "punchestown",
    "pun",
    "gowranpark",
    "gow",
    "downroyal",
    "downpatrick",
    "killarney",
    "kil",
    "listowel",
    "tramore",
    "tra",
    "roscommon",
    "ros",
    "ballinrobe",
    "bal",
    "bellewstown",
    "clonmel",
    "clo",
    "cork",
    "cor",
    "galway",
    "kilbeggan",
    "klb",
    "laytown",
    "limerick",
    "lim",
    "thurles",
    "thi",
    "tipperary",
    "wexford",
    "wex",
    "corkgowran",
]

_GB_COURSES = [
    "ascot",
    "asc",
    "aintree",
    "ayr",
    "bangorondee",
    "bath",
    "bat",
    "beverley",
    "bev",
    "brighton",
    "bri",
    "cartmel",
    "carlisle",
    "car",
    "catterick",
    "cat",
    "chepstow",
    "chp",
    "chelmsfordcity",
    "chester",
    "chs",
    "doncaster",
    "don",
    "epsom",
    "eps",
    "exeter",
    "fakenham",
    "ffoslas",
    "ffo",
    "fontwell",
    "flk",
    "goodwood",
    "goo",
    "hamilton",
    "ham",
    "haydock",
    "hereford",
    "hexham",
    "hex",
    "huntingdon",
    "kelso",
    "kempton",
    "kem",
    "leicester",
    "lei",
    "lingfield",
    "lin",
    "linaw",
    "ludlow",
    "marketrasen",
    "mar",
    "musselburgh",
    "mus",
    "newbury",
    "newcastle",
    "newcastleaw",
    "newmarket",
    "newmarketjuly",
    "new",
    "newtonabbot",
    "nottingham",
    "not",
    "perth",
    "per",
    "plumpton",
    "pontefract",
    "pon",
    "redcar",
    "red",
    "ripon",
    "rip",
    "salisbury",
    "sal",
    "sandown",
    "san",
    "sedgefield",
    "southwell",
    "sth",
    "stratford",
    "str",
    "taunton",
    "thirsk",
    "towcester",
    "uttoxeter",
    "warwick",
    "wetherby",
    "wet",
    "wincanton",
    "windsor",
    "win",
    "wolverhampton",
    "wol",
    "worcester",
    "wor",
    "yarmouth",
    "yar",
    "york",
    "yor",
    "cartmelbangor",
]

_COURSE_TIMEZONE: dict[str, str] = {}
for _c in _IRE_COURSES:
    _COURSE_TIMEZONE[_c] = _IRE_TZ
for _c in _GB_COURSES:
    _COURSE_TIMEZONE[_c] = _GB_TZ


def course_timezone(course: str | None) -> str | None:
    """Explicit course->timezone lookup. Returns None (TIMEZONE_UNPROVEN)
    for anything not in the known GB/IRE mapping -- never guesses."""
    return _COURSE_TIMEZONE.get(normalise_name(course))


@dataclass
class RunSelection:
    race_id: str
    selected_run_id: str | None
    selected_rows: list[dict] = field(default_factory=list)
    resolved: bool = False
    reason: str | None = None
    candidate_run_ids: list[str] = field(default_factory=list)
    excluded_runs: dict[str, str] = field(default_factory=dict)  # run_id -> exclusion reason
    pre_race_proof: str = PROOF_UNPROVEN


def _parse_utc(value: Any) -> datetime | None:
    """Parse an ISO timestamp into a tz-aware UTC datetime. Naive inputs
    are assumed UTC (Supabase `created_at` is stored in UTC)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _race_off_datetime_utc(
    race_date: str | None, off_time: str | None, course: str | None
) -> tuple[datetime | None, str]:
    """Returns (off_datetime_utc, status). `status` is PROOF_TIMEZONE_UNPROVEN
    if the course's jurisdiction is unmapped, PROOF_UNPROVEN if the
    date/time itself is unparseable, or "OK" once a timezone-correct UTC
    off-datetime was computed -- callers must not treat a None datetime
    as proof of pre/post-race timing."""
    minutes = parse_time_to_minutes(off_time)
    if minutes is None or not race_date:
        return None, PROOF_UNPROVEN

    tz_name = course_timezone(course)
    if tz_name is None:
        return None, PROOF_TIMEZONE_UNPROVEN

    try:
        local_date = datetime.fromisoformat(str(race_date))
    except ValueError:
        return None, PROOF_UNPROVEN

    local_naive = local_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=minutes)
    local_aware = local_naive.replace(tzinfo=ZoneInfo(tz_name))
    return local_aware.astimezone(UTC), "OK"


def _run_created_at(run_rows: list[dict]) -> datetime | None:
    timestamps = [t for t in (_parse_utc(r.get("created_at")) for r in run_rows) if t is not None]
    return max(timestamps) if timestamps else None


def select_canonical_run(race_id: str, rows: list[dict]) -> RunSelection:
    """
    rows: all runner_prediction_snapshots rows for this race_id, spanning
    possibly many run_ids. Each row should carry run_id, horse_id, rank,
    created_at, race_date, off_time, course.

    Hard gates applied per run before it becomes a candidate:
      - no duplicate horse_id within the run
      - no duplicate rank value within the run (no implicit tie policy)
    Among surviving candidates:
      - if the venue's timezone is known and at least one candidate run
        is provably before the race's (timezone-correct) off-time, select
        the latest such run -- PROVEN_PRE_RACE.
      - if the venue's timezone is known but EVERY timed candidate is
        after off-time, no run is selected: the race is excluded as
        NO_PRE_RACE_RUN. A post-race snapshot must never become the
        canonical prediction run.
      - if the venue's timezone is unmapped, timing cannot be proven
        either way -- the latest run is retained for analysis only,
        proof=TIMEZONE_UNPROVEN (never PROVEN_PRE_RACE).
      - a tie at the latest timestamp among the winning set is
        AMBIGUOUS_RUN_SELECTION, not a silent pick.
    """
    runs: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        runs[r.get("run_id")].append(r)

    candidate_run_ids: list[str] = []
    excluded_runs: dict[str, str] = {}

    for run_id, run_rows in runs.items():
        horse_ids = [r.get("horse_id") for r in run_rows if r.get("horse_id")]
        if len(horse_ids) != len(set(horse_ids)):
            excluded_runs[run_id] = REASON_DUPLICATE_HORSE_IN_RUN
            continue

        ranks = [r.get("rank") for r in run_rows if r.get("rank") is not None]
        if len(ranks) != len(set(ranks)):
            excluded_runs[run_id] = REASON_DUPLICATE_RANK_IN_RUN
            continue

        candidate_run_ids.append(run_id)

    if not candidate_run_ids:
        return RunSelection(
            race_id=race_id,
            selected_run_id=None,
            resolved=False,
            reason=REASON_NO_COMPLETE_RUN,
            candidate_run_ids=[],
            excluded_runs=excluded_runs,
        )

    first_row = rows[0]
    off_dt, tz_proof = _race_off_datetime_utc(
        first_row.get("race_date"), first_row.get("off_time"), first_row.get("course")
    )

    run_ts = {rid: _run_created_at(runs[rid]) for rid in candidate_run_ids}
    eligible = candidate_run_ids
    pre_race_proof = PROOF_UNPROVEN

    if tz_proof == PROOF_TIMEZONE_UNPROVEN:
        pre_race_proof = PROOF_TIMEZONE_UNPROVEN
        # timing unprovable either way -- fall through to latest-overall,
        # retained for analysis only, never labelled PROVEN_PRE_RACE.
    elif off_dt is not None:
        timed = {rid: ts for rid, ts in run_ts.items() if ts is not None}
        if timed:
            pre_race = [rid for rid, ts in timed.items() if ts <= off_dt]
            if pre_race:
                eligible = pre_race
                pre_race_proof = PROOF_PRE_RACE
            else:
                # Every timed candidate run is after the race's real
                # off-time -- a post-race snapshot must never become the
                # canonical prediction run.
                return RunSelection(
                    race_id=race_id,
                    selected_run_id=None,
                    resolved=False,
                    reason=REASON_NO_PRE_RACE_RUN,
                    candidate_run_ids=candidate_run_ids,
                    excluded_runs=excluded_runs,
                    pre_race_proof=PROOF_POST_RACE,
                )

    def sort_ts(rid: str) -> datetime:
        return run_ts.get(rid) or datetime.min.replace(tzinfo=UTC)

    ranked = sorted(eligible, key=sort_ts)
    latest_ts = sort_ts(ranked[-1])
    tied = [rid for rid in ranked if sort_ts(rid) == latest_ts]

    if len(tied) > 1:
        return RunSelection(
            race_id=race_id,
            selected_run_id=None,
            resolved=False,
            reason=REASON_AMBIGUOUS_RUN_SELECTION,
            candidate_run_ids=candidate_run_ids,
            excluded_runs=excluded_runs,
            pre_race_proof=pre_race_proof,
        )

    selected_run_id = tied[0]
    return RunSelection(
        race_id=race_id,
        selected_run_id=selected_run_id,
        selected_rows=runs[selected_run_id],
        resolved=True,
        candidate_run_ids=candidate_run_ids,
        excluded_runs=excluded_runs,
        pre_race_proof=pre_race_proof,
    )
