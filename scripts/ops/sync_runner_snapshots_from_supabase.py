"""Read-only hydration of the latest durable runner snapshot batch.

Railway cron containers are ephemeral.  When Prime scoring is skipped because
``pipeline_runs`` already has a terminal PASS, downstream paper models still
need the per-runner JSONL produced by the original scoring container.  This
script reconstructs that JSONL from ``runner_prediction_snapshots`` without
rescoring, updating Supabase, or changing any prediction.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
PAGE_SIZE = 1000

load_dotenv(ROOT / ".env")


def _base_url() -> str:
    value = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    if not value:
        raise RuntimeError("SUPABASE_URL not set")
    return value


def _headers() -> dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY) not set")
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def _get(params: dict[str, str]) -> list[dict[str, Any]]:
    response = requests.get(
        f"{_base_url()}/rest/v1/runner_prediction_snapshots",
        headers=_headers(),
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"unexpected runner snapshot response: {type(payload).__name__}")
    return payload


def latest_run_id(date_str: str) -> str | None:
    rows = _get(
        {
            "select": "run_id,created_at",
            "race_date": f"eq.{date_str}",
            "order": "created_at.desc",
            "limit": "1",
        }
    )
    return str(rows[0]["run_id"]) if rows and rows[0].get("run_id") else None


def fetch_run_rows(run_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = _get(
            {
                "select": "*",
                "run_id": f"eq.{run_id}",
                "order": "race_id.asc,rank.asc",
                "limit": str(PAGE_SIZE),
                "offset": str(offset),
            }
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def hydrate_runner_snapshots(date_str: str, output_dir: Path = DATA) -> dict[str, Any]:
    run_id = latest_run_id(date_str)
    if not run_id:
        return {
            "status": "NO_DURABLE_RUNNER_SNAPSHOTS",
            "date": date_str,
            "row_count": 0,
            "path": None,
        }

    rows = fetch_run_rows(run_id)
    for row in rows:
        row.pop("id", None)
    if not rows:
        return {
            "status": "NO_DURABLE_RUNNER_SNAPSHOTS",
            "date": date_str,
            "run_id": run_id,
            "row_count": 0,
            "path": None,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    date_tag = date_str.replace("-", "_")
    output = output_dir / f"runner_snapshots_{date_tag}_{run_id}.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")

    race_ids = {str(row.get("race_id")) for row in rows if row.get("race_id")}
    return {
        "status": "LOCAL_HYDRATED",
        "date": date_str,
        "run_id": run_id,
        "row_count": len(rows),
        "race_count": len(race_ids),
        "path": str(output),
        "source": "runner_prediction_snapshots",
        "write_back": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    parser.add_argument("--output-dir", type=Path, default=DATA)
    args = parser.parse_args()

    result = hydrate_runner_snapshots(args.date, args.output_dir)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["status"] == "LOCAL_HYDRATED" else 1


if __name__ == "__main__":
    sys.exit(main())
