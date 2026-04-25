"""
VÉLØ Longshot Regime Simulation
===============================
Read-only sidecar simulation for the identified longshot blocker regime.

Current focus:
  - blocker_type = longshot_block_allowed
  - decision_tier = A
  - AW track proxy
  - actual winner SP bucket = short_<=3.0

This is not a live scoring change. It is a doctrine review artifact.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


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


def _rest_fetch(table: str, select: str, filters: list[str]) -> list[dict]:
    url = os.getenv("SUPABASE_URL", "")
    key = _service_role_key()
    if not url or not key:
        raise ReadPathUnavailable(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY) are required for PostgREST reads."
        )

    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    rows: list[dict] = []
    offset = 0
    page_size = 1000
    session = _session()
    while True:
        params = [("select", select), ("limit", str(page_size)), ("offset", str(offset))]
        params.extend((item.split("=", 1)[0], item.split("=", 1)[1]) for item in filters if "=" in item)
        response = session.get(f"{url}/rest/v1/{table}", headers=headers, params=params, timeout=20)
        response.raise_for_status()
        batch = response.json()
        if not isinstance(batch, list):
            return rows
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _fetch_sigma_window(start_date: str, end_date: str) -> list[dict]:
    start_ts = f"{start_date}T00:00:00+00:00"
    end_ts = f"{end_date}T23:59:59+00:00"
    sql_rows = _management_sql(f"""
        SELECT race_id, outcome, decision_tier, miss_reason, track, created_at
        FROM sigma_audits
        WHERE created_at >= '{start_ts}' AND created_at <= '{end_ts}' AND outcome IS NOT NULL
        ORDER BY created_at ASC
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "sigma_audits",
        "race_id,outcome,decision_tier,miss_reason,track,created_at",
        [f"created_at=gte.{start_ts}", f"created_at=lte.{end_ts}", "outcome=not.is.null"],
    )


def _fetch_truth_window(start_date: str, end_date: str) -> list[dict]:
    sql_rows = _management_sql(f"""
        SELECT race_id, race_date, blocker_fired, blocker_type, actual_winner_sp
        FROM race_truth_audits
        WHERE race_date >= '{start_date}' AND race_date <= '{end_date}'
    """)
    if sql_rows is not None:
        return sql_rows
    return _rest_fetch(
        "race_truth_audits",
        "race_id,race_date,blocker_fired,blocker_type,actual_winner_sp",
        [f"race_date=gte.{start_date}", f"race_date=lte.{end_date}"],
    )


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


def _window_bounds(target_date: str, days: int) -> tuple[str, str]:
    end = datetime.strptime(target_date, "%Y-%m-%d").date()
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _rate(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 0.0


def generate(target_date: str, days: int) -> Path:
    start_date, end_date = _window_bounds(target_date, days)
    sigma_rows = _fetch_sigma_window(start_date, end_date)
    truth_rows = _fetch_truth_window(start_date, end_date)

    sigma_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sigma_rows:
        sigma_by_race[row.get("race_id")].append(row)

    base_a_tier_rows = [row for row in sigma_rows if row.get("decision_tier") == "A"]
    base_outcomes = Counter((row.get("outcome") or "unknown") for row in base_a_tier_rows)
    base_precision = _rate(base_outcomes.get("WIN", 0), len(base_a_tier_rows))
    base_place_rate = _rate(base_outcomes.get("PLACED", 0), len(base_a_tier_rows))

    regime_rows: list[dict[str, Any]] = []
    for truth_row in truth_rows:
        if not truth_row.get("blocker_fired"):
            continue
        if truth_row.get("blocker_type") != "longshot_block_allowed":
            continue
        if _sp_bucket(truth_row.get("actual_winner_sp")) != "short_<=3.0":
            continue
        for sigma_row in sigma_by_race.get(truth_row.get("race_id"), []):
            if sigma_row.get("decision_tier") != "A":
                continue
            if _surface_bucket(sigma_row.get("track")) != "AW":
                continue
            regime_rows.append(
                {
                    "race_id": truth_row.get("race_id"),
                    "track": sigma_row.get("track"),
                    "outcome": sigma_row.get("outcome"),
                    "miss_reason": sigma_row.get("miss_reason"),
                    "actual_winner_sp": truth_row.get("actual_winner_sp"),
                    "actual_winner_bucket": "short_<=3.0",
                }
            )

    regime_outcomes = Counter((row.get("outcome") or "unknown") for row in regime_rows)
    admitted = len(regime_rows)
    recovered_winners = regime_outcomes.get("WIN", 0)
    added_places = regime_outcomes.get("PLACED", 0)
    false_positive_increase = regime_outcomes.get("MISS", 0)

    relaxed_precision = _rate(recovered_winners, admitted)
    relaxed_place_rate = _rate(added_places, admitted)
    net_precision_change = round(relaxed_precision - base_precision, 1)
    place_rate_change = round(relaxed_place_rate - base_place_rate, 1)

    lines: list[str] = []
    lines.append(f"# Longshot Regime Simulation — {target_date}")
    lines.append(f"Window: {start_date} to {end_date}")
    lines.append("Model: sidecar doctrine simulation only")
    lines.append("")
    lines.append("## Regime")
    lines.append("- blocker: `longshot_block_allowed`")
    lines.append("- decision tier: `A`")
    lines.append("- surface: `AW`")
    lines.append("- actual winner SP bucket: `short_<=3.0`")
    lines.append("")
    lines.append("## Current vs Relaxed Proxy")
    lines.append("| metric | value |")
    lines.append("| --- | --- |")
    lines.append(f"| winner_recovery_count | {recovered_winners} |")
    lines.append(f"| false_positive_increase | {false_positive_increase} |")
    lines.append(f"| relaxed_regime_win_rate_pct | {relaxed_precision} |")
    lines.append(f"| relaxed_regime_place_rate_pct | {relaxed_place_rate} |")
    lines.append(f"| net_a_tier_precision_change_pct_points | {net_precision_change} |")
    lines.append(f"| place_rate_change_pct_points | {place_rate_change} |")
    lines.append("")
    lines.append("## Outcome Split")
    lines.append("| outcome | count |")
    lines.append("| --- | --- |")
    for outcome, count in regime_outcomes.most_common():
        lines.append(f"| {outcome} | {count} |")
    if not regime_outcomes:
        lines.append("| none | 0 |")
    lines.append("")
    lines.append("## Top Tracks")
    lines.append("| track | count |")
    lines.append("| --- | --- |")
    for track, count in Counter(row.get("track") or "unknown" for row in regime_rows).most_common():
        lines.append(f"| {track} | {count} |")
    if not regime_rows:
        lines.append("| none | 0 |")
    lines.append("")
    lines.append("## Notes")
    lines.append("- `winner_recovery_count` is the number of blocker-fired regime rows whose observed outcome was `WIN`.")
    lines.append("- `false_positive_increase` is the number of regime rows whose observed outcome was `MISS` and would be re-admitted under the relaxed regime proxy.")
    lines.append("- `net_a_tier_precision_change_pct_points` compares the regime proxy win rate against the observed base A-tier win rate over the same window.")
    lines.append("- This is a sidecar counterfactual proxy, not a deployed scoring simulation.")

    out_dir = Path(__file__).parent.parent / "reports" / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"longshot_regime_simulation_{target_date}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")

    json_path = out_dir / f"longshot_regime_simulation_{target_date}.json"
    json_path.write_text(
        json.dumps(
            {
                "window": {"start": start_date, "end": end_date},
                "regime_count": admitted,
                "winner_recovery_count": recovered_winners,
                "false_positive_increase": false_positive_increase,
                "relaxed_regime_win_rate_pct": relaxed_precision,
                "relaxed_regime_place_rate_pct": relaxed_place_rate,
                "base_a_tier_win_rate_pct": base_precision,
                "base_a_tier_place_rate_pct": base_place_rate,
                "net_a_tier_precision_change_pct_points": net_precision_change,
                "place_rate_change_pct_points": place_rate_change,
                "outcome_split": regime_outcomes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Written: {out_path}")
    print(f"Written: {json_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    generate(args.date, args.days)
