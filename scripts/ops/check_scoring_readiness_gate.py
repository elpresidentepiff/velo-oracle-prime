#!/usr/bin/env python3.11
"""
VÉLØ Scoring Readiness Gate
============================
Hard precondition check: NOTHING scores for a race date until both of these
are true:

  1. PASSPORT — New Build's current-card passport feed
     (data/new_build/current_cards/current_card_passport_feed_{date}.jsonl)
     exists and is non-empty for the date.

  2. RP PDF INGESTION — every course racing today has PDF-derived
     enrichment merged into its racecard_merged/racecard_{venue}_{date}.json
     file (postdata_score / plot_conviction / spotlight text present on at
     least one horse). This is the RP ratings-sheet PDF layer the operator
     supplies each morning, distinct from the live RP HTML capture.

Rule origin (2026-07-18): every day the same failure mode repeated --
scoring and the downstream report chain (New Build, Old VELO, Champion
Intent, No-RPR Shadow) ran before the operator's PDFs had landed, which
meant re-running 6+ reports by hand after the fact once PDFs arrived, and
created repeated openings for phantom-race/ID-mismatch bugs. This gate
makes "scoring waited for both inputs" a checked precondition, not a
memory the operator or Claude has to hold every single day.

Exit code 0  = gate PASS, safe to score.
Exit code 1  = gate FAIL, do NOT score. Prints exactly what's missing.

Override (documented, not silent): --allow-missing-pdfs skips check #2 for
the rare day when a venue genuinely never gets PDFs (e.g. int'l-only card).
Passport is never overridable -- if Step 6 didn't run, nothing downstream
can be trusted.
"""

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PDF_ENRICHMENT_FIELDS = ("postdata_score", "plot_conviction", "or_compression_score")


def _venue_files_for_date(date_us: str) -> list[Path]:
    pattern = str(ROOT / "data" / "racecard_merged" / f"racecard_*_{date_us}.json")
    return sorted(Path(p) for p in glob.glob(pattern))


def _pdf_eligible_courses(date_us: str) -> set[str] | None:
    """Course display names RP actually publishes ratings-sheet PDFs for
    (GB/IRE only -- RP does not publish these for USA/other international
    tracks). Returns None if the standard cache can't be read, meaning the
    caller should not exempt anything (fail safe, not fail open)."""
    cache_path = ROOT / "data" / f"racecards_{date_us.replace('-', '_')}_standard.json"
    if not cache_path.exists():
        return None
    try:
        d = json.loads(cache_path.read_text())
    except Exception:
        return None
    races = d if isinstance(d, list) else d.get("racecards", [])
    eligible = set()
    for r in races:
        region = (r.get("region") or r.get("country") or "").upper()
        course = r.get("course")
        if course and region in ("GB", "IRE", "IE", "UK"):
            eligible.add(course)
    return eligible


def check_passport(date_us: str) -> tuple[bool, str]:
    path = ROOT / "data" / "new_build" / "current_cards" / f"current_card_passport_feed_{date_us.replace('-', '_')}.jsonl"
    if not path.exists():
        return False, f"MISSING: {path.name} does not exist (Step 6 New Build current-card feed has not run for {date_us})"
    if path.stat().st_size == 0:
        return False, f"EMPTY: {path.name} exists but has zero rows"
    return True, f"OK: {path.name} present and non-empty"


def check_pdf_ingestion(date_us: str) -> tuple[bool, list[str], list[str]]:
    """Returns (all_ok, ok_venues, missing_venues). Venues RP doesn't publish
    ratings-sheet PDFs for (non-GB/IRE, e.g. USA tracks) are auto-exempted
    via the standard racecard cache's region field -- they never block the
    gate and are not reported as missing."""
    date_hyphen = date_us
    files = _venue_files_for_date(date_hyphen)
    if not files:
        return False, [], ["NO_RACECARD_MERGED_FILES_FOR_DATE"]

    pdf_eligible = _pdf_eligible_courses(date_us)  # None => can't determine, don't exempt anything

    ok_venues: list[str] = []
    missing_venues: list[str] = []
    for f in files:
        venue = f.stem.replace(f"racecard_", "").replace(f"_{date_hyphen}", "")
        try:
            d = json.loads(f.read_text())
        except Exception:
            missing_venues.append(f"{venue} (unreadable file)")
            continue

        display_name = d.get("venue", venue)
        if pdf_eligible is not None and display_name not in pdf_eligible:
            continue  # not a GB/IRE track -- RP never publishes PDFs for it, not a gate blocker

        races = d.get("races", {})
        enriched = False
        for race_data in races.values():
            for h in race_data.get("horses", []):
                if any(h.get(field) for field in PDF_ENRICHMENT_FIELDS):
                    enriched = True
                    break
            if enriched:
                break
        if enriched:
            ok_venues.append(venue)
        else:
            missing_venues.append(venue)

    return (len(missing_venues) == 0), ok_venues, missing_venues


def main() -> int:
    parser = argparse.ArgumentParser(description="VÉLØ Scoring Readiness Gate")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--allow-missing-pdfs", action="store_true",
                         help="Skip the PDF-ingestion check (passport check is never overridable)")
    args = parser.parse_args()

    date_us = args.date  # racecard_merged files are keyed YYYY-MM-DD already
    print(f"\nVÉLØ SCORING READINESS GATE — {args.date}")
    print("=" * 60)

    passport_ok, passport_msg = check_passport(args.date)
    print(f"1. Passport (New Build feed):  {'[OK]  ' if passport_ok else '[FAIL]'} {passport_msg}")

    pdf_ok, ok_venues, missing_venues = check_pdf_ingestion(date_us)
    if args.allow_missing_pdfs:
        print(f"2. PDF ingestion:               [SKIP] --allow-missing-pdfs set "
              f"(ingested: {ok_venues or 'none'}; not ingested: {missing_venues or 'none'})")
        pdf_ok = True
    else:
        status = "[OK]  " if pdf_ok else "[FAIL]"
        print(f"2. PDF ingestion:               {status} ingested: {ok_venues or 'none'}")
        if missing_venues:
            print(f"                                       NOT ingested: {missing_venues}")

    print("=" * 60)
    if passport_ok and pdf_ok:
        print("GATE: PASS -- safe to score.\n")
        return 0

    print("GATE: FAIL -- scoring BLOCKED.")
    if not passport_ok:
        print(f"  -> Run Step 6 (new_build_current_card_feed.py) for {args.date} first.")
    if not pdf_ok:
        print(f"  -> Ingest RP PDFs for: {missing_venues}")
        print("     python scripts/ops/ingest_racecard_pdfs.py --dir <pdf_dir> --venue <CODE> --date "
              f"{args.date}")
        print("  -> Or, if these venues genuinely have no PDFs today, rerun with --allow-missing-pdfs.")
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
