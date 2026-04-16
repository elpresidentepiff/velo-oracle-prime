"""
VÉLØ Contradiction Miner
========================
Read-only sidecar contradiction report.

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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

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


def _fetch_race_truth_audits(target_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, result_outcome, blocker_fired, blocker_type, blocker_hurt, blocker_helped, assigned_archetype
        FROM race_truth_audits
        WHERE race_date = '{target_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "race_truth_audits",
        "race_id,result_outcome,blocker_fired,blocker_type,blocker_hurt,blocker_helped,assigned_archetype",
        [f"race_date=eq.{target_date}"],
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


def _require_doctrine_registry() -> None:
    _management = _management_sql("SELECT doctrine_key FROM velo_doctrine_registry LIMIT 1")
    if _management is not None:
        return
    _rest_fetch("velo_doctrine_registry", "doctrine_key", [])


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


def _is_weak_a(row: dict) -> bool:
    top_pick_position = row.get("top_pick_position")
    return row.get("decision_tier") == "A" and (
        row.get("confidence_level") == "low" or top_pick_position is None or int(top_pick_position) > 2
    )


def _outcome_rates(rows: list[dict]) -> list[object]:
    total = len(rows)
    if total == 0:
        return [0, 0.0, 0.0, 0.0]
    wins = sum(1 for row in rows if row.get("outcome") == "WIN")
    placed = sum(1 for row in rows if row.get("outcome") == "PLACED")
    misses = sum(1 for row in rows if row.get("outcome") == "MISS")
    return [total, round(100 * wins / total, 1), round(100 * placed / total, 1), round(100 * misses / total, 1)]


def _top_counts(values: list[str | None], limit: int = 3) -> str:
    counts = Counter((value or "unknown") for value in values)
    if not counts:
        return "none"
    return ", ".join(f"{key} ({count})" for key, count in counts.most_common(limit))


def generate(target_date: str) -> Path:
    _require_doctrine_registry()
    generated_at = datetime.now(timezone.utc).isoformat()
    sigma_rows = _fetch_sigma_audits(target_date)
    truth_rows = _fetch_race_truth_audits(target_date)
    rpdc_rows = _fetch_runner_release_candidates(target_date)

    truth_by_race = _truth_by_race(truth_rows)
    rpdc_by_race = _rpdc_by_race(rpdc_rows)

    flagged: list[dict] = []
    for sigma in sigma_rows:
        race_id = sigma.get("race_id")
        contradiction_type = _contradiction_type(
            sigma,
            truth_by_race.get(race_id, {}),
            rpdc_by_race.get(race_id, {"has_cash_window": False, "max_rpdc_release_score": 0.0}),
        )
        if contradiction_type:
            flagged.append(
                {
                    "race_id": race_id,
                    "contradiction_type": contradiction_type,
                    "decision_tier": sigma.get("decision_tier"),
                    "confidence_level": sigma.get("confidence_level"),
                    "verdict_score": sigma.get("verdict_score"),
                    "outcome": sigma.get("outcome"),
                    "blocker_type": truth_by_race.get(race_id, {}).get("blocker_type"),
                    "has_cash_window": rpdc_by_race.get(race_id, {}).get("has_cash_window"),
                    "max_rpdc_release_score": rpdc_by_race.get(race_id, {}).get("max_rpdc_release_score"),
                    "miss_reason": sigma.get("miss_reason"),
                    "track": sigma.get("track"),
                    "assigned_archetype": truth_by_race.get(race_id, {}).get("assigned_archetype"),
                }
            )

    type_counts = Counter(row["contradiction_type"] for row in flagged)
    weak_a_with_blocker = [
        row
        for row in flagged
        if row["contradiction_type"] == "a_tier_weak_place_support"
        and truth_by_race.get(row.get("race_id"), {}).get("blocker_fired")
    ]
    weak_a_without_blocker = [
        {
            "miss_reason": row.get("miss_reason"),
            "track": row.get("track"),
            "assigned_archetype": truth_by_race.get(row.get("race_id"), {}).get("assigned_archetype"),
            "outcome": row.get("outcome"),
        }
        for row in sigma_rows
        if _is_weak_a(row) and not truth_by_race.get(row.get("race_id"), {}).get("blocker_fired")
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
    for contradiction_type, count in type_counts.most_common():
        lines.append(f"| {contradiction_type} | {count} |")
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
        races, win_pct, place_pct, miss_pct = _outcome_rates(rows)
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
            f"{_top_counts([row.get('miss_reason') for row in rows if row.get('outcome') == 'MISS'])} | "
            f"{_top_counts([row.get('track') for row in rows])} | "
            f"{_top_counts([row.get('assigned_archetype') for row in rows])} |"
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
