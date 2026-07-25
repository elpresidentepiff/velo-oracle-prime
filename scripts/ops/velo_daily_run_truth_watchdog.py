"""
Daily truth watchdog for VÉLØ scoring.

Purpose:
- prove whether the day actually scored
- distinguish automated cron truth from manual recovery truth
- separate Supabase truth, local file truth, and Telegram truth
- produce an alert packet that the LLM Council can audit

Usage:
    python scripts/velo_daily_run_truth_watchdog.py --date YYYY-MM-DD
    python scripts/velo_daily_run_truth_watchdog.py --date YYYY-MM-DD --notify-on-alert
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from runtime_truth_support import append_telegram_event, telegram_truth_status
from sync_verdicts_from_supabase import sync_local_verdict_archive

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(ROOT / ".env")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SB_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_VOX_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Accept": "application/json",
}


def _get(path: str, params: dict[str, str]) -> list[dict]:
    url = f"{SB_URL}/rest/v1/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read())


def _tg(text: str) -> bool:
    target = next((line.split(":", 1)[1].strip() for line in text.splitlines() if line.lower().startswith("date:")), "")
    if not TG_TOKEN or not TG_CHAT:
        if target:
            append_telegram_event(
                date_str=target,
                service="velo-run-watchdog",
                event_type="watchdog_alert",
                sent=False,
                notify_enabled=False,
                message_preview=text.splitlines()[0] if text else "",
                error="NO_TOKEN_OR_CHAT",
            )
        return False
    body = json.dumps({"chat_id": TG_CHAT, "text": text[:4096]}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            sent = resp.status == 200
    except Exception:
        sent = False
    if target:
        append_telegram_event(
            date_str=target,
            service="velo-run-watchdog",
            event_type="watchdog_alert",
            sent=sent,
            notify_enabled=True,
            message_preview=text.splitlines()[0] if text else "",
            error=None if sent else "SEND_FAILED",
        )
    return sent


def _load_local_verdict_file(target: str) -> tuple[bool, int | None, str]:
    path = ROOT / "data" / f"velo_prime_verdicts_{target.replace('-', '_')}.json"
    if not path.exists():
        return False, None, str(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return True, None, str(path)

    if isinstance(payload, list):
        return True, len(payload), str(path)
    if isinstance(payload, dict):
        if isinstance(payload.get("verdicts"), list):
            return True, len(payload["verdicts"]), str(path)
        if isinstance(payload.get("rows"), list):
            return True, len(payload["rows"]), str(path)
    return True, None, str(path)


def _classify(
    pipeline_rows: list[dict],
    verdict_rows: list[dict],
    local_exists: bool,
    local_count: int | None,
) -> tuple[str, list[str], list[str]]:
    issues: list[str] = []
    warnings: list[str] = []
    latest = pipeline_rows[0] if pipeline_rows else None
    verdict_count = len(verdict_rows)

    if not latest and verdict_count == 0:
        issues.extend(["NO_PIPELINE_RUN", "NO_VERDICTS_WRITTEN"])
        if not local_exists:
            issues.append("LOCAL_VERDICT_FILE_MISSING")
        return "NO_SCORING_RUN", issues, warnings

    if latest:
        status = (latest.get("status") or "").upper()
        run_state = (latest.get("run_state") or "").lower()
        trigger_source = (latest.get("trigger_source") or "").lower()
        commit_sha = latest.get("commit_sha")

        if run_state == "running":
            issues.append("PIPELINE_STILL_RUNNING")
            return "RUNNING_OR_STALLED", issues, warnings

        if status == "FAIL" and verdict_count == 0:
            issues.extend(["PIPELINE_FAIL", "NO_VERDICTS_WRITTEN"])
            return "RUN_FAILED_NO_VERDICTS", issues, warnings

        if status == "PASS" and verdict_count == 0:
            issues.append("FALSE_PASS_NO_VERDICTS")
            return "FALSE_PASS_NO_VERDICTS", issues, warnings

        if verdict_count > 0 and trigger_source == "manual":
            issues.append("MANUAL_RUN_ONLY")
            warnings.append("AUTOMATION_DID_NOT_DELIVER")
            if not commit_sha:
                warnings.append("COMMIT_SHA_MISSING")
            if not local_exists:
                warnings.append("LOCAL_VERDICT_FILE_MISSING")
            elif local_count == 0:
                warnings.append("LOCAL_VERDICT_FILE_EMPTY")
            return "MANUAL_RECOVERY_ONLY", issues, warnings

        if verdict_count > 0:
            if not commit_sha:
                warnings.append("COMMIT_SHA_MISSING")
            if not local_exists:
                warnings.append("LOCAL_VERDICT_FILE_MISSING")
            elif local_count == 0:
                warnings.append("LOCAL_VERDICT_FILE_EMPTY")
            return "AUTOMATED_RUN_OK", issues, warnings

    if verdict_count > 0:
        issues.append("VERDICTS_WITHOUT_PIPELINE_TRUTH")
        return "VERDICTS_WITHOUT_PIPELINE_TRUTH", issues, warnings

    return "UNKNOWN_NEEDS_INVESTIGATION", issues, warnings


def _markdown(report: dict) -> str:
    latest = report.get("latest_pipeline_run") or {}
    lines = [
        f"# VELO Daily Run Truth Watchdog - {report['date']}",
        "",
        f"- **status**: `{report['status']}`",
        f"- **alert_required**: `{report['alert_required']}`",
        f"- **council_owner**: `{report['council_owner']}`",
        f"- **escalation_owner**: `{report['escalation_owner']}`",
        "",
        "## Truth Separation",
        f"- deploy truth: `{report['deploy_truth_status']}`",
        f"- cron truth: `{report['cron_truth_status']}`",
        f"- Supabase verdict truth: `{report['supabase_verdict_truth_status']}`",
        f"- local verdict truth: `{report['local_verdict_truth_status']}`",
        f"- Telegram truth: `{report['telegram_truth_status']}`",
        "",
        "## Pipeline Run",
        f"- trigger_source: `{latest.get('trigger_source')}`",
        f"- status: `{latest.get('status')}`",
        f"- run_state: `{latest.get('run_state')}`",
        f"- started_at: `{latest.get('started_at')}`",
        f"- finished_at: `{latest.get('finished_at')}`",
        f"- races_processed: `{latest.get('races_processed')}`",
        f"- runners_processed: `{latest.get('runners_processed')}`",
        f"- commit_sha: `{latest.get('commit_sha')}`",
        "",
        "## Verdicts",
        f"- supabase_verdict_count: `{report['supabase_verdict_count']}`",
        f"- local_verdict_file: `{report['local_verdict_file']}`",
        f"- local_verdict_exists: `{report['local_verdict_exists']}`",
        f"- local_verdict_count: `{report['local_verdict_count']}`",
        "",
        "## Issues",
    ]

    if report["issues"]:
        lines.extend([f"- `{issue}`" for issue in report["issues"]])
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Warnings")
    if report["warnings"]:
        lines.extend([f"- `{warning}`" for warning in report["warnings"]])
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Verdict Preview")
    if report["verdict_preview"]:
        for row in report["verdict_preview"]:
            lines.append(f"- `{row.get('generated_at')}` - `{row.get('race_id')}`")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def _known_race_ids_for_date(target: str) -> list:
    """race_ids from the standard racecard cache for this date, if it exists.

    generated_at is write-time, not race-date -- scoring the evening before
    race day stamps generated_at under the wrong calendar day and silently
    zeroes out any date-range query, which would falsely tell this watchdog
    "the day never scored" for VELO's normal evening-before operating pattern.
    race_id reliably correlates to the actual race date instead.
    """
    path = ROOT / "data" / f"racecards_{target.replace('-', '_')}_standard.json"
    if not path.exists():
        return []
    try:
        races = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [r["race_id"] for r in races if r.get("race_id")]


def build_report(target: str) -> dict:
    next_day = date.fromisoformat(target) + timedelta(days=1)
    start_utc = f"{target}T00:00:00Z"
    end_utc = f"{next_day.isoformat()}T00:00:00Z"

    pipeline_rows = _get(
        "pipeline_runs",
        {
            "select": "id,service_name,run_type,source_date,status,run_state,started_at,finished_at,races_processed,runners_processed,error_message,trigger_source,commit_sha,environment",
            "service_name": "eq.velo-prime-scoring",
            "source_date": f"eq.{target}",
            "order": "started_at.desc",
            "limit": "10",
        },
    )
    known_race_ids = _known_race_ids_for_date(target)
    verdict_rows = []
    if known_race_ids:
        for offset in range(0, len(known_race_ids), 50):
            verdict_rows.extend(
                _get(
                    "velo_verdicts",
                    {
                        "select": "race_id,generated_at,engine_version,git_commit_sha,environment",
                        "race_id": f"in.({','.join(known_race_ids[offset:offset + 50])})",
                        "order": "generated_at.asc",
                        "limit": "1000",
                    },
                )
            )
    if not verdict_rows:
        verdict_rows = _get(
            "velo_verdicts",
            {
                "select": "race_id,generated_at,engine_version,git_commit_sha,environment",
                "generated_at": f"gte.{start_utc}",
                "order": "generated_at.asc",
                "limit": "1000",
            },
        )
        verdict_rows = [row for row in verdict_rows if row.get("generated_at", "") < end_utc]

    local_exists, local_count, local_file = _load_local_verdict_file(target)
    status, issues, warnings = _classify(pipeline_rows, verdict_rows, local_exists, local_count)
    latest = pipeline_rows[0] if pipeline_rows else {}
    tg_truth = telegram_truth_status(target)

    return {
        "date": target,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": status,
        "alert_required": status != "AUTOMATED_RUN_OK",
        "council_owner": "DATA_AUDITOR",
        "escalation_owner": "PRIME_CHAIR",
        "deploy_truth_status": "UNKNOWN_UNLESS_RAILWAY_COMMIT_EXPOSED",
        "cron_truth_status": "PASS" if latest and latest.get("trigger_source") != "manual" and latest.get("status") == "PASS" else "FAIL_OR_UNPROVEN",
        "supabase_verdict_truth_status": "PASS" if verdict_rows else "FAIL",
        "local_verdict_truth_status": "PASS" if local_exists and (local_count or 0) > 0 else "FAIL_OR_PARTIAL",
        "telegram_truth_status": tg_truth["status"],
        "telegram_truth_path": tg_truth["path"],
        "telegram_truth_summary": tg_truth["summary"],
        "supabase_verdict_count": len(verdict_rows),
        "local_verdict_exists": local_exists,
        "local_verdict_count": local_count,
        "local_verdict_file": local_file,
        "issues": issues,
        "warnings": warnings,
        "latest_pipeline_run": latest,
        "pipeline_run_count": len(pipeline_rows),
        "verdict_preview": verdict_rows[:5],
    }


def write_report(target: str, *, repair_local_archive: bool = False) -> dict:
    report = build_report(target)
    repair_result = None
    needs_repair = (
        repair_local_archive
        and report["supabase_verdict_count"] > 0
        and (
            not report["local_verdict_exists"]
            or not report["local_verdict_count"]
            or report["local_verdict_truth_status"] != "PASS"
        )
    )
    if needs_repair:
        repair_result = sync_local_verdict_archive(target)
        if repair_result.get("status") == "LOCAL_HYDRATED":
            report = build_report(target)
        report["local_archive_repair"] = repair_result
    else:
        report["local_archive_repair"] = {"status": "SKIPPED"}

    date_tag = target.replace("-", "_")
    json_path = ROOT / "data" / f"velo_daily_run_truth_{date_tag}.json"
    md_path = ROOT / "data" / f"velo_daily_run_truth_{date_tag}.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    report["json_path"] = str(json_path)
    report["md_path"] = str(md_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    parser.add_argument("--notify-on-alert", action="store_true", help="Send Telegram only when the day is not AUTOMATED_RUN_OK")
    parser.add_argument("--repair-local-archive", action="store_true", help="Hydrate the local verdict archive from Supabase when missing")
    args = parser.parse_args()

    report = write_report(args.date, repair_local_archive=args.repair_local_archive)

    print(json.dumps(report, indent=2))

    if args.notify_on_alert and report["alert_required"]:
        sent = _tg(
            f"VELO RUN TRUTH ALERT\n"
            f"date: {report['date']}\n"
            f"status: {report['status']}\n"
            f"owner: {report['council_owner']}\n"
            f"escalation: {report['escalation_owner']}\n"
            f"issues: {', '.join(report['issues']) or 'none'}\n"
            f"warnings: {', '.join(report['warnings']) or 'none'}"
        )
        print(f"telegram_alert_sent={sent}")


if __name__ == "__main__":
    main()
