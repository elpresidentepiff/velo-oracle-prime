"""New Build-only Racing API result capture.

Fetches result truth into local raw files without touching Live/Shadow flows,
Supabase, Sigma, Telegram, or old learning state.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from new_build_velo.spine import ROOT, TRUST_POLICY, utc_now, write_json


REPORT_ROOT = ROOT / "data" / "new_build" / "reports"


def _load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def _date_range(from_date: str, to_date: str) -> list[str]:
    start = datetime.strptime(from_date, "%Y-%m-%d").date()
    end = datetime.strptime(to_date, "%Y-%m-%d").date()
    days: list[str] = []
    cursor = start
    while cursor <= end:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def _credentials() -> tuple[str, str, str]:
    _load_env_file()
    username = os.getenv("RACING_API_USERNAME", "").strip()
    password = os.getenv("RACING_API_PASSWORD", "").strip()
    base_url = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com").strip().rstrip("/")
    if not username or not password:
        raise RuntimeError("RACING_API_USERNAME/RACING_API_PASSWORD missing from environment or .env")
    return username, password, base_url


def _fetch_date(session: requests.Session, *, base_url: str, username: str, password: str, date_str: str) -> dict[str, Any]:
    endpoint = f"{base_url}/results" if base_url.endswith("/v1") else urljoin(base_url + "/", "v1/results")
    params = {"start_date": date_str, "end_date": date_str}
    started_at = utc_now()
    response = session.get(endpoint, params=params, auth=(username, password), timeout=30)
    finished_at = utc_now()
    payload: dict[str, Any]
    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": response.text}
    results = payload.get("results") if isinstance(payload, dict) else None
    return {
        "date": date_str,
        "endpoint": endpoint,
        "params": params,
        "started_at": started_at,
        "finished_at": finished_at,
        "status_code": response.status_code,
        "ok": response.status_code == 200,
        "race_count": len(results) if isinstance(results, list) else 0,
        "payload": payload,
    }


def capture_results(*, from_date: str, to_date: str, execute: bool = False, write_empty: bool = False) -> dict[str, Any]:
    username, password, base_url = _credentials()
    session = requests.Session()
    rows: list[dict[str, Any]] = []
    written = 0
    skipped_empty = 0
    for date_str in _date_range(from_date, to_date):
        row = _fetch_date(session, base_url=base_url, username=username, password=password, date_str=date_str)
        out_path = ROOT / "data" / f"results_{date_str.replace('-', '_')}.json"
        row_report = {k: v for k, v in row.items() if k != "payload"}
        row_report["output_path"] = str(out_path)
        if execute and row["ok"] and (row["race_count"] > 0 or write_empty):
            out_path.write_text(json.dumps(row["payload"], indent=2, ensure_ascii=False), encoding="utf-8")
            written += 1
            row_report["written"] = True
        else:
            if row["race_count"] == 0:
                skipped_empty += 1
            row_report["written"] = False
        rows.append(row_report)

    report = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_RESULTS_CAPTURE_COMPLETE",
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "from_date": from_date,
        "to_date": to_date,
        "dates_checked": len(rows),
        "files_written": written,
        "empty_dates_skipped": skipped_empty,
        "total_races_fetched": sum(int(row.get("race_count") or 0) for row in rows),
        "rows": rows,
        "trust_policy": TRUST_POLICY,
        "rpr_policy": "RPR_ARCHIVE_ONLY",
        "live_velo_touched": False,
        "shadow_velo_touched": False,
        "credentials_in_code": False,
    }
    if execute:
        write_json(REPORT_ROOT / "results_capture_latest.json", report)
        lines = [
            "# New Build Results Capture",
            "",
            f"- Date range: {from_date} to {to_date}",
            f"- Dates checked: {len(rows)}",
            f"- Files written: {written}",
            f"- Empty dates skipped: {skipped_empty}",
            f"- Total races fetched: {report['total_races_fetched']}",
            "",
            "## Dates",
        ]
        for row in rows:
            lines.append(
                f"- {row['date']}: status={row['status_code']} races={row['race_count']} "
                f"written={row['written']} path={row['output_path']}"
            )
        lines.extend(["", "Live VELO untouched. Shadow VELO untouched."])
        (REPORT_ROOT / "results_capture_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture Racing API results for New Build VELO only.")
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--write-empty", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(capture_results(from_date=args.from_date, to_date=args.to_date, execute=args.execute, write_empty=args.write_empty), indent=2, ensure_ascii=False))
    return 0
