"""
Auto-ingest RP ratings-sheet PDFs from the operator's inbox folder.

Closes the last manual step in the morning pipeline. Before this (2026-07-30),
the 07:00 scheduled run always self-blocked at the scoring readiness gate
because the six RP sheets per venue (F_0010/0011/0012 spotlight-family,
F_0015_OR, F_0016, F_0032_TS) were only ever copied and ingested by hand —
confirmed on 2026-07-24, 07-25 and 07-30. The operator already downloads them
into a single OneDrive folder with venue+date encoded in every filename, so
this step discovers, stages and ingests them with no human action.

Filename contract (as produced by RP's download):
    {VENUE}_{YYYYMMDD}_00_00_F_{SHEET}_{TYPE}_{CourseName}.pdf
e.g. GOO_20260730_00_00_F_0015_OR_Goodwood.pdf  ->  venue GOO

Inbox path: VELO_PDF_INBOX env var, else the known OneDrive folder.

This step never blocks the day: missing or partial PDFs simply mean fewer
venues ingested, and `check_scoring_readiness_gate.py` remains the single
enforcer of whether scoring may proceed. Ingestion merges into existing
racecard_merged files, preserving real race_id/horse_id.

Usage:
    PYTHONPATH=. python scripts/ops/auto_ingest_pdf_inbox.py --date YYYY-MM-DD --execute
    PYTHONPATH=. python scripts/ops/auto_ingest_pdf_inbox.py --date YYYY-MM-DD   # dry run
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

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INBOX = Path("/mnt/c/Users/puror/OneDrive/Documents/horses for courses")
FILENAME_RE = re.compile(r"^(?P<venue>[A-Z]{3})_(?P<ymd>\d{8})_.*\.pdf$", re.IGNORECASE)


def discover(inbox: Path, date_str: str) -> dict[str, list[Path]]:
    """{VENUE: [pdf paths]} for the given date, from the inbox folder."""
    ymd = date_str.replace("-", "")
    found: dict[str, list[Path]] = {}
    if not inbox.is_dir():
        return found
    for pdf in sorted(inbox.glob("*.pdf")):
        m = FILENAME_RE.match(pdf.name)
        if not m or m.group("ymd") != ymd:
            continue
        found.setdefault(m.group("venue").upper(), []).append(pdf)
    return found


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--execute", action="store_true", help="Copy and ingest (omit for dry run)")
    p.add_argument("--inbox", type=Path, default=None, help="Override inbox folder")
    args = p.parse_args()

    import os

    inbox = args.inbox or Path(os.getenv("VELO_PDF_INBOX", str(DEFAULT_INBOX)))
    date_str = args.date
    tag = date_str.replace("-", "_")
    stage_dir = ROOT / "data" / "incoming_pdfs" / date_str

    print(f"AUTO PDF INGEST — {date_str}")
    print(f"  inbox: {inbox}")
    if not inbox.is_dir():
        print("  [WARN] inbox folder not found — nothing to ingest. "
              "Set VELO_PDF_INBOX if the folder moved.")
        return 0

    by_venue = discover(inbox, date_str)
    if not by_venue:
        print(f"  no PDFs for {date_str} in inbox yet — scoring readiness gate will "
              "block until they arrive (expected if sheets are not downloaded yet).")
        return 0

    total = sum(len(v) for v in by_venue.values())
    print(f"  found {total} PDFs across {len(by_venue)} venues: {', '.join(sorted(by_venue))}")
    if not args.execute:
        for venue, files in sorted(by_venue.items()):
            print(f"    [DRY] {venue}: {len(files)} sheets")
        print("  [DRY RUN] pass --execute to stage and ingest")
        return 0

    stage_dir.mkdir(parents=True, exist_ok=True)
    staged = 0
    for files in by_venue.values():
        for src in files:
            dst = stage_dir / src.name
            if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                shutil.copy2(src, dst)
            staged += 1
    print(f"  staged {staged} PDFs -> {stage_dir.relative_to(ROOT)}")

    ingested, failed = [], []
    for venue in sorted(by_venue):
        cmd = [
            sys.executable, "scripts/ops/ingest_racecard_pdfs.py",
            "--dir", str(stage_dir), "--venue", venue, "--date", date_str,
        ]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode == 0:
            ingested.append(venue)
            tail = [ln for ln in r.stdout.splitlines() if "TOTAL:" in ln]
            print(f"  [OK]   {venue}: {tail[0].strip() if tail else 'ingested'}")
        else:
            failed.append(venue)
            print(f"  [FAIL] {venue}: {(r.stderr or r.stdout).strip().splitlines()[-1][:160]}")

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "date": date_str,
        "inbox": str(inbox),
        "pdfs_found": total,
        "venues_found": sorted(by_venue),
        "venues_ingested": ingested,
        "venues_failed": failed,
    }
    out = ROOT / "data" / "reports" / f"auto_pdf_ingest_{tag}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  ingested={len(ingested)} failed={len(failed)} -> {out.relative_to(ROOT)}")
    # Never fail the day: the readiness gate decides whether scoring proceeds.
    return 0


if __name__ == "__main__":
    sys.exit(main())
