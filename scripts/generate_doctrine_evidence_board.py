"""
VÉLØ Doctrine Evidence Board
============================
Read-only sidecar report for the Doctrine Layer.

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
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


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
        SELECT race_id, decision_tier, confidence_level, verdict_score, outcome, top_pick_position, miss_reason, track, created_at
        FROM sigma_audits
        WHERE created_at >= '{start_ts}' AND created_at <= '{end_ts}' AND outcome IS NOT NULL
        ORDER BY created_at ASC
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "sigma_audits",
        "race_id,decision_tier,confidence_level,verdict_score,outcome,top_pick_position,miss_reason,track,created_at",
        [f"created_at=gte.{start_ts}", f"created_at=lte.{end_ts}", "outcome=not.is.null"],
    )


def _fetch_sigma_audits_window(start_date: str, end_date: str) -> list[dict]:
    start_ts = f"{start_date}T00:00:00+00:00"
    end_ts = f"{end_date}T23:59:59+00:00"
    sql_rows = _management_sql(f"""
        SELECT race_id, decision_tier, confidence_level, verdict_score, outcome, top_pick_position, miss_reason, track, created_at
        FROM sigma_audits
        WHERE created_at >= '{start_ts}' AND created_at <= '{end_ts}' AND outcome IS NOT NULL
        ORDER BY created_at ASC
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "sigma_audits",
        "race_id,decision_tier,confidence_level,verdict_score,outcome,top_pick_position,miss_reason,track,created_at",
        [f"created_at=gte.{start_ts}", f"created_at=lte.{end_ts}", "outcome=not.is.null"],
    )


def _fetch_race_truth_audits(target_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, race_date, result_outcome, blocker_fired, blocker_type, blocker_helped, blocker_hurt, assigned_archetype
        FROM race_truth_audits
        WHERE race_date = '{target_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "race_truth_audits",
        "race_id,race_date,result_outcome,blocker_fired,blocker_type,blocker_helped,blocker_hurt,assigned_archetype",
        [f"race_date=eq.{target_date}"],
    )


def _fetch_race_truth_audits_window(start_date: str, end_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, race_date, result_outcome, blocker_fired, blocker_type, blocker_helped, blocker_hurt, assigned_archetype, actual_winner_sp
        FROM race_truth_audits
        WHERE race_date >= '{start_date}' AND race_date <= '{end_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "race_truth_audits",
        "race_id,race_date,result_outcome,blocker_fired,blocker_type,blocker_helped,blocker_hurt,assigned_archetype,actual_winner_sp",
        [f"race_date=gte.{start_date}", f"race_date=lte.{end_date}"],
    )


def _fetch_today_rpdc_tags(target_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, horse_id, tag, tag_value, tag_strength
        FROM today_rpdc_tags
        WHERE run_date = '{target_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "today_rpdc_tags",
        "race_id,horse_id,tag,tag_value,tag_strength",
        [f"run_date=eq.{target_date}"],
    )


def _fetch_runner_release_candidates(target_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, horse_id, rpdc_cash_window_flag, rpdc_release_score, rpdc_tag_count
        FROM runner_release_candidates
        WHERE run_date = '{target_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "runner_release_candidates",
        "race_id,horse_id,rpdc_cash_window_flag,rpdc_release_score,rpdc_tag_count",
        [f"run_date=eq.{target_date}"],
    )


def _fetch_runner_release_candidates_window(start_date: str, end_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, horse_id, rpdc_cash_window_flag, rpdc_release_score, rpdc_tag_count
        FROM runner_release_candidates
        WHERE run_date >= '{start_date}' AND run_date <= '{end_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "runner_release_candidates",
        "race_id,horse_id,rpdc_cash_window_flag,rpdc_release_score,rpdc_tag_count",
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


def _md_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(v) if v is not None else "—" for v in row) + " |")
    return lines


def _truth_by_race(rows: list[dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for row in rows:
        race_id = row.get("race_id")
        if not race_id:
            continue
        current = merged.setdefault(
            race_id,
            {
                "blocker_fired": False,
                "blocker_type": None,
                "blocker_hurt": False,
                "blocker_helped": False,
                "result_outcome": None,
                "assigned_archetype": None,
            },
        )
        current["blocker_fired"] = current["blocker_fired"] or bool(row.get("blocker_fired"))
        current["blocker_hurt"] = current["blocker_hurt"] or bool(row.get("blocker_hurt"))
        current["blocker_helped"] = current["blocker_helped"] or bool(row.get("blocker_helped"))
        current["blocker_type"] = current["blocker_type"] or row.get("blocker_type")
        current["result_outcome"] = current["result_outcome"] or row.get("result_outcome")
        current["assigned_archetype"] = current["assigned_archetype"] or row.get("assigned_archetype")
    return merged


def _rpdc_by_race(rows: list[dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for row in rows:
        race_id = row.get("race_id")
        if not race_id:
            continue
        current = merged.setdefault(race_id, {"has_cash_window": False, "max_rpdc_release_score": 0.0})
        current["has_cash_window"] = current["has_cash_window"] or bool(row.get("rpdc_cash_window_flag"))
        current["max_rpdc_release_score"] = max(current["max_rpdc_release_score"], float(row.get("rpdc_release_score") or 0))
    return merged


def _contradiction_type(sigma: dict, truth: dict, rpdc: dict) -> str | None:
    verdict_score = float(sigma.get("verdict_score") or 0)
    confidence_level = sigma.get("confidence_level") or ""
    decision_tier = sigma.get("decision_tier")
    top_pick_position = sigma.get("top_pick_position")
    outcome = sigma.get("outcome")

    if verdict_score >= 0.70 and truth.get("blocker_fired"):
        return "strong_model_negative_doctrine"
    if verdict_score < 0.40 and rpdc.get("has_cash_window"):
        return "weak_model_strong_doctrine"
    if truth.get("blocker_fired") and outcome == "WIN":
        return "blocker_fired_horse_won"
    if rpdc.get("has_cash_window") and confidence_level == "low":
        return "rpdc_cash_window_low_model_confidence"
    if decision_tier == "A" and (confidence_level == "low" or top_pick_position is None or int(top_pick_position) > 2):
        return "a_tier_weak_place_support"
    return None


def _contradiction_count(sigma_rows: list[dict], truth_rows: list[dict], release_candidate_rows: list[dict]) -> int:
    truth_map = _truth_by_race(truth_rows)
    rpdc_map = _rpdc_by_race(release_candidate_rows)
    return sum(
        1
        for row in sigma_rows
        if _contradiction_type(
            row,
            truth_map.get(row.get("race_id"), {}),
            rpdc_map.get(row.get("race_id"), {"has_cash_window": False, "max_rpdc_release_score": 0.0}),
        )
    )


def _is_weak_a(row: dict[str, Any]) -> bool:
    top_pick_position = row.get("top_pick_position")
    return row.get("decision_tier") == "A" and (
        row.get("confidence_level") == "low"
        or top_pick_position is None
        or int(top_pick_position) > 2
    )


def _outcome_rate_rows(rows: list[dict[str, Any]]) -> list[object]:
    total = len(rows)
    if total == 0:
        return [0, 0.0, 0.0, 0.0]
    wins = sum(1 for row in rows if row.get("outcome") == "WIN")
    placed = sum(1 for row in rows if row.get("outcome") == "PLACED")
    misses = sum(1 for row in rows if row.get("outcome") == "MISS")
    return [
        total,
        round(100 * wins / total, 1),
        round(100 * placed / total, 1),
        round(100 * misses / total, 1),
    ]


def _top_counts(values: list[str | None], limit: int = 3) -> str:
    counts = Counter((value or "unknown") for value in values)
    if not counts:
        return "none"
    return ", ".join(f"{key} ({count})" for key, count in counts.most_common(limit))


def _weak_a_blocker_sections(sigma_rows: list[dict], truth_rows: list[dict]) -> dict[str, list[list[object]]]:
    truth_map = _truth_by_race(truth_rows)
    with_blocker: list[dict[str, Any]] = []
    without_blocker: list[dict[str, Any]] = []

    for row in sigma_rows:
        if not _is_weak_a(row):
            continue
        race_truth = truth_map.get(row.get("race_id"), {})
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
        "summary": [
            ["weak_a_no_blocker", *_outcome_rate_rows(without_blocker)],
            ["weak_a_with_blocker", *_outcome_rate_rows(with_blocker)],
        ],
        "blocker_types": [[blocker_type, count] for blocker_type, count in blocker_type_split.most_common()] or [["none", 0]],
        "top_miss_reasons": [
            ["weak_a_no_blocker", _top_counts([row.get("miss_reason") for row in without_blocker if row.get("outcome") == "MISS"])],
            ["weak_a_with_blocker", _top_counts([row.get("miss_reason") for row in with_blocker if row.get("outcome") == "MISS"])],
        ],
        "top_tracks": [
            ["weak_a_no_blocker", _top_counts([row.get("track") for row in without_blocker])],
            ["weak_a_with_blocker", _top_counts([row.get("track") for row in with_blocker])],
        ],
        "top_archetypes": [
            ["weak_a_no_blocker", _top_counts([row.get("assigned_archetype") for row in without_blocker])],
            ["weak_a_with_blocker", _top_counts([row.get("assigned_archetype") for row in with_blocker])],
        ],
    }


def _rolling_window_bounds(target_date: str, days: int) -> tuple[str, str]:
    end = datetime.strptime(target_date, "%Y-%m-%d").date()
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _surface_bucket(track: str | None) -> str:
    if not track:
        return "unknown"
    aw_markers = [
        "(AW)",
        "Dundalk",
        "Kempton (AW)",
        "Southwell (AW)",
        "Wolverhampton",
        "Newcastle (AW)",
        "Lingfield (AW)",
        "Chelmsford",
    ]
    if any(marker in track for marker in aw_markers):
        return "AW"
    return "non_AW_or_unknown"


def _sp_bucket(price: Any) -> str:
    if price is None:
        return "unknown"
    try:
        value = float(price)
    except (TypeError, ValueError):
        return "unknown"
    if value <= 3.0:
        return "short_<=3.0"
    if value <= 6.0:
        return "mid_3.01_6.0"
    return "outsider_>6.0"


def _doctrine_status_for_type(contradiction_type: str, doctrine_rows: list[dict]) -> str:
    doctrine_by_key = {row.get("doctrine_key"): row.get("status") for row in doctrine_rows}
    key_map = {
        "a_tier_weak_place_support": "a_tier_weak_place_watch",
        "blocker_fired_horse_won": "longshot_block_allowed_watch_only",
        "weak_model_strong_doctrine": "mark_ready_requires_trainer_authority",
    }
    mapped = doctrine_by_key.get(key_map.get(contradiction_type))
    return mapped or "review"


def _rolling_doctrine_summary(target_date: str, doctrine_rows: list[dict]) -> list[list[object]]:
    tracked_types = [
        "a_tier_weak_place_support",
        "blocker_fired_horse_won",
        "weak_model_strong_doctrine",
    ]
    summary_rows: list[list[object]] = []

    for label, days in (("7d", 7), ("30d", 30)):
        start_date, end_date = _rolling_window_bounds(target_date, days)
        sigma_rows = _fetch_sigma_audits_window(start_date, end_date)
        truth_rows = _fetch_race_truth_audits_window(start_date, end_date)
        release_rows = _fetch_runner_release_candidates_window(start_date, end_date)
        truth_map = _truth_by_race(truth_rows)
        rpdc_map = _rpdc_by_race(release_rows)

        rows_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in sigma_rows:
            contradiction_type = _contradiction_type(
                row,
                truth_map.get(row.get("race_id"), {}),
                rpdc_map.get(row.get("race_id"), {"has_cash_window": False, "max_rpdc_release_score": 0.0}),
            )
            if contradiction_type in tracked_types:
                rows_by_type[contradiction_type].append(row)

        for contradiction_type in tracked_types:
            rows = rows_by_type.get(contradiction_type, [])
            count, win_pct, place_pct, miss_pct = _outcome_rate_rows(rows)
            last_seen = max((row.get("created_at") or "—") for row in rows) if rows else "—"
            summary_rows.append(
                [
                    label,
                    contradiction_type,
                    count,
                    win_pct,
                    place_pct,
                    miss_pct,
                    last_seen,
                    _doctrine_status_for_type(contradiction_type, doctrine_rows),
                ]
            )
    return summary_rows


def _blocker_review_section(target_date: str) -> list[list[object]]:
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
        sigma_rows = _fetch_sigma_audits_window(start_date, end_date)
        truth_rows = _fetch_race_truth_audits_window(start_date, end_date)
        truth_map = _truth_by_race(truth_rows)

        sigma_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in sigma_rows:
            sigma_by_race[row.get("race_id")].append(row)

        for blocker in tracked_blockers:
            matching_truth = [
                row for row in truth_rows if row.get("blocker_fired") and row.get("blocker_type") == blocker
            ]
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
            summary_by_blocker[blocker]["top_tracks"] = _top_counts(track_values)
            summary_by_blocker[blocker]["top_archetypes"] = _top_counts(archetype_values)
            summary_by_blocker[blocker]["top_miss_reasons"] = _top_counts(miss_reason_values)

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


def _longshot_regime_split(target_date: str) -> dict[str, list[list[object]]]:
    start_date, end_date = _rolling_window_bounds(target_date, 30)
    sigma_rows = _fetch_sigma_audits_window(start_date, end_date)
    truth_rows = _fetch_race_truth_audits_window(start_date, end_date)
    sigma_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sigma_rows:
        sigma_by_race[row.get("race_id")].append(row)

    longshot_truth = [
        row for row in truth_rows if row.get("blocker_fired") and row.get("blocker_type") == "longshot_block_allowed"
    ]
    regime_rows: list[dict[str, Any]] = []
    for truth_row in longshot_truth:
        race_id = truth_row.get("race_id")
        sigma_for_race = sigma_by_race.get(race_id) or [{}]
        for sigma_row in sigma_for_race:
            regime_rows.append(
                {
                    "race_id": race_id,
                    "track": sigma_row.get("track") or "unknown",
                    "surface": _surface_bucket(sigma_row.get("track")),
                    "decision_tier": sigma_row.get("decision_tier") or "unknown",
                    "outcome": sigma_row.get("outcome") or "unknown",
                    "miss_reason": sigma_row.get("miss_reason") or "unknown",
                    "actual_winner_bucket": _sp_bucket(truth_row.get("actual_winner_sp")),
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
    sigma_rows = _fetch_sigma_audits(target_date)
    truth_rows = _fetch_race_truth_audits(target_date)
    rpdc_tag_rows = _fetch_today_rpdc_tags(target_date)
    release_candidate_rows = _fetch_runner_release_candidates(target_date)
    doctrine_rows = _fetch_doctrine_rows()

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

    weak_a_rows = sum(1 for row in sigma_rows if _is_weak_a(row))
    weak_a_sections = _weak_a_blocker_sections(sigma_rows, truth_rows)
    rolling_summary_rows = _rolling_doctrine_summary(target_date, doctrine_rows)
    blocker_review_rows = _blocker_review_section(target_date)
    longshot_regime = _longshot_regime_split(target_date)

    contradiction_count = _contradiction_count(sigma_rows, truth_rows, release_candidate_rows)

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
