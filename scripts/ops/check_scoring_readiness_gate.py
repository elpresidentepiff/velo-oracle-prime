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
import os
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


def check_passport_coverage(date_us: str) -> tuple[bool, dict]:
    """PHASE D (2026-08-02) — report what fraction of today's runners actually
    have a passport, and WARN when it is low.

    Why this exists
    ---------------
    check_passport() above only asks "does the feed file exist and have rows".
    That check passed every single day while real coverage sat at 45-63%,
    because a feed row is emitted for every runner whether or not a passport
    was found for it. On 2026-08-02: 256 rows, 116 with a passport (45.3%),
    and 79 of the 140 missing horses held an official rating -- meaning they
    have raced, they are not newcomers, and their history simply was not in
    the bank.

    The passport bank (data/new_build/passports/horse_passports_v1.jsonl) is
    refreshed by run_full_raceday_eod.py Step 21 (wired 2026-08-02). Before
    that it was only ever rebuilt by hand, and had been frozen since
    2026-07-29 12:54. Nothing reported the decay because nothing measured
    coverage -- only presence.

    This WARNS and never blocks: per operator ruling, a degraded day must
    still score and still learn. Returns (meets_threshold, stats).

    GB/IRE is what the threshold judges
    -----------------------------------
    The bank is built from Racing Post UK/IRE horse-profile scrapes, so
    international runners structurally cannot have one. On 2026-08-02 that was
    64 runners across Deauville, Dusseldorf and Saratoga, dragging the headline
    from 52.6% (GB/IRE) to 45.3% (all). Thresholding on the blended figure
    would mean the warning could never clear no matter how well Step 21 works,
    which would make it noise. Both numbers are reported; the threshold judges
    the GB/IRE one. Region comes from the same per-race region data
    _pdf_eligible_courses() uses -- not a hand-maintained course list. If that
    cache is unreadable the split is unavailable and the threshold falls back
    to all-courses, which is stated in the output rather than assumed.
    """
    path = ROOT / "data" / "new_build" / "current_cards" / f"current_card_passport_feed_{date_us.replace('-', '_')}.jsonl"
    stats: dict = {
        "path": path.name, "total": 0, "found": 0, "coverage": 0.0,
        "gbire_total": 0, "gbire_found": 0, "gbire_coverage": 0.0,
        "missing": 0, "missing_with_official_rating": 0,
        "threshold": _coverage_threshold(), "worst_courses": [],
        "region_split_available": False,
    }
    if not path.exists():
        stats["error"] = "FEED_MISSING"
        return False, stats

    gbire_courses = _pdf_eligible_courses(date_us)  # None => cannot determine region
    stats["region_split_available"] = gbire_courses is not None

    per_course: dict[str, list[int]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            stats["total"] += 1
            found = bool(row.get("passport_found"))
            course = str(row.get("course") or "UNKNOWN")
            is_gbire = gbire_courses is not None and course in gbire_courses
            if is_gbire:
                stats["gbire_total"] += 1
                stats["gbire_found"] += 1 if found else 0
            # Only GB/IRE courses are scored on coverage; international courses
            # are still counted in the headline but never in worst_courses,
            # where they would crowd out the gaps that are actually fixable.
            if gbire_courses is None or is_gbire:
                seen, hit = per_course.setdefault(course, [0, 0])
                per_course[course] = [seen + 1, hit + (1 if found else 0)]
            if found:
                stats["found"] += 1
            else:
                stats["missing"] += 1
                # An official rating is only ever assigned to a horse that has
                # already run. A missing passport on such a horse is a bank gap,
                # not a genuine newcomer.
                if row.get("official_rating"):
                    stats["missing_with_official_rating"] += 1

    if stats["total"]:
        stats["coverage"] = round(stats["found"] / stats["total"], 4)
    if stats["gbire_total"]:
        stats["gbire_coverage"] = round(stats["gbire_found"] / stats["gbire_total"], 4)
    stats["worst_courses"] = sorted(
        ({"course": c, "runners": n, "with_passport": h, "coverage": round(h / n, 3)}
         for c, (n, h) in per_course.items() if n),
        key=lambda d: d["coverage"],
    )[:5]

    judged = stats["gbire_coverage"] if stats["gbire_total"] else stats["coverage"]
    stats["judged_coverage"] = judged
    stats["judged_on"] = "GB/IRE" if stats["gbire_total"] else "all courses"
    return (judged >= stats["threshold"]), stats


def _coverage_threshold() -> float:
    """Warn below this. Default 0.70: coverage has run 45-63% for the ten days
    to 2026-08-02, so this warns loudly today and falls silent once the Step 21
    refresh loop has actually raised it. Override for a one-off with
    VELO_PASSPORT_COVERAGE_MIN."""
    raw = os.environ.get("VELO_PASSPORT_COVERAGE_MIN", "").strip()
    if raw:
        try:
            return max(0.0, min(1.0, float(raw)))
        except ValueError:
            pass
    return 0.70


def format_coverage_line(stats: dict) -> list[str]:
    """Shared renderer so the gate CLI and run_full_raceday.py print the same
    thing -- a number, every day, whether it is good or bad."""
    if stats.get("error") == "FEED_MISSING":
        return [f"WARN  coverage unmeasurable — {stats['path']} not found"]
    judged = stats.get("judged_coverage", stats["coverage"])
    ok = judged >= stats["threshold"]
    lines = [
        f"{'OK   ' if ok else 'WARN '}"
        f"{stats['found']}/{stats['total']} runners have a passport "
        f"({stats['coverage']*100:.1f}% all courses)"
    ]
    if stats["gbire_total"]:
        lines.append(
            f"         GB/IRE {stats['gbire_found']}/{stats['gbire_total']} "
            f"({stats['gbire_coverage']*100:.1f}%) — threshold "
            f"{stats['threshold']*100:.0f}%, judged on {stats['judged_on']}"
        )
    elif not stats["region_split_available"]:
        lines.append(
            f"         region split unavailable (no standard racecard cache) — "
            f"judged on all courses, threshold {stats['threshold']*100:.0f}%"
        )
    if not ok:
        lines.append(
            f"         {stats['missing']} missing, of which "
            f"{stats['missing_with_official_rating']} hold an official rating "
            f"(they have raced — this is a bank gap, not newcomers)."
        )
        worst = ", ".join(f"{d['course']} {d['with_passport']}/{d['runners']}"
                          for d in stats["worst_courses"][:3])
        if worst:
            lines.append(f"         Worst: {worst}")
        lines.append(
            "         Scoring PROCEEDS (warn-only). The bank is refreshed by "
            "run_full_raceday_eod.py Step 21."
        )
    return lines


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

    # PHASE D — coverage is reported every day, warn-only, never a blocker.
    cov_ok, cov_stats = check_passport_coverage(args.date)
    for i, line in enumerate(format_coverage_line(cov_stats)):
        print(f"1b. Passport coverage:         {line}" if i == 0 else f"    {line}")

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
