#!/usr/bin/env python3.11
"""
VÉLØ Spotlight PDF Ingestion Pipeline
======================================
Parses Racing Post Spotlight PDFs (F_0016_XX files), extracts per-horse
comments, runs the full 15-flag NLP parser, and writes enriched signals
to Supabase `horse_comments` table.

Usage:
    # Single PDF
    python scripts/ingest_spotlight_pdf.py --pdf data/incoming_pdfs/PON_20260421_00_00_F_0016_XX_Pontefract.pdf

    # All PDFs in incoming directory
    python scripts/ingest_spotlight_pdf.py --dir data/incoming_pdfs/

    # Dry run (parse only, no DB write)
    python scripts/ingest_spotlight_pdf.py --pdf path/to/file.pdf --dry-run

Environment:
    SUPABASE_URL          (required for DB write)
    SUPABASE_SERVICE_KEY  (required for DB write)
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, date
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("velo.spotlight_pdf")

# ── CONSTANTS ────────────────────────────────────────────────────────────────

# Racing Post Spotlight PDF filename pattern:
# COURSE_YYYYMMDD_00_00_F_0016_XX_CourseName.pdf
SPOTLIGHT_FILE_PATTERN = re.compile(
    r"^([A-Z]{2,4})_(\d{8})_\d{2}_\d{2}_F_0016_XX_(.+)\.pdf$"
)

# Race header pattern in Spotlight PDFs
# Matches: "1.42 Racing TV Sky Channel 424 EBF Restricted Novice Stakes"
RACE_HEADER_PATTERN = re.compile(
    r"^(\d{1,2}\.\d{2})\s+(.+?)(?:\s+£[\d,]+.*?(?:RTV|SIS|ATR|ITV)?\s+(\d+f\d*y?|\d+m\d*f?\d*y?))",
    re.MULTILINE,
)

# Simpler race time pattern for splitting
RACE_TIME_PATTERN = re.compile(r"^(\d{1,2}\.\d{2})\s", re.MULTILINE)

# Runner line pattern: "Horse Name 2 9-7 Trainer Jockey SP OR TS RPR"
# or the comment block that follows
RUNNER_HEADER_PATTERN = re.compile(
    r"^([A-Z][A-Za-z\s\'\-\(\)]+?)\s+(\d+)\s+(\d{1,2}-\d{1,2})\s+(.+?)$",
    re.MULTILINE,
)

# Spotlight verdict pattern
VERDICT_PATTERN = re.compile(
    r"SPOTLIGHT\s+VERDICT\s+(.*?)(?=\n\d{1,2}\.\d{2}\s|\Z)",
    re.DOTALL | re.IGNORECASE,
)


# ── PDF EXTRACTION ───────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF using pdfplumber."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def parse_metadata_from_filename(filename: str) -> dict | None:
    """Extract course code, date, and course name from filename."""
    match = SPOTLIGHT_FILE_PATTERN.match(filename)
    if not match:
        return None
    return {
        "course_code": match.group(1),
        "race_date": match.group(2),  # YYYYMMDD
        "course_name": match.group(3),
    }


def split_into_races(full_text: str) -> list[dict]:
    """
    Split full PDF text into per-race blocks.
    Returns list of {off_time, race_name, text_block}.
    """
    # Find all race time positions
    time_matches = list(RACE_TIME_PATTERN.finditer(full_text))
    if not time_matches:
        log.warning("No race headers found in PDF text")
        return []

    races = []
    for i, match in enumerate(time_matches):
        off_time = match.group(1)
        start = match.start()
        end = time_matches[i + 1].start() if i + 1 < len(time_matches) else len(full_text)
        block = full_text[start:end]

        # Extract race name (first line after time)
        first_line = block.split("\n")[0] if block else ""

        races.append({
            "off_time": off_time,
            "race_header": first_line.strip(),
            "text_block": block,
        })

    return races


def extract_horse_comments(race_block: str) -> list[dict]:
    """
    Extract per-horse spotlight comments from a race block.

    The Spotlight PDF format is:
        Horse Name  Age  Weight  Trainer  Jockey  SP  OR  TS  RPR
        Comment text spanning one or more lines...

    Returns list of {horse_name, comment, sp, or_rating, ts, rpr}.
    """
    lines = race_block.split("\n")
    horses = []
    current_horse = None
    comment_lines = []

    # Skip the first few lines (race header, conditions, column headers)
    # Find where "Trainer Jockey SP OR TS RPR" header line is
    start_idx = 0
    for i, line in enumerate(lines):
        if "Trainer" in line and "Jockey" in line and "SP" in line:
            start_idx = i + 1
            break

    # State machine: detect horse header lines vs comment continuation
    for i in range(start_idx, len(lines)):
        line = lines[i].strip()
        if not line:
            continue

        # Check for SPOTLIGHT VERDICT (end of runners)
        if "SPOTLIGHT VERDICT" in line.upper():
            # Save current horse
            if current_horse and comment_lines:
                current_horse["comment"] = " ".join(comment_lines).strip()
                horses.append(current_horse)
            # Extract verdict
            verdict_text = line
            # Collect remaining verdict lines
            for j in range(i + 1, len(lines)):
                vl = lines[j].strip()
                if not vl:
                    continue
                verdict_text += " " + vl
            horses.append({
                "horse_name": "__VERDICT__",
                "comment": verdict_text.strip(),
            })
            break

        # Try to match a runner header line
        # Pattern: "Horse Name  Age  Weight  Trainer  Jockey  SP  OR  TS  RPR"
        # The horse name is typically in mixed case, followed by age (single digit),
        # weight (N-N), trainer name, jockey name, and ratings
        runner_match = re.match(
            r"^([A-Z][A-Za-z\s\'\-\(\)]+?)\s+(\d+)\s+(\d{1,2}-\d{1,2})\s+(.+)$",
            line,
        )

        if runner_match:
            # Save previous horse
            if current_horse and comment_lines:
                current_horse["comment"] = " ".join(comment_lines).strip()
                horses.append(current_horse)

            horse_name = runner_match.group(1).strip()
            age = runner_match.group(2)
            weight = runner_match.group(3)
            rest = runner_match.group(4)

            # Extract SP and ratings from the rest
            sp_match = re.search(r"(\d+/\d+|\d+-\d+|evens?|Evs)", rest)
            or_match = re.search(r"(\d+)\s+(\d+|-)\s+(\d+|-)\s*$", rest)

            current_horse = {
                "horse_name": horse_name,
                "age": int(age) if age else None,
                "weight": weight,
                "sp_forecast": sp_match.group(1) if sp_match else None,
            }

            if or_match:
                or_val = or_match.group(1)
                ts_val = or_match.group(2)
                rpr_val = or_match.group(3)
                current_horse["or_rating"] = int(or_val) if or_val != "-" else None
                current_horse["ts"] = int(ts_val) if ts_val != "-" else None
                current_horse["rpr"] = int(rpr_val) if rpr_val != "-" else None

            comment_lines = []
        else:
            # This is a comment continuation line
            comment_lines.append(line)

    # Don't forget the last horse
    if current_horse and comment_lines:
        current_horse["comment"] = " ".join(comment_lines).strip()
        horses.append(current_horse)

    return horses


# ── NLP ENRICHMENT ───────────────────────────────────────────────────────────

def enrich_with_spotlight_parser(
    horse_name: str, comment: str,
    race_id: str = "", race_date: str = "",
) -> dict:
    """
    Run the full 15-flag spotlight NLP parser on a comment.
    Falls back to basic sentiment if the parser fails.
    """
    try:
        from workers.spotlight_parser import extract_spotlight_signals
        from datetime import date as _date
        # Parse race_date string to date object
        if isinstance(race_date, str) and race_date:
            rd = _date.fromisoformat(race_date)
        else:
            rd = _date.today()
        return extract_spotlight_signals(
            raw_text=comment,
            horse_name=horse_name,
            race_id=race_id,
            race_date=rd,
            source="pdf_spotlight",
        )
    except ImportError as exc:
        log.warning(f"spotlight_parser not available ({exc}), using basic sentiment")
        return _basic_sentiment(comment)
    except Exception as exc:
        log.error(f"spotlight_parser failed for {horse_name}: {exc}")
        return _basic_sentiment(comment)


def _basic_sentiment(comment: str) -> dict:
    """Fallback basic sentiment when full parser unavailable."""
    text_lower = comment.lower()
    positive = [
        "eye-catching", "unlucky", "progressive", "well handicapped",
        "open to improvement", "unexposed", "course specialist",
        "trainer in form", "yard in form",
    ]
    negative = [
        "needs to improve", "well held", "out of depth", "struggling",
        "tailed off", "weakened", "faded",
    ]
    pos = sum(1 for p in positive if p in text_lower)
    neg = sum(1 for p in negative if p in text_lower)
    return {
        "sentiment_score": pos - neg,
        "flag_intent_today": False,
        "flag_excuse_last": False,
        "raw_comment": comment[:500],
    }


# ── SUPABASE WRITE ───────────────────────────────────────────────────────────

def write_to_supabase(records: list[dict], race_date: str) -> bool:
    """Write enriched spotlight records to Supabase horse_comments table."""
    import requests

    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not service_key:
        log.error("SUPABASE_URL or SUPABASE_SERVICE_KEY not set")
        return False

    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    rows = []
    for rec in records:
        if rec.get("horse_name") == "__VERDICT__":
            continue  # Skip race verdict records

        nlp = rec.get("nlp_signals", {})
        rows.append({
            "race_id": rec.get("race_id", ""),
            "horse_name": rec["horse_name"],
            "horse_id": rec.get("horse_id", ""),
            "comment_raw": rec.get("comment", "")[:1000],
            "spotlight_flags": {
                k.replace("flag_", ""): v
                for k, v in nlp.items()
                if k.startswith("flag_")
            },
            "sentiment_score": nlp.get("sentiment_score", 0),
            "race_date": race_date,
            "source": "pdf_spotlight",
            "day_type_push": nlp.get("day_type_push", "NEUTRAL"),
        })

    if not rows:
        log.info("No rows to write")
        return True

    url = f"{supabase_url}/rest/v1/horse_comments"
    try:
        resp = requests.post(url, headers=headers, json=rows, timeout=15)
        if resp.status_code in (200, 201, 204):
            log.info(f"Wrote {len(rows)} spotlight records to Supabase")
            return True
        else:
            log.error(f"Supabase write failed: {resp.status_code} {resp.text[:300]}")
            return False
    except Exception as exc:
        log.error(f"Supabase write exception: {exc}")
        return False


# ── MAIN PIPELINE ────────────────────────────────────────────────────────────

def process_spotlight_pdf(pdf_path: str, dry_run: bool = False) -> dict:
    """
    Full pipeline: PDF → text → per-horse comments → NLP → Supabase.

    Returns summary dict with counts and any errors.
    """
    pdf_path = Path(pdf_path)
    filename = pdf_path.name
    log.info(f"Processing: {filename}")

    # 1. Parse metadata from filename
    meta = parse_metadata_from_filename(filename)
    if meta:
        course = meta["course_name"]
        race_date_str = meta["race_date"]
        race_date = f"{race_date_str[:4]}-{race_date_str[4:6]}-{race_date_str[6:8]}"
        log.info(f"  Course: {course}  Date: {race_date}")
    else:
        log.warning(f"  Could not parse filename metadata, using defaults")
        course = "UNKNOWN"
        race_date = date.today().isoformat()

    # 2. Extract text
    full_text = extract_text_from_pdf(str(pdf_path))
    if not full_text:
        return {"status": "FAIL", "error": "No text extracted from PDF"}

    log.info(f"  Extracted {len(full_text)} chars from {len(full_text.splitlines())} lines")

    # 3. Split into races
    races = split_into_races(full_text)
    log.info(f"  Found {len(races)} races")

    # 4. Extract per-horse comments and run NLP
    all_records = []
    for race in races:
        off_time = race["off_time"]
        race_id = f"{race_date}_{course}_{off_time.replace('.', '')}"
        log.info(f"  Race {off_time}: {race['race_header'][:60]}")

        horses = extract_horse_comments(race["text_block"])
        log.info(f"    Extracted {len(horses)} entries (incl. verdict)")

        for horse in horses:
            comment = horse.get("comment", "")
            if not comment or len(comment) < 10:
                continue

            # Run NLP
            nlp_signals = enrich_with_spotlight_parser(
                horse["horse_name"], comment,
                race_id=race_id, race_date=race_date,
            )

            record = {
                **horse,
                "race_id": race_id,
                "off_time": off_time,
                "course": course,
                "race_date": race_date,
                "nlp_signals": nlp_signals,
            }
            all_records.append(record)

    log.info(f"  Total enriched records: {len(all_records)}")

    # 5. Write to Supabase (unless dry run)
    if dry_run:
        log.info("  DRY RUN — skipping Supabase write")
        # Print summary
        for rec in all_records:
            nlp = rec.get("nlp_signals", {})
            sentiment = nlp.get("sentiment_score", 0)
            flags = [k for k, v in nlp.items() if k.startswith("flag_") and v]
            horse = rec["horse_name"]
            log.info(
                f"    {horse:<25s}  sentiment={sentiment:+d}  "
                f"flags=[{', '.join(flags)}]"
            )
    else:
        write_to_supabase(all_records, race_date)

    # 6. Save JSON output for audit
    output_dir = ROOT / "data" / "spotlight_parsed"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"spotlight_{course}_{race_date}.json"

    # Make records JSON-serializable
    serializable = []
    for rec in all_records:
        s = {k: v for k, v in rec.items() if k != "nlp_signals"}
        s["nlp_signals"] = rec.get("nlp_signals", {})
        serializable.append(s)

    with open(output_file, "w") as f:
        json.dump(serializable, f, indent=2, default=str)
    log.info(f"  Saved parsed output to {output_file}")

    return {
        "status": "OK",
        "course": course,
        "race_date": race_date,
        "races": len(races),
        "horses": len([r for r in all_records if r["horse_name"] != "__VERDICT__"]),
        "verdicts": len([r for r in all_records if r["horse_name"] == "__VERDICT__"]),
        "output_file": str(output_file),
    }


def main():
    parser = argparse.ArgumentParser(description="VÉLØ Spotlight PDF Ingestion")
    parser.add_argument("--pdf", help="Path to a single Spotlight PDF")
    parser.add_argument("--dir", help="Directory containing Spotlight PDFs")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no DB write")
    args = parser.parse_args()

    if not args.pdf and not args.dir:
        # Default: process all F_0016 PDFs in incoming_pdfs
        args.dir = str(ROOT / "data" / "incoming_pdfs")

    results = []

    if args.pdf:
        result = process_spotlight_pdf(args.pdf, dry_run=args.dry_run)
        results.append(result)
    elif args.dir:
        pdf_dir = Path(args.dir)
        spotlight_pdfs = sorted(pdf_dir.glob("*_F_0016_XX_*.pdf"))
        if not spotlight_pdfs:
            log.warning(f"No F_0016 Spotlight PDFs found in {pdf_dir}")
            return

        log.info(f"Found {len(spotlight_pdfs)} Spotlight PDFs")
        for pdf_file in spotlight_pdfs:
            result = process_spotlight_pdf(str(pdf_file), dry_run=args.dry_run)
            results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("  SPOTLIGHT PDF INGESTION SUMMARY")
    print("=" * 60)
    for r in results:
        status = r.get("status", "?")
        course = r.get("course", "?")
        horses = r.get("horses", 0)
        races = r.get("races", 0)
        print(f"  {status:6s}  {course:<20s}  {races} races  {horses} horses")
    print("=" * 60)


if __name__ == "__main__":
    main()
