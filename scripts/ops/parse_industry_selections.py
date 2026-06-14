#!/usr/bin/env python3
"""
parse_industry_selections.py
-----------------------------
Parses Racing Post F_0010_XX tipster selection PDF files and produces
data/industry_selections_YYYYMMDD.json for use by build_industry_comparison.py.

Handles one or more F_0010 PDFs for a given date (one per venue).

Usage:
    # Parse all F_0010 PDFs for a date from incoming_pdfs/
    source venv/bin/activate
    PYTHONPATH=. python scripts/ops/parse_industry_selections.py --date 2026-05-20

    # Parse specific PDF files
    PYTHONPATH=. python scripts/ops/parse_industry_selections.py --date 2026-05-20 \\
        --pdfs data/incoming_pdfs/AYR_20260520_00_00_F_0010_XX_Ayr.pdf

Output: data/industry_selections_YYYYMMDD.json
"""
import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PDF_DIR  = DATA_DIR / "incoming_pdfs"

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber required — pip install pdfplumber")
    sys.exit(1)

# Canonical tipster names (match what build_industry_comparison.py expects)
TIPSTER_ALIASES = {
    "SPOTLIGHT": "SPOTLIGHT",
    "RP RATINGS (PAUL CURTIS)": "RP RATINGS (Paul Curtis)",
    "RP RATINGS (AINSLEY SCORAH)": "RP RATINGS (Ainsley Scorah)",
    "TOPSPEED": "TOPSPEED",
    "POSTDATA": "POSTDATA",
    "THE TIMES (ROB WRIGHT)": "THE TIMES (Rob Wright)",
    "TELEGRAPH (MARLBOROUGH)": "TELEGRAPH (Marlborough)",
    "THE GUARDIAN": "THE GUARDIAN",
    "DAILY MAIL (ROBIN GOODFELLOW)": "DAILY MAIL (Robin Goodfellow)",
    "DAILY MIRROR (NEWSBOY)": "DAILY MIRROR (Newsboy)",
    "D EXPRESS (MELISSA JONES)": "D EXPRESS (Melissa Jones)",
    "THE SUN (TEMPLEGATE)": "THE SUN (Templegate)",
    "THE STAR (JASON HEAVEY)": "THE STAR (Jason Heavey)",
    "DAILY RECORD (GARRY OWEN)": "DAILY RECORD (Garry Owen)",
    "LAMBOURN (LIAM HEADD)": "LAMBOURN (Liam Headd)",
    "NEWMARKET (DAVID MILNES)": "NEWMARKET (David Milnes)",
    "WEST COUNTRY (LIAM WATSON)": "WEST COUNTRY (Liam Watson)",
    "THE NORTH (COLIN RUSSELL)": "THE NORTH (Colin Russell)",
    "THE IRISH SUN": "THE IRISH SUN",
}

# Tipster name prefixes for recognition (match start of concatenated row text)
TIPSTER_PREFIXES = [
    "SPOTLIGHT",
    "RP RATINGS",
    "TOPSPEED",
    "POSTDATA",
    "THE TIMES",
    "TELEGRAPH",
    "THE GUARDIAN",
    "DAILY MAIL",
    "DAILY MIRROR",
    "D EXPRESS",
    "THE SUN",
    "THE STAR",
    "DAILY RECORD",
    "LAMBOURN",
    "NEWMARKET",
    "WEST COUNTRY",
    "THE NORTH",
    "THE IRISH SUN",
]

_TIPSTER_PREFIXES_SORTED = sorted(TIPSTER_PREFIXES, key=len, reverse=True)

# Y-tolerance: words within this many points are on the same row
Y_TOL = 3.0
# X threshold: words below this x are tipster label, above are picks
TIPSTER_X_THRESH = 130.0
# Column tolerance: word belongs to a race column if col_x <= word.x0 + COL_TOL
# Small value — column must start at or before word position (5px for PDF rounding)
COL_TOL = 5.0


def _normalise_time(t: str) -> str:
    """Convert '1:42' or '13:42' to 'H:MM' normalised."""
    t = t.strip()
    if re.fullmatch(r"\d:\d{2}", t):
        return t
    if re.fullmatch(r"\d{1,2}:\d{2}", t):
        h, m = t.split(":")
        return f"{int(h)}:{m}"
    return t


def _is_time_token(text: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}:\d{2}", text.strip()))


def _is_draw_token(text: str) -> bool:
    """Single digit or digit+★ = draw number."""
    return bool(re.fullmatch(r"\d{1,2}[★]?|[★]\d{0,2}", text.strip()))


def _has_nap(text: str) -> bool:
    return "★" in text or "(tb)" in text.lower()


def _clean_horse(text: str) -> str:
    """Remove draw numbers, ★, (nb), (tb), trailing/leading space."""
    t = re.sub(r"\s+\d{1,2}[★]?$", "", text)   # trailing number
    t = re.sub(r"\s+[★]$", "", t)               # trailing ★
    t = re.sub(r"\([nt]b\)", "", t, flags=re.I)  # (nb) (tb)
    t = re.sub(r"[★]", "", t)                    # inline ★
    return t.strip()


def _group_words_by_row(words: list) -> list:
    """Group words into rows by proximity of `top` y coordinate."""
    if not words:
        return []
    rows = []
    current_row = [words[0]]
    for w in words[1:]:
        if abs(w["top"] - current_row[-1]["top"]) <= Y_TOL:
            current_row.append(w)
        else:
            rows.append(current_row)
            current_row = [w]
    rows.append(current_row)
    return rows


def _extract_tipster_name(label_words: list) -> str:
    """Reconstruct tipster name from left-side label words."""
    text = " ".join(w["text"] for w in label_words).upper().strip()
    # Remove trailing punctuation artefacts
    text = re.sub(r"[:\-]+$", "", text).strip()
    # Map to canonical
    if text in TIPSTER_ALIASES:
        return TIPSTER_ALIASES[text]
    # Fuzzy: starts-with matching
    for prefix in _TIPSTER_PREFIXES_SORTED:
        if text.startswith(prefix):
            canonical_upper = text
            if canonical_upper in TIPSTER_ALIASES:
                return TIPSTER_ALIASES[canonical_upper]
            # Fallback: reconstruct from mixed case
            for k, v in TIPSTER_ALIASES.items():
                if k.startswith(prefix) and text.startswith(prefix):
                    return v
    return text.title()


def _assign_to_columns(pick_words: list, col_xs: list) -> dict:
    """
    Assign pick words to race columns based on x position.
    Returns {col_idx: [words]}
    """
    buckets = {i: [] for i in range(len(col_xs))}
    for w in pick_words:
        # Find the rightmost column start that is <= word x0
        col_idx = None
        for i, cx in enumerate(col_xs):
            if w["x0"] >= cx - COL_TOL:
                col_idx = i
        if col_idx is not None:
            buckets[col_idx].append(w)
    return buckets


def _build_pick(bucket_words: list) -> dict:
    """Build a pick dict from words in a single race column cell."""
    if not bucket_words:
        return {}
    parts = []
    is_nap = False
    meta_parts = []
    for w in sorted(bucket_words, key=lambda x: x["x0"]):
        text = w["text"]
        if _has_nap(text):
            is_nap = True
        if _is_draw_token(text):
            meta_parts.append(re.sub(r"[★]", "", text))
            continue
        clean = re.sub(r"[★]", "", text)
        clean = re.sub(r"\([nt]b\)", "", clean, flags=re.I).strip()
        if clean:
            parts.append(clean)
    horse = " ".join(parts).strip()
    if not horse:
        return {}
    return {
        "horse": horse,
        "is_nap": is_nap,
        "meta": " ".join(meta_parts),
    }


def parse_f0010_pdf(pdf_path: Path) -> dict | None:
    """
    Parse one F_0010_XX selection PDF.
    Returns venue dict: {course, race_times, tipsters} or None on failure.
    """
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            # Collect words from all pages
            all_words = []
            for page in pdf.pages:
                all_words.extend(page.extract_words())
    except Exception as e:
        print(f"  [ERROR] Cannot open {pdf_path.name}: {e}")
        return None

    if not all_words:
        print(f"  [WARN] No words in {pdf_path.name}")
        return None

    rows = _group_words_by_row(all_words)

    # --- Step 1: Find venue name and race times row ---
    course_name = ""
    times_row_idx = -1
    col_xs = []
    times = []

    for ridx, row in enumerate(rows):
        row_text = " ".join(w["text"] for w in row)
        # Look for "SELECTION BOX" header to get venue
        if "SELECTION" in row_text.upper() and "BOX" in row_text.upper():
            parts = row_text.upper().replace("SELECTION BOX", "").strip()
            if parts:
                course_name = parts.title()
            continue
        # Look for the times row: majority of words match H:MM
        time_words = [w for w in row if _is_time_token(w["text"])]
        if len(time_words) >= 2:
            times_row_idx = ridx
            times = [_normalise_time(w["text"]) for w in time_words]
            col_xs = [w["x0"] for w in time_words]
            break

    if not times:
        print(f"  [WARN] No race times found in {pdf_path.name}")
        return None

    # Try to get course from filename if not found in PDF
    if not course_name:
        m = re.search(r"F_0010_XX_(.+)\.pdf", pdf_path.name, re.IGNORECASE)
        if m:
            course_name = m.group(1).replace("_", " ").title()

    # --- Step 2: Parse tipster rows ---
    tipsters: dict[str, dict] = {}

    # Accumulate multi-row tipster state
    current_tipster = None
    current_cells: dict[int, list] = {}

    def _flush_tipster():
        nonlocal current_tipster, current_cells
        if current_tipster and current_cells:
            picks = {}
            for col_idx, words in current_cells.items():
                if words:
                    p = _build_pick(words)
                    if p:
                        picks[times[col_idx]] = p
            if picks:
                if current_tipster not in tipsters:
                    tipsters[current_tipster] = {}
                tipsters[current_tipster].update(picks)
        current_tipster = None
        current_cells = {}

    for ridx in range(times_row_idx + 1, len(rows)):
        row = rows[ridx]
        if not row:
            continue

        # Split into label (left) and pick (right) words
        label_words = [w for w in row if w["x0"] < TIPSTER_X_THRESH]
        pick_words  = [w for w in row if w["x0"] >= TIPSTER_X_THRESH]

        # Check if this row starts a new tipster (has label words)
        if label_words:
            label_text = " ".join(w["text"] for w in label_words).upper()
            is_new_tipster = any(label_text.startswith(p) for p in _TIPSTER_PREFIXES_SORTED)
            if is_new_tipster:
                _flush_tipster()
                current_tipster = _extract_tipster_name(label_words)
                current_cells = _assign_to_columns(pick_words, col_xs)
                continue

        # Continuation row (no label, or label not a tipster)
        if current_tipster and pick_words:
            extra = _assign_to_columns(pick_words, col_xs)
            for col_idx, words in extra.items():
                current_cells.setdefault(col_idx, []).extend(words)

    _flush_tipster()

    return {
        "course": course_name,
        "race_times": times,
        "tipsters": tipsters,
    }


def find_f0010_pdfs(date_str: str) -> list[Path]:
    """Find all F_0010 PDFs in incoming_pdfs (and subdirectories) for the given date."""
    date_tag = date_str.replace("-", "")
    found = []
    for f in PDF_DIR.rglob("*.pdf"):
        if date_tag in f.name and "F_0010" in f.name.upper():
            found.append(f)
    return sorted(found)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="Date YYYY-MM-DD")
    ap.add_argument("--pdfs", nargs="*", help="Specific PDF paths (optional, auto-discovered if omitted)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    date_str = args.date
    date_tag  = date_str.replace("-", "")

    if args.pdfs:
        pdf_paths = [Path(p) for p in args.pdfs]
    else:
        pdf_paths = find_f0010_pdfs(date_str)

    if not pdf_paths:
        print(f"No F_0010 PDFs found for {date_str} in {PDF_DIR}")
        print("Expected filename format: VEN_YYYYMMDD_HH_MM_F_0010_XX_VenueName.pdf")
        sys.exit(1)

    print(f"Parsing {len(pdf_paths)} F_0010 PDF(s) for {date_str}:")
    venues = []
    for p in pdf_paths:
        print(f"  {p.name}")
        venue = parse_f0010_pdf(p)
        if venue:
            print(f"    → {venue['course']}: {len(venue['race_times'])} races, {len(venue['tipsters'])} tipsters")
            venues.append(venue)
        else:
            print(f"    → FAILED")

    if not venues:
        print("No venues parsed. Exiting.")
        sys.exit(1)

    output = {
        "date": date_str,
        "venues": venues,
    }

    out_path = DATA_DIR / f"industry_selections_{date_tag}.json"
    if args.dry_run:
        print(f"\n[DRY RUN] Would write: {out_path}")
        print(json.dumps(output, indent=2)[:2000])
    else:
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        print(f"\nSaved: {out_path}")
        total_races = sum(len(v["race_times"]) for v in venues)
        print(f"Venues: {len(venues)} | Races: {total_races}")


if __name__ == "__main__":
    main()
