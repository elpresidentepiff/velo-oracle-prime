"""
pipeline_stale_run_audit.py — READ-ONLY stale pipeline-run detector.

Queries Supabase pipeline_runs for rows stuck in a RUNNING/running state
beyond a configurable TTL.  Does NOT mutate any rows.  Outputs a report
and exits 0 even when stale runs are found so it is safe to call from cron.

Usage:
    PYTHONPATH=. python scripts/audit/pipeline_stale_run_audit.py [--ttl-hours 2]

Output:
    data/security/pipeline_stale_run_audit_latest.json
    data/security/pipeline_stale_run_audit_latest.md
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "security"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sb_get(path: str) -> list[dict]:
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
    url = f"{_SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": _SUPABASE_KEY,
            "Authorization": f"Bearer {_SUPABASE_KEY}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _detect_stale(ttl_hours: float) -> dict:
    cutoff = _utc_now() - timedelta(hours=ttl_hours)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")

    rows = _sb_get(
        f"pipeline_runs"
        f"?select=id,status,run_state,started_at,completed_at,service_name,run_type,source_date,error_message"
        f"&or=(status.eq.RUNNING,run_state.eq.running)"
        f"&started_at=lt.{cutoff_iso}"
        f"&order=started_at.asc"
        f"&limit=100"
    )

    stale = []
    for row in rows:
        started = row.get("started_at") or ""
        try:
            started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        except ValueError:
            started_dt = None
        hours_running = round((_utc_now() - started_dt).total_seconds() / 3600, 2) if started_dt else None
        stale.append({
            **row,
            "hours_running": hours_running,
            "recommended_action": "MANUAL_REVIEW — mark status=FAIL if confirmed crashed",
        })

    return {
        "audit_timestamp": _utc_now().isoformat(),
        "ttl_hours": ttl_hours,
        "cutoff_before": cutoff_iso,
        "stale_count": len(stale),
        "stale_runs": stale,
        "recovery_note": (
            "This report is READ-ONLY. No rows were mutated. "
            "To recover a stuck run, update pipeline_runs SET status='FAIL', run_state='failed' "
            "WHERE id=<run_id> after confirming the subprocess is no longer running."
        ),
    }


def _as_markdown(report: dict) -> str:
    lines = [
        "# Pipeline Stale-Run Audit",
        "",
        f"**Audit time:** {report['audit_timestamp']}  ",
        f"**TTL threshold:** {report['ttl_hours']} hours  ",
        f"**Stale runs found:** {report['stale_count']}  ",
        "",
    ]
    if report["stale_count"] == 0:
        lines += ["No stale pipeline runs detected. All RUNNING rows are within TTL.", ""]
    else:
        lines += [
            "## Stale Runs",
            "",
            "| ID | Status | run_state | service | type | source_date | started_at | hours_running |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in report["stale_runs"]:
            lines.append(
                f"| {r.get('id','')[:8]}… | {r.get('status','')} | {r.get('run_state','')} "
                f"| {r.get('service_name','')} | {r.get('run_type','')} "
                f"| {r.get('source_date','')} | {r.get('started_at','')[:19]} "
                f"| {r.get('hours_running','?')} |"
            )
        lines += [
            "",
            "## Recovery",
            "",
            report["recovery_note"],
            "",
            "```sql",
            "-- Example: mark a single stuck run as failed (run manually after confirming subprocess is dead)",
            "UPDATE pipeline_runs SET status='FAIL', run_state='failed', completed_at=now()",
            "WHERE id = '<run_id>';",
            "```",
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect stale pipeline runs (read-only)")
    parser.add_argument("--ttl-hours", type=float, default=2.0, help="Hours after which a RUNNING run is stale")
    args = parser.parse_args()

    if not _SUPABASE_URL or not _SUPABASE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in environment")
        return 1

    try:
        report = _detect_stale(args.ttl_hours)
    except Exception as exc:
        report = {
            "audit_timestamp": _utc_now().isoformat(),
            "ttl_hours": args.ttl_hours,
            "error": str(exc),
            "stale_count": None,
            "stale_runs": [],
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUT_DIR / "pipeline_stale_run_audit_latest.json"
    out_md = OUT_DIR / "pipeline_stale_run_audit_latest.md"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    out_md.write_text(_as_markdown(report), encoding="utf-8")

    print(f"Stale runs: {report.get('stale_count', 'ERROR')}")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
