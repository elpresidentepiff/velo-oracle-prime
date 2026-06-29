#!/usr/bin/env python3
"""
Old VELO RP Newspaper File Gate
===============================

Hard source contract:
  - Old VELO must ingest the five Racing Post Newspaper Form engine files.
  - F_0010_XX selection-box files are competitor intelligence only and are
    never staged into the Old VELO engine directory by this script.
  - If any expected venue is missing any required file, the script exits
    non-zero before scoring can run.

Typical use:
  python scripts/ops/ensure_old_velo_rp_newspaper_files.py --date 2026-06-25 --execute
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

REQUIRED_KEYS = {
    "0011_XX": "Postdata grid",
    "0012_XX": "Colour racecard",
    "0015_OR": "Official ratings/history",
    "0016_XX": "Spotlight comments",
    "0032_TS": "Topspeed ratings",
}

EXCLUDED_KEYS = {
    "0010_XX": "Selection box / competitor consensus",
}

PDF_RE = re.compile(
    r"^(?P<venue>[A-Z]{2,4})_(?P<date>\d{8})_\d{2}_\d{2}_F_"
    r"(?P<code>\d{4})_(?P<label>[A-Z]{2})_(?P<name>.+)\.pdf$",
    re.IGNORECASE,
)


def _date_tag(date_str: str) -> str:
    return date_str.replace("-", "")


def _json_date_tag(date_str: str) -> str:
    return date_str.replace("-", "_")


def classify_rp_pdf(path: Path) -> dict[str, str] | None:
    match = PDF_RE.match(path.name)
    if not match:
        return None
    code = match.group("code").upper()
    label = match.group("label").upper()
    key = f"{code}_{label}"
    if code == "0015" and label != "OR":
        key = f"{code}_{label}"
    return {
        "venue": match.group("venue").upper(),
        "date": match.group("date"),
        "code": code,
        "label": label,
        "key": key,
        "course_name": match.group("name").replace("_", " "),
    }


def infer_expected_venues(date_str: str) -> list[str]:
    """Infer expected venue codes from committed/runtime race-day artifacts."""
    venues: set[str] = set()
    date_tag = _json_date_tag(date_str)

    for path in (DATA / "racecard_merged").glob(f"racecard_*_{date_str}.json"):
        parts = path.stem.split("_")
        if len(parts) >= 2:
            venues.add(parts[1].upper())

    cache = DATA / f"racecards_{date_tag}_standard.json"
    if cache.exists():
        try:
            raw = json.loads(cache.read_text(encoding="utf-8"))
            races = raw if isinstance(raw, list) else raw.get("racecards", [])
            for race in races:
                course_id = race.get("course_id") or race.get("courseCode") or race.get("course_code")
                if course_id and str(course_id).isalpha() and len(str(course_id)) <= 4:
                    venues.add(str(course_id).upper())
        except Exception:
            pass

    url_list = DATA / "racing_post_url_lists" / f"rp_racecards_{date_str}.txt"
    if url_list.exists():
        for line in url_list.read_text(encoding="utf-8", errors="ignore").splitlines():
            # URL form contains /racecards/{course_id}/... in some captures.
            m = re.search(r"/racecards/([a-z]{2,4})/", line, re.IGNORECASE)
            if m:
                venues.add(m.group(1).upper())

    return sorted(venues)


def iter_candidate_pdfs(search_dirs: list[Path], compact_date: str) -> list[Path]:
    seen: set[Path] = set()
    found: list[Path] = []
    for directory in search_dirs:
        if not directory.exists():
            continue
        # Downloads is usually flat; incoming_pdfs may be date-subfoldered.
        iterator = directory.rglob(f"*{compact_date}*.pdf")
        for path in iterator:
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append(path)
    return sorted(found, key=lambda p: str(p).lower())


def copy_to_stage(src: Path, stage_dir: Path) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    dest = stage_dir / src.name
    if dest.exists():
        try:
            if dest.stat().st_size == src.stat().st_size:
                return dest
        except OSError:
            pass
    shutil.copy2(src, dest)
    return dest


def write_reports(date_str: str, report: dict[str, Any]) -> None:
    out_dir = DATA / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    token = _json_date_tag(date_str)
    json_path = out_dir / f"old_velo_rp_newspaper_file_gate_{token}.json"
    md_path = out_dir / f"old_velo_rp_newspaper_file_gate_{token}.md"
    latest_json = out_dir / "old_velo_rp_newspaper_file_gate_latest.json"
    latest_md = out_dir / "old_velo_rp_newspaper_file_gate_latest.md"

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    json_path.write_text(payload + "\n", encoding="utf-8")
    latest_json.write_text(payload + "\n", encoding="utf-8")

    lines = [
        f"# Old VELO RP Newspaper File Gate - {date_str}",
        "",
        f"Status: **{report['status']}**",
        f"Stage dir: `{report['stage_dir']}`",
        "",
        "## Required Engine Files",
        "",
    ]
    for key, label in REQUIRED_KEYS.items():
        lines.append(f"- `{key}` - {label}")
    lines.extend(["", "## Excluded", ""])
    for key, label in EXCLUDED_KEYS.items():
        lines.append(f"- `{key}` - {label}")
    lines.extend(["", "## Venues", ""])
    for venue, info in report["venues"].items():
        lines.append(f"### {venue}")
        lines.append(f"Complete: `{info['complete']}`")
        if info["missing"]:
            lines.append(f"Missing: `{', '.join(info['missing'])}`")
        if info["staged"]:
            lines.append("Staged:")
            for key, path in sorted(info["staged"].items()):
                lines.append(f"- `{key}` -> `{path}`")
        lines.append("")
    if report.get("blocked_reason"):
        lines.extend(["## Blocked Reason", "", report["blocked_reason"], ""])
    md = "\n".join(lines)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")


def run_ingestion(date_str: str, venues: list[str], stage_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for venue in venues:
        cmd = [
            sys.executable,
            "scripts/ops/ingest_racecard_pdfs.py",
            "--dir",
            str(stage_dir),
            "--venue",
            venue,
            "--date",
            date_str,
        ]
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        results.append(
            {
                "venue": venue,
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-4000:],
                "stderr_tail": proc.stderr[-4000:],
            }
        )
        if proc.returncode != 0:
            raise RuntimeError(f"PDF ingestion failed for {venue}: {proc.stderr or proc.stdout}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure Old VELO has the five RP newspaper-form files before scoring.")
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    parser.add_argument("--venues", nargs="*", help="Venue codes. If omitted, infer from race-day artifacts.")
    parser.add_argument(
        "--search-dir",
        action="append",
        type=Path,
        default=[],
        help="Directory to search recursively for RP PDFs. Can be passed more than once.",
    )
    parser.add_argument(
        "--stage-dir",
        type=Path,
        help="Directory to stage engine PDFs. Defaults to data/incoming_pdfs/YYYY-MM-DD",
    )
    parser.add_argument("--execute", action="store_true", help="Copy files and run PDF ingestion.")
    parser.add_argument("--no-ingest", action="store_true", help="Copy/verify only; do not run PDF ingestion.")
    args = parser.parse_args()

    compact_date = _date_tag(args.date)
    expected_venues = sorted({v.upper() for v in (args.venues or infer_expected_venues(args.date))})
    stage_dir = args.stage_dir or (DATA / "incoming_pdfs" / args.date)

    search_dirs = args.search_dir or [
        Path.home() / "Downloads",
        DATA / "incoming_pdfs",
        DATA / "incoming_pdfs" / args.date,
    ]

    report: dict[str, Any] = {
        "schema_version": "old_velo_rp_newspaper_file_gate_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "date": args.date,
        "status": "PENDING",
        "execute": args.execute,
        "required_keys": REQUIRED_KEYS,
        "excluded_keys": EXCLUDED_KEYS,
        "expected_venues": expected_venues,
        "search_dirs": [str(p) for p in search_dirs],
        "stage_dir": str(stage_dir),
        "venues": {},
        "excluded_files_seen": [],
        "ingestion_results": [],
        "blocked_reason": None,
    }

    if not expected_venues:
        report["status"] = "BLOCKED"
        report["blocked_reason"] = "Could not infer expected venues. Run racecard capture/parse first or pass --venues."
        write_reports(args.date, report)
        print(report["blocked_reason"], file=sys.stderr)
        return 2

    by_venue: dict[str, dict[str, Path]] = {venue: {} for venue in expected_venues}
    for pdf in iter_candidate_pdfs(search_dirs, compact_date):
        info = classify_rp_pdf(pdf)
        if not info or info["date"] != compact_date:
            continue
        venue = info["venue"]
        key = info["key"]
        if key in EXCLUDED_KEYS:
            report["excluded_files_seen"].append(str(pdf))
            continue
        if venue not in by_venue:
            continue
        if key in REQUIRED_KEYS and key not in by_venue[venue]:
            by_venue[venue][key] = pdf

    complete_venues: list[str] = []
    for venue in expected_venues:
        staged: dict[str, str] = {}
        missing = [key for key in REQUIRED_KEYS if key not in by_venue[venue]]
        if not missing and args.execute:
            for key, src in sorted(by_venue[venue].items()):
                staged[key] = str(copy_to_stage(src, stage_dir))
        elif not missing:
            staged = {key: str(path) for key, path in sorted(by_venue[venue].items())}

        complete = not missing
        if complete:
            complete_venues.append(venue)
        report["venues"][venue] = {
            "complete": complete,
            "missing": missing,
            "found": {key: str(path) for key, path in sorted(by_venue[venue].items())},
            "staged": staged,
        }

    incomplete = [v for v, info in report["venues"].items() if not info["complete"]]
    if incomplete:
        report["status"] = "BLOCKED"
        report["blocked_reason"] = (
            "Missing required RP Newspaper Form engine PDFs for: "
            + ", ".join(incomplete)
            + ". Old VELO scoring must not run from injection fallback."
        )
        write_reports(args.date, report)
        print(report["blocked_reason"], file=sys.stderr)
        return 3

    if args.execute and not args.no_ingest:
        try:
            report["ingestion_results"] = run_ingestion(args.date, complete_venues, stage_dir)
        except Exception as exc:
            report["status"] = "BLOCKED"
            report["blocked_reason"] = str(exc)
            write_reports(args.date, report)
            print(str(exc), file=sys.stderr)
            return 4

    report["status"] = "PASS"
    write_reports(args.date, report)
    print(f"PASS: staged {len(complete_venues)} venue(s) for {args.date} and excluded F_0010.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
