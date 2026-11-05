#!/usr/bin/env python3
"""World Sigma: settle Velo's frozen World picks against stored provider results.

PAPER/SHADOW only. Reads ``world_model_scorecards`` and ``formfav_results``; writes only
``world_sigma_audits``, ``world_learning_events`` and ``world_pipeline_runs``. Never touches
``sigma_audits``, ``velo_verdicts``, UK learning, weights or Telegram.

Dry run by default: it prints what it would write. ``--execute`` writes.

    python scripts/ops/run_world_sigma.py --days 3
    python scripts/ops/run_world_sigma.py --date 2026-11-05 --execute

The shadow job calls ``settle_dates`` after each freeze, so this runs hourly without any
separate Railway service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.world_sigma import SIGMA_VERSION, build_event, merge_audit, settle_pick

GetJson = Callable[[str], list[dict[str, Any]]]
PostJson = Callable[[str, list[dict[str, Any]], str, str], None]

PAGE = 1000
IN_CHUNK = 40
WRITE_CHUNK = 200
# A race with no result this long after the off is recorded as ``no_result`` so the gap is visible.
NO_RESULT_AFTER = timedelta(hours=3)
SCORECARD_COLS = (
    "provider_race_key,race_date,country,track,race_number,scheduled_off,model_name,runner_rank,"
    "horse_key,horse_name,score,captured_price,identity_grade,generated_pre_off,"
    "provider_predictions_consumed,feature_payload"
)


def default_io() -> tuple[GetJson, PostJson]:
    """Supabase REST reader/writer using the same service credentials as the freeze."""
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("Supabase service credentials are required for World Sigma")
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    def get_json(path: str) -> list[dict[str, Any]]:
        req = urllib.request.Request(f"{url}/rest/v1/{path}", headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
        return json.loads(body.decode()) if body else []

    def post_json(table: str, rows: list[dict[str, Any]], on_conflict: str, prefer: str) -> None:
        query = urllib.parse.urlencode({"on_conflict": on_conflict})
        req = urllib.request.Request(
            f"{url}/rest/v1/{table}?{query}",
            data=json.dumps(rows).encode(),
            method="POST",
            headers={**headers, "Content-Type": "application/json", "Prefer": prefer},
        )
        with urllib.request.urlopen(req, timeout=60):
            pass

    return get_json, post_json


def _chunks(items: list[Any], n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _fetch_scorecards(get_json: GetJson, race_date: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        qs = urllib.parse.urlencode({
            "race_date": f"eq.{race_date}", "select": SCORECARD_COLS,
            "order": "provider_race_key.asc,runner_rank.asc", "limit": PAGE, "offset": offset,
        })
        page = get_json(f"world_model_scorecards?{qs}")
        rows += page
        if len(page) < PAGE:
            return rows
        offset += PAGE


def _fetch_results(get_json: GetJson, keys: list[str]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(keys, IN_CHUNK):
        in_list = "in.(" + ",".join(f'"{k}"' for k in chunk) + ")"
        qs = urllib.parse.urlencode({
            "provider_race_key": in_list,
            "select": "provider_race_key,result_stage,interim,results_payload",
        })
        for row in get_json(f"formfav_results?{qs}"):
            results[row["provider_race_key"]] = row
    return results


def _fetch_existing(get_json: GetJson, race_date: str) -> dict[str, dict[str, Any]]:
    qs = urllib.parse.urlencode({"race_date": f"eq.{race_date}", "select": "*", "limit": 5000})
    return {r["sigma_key"]: r for r in get_json(f"world_sigma_audits?{qs}")}


def settle_dates(
    dates: list[str],
    *,
    get_json: GetJson,
    post_json: PostJson,
    execute: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    totals: Counter = Counter()
    by_basis: Counter = Counter()
    errors: list[str] = []
    audits_out: list[dict[str, Any]] = []
    events_out: list[dict[str, Any]] = []

    for race_date in dates:
        try:
            scorecards = _fetch_scorecards(get_json, race_date)
            groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for row in scorecards:
                groups.setdefault((row["provider_race_key"], row["model_name"]), []).append(row)
            results = _fetch_results(get_json, sorted({k for k, _ in groups}))
            existing = _fetch_existing(get_json, race_date)
            for (race_key, _model), rows in groups.items():
                result = results.get(race_key)
                off = datetime.fromisoformat(str(rows[0]["scheduled_off"]).replace("Z", "+00:00"))
                audit = settle_pick(rows, result, computed_at=now)
                if audit is None:
                    continue
                if audit["basis"] == "no_result" and now < off + NO_RESULT_AFTER:
                    totals["not_yet_due"] += 1  # not off yet, or an empty interim stub
                    continue
                audit = merge_audit(audit, existing.get(audit["sigma_key"]))
                audits_out.append(audit)
                events_out.append(build_event(audit))
                by_basis[audit["basis"]] += 1
                totals["eligible"] += 1 if audit["learning_eligible"] else 0
        except Exception as exc:  # noqa: BLE001 - one bad day must not hide the others
            errors.append(f"{race_date}: {type(exc).__name__}: {exc}")

    totals.update({"audits": len(audits_out), "events": len(events_out), "errors": len(errors)})
    totals.update({f"basis_{k}": v for k, v in by_basis.items()})
    report = {
        "sigma_version": SIGMA_VERSION, "dates": dates, "executed": execute,
        "totals": dict(totals), "errors": errors,
    }

    if execute:
        for chunk in _chunks(audits_out, WRITE_CHUNK):  # audits first: events reference them
            post_json("world_sigma_audits", chunk, "sigma_key", "resolution=merge-duplicates,return=minimal")
        for chunk in _chunks(events_out, WRITE_CHUNK):
            post_json("world_learning_events", chunk, "event_key", "resolution=ignore-duplicates,return=minimal")
        post_json("world_pipeline_runs", [_run_row(dates, now, totals, errors)], "run_key",
                  "resolution=merge-duplicates,return=minimal")
    return report


def _run_row(dates: list[str], now: datetime, totals: Counter, errors: list[str]) -> dict[str, Any]:
    key = hashlib.sha256(f"sigma|{','.join(dates)}|{now.isoformat()}".encode()).hexdigest()
    return {
        "run_key": key,
        "race_date": dates[0],
        "country": "world",
        "model_name": SIGMA_VERSION,
        "status": "PASS" if not errors else ("PARTIAL" if totals["audits"] else "FAILED"),
        "races_seen": totals["audits"] + totals["not_yet_due"],
        "races_scored": totals.get("basis_final", 0),
        "races_skipped_post_off": 0,
        "runners_scored": 0,
        "provider_predictions_consumed": False,
        "generated_at": now.isoformat(),
        "details": {"dates": dates, "totals": dict(totals), "errors": errors[:25]},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", action="append", help="YYYY-MM-DD; repeatable")
    ap.add_argument("--days", type=int, default=3, help="settle this many recent UTC days")
    ap.add_argument("--execute", action="store_true", help="write to Supabase (default: dry run)")
    args = ap.parse_args()

    try:
        from app.core.runtime_env import load_optional_env_file
        load_optional_env_file(ROOT / ".env")
    except Exception:  # noqa: BLE001 - env file is optional
        pass
    today = datetime.now(UTC).date()
    dates = args.date or [(today - timedelta(days=i)).isoformat() for i in range(args.days)]
    get_json, post_json = default_io()
    report = settle_dates(dates, get_json=get_json, post_json=post_json, execute=args.execute)
    print(json.dumps(report, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
