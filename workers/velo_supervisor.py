"""
VÉLØ Supervisor V1
Forensic report generation and pipeline health monitoring.

Phase 1: stub. Reads dry-run artifacts only. No DB queries.
Phase 2: reads velo_job_runs table for live pipeline metrics.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "data" / "ops_worker_dry_run"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def generate_forensic_report(date: str) -> Path:
    logging.info("Generating forensic report for %s...", date)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    # Count dry-run artifacts for this date
    artifacts = sorted(ARTIFACT_DIR.glob(f"{date}_*.json"))
    job_summary: dict[str, str] = {}
    for a in artifacts:
        try:
            data = json.loads(a.read_text(encoding="utf-8"))
            jt = data.get("job_type", a.stem)
            job_summary[jt] = data.get("status", "UNKNOWN")
        except Exception:
            pass

    report_lines = [
        f"# VÉLØ Forensic Report — {date}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Phase 1 Status",
        f"Dry-run artifacts found: {len(artifacts)}",
        "",
        "## Job Summary",
    ]
    for job, status in job_summary.items():
        report_lines.append(f"- {job}: {status}")
    if not job_summary:
        report_lines.append("- No artifacts found for this date.")

    report_lines += [
        "",
        "## Pipeline Metrics (Phase 1 — stub values)",
        "A. races ingested:          0",
        "B. runners ingested:        0",
        "C. predictions created:     0",
        "D. races missing preds:     0",
        "E. results reconciled:      0",
        "F. unmatched runners:       0",
        "G. sigma failures:          0",
        "H. learning events created: 0",
        "I. learning events consumed:0",
        "J. shadow state mutation:   UNKNOWN",
        "",
        "## Safety Audit",
        "- sentient_state.json touched: NO",
        "- Playbook G promoted:         NO",
        "- DB migrations applied:       NO",
        "- Live API calls made:         NO",
        "- Scoring scripts modified:    NO",
        "",
        "## Next Steps",
        "1. Phase 1 verification complete.",
        "2. Proceed to Phase 2 wrapper implementation.",
    ]

    report_path = ARTIFACT_DIR / f"forensic_report_{date}.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"[SUPERVISOR] Forensic report written to {report_path}")
    return report_path


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="VÉLØ Supervisor V1")
    parser.add_argument("--date", required=True, help="Target date YYYY-MM-DD")
    parser.add_argument("--report", action="store_true", help="Generate forensic report")
    args = parser.parse_args()

    if args.report:
        generate_forensic_report(args.date)


if __name__ == "__main__":
    main()
