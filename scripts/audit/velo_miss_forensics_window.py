from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from velo_miss_forensics import analyse_day


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def daterange(start: str, end: str) -> list[str]:
    cursor = date.fromisoformat(start)
    limit = date.fromisoformat(end)
    out: list[str] = []
    while cursor <= limit:
        out.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return out


def build_window(start: str, end: str) -> dict:
    days = []
    overall_causes = Counter()
    overall_flags = Counter()
    total_misses = 0
    total_trusted_failures = 0

    for day in daterange(start, end):
        report = analyse_day(day)
        if report.get("status") != "OK":
            continue
        summary = report["summary"]
        total_misses += summary["miss_count"]
        total_trusted_failures += summary["trusted_failures"]
        overall_causes.update(summary["primary_causes"])
        overall_flags.update(summary["flags"])
        top_cause = None
        if summary["primary_causes"]:
            top_cause = max(summary["primary_causes"].items(), key=lambda item: item[1])[0]
        days.append(
            {
                "date": day,
                "miss_count": summary["miss_count"],
                "trusted_failures": summary["trusted_failures"],
                "trusted_failure_rate": summary["trusted_failure_rate"],
                "top_cause": top_cause,
                "primary_causes": summary["primary_causes"],
                "top_misses": report["misses"][:5],
            }
        )

    return {
        "window": {"start": start, "end": end},
        "days": days,
        "summary": {
            "days_covered": len(days),
            "total_misses": total_misses,
            "total_trusted_failures": total_trusted_failures,
            "trusted_failure_rate": round((total_trusted_failures / total_misses) * 100, 2) if total_misses else 0.0,
            "primary_causes": dict(overall_causes),
            "flags": dict(overall_flags),
        },
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# VÉLØ Daily Close Board — Miss Forensics Window",
        "",
        f"- window: `{report['window']['start']} -> {report['window']['end']}`",
        f"- days_covered: `{report['summary']['days_covered']}`",
        f"- total_misses: `{report['summary']['total_misses']}`",
        f"- total_trusted_failures: `{report['summary']['total_trusted_failures']}`",
        f"- trusted_failure_rate: `{report['summary']['trusted_failure_rate']}%`",
        "",
        "## Primary Causes",
        "",
    ]
    for cause, count in sorted(report["summary"]["primary_causes"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{cause}`: `{count}`")
    lines.extend(
        [
            "",
            "## By Day",
            "",
            "| Date | Misses | Trusted Failures | Trusted Failure Rate | Top Cause |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for day in report["days"]:
        lines.append(
            f"| {day['date']} | {day['miss_count']} | {day['trusted_failures']} | "
            f"{day['trusted_failure_rate']:.2f}% | {day['top_cause'] or 'n/a'} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Windowed VÉLØ miss-forensics close board.")
    parser.add_argument("--start", default="2026-04-29")
    parser.add_argument("--end", default="2026-05-10")
    parser.add_argument("--output-prefix", default="velo_daily_close_board_latest")
    args = parser.parse_args()

    report = build_window(args.start, args.end)
    json_path = DATA / f"{args.output_prefix}.json"
    md_path = DATA / f"{args.output_prefix}.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"json_path": str(json_path), "md_path": str(md_path), "days": report["summary"]["days_covered"]}, indent=2))


if __name__ == "__main__":
    main()
