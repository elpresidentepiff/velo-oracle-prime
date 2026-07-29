#!/usr/bin/env python3
"""
Merge Racing Post PDF intelligence (OR/TS/Spotlight/Postdata) into the
injection-based racecard_merged files, without losing the real race_id.

Why this exists:
  build_racecard_merged_from_injection.py writes data/racecard_merged/racecard_{VENUE}_{date}.json
  with the real numeric race_id from the live RP HTML capture, but PDF-derived
  fields (postdata_score, or_compression_score, plot_conviction, ...) are left
  at 0.0 placeholders because that script has no PDF access.

  ingest_racecard_pdfs.py computes those same fields for real from the operator's
  PDFs, but writes to the SAME output path with its own from-scratch race dict
  that has no race_id at all (races are keyed by time only). Running it after
  build_racecard_merged_from_injection.py silently destroys the real race_id;
  running it before gets overwritten by the next build_racecard_merged_from_injection.py
  run. Neither script merges into the other's output.

  This script parses the PDFs (via ingest_racecard_pdfs.py's own parser
  functions) and splices only the PDF-derived per-horse fields into the
  injection-based file, matched by horse name, leaving race_id/race_info/
  runner membership untouched.

Usage:
  python scripts/ops/merge_pdf_intel_into_racecard_merged.py --dir data/incoming_pdfs/ --venue AYR --date 2026-07-05 --execute
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

import sys
sys.path.insert(0, str(ROOT))

from scripts.ops.ingest_racecard_pdfs import (  # noqa: E402
    find_pdfs_in_dir,
    parse_or_pdf,
    parse_ts_pdf,
    parse_spotlight_pdf,
    merge_race_data,
)
from workers.postdata_parser import parse_postdata_pdf  # noqa: E402

# Fields computed from PDFs that should overlay onto the injection-based horse dict.
# Deliberately excludes race_id, horse_id, and any field the injection already owns.
PDF_DERIVED_FIELDS = [
    "postdata_score", "or_compression_score", "plot_conviction",
    "handicap_plot_score", "trainer_form_signal", "ts_trend_signal",
    "or_trend_signal", "or_delta_to_best_win", "or_delta_to_lowest_win",
    "at_winning_mark", "near_winning_mark", "or_compression",
    "or_run_history", "ts_run_history", "ts_distance", "ts_class_going_hd",
    "ts_good", "ts_soft_heavy", "ts_6_11m", "ts_base", "ts_trend",
    "spotlight_sentiment", "is_postdata_pick", "is_topspeed_pick",
    "best_winning_12m", "best_winning_ssn", "best_winning_life",
    "highest_entered_12m", "highest_entered_ssn", "highest_entered_life",
    "lowest_win_ssn", "lowest_win_life",
]


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _to_off_time_key(time_str: str) -> str:
    """Normalise 'HH:MM' or 'H.MM' style times to the dot-format key used by
    both racecard_merged files (e.g. '14:25' -> '2.25')."""
    m = re.match(r"^(\d{1,2}):(\d{2})$", (time_str or "").strip())
    if not m:
        return (time_str or "").strip()
    hour = int(m.group(1))
    if hour > 12:
        hour -= 12
    return f"{hour}.{m.group(2)}"


def merge_pdf_intel(pdf_dir: Path, venue: str, date: str, execute: bool) -> dict:
    merged_path = ROOT / "data" / "racecard_merged" / f"racecard_{venue.upper()}_{date}.json"
    if not merged_path.exists():
        return {"status": "FAIL", "error": f"racecard_merged file not found: {merged_path}"}

    racecard = json.loads(merged_path.read_text(encoding="utf-8"))

    pdfs = find_pdfs_in_dir(pdf_dir, venue, date)
    or_data = parse_or_pdf(pdfs["or"]) if pdfs["or"] else {}
    ts_data = parse_ts_pdf(pdfs["ts"]) if pdfs["ts"] else {}
    spotlight_data = parse_spotlight_pdf(pdfs["spotlight"]) if pdfs["spotlight"] else {}
    postdata_data = parse_postdata_pdf(pdfs["postdata"]) if pdfs["postdata"] else {}

    pdf_merged = merge_race_data(or_data, ts_data, spotlight_data, postdata_data=postdata_data)

    # Build a name -> pdf horse dict per race_time key from the PDF side.
    attached = 0
    total = 0
    races_matched = 0
    races_unmatched = []

    for off_key, race in racecard.get("races", {}).items():
        pdf_race = pdf_merged.get(off_key)
        if not pdf_race:
            races_unmatched.append(off_key)
            continue
        races_matched += 1
        pdf_by_name = {_norm_name(h.get("horse_name", "")): h for h in pdf_race.get("horses", [])}
        for horse in race.get("horses", []):
            total += 1
            key = _norm_name(horse.get("horse_name", ""))
            pdf_h = pdf_by_name.get(key)
            if not pdf_h:
                continue
            for field in PDF_DERIVED_FIELDS:
                if field in pdf_h and pdf_h[field] not in (None, ""):
                    horse[field] = pdf_h[field]
            attached += 1

    result = {
        "status": "PASS",
        "venue": venue.upper(),
        "date": date,
        "merged_path": str(merged_path),
        "races_total": len(racecard.get("races", {})),
        "races_matched_to_pdf": races_matched,
        "races_unmatched": races_unmatched,
        "horses_total": total,
        "horses_pdf_attached": attached,
        "coverage_pct": round(attached / total * 100, 1) if total else 0.0,
        "execute": execute,
    }

    if execute:
        merged_path.write_text(json.dumps(racecard, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge PDF intel into injection-based racecard_merged files.")
    parser.add_argument("--dir", type=Path, required=True, help="Directory containing PDFs")
    parser.add_argument("--venue", required=True, help="Venue code (e.g. AYR)")
    parser.add_argument("--date", required=True, help="Race date (YYYY-MM-DD)")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    result = merge_pdf_intel(args.dir, args.venue, args.date, args.execute)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
