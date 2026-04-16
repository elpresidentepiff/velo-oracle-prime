"""
VÉLØ Doctrine Evidence Board
============================
Read-only sidecar report for the Doctrine Layer.

Doctrine review clock:
  - sigma_audits.created_at
  - truth and RPDC rows are supporting evidence mapped onto the reviewed sigma set
  - doctrine_event_id is preferred when present; legacy keys are fallback only

Sections:
  - live results
  - shadow results
  - blocker truth
  - RPDC truth
  - weak A cohort
  - doctrine candidates
  - doctrine contradictions

Read path order:
  1. Supabase management SQL API when a valid access token exists
  2. PostgREST/service-role reads
  3. hard-fail clearly

Run:
  python scripts/generate_doctrine_evidence_board.py --date 2026-04-15
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests
from dotenv import load_dotenv

from app.runtime.doctrine_sidecar_common import (
    chunked,
    contradiction_type,
    dedupe_latest_rpdc_rows,
    dedupe_latest_sigma_rows,
    dedupe_latest_truth_rows,
    doctrine_status_for_type,
    outcome_rate_rows,
    rpdc_coverage_metrics,
    rpdc_for_sigma_row,
    rpdc_selection_lookup,
    review_race_ids,
    sp_bucket,
    surface_bucket,
    top_counts,
    truth_for_sigma_row,
    truth_lookup,
    is_weak_a,
)

load_dotenv(ROOT / ".env")


class DoctrineRegistryMissing(RuntimeError):
    """Raised when the doctrine registry table is absent."""


class ReadPathUnavailable(RuntimeError):
    """Raised when no read path can access the required data."""


def _session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def _management_sql(query: str) -> list[dict] | None:
    url = os.getenv("SUPABASE_URL", "")
    token = os.getenv("SUPABASE_ACCESS_TOKEN", "")
    if not url or not token:
        return None

    project_ref = url.split("//")[-1].split(".")[0]
    response = _session().post(
        f"https://api.supabase.com/v1/projects/{project_ref}/database/query",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=20,
    )
    if response.status_code in (401, 403):
        return None
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


def _service_role_key() -> str:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or ""


def _rest_fetch(table: str, select: str, filters: list[str] | None = None) -> list[dict]:
    url = os.getenv("SUPABASE_URL", "")
    key = _service_role_key()
    if not url or not key:
        raise ReadPathUnavailable(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY) are required for PostgREST fallback."
        )

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    rows: list[dict] = []
    offset = 0
    page_size = 1000
    filters = filters or []
    session = _session()

    while True:
        params = [("select", select), ("limit", str(page_size)), ("offset", str(offset))]
        params.extend((item.split("=", 1)[0], item.split("=", 1)[1]) for item in filters if "=" in item)
        response = session.get(f"{url}/rest/v1/{table}", headers=headers, params=params, timeout=20)
        if response.status_code >= 400:
            body = response.text
            if table == "velo_doctrine_registry" and (
                "velo_doctrine_registry" in body or "relation" in body.lower() or "does not exist" in body.lower()
            ):
                raise DoctrineRegistryMissing("Doctrine registry missing — apply migration + seed before running reports.")
            response.raise_for_status()
        batch = response.json()
        if not isinstance(batch, list):
            return rows
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _fetch_sigma_audits(target_date: str) -> list[dict]:
    start_ts = f"{target_date}T00:00:00+00:00"
    end_ts = f"{target_date}T23:59:59+00:00"
    sql_rows = _management_sql(f"""
        SELECT race_id, doctrine_event_id, decision_tier, confidence_level, verdict_score, outcome, top_pick_position, miss_reason, track, created_at
               , horse_id
        FROM sigma_audits
        WHERE created_at >= '{start_ts}' AND created_at <= '{end_ts}' AND outcome IS NOT NULL
        ORDER BY created_at ASC
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "sigma_audits",
        "race_id,doctrine_event_id,decision_tier,confidence_level,verdict_score,outcome,top_pick_position,miss_reason,track,created_at,horse_id",
        [f"created_at=gte.{start_ts}", f"created_at=lte.{end_ts}", "outcome=not.is.null"],
    )


def _fetch_sigma_audits_window(start_date: str, end_date: str) -> list[dict]:
    start_ts = f"{start_date}T00:00:00+00:00"
    end_ts = f"{end_date}T23:59:59+00:00"
    sql_rows = _management_sql(f"""
        SELECT race_id, doctrine_event_id, decision_tier, confidence_level, verdict_score, outcome, top_pick_position, miss_reason, track, created_at
               , horse_id
        FROM sigma_audits
        WHERE created_at >= '{start_ts}' AND created_at <= '{end_ts}' AND outcome IS NOT NULL
        ORDER BY created_at ASC
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "sigma_audits",
        "race_id,doctrine_event_id,decision_tier,confidence_level,verdict_score,outcome,top_pick_position,miss_reason,track,created_at,horse_id",
        [f"created_at=gte.{start_ts}", f"created_at=lte.{end_ts}", "outcome=not.is.null"],
    )


def _fetch_race_truth_audits(target_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, doctrine_event_id, race_date, generated_at, result_outcome, blocker_fired, blocker_type, blocker_helped, blocker_hurt, assigned_archetype
        FROM race_truth_audits
        WHERE race_date = '{target_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "race_truth_audits",
        "race_id,doctrine_event_id,race_date,generated_at,result_outcome,blocker_fired,blocker_type,blocker_helped,blocker_hurt,assigned_archetype",
        [f"race_date=eq.{target_date}"],
    )


def _fetch_race_truth_audits_window(start_date: str, end_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, doctrine_event_id, race_date, generated_at, result_outcome, blocker_fired, blocker_type, blocker_helped, blocker_hurt, assigned_archetype, actual_winner_sp
        FROM race_truth_audits
        WHERE race_date >= '{start_date}' AND race_date <= '{end_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "race_truth_audits",
        "race_id,doctrine_event_id,race_date,generated_at,result_outcome,blocker_fired,blocker_type,blocker_helped,blocker_hurt,assigned_archetype,actual_winner_sp",
        [f"race_date=gte.{start_date}", f"race_date=lte.{end_date}"],
    )


def _fetch_today_rpdc_tags(target_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, doctrine_event_id, horse_id, tag, tag_value, tag_strength
        FROM today_rpdc_tags
        WHERE run_date = '{target_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "today_rpdc_tags",
        "race_id,doctrine_event_id,horse_id,tag,tag_value,tag_strength",
        [f"run_date=eq.{target_date}"],
    )


def _fetch_runner_release_candidates(target_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, doctrine_event_id, horse_id, run_date, generated_at, rpdc_cash_window_flag, rpdc_release_score, rpdc_tag_count
        FROM runner_release_candidates
        WHERE run_date = '{target_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "runner_release_candidates",
        "race_id,doctrine_event_id,horse_id,run_date,generated_at,rpdc_cash_window_flag,rpdc_release_score,rpdc_tag_count",
        [f"run_date=eq.{target_date}"],
    )


def _fetch_runner_release_candidates_window(start_date: str, end_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, doctrine_event_id, horse_id, run_date, generated_at, rpdc_cash_window_flag, rpdc_release_score, rpdc_tag_count
        FROM runner_release_candidates
        WHERE run_date >= '{start_date}' AND run_date <= '{end_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "runner_release_candidates",
        "race_id,doctrine_event_id,horse_id,run_date,generated_at,rpdc_cash_window_flag,rpdc_release_score,rpdc_tag_count",
        [f"run_date=gte.{start_date}", f"run_date=lte.{end_date}"],
    )


def _fetch_doctrine_rows() -> list[dict]:
    sql_rows = _management_sql("""
        SELECT doctrine_key, family, rule_type, status, sample_size, win_pct, place_pct, next_review_date
        FROM velo_doctrine_registry
        ORDER BY family ASC, doctrine_key ASC
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "velo_doctrine_registry",
        "doctrine_key,family,rule_type,status,sample_size,win_pct,place_pct,next_review_date",
    )


def _sql_in_list(values: list[str]) -> str:
    return ",".join("'" + value.replace("'", "''") + "'" for value in values)


def _fetch_race_truth_for_sigma_rows(sigma_rows: list[dict[str, Any]]) -> list[dict]:
    race_ids = review_race_ids(sigma_rows)
    if not race_ids:
        return []
    select_sql = (
        "race_id, doctrine_event_id, race_date, generated_at, result_outcome, blocker_fired, blocker_type, "
        "blocker_helped, blocker_hurt, assigned_archetype, actual_winner_sp"
    )
    select_rest = (
        "race_id,doctrine_event_id,race_date,generated_at,result_outcome,blocker_fired,blocker_type,"
        "blocker_helped,blocker_hurt,assigned_archetype,actual_winner_sp"
    )
    rows: list[dict] = []
    for race_chunk in chunked(race_ids):
        sql_rows = _management_sql(
            f"SELECT {select_sql} FROM race_truth_audits WHERE race_id IN ({_sql_in_list(race_chunk)})"
        )
        if sql_rows is not None:
            rows.extend(sql_rows)
            continue
        rows.extend(
            _rest_fetch(
                "race_truth_audits",
                select_rest,
                [f"race_id=in.({','.join(race_chunk)})"],
            )
        )
    return dedupe_latest_truth_rows(rows)


def _fetch_runner_release_for_sigma_rows(sigma_rows: list[dict[str, Any]]) -> list[dict]:
    race_ids = review_race_ids(sigma_rows)
    if not race_ids:
        return []
    select_sql = (
        "race_id, doctrine_event_id, horse_id, run_date, generated_at, rpdc_cash_window_flag, "
        "rpdc_release_score, rpdc_tag_count"
    )
    select_rest = (
        "race_id,doctrine_event_id,horse_id,run_date,generated_at,rpdc_cash_window_flag,"
        "rpdc_release_score,rpdc_tag_count"
    )
    rows: list[dict] = []
    for race_chunk in chunked(race_ids):
        sql_rows = _management_sql(
            f"SELECT {select_sql} FROM runner_release_candidates WHERE race_id IN ({_sql_in_list(race_chunk)})"
        )
        if sql_rows is not None:
            rows.extend(sql_rows)
            continue
        rows.extend(
            _rest_fetch(
                "runner_release_candidates",
                select_rest,
                [f"race_id=in.({','.join(race_chunk)})"],
            )
        )
    return dedupe_latest_rpdc_rows(rows)


def _fetch_rpdc_tags_for_sigma_rows(sigma_rows: list[dict[str, Any]], review_date: str) -> list[dict]:
    # today_rpdc_tags has no generated_at. We map tags onto the sigma review set by race_id and
    # constrain to the sigma review date as the nearest available RPDC clock.
    race_ids = review_race_ids(sigma_rows)
    if not race_ids:
        return []
    rows: list[dict] = []
    for race_chunk in chunked(race_ids):
        sql_rows = _management_sql(
            f"""
            SELECT race_id, doctrine_event_id, horse_id, run_date, tag, tag_value, tag_strength
            FROM today_rpdc_tags
            WHERE run_date = '{review_date}' AND race_id IN ({_sql_in_list(race_chunk)})
            """
        )
        if sql_rows is not None:
            rows.extend(sql_rows)
            continue
        rows.extend(
            _rest_fetch(
                "today_rpdc_tags",
                "race_id,doctrine_event_id,horse_id,run_date,tag,tag_value,tag_strength",
                [f"run_date=eq.{review_date}", f"race_id=in.({','.join(race_chunk)})"],
            )
        )
    return rows


def _md_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(v) if v is not None else "—" for v in row) + " |")
    return lines


def _contradiction_count(
    sigma_rows: list[dict],
    truth_rows: list[dict],
    release_candidate_rows: list[dict],
    *,
    lineage_stats: dict[str, int] | None = None,
) -> int:
    truth_map = truth_lookup(truth_rows)
    rpdc_map = rpdc_selection_lookup(release_candidate_rows)
    return sum(
        1
        for row in dedupe_latest_sigma_rows(sigma_rows)
        if contradiction_type(
            row,
            truth_for_sigma_row(row, truth_map, stats=lineage_stats),
            rpdc_for_sigma_row(row, rpdc_map, stats=lineage_stats),
        )
    )


def _weak_a_blocker_sections(
    sigma_rows: list[dict],
    truth_rows: list[dict],
    *,
    lineage_stats: dict[str, int] | None = None,
) -> dict[str, list[list[object]]]:
    truth_map = truth_lookup(truth_rows)
    with_blocker: list[dict[str, Any]] = []
    without_blocker: list[dict[str, Any]] = []

    for row in dedupe_latest_sigma_rows(sigma_rows):
        if not is_weak_a(row):
            continue
        race_truth = truth_for_sigma_row(row, truth_map, stats=lineage_stats)
        enriched = {
            **row,
            "blocker_type": race_truth.get("blocker_type") or "none",
            "assigned_archetype": race_truth.get("assigned_archetype") or "unknown",
        }
        if race_truth.get("blocker_fired"):
            with_blocker.append(enriched)
        else:
            without_blocker.append(enriched)

    blocker_type_split = Counter(row.get("blocker_type") or "none" for row in with_blocker)
    return {
        "summary": [["weak_a_no_blocker", *outcome_rate_rows(without_blocker)], ["weak_a_with_blocker", *outcome_rate_rows(with_blocker)]],
        "blocker_types": [[blocker_type, count] for blocker_type, count in blocker_type_split.most_common()] or [["none", 0]],
        "top_miss_reasons": [
            ["weak_a_no_blocker", top_counts([row.get("miss_reason") for row in without_blocker if row.get("outcome") == "MISS"])],
            ["weak_a_with_blocker", top_counts([row.get("miss_reason") for row in with_blocker if row.get("outcome") == "MISS"])],
        ],
        "top_tracks": [
            ["weak_a_no_blocker", top_counts([row.get("track") for row in without_blocker])],
            ["weak_a_with_blocker", top_counts([row.get("track") for row in with_blocker])],
        ],
        "top_archetypes": [
            ["weak_a_no_blocker", top_counts([row.get("assigned_archetype") for row in without_blocker])],
            ["weak_a_with_blocker", top_counts([row.get("assigned_archetype") for row in with_blocker])],
        ],
    }


def _rolling_window_bounds(target_date: str, days: int) -> tuple[str, str]:
    end = datetime.strptime(target_date, "%Y-%m-%d").date()
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _rolling_doctrine_summary(
    target_date: str,
    doctrine_rows: list[dict],
    *,
    lineage_stats: dict[str, int] | None = None,
) -> list[list[object]]:
    tracked_types = [
        "a_tier_weak_place_support",
        "blocker_fired_horse_won",
        "weak_model_strong_doctrine",
    ]
    summary_rows: list[list[object]] = []

    for label, days in (("7d", 7), ("30d", 30)):
        start_date, end_date = _rolling_window_bounds(target_date, days)
        sigma_rows = dedupe_latest_sigma_rows(_fetch_sigma_audits_window(start_date, end_date))
        truth_rows = _fetch_race_truth_for_sigma_rows(sigma_rows)
        release_rows = _fetch_runner_release_for_sigma_rows(sigma_rows)
        truth_map = truth_lookup(truth_rows)
        rpdc_map = rpdc_selection_lookup(release_rows)

        rows_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in sigma_rows:
            contradiction_type_name = contradiction_type(
                row,
                truth_for_sigma_row(row, truth_map, stats=lineage_stats),
                rpdc_for_sigma_row(row, rpdc_map, stats=lineage_stats),
            )
            if contradiction_type_name in tracked_types:
                rows_by_type[contradiction_type_name].append(row)

        for contradiction_type_name in tracked_types:
            rows = rows_by_type.get(contradiction_type_name, [])
            count, win_pct, place_pct, miss_pct = outcome_rate_rows(rows)
            last_seen = max((row.get("created_at") or "—") for row in rows) if rows else "—"
            summary_rows.append(
                [
                    label,
                    contradiction_type_name,
                    count,
                    win_pct,
                    place_pct,
                    miss_pct,
                    last_seen,
                    doctrine_status_for_type(contradiction_type_name, doctrine_rows),
                ]
            )
    return summary_rows


def _blocker_review_section(target_date: str, *, lineage_stats: dict[str, int] | None = None) -> list[list[object]]:
    tracked_blockers = ["longshot_block_allowed", "market_decoy_signal"]
    summary_by_blocker: dict[str, dict[str, Any]] = {
        blocker: {
            "7d_count": 0,
            "30d_count": 0,
            "winner_suppression_count": 0,
            "top_tracks": [],
            "top_archetypes": [],
            "top_miss_reasons": [],
        }
        for blocker in tracked_blockers
    }

    for label, days in (("7d_count", 7), ("30d_count", 30)):
        start_date, end_date = _rolling_window_bounds(target_date, days)
        sigma_rows = dedupe_latest_sigma_rows(_fetch_sigma_audits_window(start_date, end_date))
        truth_rows = _fetch_race_truth_for_sigma_rows(sigma_rows)
        truth_map = truth_lookup(truth_rows)

        sigma_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in sigma_rows:
            sigma_by_race[row.get("race_id")].append(row)

        for blocker in tracked_blockers:
            matching_truth = []
            for row in sigma_rows:
                resolved_truth = truth_for_sigma_row(row, truth_map, stats=lineage_stats)
                if resolved_truth.get("blocker_fired") and resolved_truth.get("blocker_type") == blocker:
                    matching_truth.append(resolved_truth)
            summary_by_blocker[blocker][label] = len(matching_truth)

            if label != "30d_count":
                continue

            winner_suppression = 0
            track_values: list[str | None] = []
            archetype_values: list[str | None] = []
            miss_reason_values: list[str | None] = []

            for truth_row in matching_truth:
                race_id = truth_row.get("race_id")
                sigma_for_race = sigma_by_race.get(race_id, [])
                if any(sigma_row.get("outcome") == "WIN" for sigma_row in sigma_for_race):
                    winner_suppression += 1
                track_values.extend(sigma_row.get("track") for sigma_row in sigma_for_race)
                archetype_values.append(truth_row.get("assigned_archetype"))
                miss_reason_values.extend(
                    sigma_row.get("miss_reason") for sigma_row in sigma_for_race if sigma_row.get("outcome") == "MISS"
                )

            summary_by_blocker[blocker]["winner_suppression_count"] = winner_suppression
            summary_by_blocker[blocker]["top_tracks"] = top_counts(track_values)
            summary_by_blocker[blocker]["top_archetypes"] = top_counts(archetype_values)
            summary_by_blocker[blocker]["top_miss_reasons"] = top_counts(miss_reason_values)

    return [
        [
            blocker,
            metrics["7d_count"],
            metrics["30d_count"],
            metrics["winner_suppression_count"],
            metrics["top_tracks"],
            metrics["top_archetypes"],
            metrics["top_miss_reasons"],
        ]
        for blocker, metrics in summary_by_blocker.items()
    ]


def _longshot_regime_split(target_date: str, *, lineage_stats: dict[str, int] | None = None) -> dict[str, list[list[object]]]:
    start_date, end_date = _rolling_window_bounds(target_date, 30)
    sigma_rows = dedupe_latest_sigma_rows(_fetch_sigma_audits_window(start_date, end_date))
    truth_rows = _fetch_race_truth_for_sigma_rows(sigma_rows)
    truth_map = truth_lookup(truth_rows)
    sigma_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sigma_rows:
        sigma_by_race[row.get("race_id")].append(row)

    longshot_truth = []
    for row in sigma_rows:
        resolved_truth = truth_for_sigma_row(row, truth_map, stats=lineage_stats)
        if resolved_truth.get("blocker_fired") and resolved_truth.get("blocker_type") == "longshot_block_allowed":
            longshot_truth.append(resolved_truth)
    regime_rows: list[dict[str, Any]] = []
    for truth_row in longshot_truth:
        race_id = truth_row.get("race_id")
        sigma_for_race = sigma_by_race.get(race_id) or [{}]
        for sigma_row in sigma_for_race:
            regime_rows.append(
                {
                    "race_id": race_id,
                    "track": sigma_row.get("track") or "unknown",
                    "surface": surface_bucket(sigma_row.get("track")),
                    "decision_tier": sigma_row.get("decision_tier") or "unknown",
                    "outcome": sigma_row.get("outcome") or "unknown",
                    "miss_reason": sigma_row.get("miss_reason") or "unknown",
                    "actual_winner_bucket": sp_bucket(truth_row.get("actual_winner_sp")),
                }
            )

    a_tier_rows = [row for row in regime_rows if row.get("decision_tier") == "A"]
    a_tier_aw_rows = [row for row in a_tier_rows if row.get("surface") == "AW"]
    outcome_split = Counter(row.get("outcome") or "unknown" for row in a_tier_aw_rows)
    suppressed_winners = outcome_split.get("WIN", 0)
    live_blocked = outcome_split.get("WIN", 0) + outcome_split.get("PLACED", 0)
    short_actual_winners = sum(1 for row in a_tier_aw_rows if row.get("actual_winner_bucket") == "short_<=3.0")

    return {
        "surface_split": [
            [surface, count] for surface, count in Counter(row.get("surface") for row in regime_rows).most_common()
        ] or [["none", 0]],
        "winner_sp_split": [
            [bucket, count]
            for bucket, count in Counter(row.get("actual_winner_bucket") for row in regime_rows).most_common()
        ] or [["none", 0]],
        "a_tier_aw_summary": [[
            len(a_tier_aw_rows),
            suppressed_winners,
            round(100 * outcome_split.get("WIN", 0) / len(a_tier_aw_rows), 1) if a_tier_aw_rows else 0.0,
            round(100 * outcome_split.get("PLACED", 0) / len(a_tier_aw_rows), 1) if a_tier_aw_rows else 0.0,
            round(100 * outcome_split.get("MISS", 0) / len(a_tier_aw_rows), 1) if a_tier_aw_rows else 0.0,
        ]],
        "a_tier_aw_pressure": [[
            round(100 * suppressed_winners / len(a_tier_aw_rows), 1) if a_tier_aw_rows else 0.0,
            round(100 * live_blocked / len(a_tier_aw_rows), 1) if a_tier_aw_rows else 0.0,
            round(100 * short_actual_winners / len(a_tier_aw_rows), 1) if a_tier_aw_rows else 0.0,
        ]],
        "a_tier_aw_winner_sp_split": [
            [bucket, count]
            for bucket, count in Counter(row.get("actual_winner_bucket") for row in a_tier_aw_rows).most_common()
        ] or [["none", 0]],
        "a_tier_aw_outcome_split": [
            [outcome, count] for outcome, count in Counter(row.get("outcome") for row in a_tier_aw_rows).most_common()
        ] or [["none", 0]],
        "blocked_outcome_split": [
            [outcome, count] for outcome, count in Counter(row.get("outcome") for row in regime_rows).most_common()
        ] or [["none", 0]],
    }


def generate(target_date: str) -> Path:
    generated_at = datetime.now(timezone.utc).isoformat()
    lineage_stats: dict[str, int] = {}
    sigma_rows = dedupe_latest_sigma_rows(_fetch_sigma_audits(target_date))
    truth_rows = _fetch_race_truth_for_sigma_rows(sigma_rows)
    rpdc_tag_rows = _fetch_rpdc_tags_for_sigma_rows(sigma_rows, target_date)
    release_candidate_rows = _fetch_runner_release_for_sigma_rows(sigma_rows)
    doctrine_rows = _fetch_doctrine_rows()
    rpdc_coverage = rpdc_coverage_metrics(sigma_rows, release_candidate_rows)

    wins = sum(1 for row in sigma_rows if row.get("outcome") == "WIN")
    placed = sum(1 for row in sigma_rows if row.get("outcome") == "PLACED")
    misses = sum(1 for row in sigma_rows if row.get("outcome") == "MISS")

    blocker_fired_rows = sum(1 for row in truth_rows if row.get("blocker_fired") is True)
    blocker_helped_rows = sum(1 for row in truth_rows if row.get("blocker_helped") is True)
    blocker_hurt_rows = sum(1 for row in truth_rows if row.get("blocker_hurt") is True)

    blocker_truth = Counter((row.get("blocker_type") or "none") for row in truth_rows if row.get("blocker_fired") is True)
    blocker_helped = Counter((row.get("blocker_type") or "none") for row in truth_rows if row.get("blocker_helped") is True)
    blocker_hurt = Counter((row.get("blocker_type") or "none") for row in truth_rows if row.get("blocker_hurt") is True)

    tagged_rows = len(rpdc_tag_rows)
    cash_window_rows = sum(1 for row in release_candidate_rows if row.get("rpdc_cash_window_flag") is True)
    high_release_score_rows = sum(1 for row in release_candidate_rows if float(row.get("rpdc_release_score") or 0) >= 3.0)

    weak_a_rows = sum(1 for row in sigma_rows if is_weak_a(row))
    weak_a_sections = _weak_a_blocker_sections(sigma_rows, truth_rows, lineage_stats=lineage_stats)
    rolling_summary_rows = _rolling_doctrine_summary(target_date, doctrine_rows, lineage_stats=lineage_stats)
    blocker_review_rows = _blocker_review_section(target_date, lineage_stats=lineage_stats)
    longshot_regime = _longshot_regime_split(target_date, lineage_stats=lineage_stats)

    contradiction_count = _contradiction_count(
        sigma_rows,
        truth_rows,
        release_candidate_rows,
        lineage_stats=lineage_stats,
    )

    lines: list[str] = []
    lines.append(f"# VÉLØ Doctrine Evidence Board — {target_date}")
    lines.append(f"Generated: {generated_at}")
    lines.append("")

    lines.append("## Live Results")
    lines.extend(_md_table(["races", "wins", "placed", "misses"], [[len(sigma_rows), wins, placed, misses]]))
    lines.append("")

    lines.append("## Shadow Results")
    lines.extend(
        _md_table(
            ["races", "blocker_fired_rows", "blocker_helped_rows", "blocker_hurt_rows"],
            [[len(truth_rows), blocker_fired_rows, blocker_helped_rows, blocker_hurt_rows]],
        )
    )
    lines.append("")

    lines.append("## Blocker Truth")
    if blocker_truth:
        lines.extend(
            _md_table(
                ["blocker_type", "fires", "helped", "hurt"],
                [
                    [blocker_type, blocker_truth[blocker_type], blocker_helped[blocker_type], blocker_hurt[blocker_type]]
                    for blocker_type, _ in blocker_truth.most_common()
                ],
            )
        )
    else:
        lines.append("_No blocker truth rows for this date._")
    lines.append("")

    lines.append("## RPDC Truth")
    lines.extend(
        _md_table(
            ["tagged_rows", "cash_window_rows", "high_release_score_rows"],
            [[tagged_rows, cash_window_rows, high_release_score_rows]],
        )
    )
    lines.append("")

    lines.append("## RPDC Coverage")
    lines.extend(
        _md_table(
            [
                "reviewed_sigma_rows",
                "reviewed_sigma_rows_with_horse_id",
                "reviewed_sigma_rows_in_rpdc_covered_events",
                "reviewed_sigma_rows_with_exact_event_horse_match",
            ],
            [[
                rpdc_coverage["reviewed_sigma_rows"],
                rpdc_coverage["reviewed_sigma_rows_with_horse_id"],
                rpdc_coverage["reviewed_sigma_rows_in_rpdc_covered_events"],
                rpdc_coverage["reviewed_sigma_rows_with_exact_rpdc_match"],
            ]],
        )
    )
    lines.append("")

    lines.append("## Weak A Cohort")
    lines.extend(_md_table(["weak_a_rows"], [[weak_a_rows]]))
    lines.append("")

    lines.append("## Weak A Blocker Split")
    lines.extend(_md_table(["cohort", "races", "win_pct", "place_pct", "miss_pct"], weak_a_sections["summary"]))
    lines.append("")
    lines.extend(_md_table(["blocker_type", "count"], weak_a_sections["blocker_types"]))
    lines.append("")
    lines.extend(_md_table(["cohort", "top_miss_reasons"], weak_a_sections["top_miss_reasons"]))
    lines.append("")
    lines.extend(_md_table(["cohort", "top_tracks"], weak_a_sections["top_tracks"]))
    lines.append("")
    lines.extend(_md_table(["cohort", "top_archetypes"], weak_a_sections["top_archetypes"]))
    lines.append("")

    lines.append("## Rolling Doctrine Summary")
    lines.extend(
        _md_table(
            ["window", "doctrine_family", "count", "win_pct", "place_pct", "miss_pct", "last_seen", "status"],
            rolling_summary_rows,
        )
    )
    lines.append("")

    lines.append("## Blocker Review")
    lines.extend(
        _md_table(
            ["blocker_type", "7d_count", "30d_count", "winner_suppression_count", "top_tracks", "top_archetypes", "top_miss_reasons"],
            blocker_review_rows,
        )
    )
    lines.append("")

    lines.append("## Longshot Block Allowed Regime Split")
    lines.extend(_md_table(["surface", "count"], longshot_regime["surface_split"]))
    lines.append("")
    lines.extend(_md_table(["actual_winner_sp_bucket", "count"], longshot_regime["winner_sp_split"]))
    lines.append("")
    lines.append("### A-Tier AW Slice")
    lines.extend(
        _md_table(
            ["races", "suppressed_winners", "win_pct", "place_pct", "miss_pct"],
            longshot_regime["a_tier_aw_summary"],
        )
    )
    lines.append("")
    lines.extend(
        _md_table(
            ["suppression_rate_pct", "blocked_horse_live_rate_pct", "short_priced_actual_winner_share_pct"],
            longshot_regime["a_tier_aw_pressure"],
        )
    )
    lines.append("")
    lines.extend(_md_table(["actual_winner_sp_bucket", "count"], longshot_regime["a_tier_aw_winner_sp_split"]))
    lines.append("")
    lines.extend(_md_table(["blocked_horse_outcome", "count"], longshot_regime["a_tier_aw_outcome_split"]))
    lines.append("")

    lines.append("## Doctrine Candidates")
    if doctrine_rows:
        lines.extend(
            _md_table(
                ["doctrine_key", "family", "rule_type", "status", "sample_size", "win_pct", "place_pct", "next_review_date"],
                [
                    [
                        row.get("doctrine_key"),
                        row.get("family"),
                        row.get("rule_type"),
                        row.get("status"),
                        row.get("sample_size"),
                        row.get("win_pct"),
                        row.get("place_pct"),
                        row.get("next_review_date"),
                    ]
                    for row in doctrine_rows
                ],
            )
        )
    else:
        lines.append("_No doctrine registry rows found._")
    lines.append("")

    lines.append("## Doctrine Contradictions")
    lines.extend(_md_table(["contradiction_count"], [[contradiction_count]]))
    lines.append("")
    lines.append("## Review Clock Notes")
    lines.append("- doctrine review clock: `sigma_audits.created_at`")
    lines.append("- truth rows are mapped onto the sigma review set with `doctrine_event_id` first; `race_id` fallback is used only when doctrine lineage is missing.")
    lines.append("- RPDC release rows are mapped onto the sigma review set with `(doctrine_event_id, horse_id)` first; `(race_id, horse_id)` fallback is used only when doctrine lineage is missing.")
    lines.append("- RPDC is currently a sparse candidate surface, not full reviewed-selection coverage.")
    lines.append("- `today_rpdc_tags` has no `generated_at`; tag counts are therefore approximated by intersecting sigma review `race_id`s with `run_date = review_date`.")
    lines.append(f"- truth lineage matches: event_id={lineage_stats.get('truth_event_matches', 0)} fallback_race_id={lineage_stats.get('truth_fallback_matches', 0)} unmatched={lineage_stats.get('truth_unmatched', 0)}")
    lines.append(f"- RPDC lineage matches: event_id+horse={lineage_stats.get('rpdc_event_matches', 0)} fallback_race_id+horse={lineage_stats.get('rpdc_fallback_matches', 0)} unmatched={lineage_stats.get('rpdc_unmatched', 0)}")
    lines.append(
        f"- RPDC coverage: reviewed_sigma_rows={rpdc_coverage['reviewed_sigma_rows']} "
        f"with_horse_id={rpdc_coverage['reviewed_sigma_rows_with_horse_id']} "
        f"in_rpdc_covered_events={rpdc_coverage['reviewed_sigma_rows_in_rpdc_covered_events']} "
        f"exact_event_horse_matches={rpdc_coverage['reviewed_sigma_rows_with_exact_rpdc_match']}"
    )
    lines.append("")

    out_dir = Path(__file__).parent.parent / "reports" / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"doctrine_evidence_board_{target_date}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written: {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = parser.parse_args()
    try:
        generate(args.date)
    except DoctrineRegistryMissing as exc:
        raise SystemExit(str(exc))
