"""Read-only hydration of the local VELO verdict archive from Supabase."""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
load_dotenv(ROOT / ".env")

SB_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
HEADERS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Accept": "application/json"}


def _get(table: str, params: dict[str, str]) -> list[dict]:
    if not SB_URL or not SB_KEY:
        raise RuntimeError("Supabase credentials are not configured")
    query = urllib.parse.urlencode(params, safe="(),.*")
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}?{query}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def _fetch_verdicts(target: str) -> tuple[list[dict], str]:
    next_day = date.fromisoformat(target) + timedelta(days=1)
    columns = (
        "race_id,generated_at,engine_version,git_commit_sha,environment,"
        "velo_prime_prob,improvement_score,market_deception_score,place_prob,"
        "longshot_prob,release_day_prob,decision_tier,confidence_level,"
        "assigned_product,router_reasons,execution_allowed,top_rank_horse_id,"
        "selections,full_analysis,active_components,excluded_from_ensemble,"
        "g_shadow_multiplier,g_shadow_flags"
    )
    for label, start, end in (
        ("uk_window", f"{target}T03:00:00Z", f"{next_day.isoformat()}T03:00:00Z"),
        ("utc_day", f"{target}T00:00:00Z", f"{next_day.isoformat()}T00:00:00Z"),
    ):
        rows = _get(
            "velo_verdicts",
            {
                "select": columns,
                "generated_at": f"gte.{start}",
                "and": f"(generated_at.lt.{end})",
                "order": "velo_prime_prob.desc",
                "limit": "1000",
            },
        )
        if rows:
            return rows, label

    race_rows = _get("races", {"select": "id", "date": f"eq.{target}", "limit": "1000"})
    race_ids = [str(row["id"]) for row in race_rows if row.get("id")]
    rows: list[dict] = []
    for offset in range(0, len(race_ids), 50):
        rows.extend(
            _get(
                "velo_verdicts",
                {
                    "select": columns,
                    "race_id": f"in.({','.join(race_ids[offset:offset + 50])})",
                    "order": "velo_prime_prob.desc",
                    "limit": "1000",
                },
            )
        )
    return rows, "race_id_join" if rows else "none"


def sync_local_verdict_archive(target: str) -> dict:
    """Hydrate the canonical dated local verdict file without scoring or DB writes."""
    output = DATA / f"velo_prime_verdicts_{target.replace('-', '_')}.json"
    rows, method = _fetch_verdicts(target)
    if not rows:
        return {
            "status": "NO_VERDICTS_FOUND",
            "date": target,
            "query_method": method,
            "row_count": 0,
            "path": str(output),
        }
    output.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    return {
        "status": "LOCAL_HYDRATED",
        "date": target,
        "query_method": method,
        "row_count": len(rows),
        "path": str(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    args = parser.parse_args()
    print(json.dumps(sync_local_verdict_archive(args.date), indent=2))


if __name__ == "__main__":
    main()
