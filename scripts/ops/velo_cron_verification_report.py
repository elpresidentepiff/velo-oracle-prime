"""
VÉLØ Cron Verification Report
===============================
Implements the cron verification requirement from VELO_AGENT_HARNESS_DOCTRINE_V1.

Audits the Railway cron registration state and PDF ingestion daily path.
Produces a structured report of the automation gap.

Hard constraints:
  - READ_ONLY: no cron changes, no Railway config changes, no file writes
  - No live-state mutation of any kind
  - Reports only — operator must explicitly approve any cron changes

Usage:
    python scripts/ops/velo_cron_verification_report.py
    python scripts/ops/velo_cron_verification_report.py --json
    python scripts/ops/velo_cron_verification_report.py --save   # writes report to data/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT))

# ── Expected automation config ────────────────────────────────────────────────
EXPECTED_CRON_SCHEDULE = "0 9 * * 1-6"   # 09:00 UTC Mon–Sat
EXPECTED_CRON_COMMAND = "python scripts/ops/run_prime_today.py"
EXPECTED_RP_MERGED_DIR = DATA / "racecard_merged"
EXPECTED_DAILY_PDF_COUNT = 7  # 7 canonical Racing Post PDFs per race day


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_railway_toml() -> dict:
    """Check railway.toml for cron schedule registration."""
    toml_path = ROOT / "railway.toml"
    if not toml_path.exists():
        return {
            "file": "railway.toml",
            "exists": False,
            "cron_found": False,
            "cron_schedule": None,
            "status": "MISSING",
            "detail": "railway.toml not found in repo root",
        }
    content = toml_path.read_text(encoding="utf-8")
    cron_found = "cronSchedule" in content or "cron" in content.lower()
    schedule_val = None
    for line in content.splitlines():
        if "cronSchedule" in line or "cron_schedule" in line.lower():
            schedule_val = line.strip()
            break
    return {
        "file": "railway.toml",
        "exists": True,
        "cron_found": cron_found,
        "cron_schedule": schedule_val,
        "status": "FOUND" if cron_found else "CRON_NOT_REGISTERED",
        "detail": schedule_val or "No cronSchedule key found in railway.toml",
    }


def _check_manual_trigger_pattern() -> dict:
    """
    Audit daily truth watchdog files to detect manual-only trigger pattern.
    Returns count of days with manual-only vs automated triggers.
    """
    manual_days = []
    auto_days = []
    unknown_days = []

    for f in sorted(DATA.glob("velo_daily_run_truth_*.md")):
        content = f.read_text(encoding="utf-8")
        parts = f.stem.replace("velo_daily_run_truth_", "").split("_")
        date_str = "-".join(parts) if len(parts) == 3 else f.stem
        if "trigger_source: `manual`" in content or "MANUAL_RECOVERY_ONLY" in content:
            manual_days.append(date_str)
        elif "trigger_source: `cron`" in content or "trigger_source: `automated`" in content:
            auto_days.append(date_str)
        else:
            unknown_days.append(date_str)

    total = len(manual_days) + len(auto_days) + len(unknown_days)
    automation_rate = (len(auto_days) / total * 100) if total > 0 else 0.0

    return {
        "total_days_audited": total,
        "manual_trigger_days": len(manual_days),
        "automated_trigger_days": len(auto_days),
        "unknown_days": len(unknown_days),
        "automation_rate_pct": round(automation_rate, 1),
        "last_manual_days": manual_days[-5:],
        "last_auto_days": auto_days[-3:],
        "status": "AUTOMATION_BROKEN" if automation_rate < 50 else "AUTOMATION_OK",
        "detail": (
            f"Only {automation_rate:.0f}% of days triggered automatically. "
            f"Cron is effectively non-functional." if automation_rate < 50
            else f"Automation rate: {automation_rate:.0f}%"
        ),
    }


def _check_rp_merged_ingestion() -> dict:
    """Check whether RP merged JSON files are being delivered daily."""
    if not EXPECTED_RP_MERGED_DIR.exists():
        return {
            "directory": str(EXPECTED_RP_MERGED_DIR),
            "exists": False,
            "file_count": 0,
            "last_date": None,
            "gap_days": None,
            "status": "DIRECTORY_MISSING",
            "detail": "racecard_merged/ directory does not exist",
        }

    files = sorted(EXPECTED_RP_MERGED_DIR.glob("racecard_*.json"))
    if not files:
        return {
            "directory": str(EXPECTED_RP_MERGED_DIR),
            "exists": True,
            "file_count": 0,
            "last_date": None,
            "gap_days": None,
            "status": "NO_FILES",
            "detail": "racecard_merged/ exists but contains no JSON files",
        }

    last_file = files[-1]
    # Extract date from filename: racecard_{VENUE}_{YYYY-MM-DD}.json
    # e.g. racecard_YOR_2026-05-14.json
    import re as _re
    name = last_file.stem
    date_match = _re.search(r"(\d{4}-\d{2}-\d{2})$", name)
    last_date_str = None
    if date_match:
        try:
            last_date_str = date_match.group(1)
            date.fromisoformat(last_date_str)  # validate
        except ValueError:
            last_date_str = None

    gap_days = None
    status = "UNKNOWN"
    if last_date_str:
        last_date = date.fromisoformat(last_date_str)
        gap_days = (date.today() - last_date).days
        if gap_days == 0:
            status = "CURRENT"
        elif gap_days <= 1:
            status = "ONE_DAY_BEHIND"
        elif gap_days <= 7:
            status = "STALE"
        else:
            status = "INGESTION_GAP_CRITICAL"

    return {
        "directory": str(EXPECTED_RP_MERGED_DIR),
        "exists": True,
        "file_count": len(files),
        "last_date": last_date_str,
        "gap_days": gap_days,
        "status": status,
        "detail": (
            f"Last RP merged file: {last_file.name}. "
            f"Gap: {gap_days} day(s)." if gap_days is not None
            else f"Could not parse date from {last_file.name}"
        ),
    }


def _check_data_gap() -> dict:
    """Check for the data gap between last truth file and today."""
    truth_files = sorted(DATA.glob("velo_daily_run_truth_*.md"))
    if not truth_files:
        return {
            "last_truth_date": None,
            "gap_days": None,
            "status": "NO_TRUTH_FILES",
            "detail": "No daily truth watchdog files found",
        }
    last_file = truth_files[-1]
    parts = last_file.stem.replace("velo_daily_run_truth_", "").split("_")
    last_date_str = "-".join(parts) if len(parts) == 3 else None
    gap_days = None
    if last_date_str:
        try:
            last_date = date.fromisoformat(last_date_str)
            gap_days = (date.today() - last_date).days
        except ValueError:
            pass
    status = "OK" if gap_days is not None and gap_days <= 1 else "DATA_GAP_ACTIVE"
    return {
        "last_truth_date": last_date_str,
        "gap_days": gap_days,
        "status": status,
        "detail": (
            f"Last truth file: {last_file.name}. Gap: {gap_days} day(s)."
            if gap_days is not None else "Could not determine gap"
        ),
    }


# ── Report builder ────────────────────────────────────────────────────────────

def build_report() -> dict:
    railway = _check_railway_toml()
    trigger_audit = _check_manual_trigger_pattern()
    ingestion = _check_rp_merged_ingestion()
    data_gap = _check_data_gap()

    # Overall status
    critical_flags = []
    if railway["status"] == "CRON_NOT_REGISTERED":
        critical_flags.append("RAILWAY_CRON_NOT_REGISTERED")
    if trigger_audit["status"] == "AUTOMATION_BROKEN":
        critical_flags.append("AUTOMATION_BROKEN")
    if ingestion["status"] in ("INGESTION_GAP_CRITICAL", "NO_FILES", "DIRECTORY_MISSING"):
        critical_flags.append("PDF_INGESTION_GAP_ACTIVE")
    if data_gap["status"] == "DATA_GAP_ACTIVE":
        critical_flags.append("DATA_GAP_ACTIVE")

    overall = "CRITICAL" if critical_flags else "OK"

    return {
        "report_type": "VELO_CRON_VERIFICATION_REPORT",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "overall_status": overall,
        "critical_flags": critical_flags,
        "sections": {
            "railway_toml": railway,
            "trigger_audit": trigger_audit,
            "rp_merged_ingestion": ingestion,
            "data_gap": data_gap,
        },
        "operator_actions_required": _build_action_list(railway, trigger_audit, ingestion, data_gap),
    }


def _build_action_list(railway, trigger_audit, ingestion, data_gap) -> list[str]:
    actions = []
    if railway["status"] == "CRON_NOT_REGISTERED":
        actions.append(
            "ACTION 1: Re-register Railway cron schedule. "
            f"Expected: cronSchedule = \"{EXPECTED_CRON_SCHEDULE}\" "
            f"Command: {EXPECTED_CRON_COMMAND}. "
            "Requires operator approval — DO NOT change without explicit sign-off."
        )
    if trigger_audit["status"] == "AUTOMATION_BROKEN":
        actions.append(
            "ACTION 2: Investigate why Railway cron is not firing. "
            "Check Railway service logs for the velo-oracle service. "
            "Verify the service is not in sleep/paused state."
        )
    if ingestion["status"] in ("INGESTION_GAP_CRITICAL", "STALE", "NO_FILES"):
        actions.append(
            "ACTION 3: Restore RP PDF ingestion pipeline. "
            "Upload today's 7 Racing Post PDFs to the ingestion_spine incoming/ directory. "
            "Run: python scripts/ops/ingest_racecard_pdfs.py --date TODAY"
        )
    if data_gap["status"] == "DATA_GAP_ACTIVE":
        actions.append(
            f"ACTION 4: Manual recovery required for gap period. "
            f"Last truth date: {data_gap['last_truth_date']}. "
            "Run manual recovery for each missing date once PDFs are available."
        )
    if not actions:
        actions.append("No operator actions required. Automation is healthy.")
    return actions


# ── CLI ───────────────────────────────────────────────────────────────────────

def print_report(report: dict) -> None:
    print("\nVÉLØ CRON VERIFICATION REPORT")
    print("=" * 72)
    print(f"Timestamp : {report['timestamp']}")
    print(f"Status    : {report['overall_status']}")
    if report["critical_flags"]:
        print(f"Flags     : {', '.join(report['critical_flags'])}")
    print()

    s = report["sections"]
    print("Railway Cron:")
    print(f"  {s['railway_toml']['status']}: {s['railway_toml']['detail']}")
    print()
    print("Trigger Audit:")
    ta = s["trigger_audit"]
    print(f"  {ta['status']}: {ta['detail']}")
    print(f"  Manual days: {ta['manual_trigger_days']} / {ta['total_days_audited']} total")
    print(f"  Automation rate: {ta['automation_rate_pct']}%")
    print()
    print("RP Merged Ingestion:")
    ing = s["rp_merged_ingestion"]
    print(f"  {ing['status']}: {ing['detail']}")
    print()
    print("Data Gap:")
    dg = s["data_gap"]
    print(f"  {dg['status']}: {dg['detail']}")
    print()
    print("Operator Actions Required:")
    for action in report["operator_actions_required"]:
        print(f"  {action}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="VÉLØ Cron Verification Report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--save", action="store_true", help="Save report to data/")
    args = parser.parse_args()

    report = build_report()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    if args.save:
        ts = datetime.utcnow().strftime("%Y_%m_%d")
        out = DATA / f"velo_cron_verification_report_{ts}.json"
        DATA.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[OK] Report saved: {out}")

    return 1 if report["overall_status"] == "CRITICAL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
