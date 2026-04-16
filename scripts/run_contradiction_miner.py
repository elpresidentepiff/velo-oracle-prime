"""
VÉLØ Contradiction Miner
========================
Read-only sidecar contradiction report.

Doctrine review clock:
  - sigma_audits.created_at
  - truth and RPDC rows are supporting evidence mapped onto the reviewed sigma set

Flags races where:
  - strong model + negative doctrine
  - weak model + strong doctrine
  - blocker fired + horse won
  - RPDC cash window + low model confidence
  - A-tier + weak place support

Read path order:
  1. Supabase management SQL API when a valid access token exists
  2. PostgREST/service-role reads
  3. hard-fail clearly

Run:
  python scripts/run_contradiction_miner.py --date 2026-04-15
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

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
    outcome_rate_rows,
    rpdc_coverage_metrics,
    rpdc_for_sigma_row,
    rpdc_selection_lookup,
    review_race_ids,
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
        SELECT race_id, doctrine_event_id, decision_tier, confidence_level, verdict_score, outcome, top_pick_position, miss_reason, track, created_at, horse_id
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
        SELECT race_id, doctrine_event_id, race_date, generated_at, result_outcome, blocker_fired, blocker_type, blocker_hurt, blocker_helped, assigned_archetype
        FROM race_truth_audits
        WHERE race_date = '{target_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "race_truth_audits",
        "race_id,doctrine_event_id,race_date,generated_at,result_outcome,blocker_fired,blocker_type,blocker_hurt,blocker_helped,assigned_archetype",
        [f"race_date=eq.{target_date}"],
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


def _sql_in_list(values: list[str]) -> str:
    return ",".join("'" + value.replace("'", "''") + "'" for value in values)


def _fetch_truth_for_sigma_rows(sigma_rows: list[dict]) -> list[dict]:
    race_ids = review_race_ids(sigma_rows)
    if not race_ids:
        return []
    rows: list[dict] = []
    for race_chunk in chunked(race_ids):
        sql_rows = _management_sql(
            f"""
            SELECT race_id, doctrine_event_id, race_date, generated_at, result_outcome, blocker_fired, blocker_type, blocker_hurt, blocker_helped, assigned_archetype
            FROM race_truth_audits
            WHERE race_id IN ({_sql_in_list(race_chunk)})
            """
        )
        if sql_rows is not None:
            rows.extend(sql_rows)
            continue
        rows.extend(
            _rest_fetch(
                "race_truth_audits",
                "race_id,doctrine_event_id,race_date,generated_at,result_outcome,blocker_fired,blocker_type,blocker_hurt,blocker_helped,assigned_archetype",
                [f"race_id=in.({','.join(race_chunk)})"],
            )
        )
    return rows


def _fetch_rpdc_for_sigma_rows(sigma_rows: list[dict]) -> list[dict]:
    race_ids = review_race_ids(sigma_rows)
    if not race_ids:
        return []
    rows: list[dict] = []
    for race_chunk in chunked(race_ids):
        sql_rows = _management_sql(
            f"""
            SELECT race_id, doctrine_event_id, horse_id, run_date, generated_at, rpdc_cash_window_flag, rpdc_release_score, rpdc_tag_count
            FROM runner_release_candidates
            WHERE race_id IN ({_sql_in_list(race_chunk)})
            """
        )
        if sql_rows is not None:
            rows.extend(sql_rows)
            continue
        rows.extend(
            _rest_fetch(
                "runner_release_candidates",
                "race_id,doctrine_event_id,horse_id,run_date,generated_at,rpdc_cash_window_flag,rpdc_release_score,rpdc_tag_count",
                [f"race_id=in.({','.join(race_chunk)})"],
            )
        )
    return dedupe_latest_rpdc_rows(rows)


def _require_doctrine_registry() -> None:
    _management = _management_sql("SELECT doctrine_key FROM velo_doctrine_registry LIMIT 1")
    if _management is not None:
        return
    _rest_fetch("velo_doctrine_registry", "doctrine_key", [])


def generate(target_date: str) -> Path:
    _require_doctrine_registry()
    generated_at = datetime.now(timezone.utc).isoformat()
    lineage_stats: dict[str, int] = {}
    sigma_rows = dedupe_latest_sigma_rows(_fetch_sigma_audits(target_date))
    truth_rows = _fetch_truth_for_sigma_rows(sigma_rows)
    rpdc_rows = _fetch_rpdc_for_sigma_rows(sigma_rows)
    rpdc_coverage = rpdc_coverage_metrics(sigma_rows, rpdc_rows)

    truth_map = truth_lookup(truth_rows)
    rpdc_map = rpdc_selection_lookup(rpdc_rows)

    flagged: list[dict] = []
    for sigma in sigma_rows:
        race_id = sigma.get("race_id")
        truth_row = truth_for_sigma_row(sigma, truth_map, stats=lineage_stats)
        rpdc_row = rpdc_for_sigma_row(sigma, rpdc_map, stats=lineage_stats)
        contradiction_type_name = contradiction_type(
            sigma,
            truth_row,
            rpdc_row,
        )
        if contradiction_type_name:
            flagged.append(
                {
                    "race_id": race_id,
                    "contradiction_type": contradiction_type_name,
                    "decision_tier": sigma.get("decision_tier"),
                    "confidence_level": sigma.get("confidence_level"),
                    "verdict_score": sigma.get("verdict_score"),
                    "outcome": sigma.get("outcome"),
                    "blocker_type": truth_row.get("blocker_type"),
                    "has_cash_window": rpdc_row.get("has_cash_window"),
                    "max_rpdc_release_score": rpdc_row.get("max_rpdc_release_score"),
                    "miss_reason": sigma.get("miss_reason"),
                    "track": sigma.get("track"),
                    "assigned_archetype": truth_row.get("assigned_archetype"),
                }
            )

    type_counts = Counter(row["contradiction_type"] for row in flagged)
    weak_a_with_blocker = [
        row
        for row in flagged
        if row["contradiction_type"] == "a_tier_weak_place_support"
        and truth_map.get(row.get("race_id"), {}).get("blocker_fired")
    ]
    weak_a_without_blocker = [
        {
            "miss_reason": row.get("miss_reason"),
            "track": row.get("track"),
            "assigned_archetype": truth_for_sigma_row(row, truth_map, stats=lineage_stats).get("assigned_archetype"),
            "outcome": row.get("outcome"),
        }
        for row in sigma_rows
        if is_weak_a(row) and not truth_for_sigma_row(row, truth_map, stats=lineage_stats).get("blocker_fired")
    ]
    weak_a_with_blocker_detail = [
        {
            "miss_reason": row.get("miss_reason"),
            "track": row.get("track"),
            "assigned_archetype": row.get("assigned_archetype"),
            "outcome": row.get("outcome"),
            "blocker_type": row.get("blocker_type"),
        }
        for row in weak_a_with_blocker
    ]
    blocker_type_split = Counter(row.get("blocker_type") or "unknown" for row in weak_a_with_blocker_detail)

    lines: list[str] = []
    lines.append(f"# VÉLØ Contradiction Miner — {target_date}")
    lines.append(f"Generated: {generated_at}")
    lines.append("")
    lines.append(f"Total flagged races: {len(flagged)}")
    lines.append("")
    lines.append("## Contradiction Counts")
    lines.append("| contradiction_type | count |")
    lines.append("| --- | --- |")
    for contradiction_name, count in type_counts.most_common():
        lines.append(f"| {contradiction_name} | {count} |")
    if not type_counts:
        lines.append("| none | 0 |")
    lines.append("")
    lines.append("## Weak A Blocker Split")
    lines.append("| cohort | races | win_pct | place_pct | miss_pct |")
    lines.append("| --- | --- | --- | --- | --- |")
    for label, rows in (
        ("weak_a_no_blocker", weak_a_without_blocker),
        ("weak_a_with_blocker", weak_a_with_blocker_detail),
    ):
        races, win_pct, place_pct, miss_pct = outcome_rate_rows(rows)
        lines.append(f"| {label} | {races} | {win_pct} | {place_pct} | {miss_pct} |")
    lines.append("")
    lines.append("| blocker_type | count |")
    lines.append("| --- | --- |")
    for blocker_type, count in blocker_type_split.most_common():
        lines.append(f"| {blocker_type} | {count} |")
    if not blocker_type_split:
        lines.append("| none | 0 |")
    lines.append("")
    lines.append("| cohort | top_miss_reasons | top_tracks | top_archetypes |")
    lines.append("| --- | --- | --- | --- |")
    for label, rows in (
        ("weak_a_no_blocker", weak_a_without_blocker),
        ("weak_a_with_blocker", weak_a_with_blocker_detail),
    ):
        lines.append(
            f"| {label} | "
            f"{top_counts([row.get('miss_reason') for row in rows if row.get('outcome') == 'MISS'])} | "
            f"{top_counts([row.get('track') for row in rows])} | "
            f"{top_counts([row.get('assigned_archetype') for row in rows])} |"
        )
    lines.append("")
    lines.append("## RPDC Coverage")
    lines.append("| reviewed_sigma_rows | reviewed_sigma_rows_with_horse_id | reviewed_sigma_rows_in_rpdc_covered_events | reviewed_sigma_rows_with_exact_event_horse_match |")
    lines.append("| --- | --- | --- | --- |")
    lines.append(
        f"| {rpdc_coverage['reviewed_sigma_rows']} | "
        f"{rpdc_coverage['reviewed_sigma_rows_with_horse_id']} | "
        f"{rpdc_coverage['reviewed_sigma_rows_in_rpdc_covered_events']} | "
        f"{rpdc_coverage['reviewed_sigma_rows_with_exact_rpdc_match']} |"
    )
    lines.append("")
    lines.append("## Flagged Races")
    lines.append("| race_id | contradiction_type | tier | confidence | verdict_score | outcome | blocker_type | has_cash_window | max_rpdc_release_score |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in flagged:
        lines.append(
            "| {race_id} | {contradiction_type} | {decision_tier} | {confidence_level} | {verdict_score} | {outcome} | {blocker_type} | {has_cash_window} | {max_rpdc_release_score} |".format(
                race_id=row.get("race_id", "—"),
                contradiction_type=row.get("contradiction_type", "—"),
                decision_tier=row.get("decision_tier", "—"),
                confidence_level=row.get("confidence_level", "—"),
                verdict_score=row.get("verdict_score", "—"),
                outcome=row.get("outcome", "—"),
                blocker_type=row.get("blocker_type", "—"),
                has_cash_window=row.get("has_cash_window", "—"),
                max_rpdc_release_score=row.get("max_rpdc_release_score", "—"),
            )
        )
    if not flagged:
        lines.append("_No contradictions detected for this date._")
    lines.append("")
    lines.append("## Review Clock Notes")
    lines.append("- doctrine review clock: `sigma_audits.created_at`")
    lines.append("- truth rows are mapped onto the reviewed sigma set with `doctrine_event_id` first; `race_id` fallback is used only when doctrine lineage is missing.")
    lines.append("- RPDC release rows are mapped onto the reviewed sigma selections with `(doctrine_event_id, horse_id)` first; `(race_id, horse_id)` fallback is used only when doctrine lineage is missing.")
    lines.append("- RPDC is currently a sparse candidate surface, not full reviewed-selection coverage.")
    lines.append(f"- truth lineage matches: event_id={lineage_stats.get('truth_event_matches', 0)} fallback_race_id={lineage_stats.get('truth_fallback_matches', 0)} unmatched={lineage_stats.get('truth_unmatched', 0)}")
    lines.append(f"- RPDC lineage matches: event_id+horse={lineage_stats.get('rpdc_event_matches', 0)} fallback_race_id+horse={lineage_stats.get('rpdc_fallback_matches', 0)} unmatched={lineage_stats.get('rpdc_unmatched', 0)}")
    lines.append(
        f"- RPDC coverage: reviewed_sigma_rows={rpdc_coverage['reviewed_sigma_rows']} "
        f"with_horse_id={rpdc_coverage['reviewed_sigma_rows_with_horse_id']} "
        f"in_rpdc_covered_events={rpdc_coverage['reviewed_sigma_rows_in_rpdc_covered_events']} "
        f"exact_event_horse_matches={rpdc_coverage['reviewed_sigma_rows_with_exact_rpdc_match']}"
    )

    out_dir = Path(__file__).parent.parent / "reports" / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"contradiction_miner_{target_date}.md"
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
