"""
Canonical prediction-run selector — LEARNING-LOOP-01A correction (P0-1).

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
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.velo.learning.identity_resolver import parse_time_to_minutes

REASON_NO_COMPLETE_RUN = "NO_COMPLETE_RUN"
REASON_AMBIGUOUS_RUN_SELECTION = "AMBIGUOUS_RUN_SELECTION"
REASON_DUPLICATE_HORSE_IN_RUN = "DUPLICATE_HORSE_IN_RUN"
REASON_DUPLICATE_RANK_IN_RUN = "DUPLICATE_RANK_IN_RUN"

PROOF_PRE_RACE = "PROVEN_PRE_RACE"
PROOF_POST_RACE = "PROVEN_POST_RACE"
PROOF_UNPROVEN = "UNPROVEN"


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


def _race_off_datetime(race_date: str | None, off_time: str | None) -> datetime | None:
    minutes = parse_time_to_minutes(off_time)
    if minutes is None or not race_date:
        return None
    try:
        base = datetime.fromisoformat(str(race_date))
    except ValueError:
        return None
    from datetime import timedelta

    return base.replace(tzinfo=UTC) + timedelta(minutes=minutes)


def _run_created_at(run_rows: list[dict]) -> datetime | None:
    timestamps = [t for t in (_parse_utc(r.get("created_at")) for r in run_rows) if t is not None]
    return max(timestamps) if timestamps else None


def select_canonical_run(race_id: str, rows: list[dict]) -> RunSelection:
    """
    rows: all runner_prediction_snapshots rows for this race_id, spanning
    possibly many run_ids. Each row should carry run_id, horse_id, rank,
    created_at, race_date, off_time.

    Hard gates applied per run before it becomes a candidate:
      - no duplicate horse_id within the run
      - no duplicate rank value within the run (no implicit tie policy)
    Among surviving candidates:
      - prefer runs provably before the race off-time (when timestamps
        and off-time both parse)
      - select the run with the latest creation timestamp among the
        eligible set (the freshest complete pre-race scoring pass)
      - a tie at the latest timestamp is AMBIGUOUS_RUN_SELECTION, not a
        silent pick
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
    off_dt = _race_off_datetime(first_row.get("race_date"), first_row.get("off_time"))

    run_ts = {rid: _run_created_at(runs[rid]) for rid in candidate_run_ids}
    eligible = candidate_run_ids
    pre_race_proof = PROOF_UNPROVEN

    if off_dt is not None:
        timed = {rid: ts for rid, ts in run_ts.items() if ts is not None}
        if timed:
            pre_race = [rid for rid, ts in timed.items() if ts <= off_dt]
            if pre_race:
                eligible = pre_race
                pre_race_proof = PROOF_PRE_RACE
            else:
                pre_race_proof = PROOF_POST_RACE  # every timed candidate is after off -- fall through

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
