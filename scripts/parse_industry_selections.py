"""
parse_industry_selections.py
Parses Racing Post F_0010_XX (Selection Box) PDFs for a given date.
Extracts every tipster's pick for every race at each venue.
Outputs: data/industry_selections_YYYYMMDD.json
"""
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

DOWNLOADS = Path("/mnt/c/Users/puror/Downloads")
DATA_DIR  = Path(__file__).parent.parent / "data"

# Venue code → canonical course name (must match sigma/results)
VENUE_MAP = {
    "ASC": "Ascot",         "AYR": "Ayr",           "BAT": "Bath",
    "BEV": "Beverley",      "CAT": "Catterick",      "CHL": "Cheltenham",
    "CHP": "Chepstow",      "CHS": "Chester",        "COR": "Cork",
    "CUR": "Curragh",       "DON": "Doncaster",      "DRO": "Down Royal",
    "DUN": "Dundalk",       "EPS": "Epsom",          "FAI": "Fairyhouse",
    "FAK": "Fakenham",      "FON": "Fontwell",       "GOO": "Goodwood",
    "GOW": "Gowran Park",   "HAY": "Haydock",        "HER": "Hereford",
    "KEL": "Kelso",         "KEM": "Kempton (AW)",   "KLB": "Kilbeggan",
    "LEI": "Leicester",     "LEO": "Leopardstown",   "LIM": "Limerick",
    "LIN": "Lingfield",     "LUD": "Ludlow",         "NAA": "Naas",
    "NAB": "Newton Abbot",  "NAV": "Navan",          "NCS": "Newcastle",
    "NMK": "Newmarket",     "PER": "Perth",          "PON": "Pontefract",
    "PUN": "Punchestown",   "SAN": "Sandown",        "SLI": "Sligo",
    "STH": "Southwell (AW)", "TAU": "Taunton",        "WAR": "Warwick",
    "WDR": "Windsor",      "WIN": "Windsor",        "WEX": "Wexford",
    "WOL": "Wolverhampton","YAR": "Yarmouth",       "RED": "Redcar",
    "HUN": "Huntingdon",   "MUS": "Musselburgh",    "CHE": "Chelmsford (AW)",
    "CHF": "Chelmsford (AW)", "NOT": "Nottingham",  "BRI": "Brighton",
    "SAL": "Salisbury",    "CHT": "Chepstow",       "EXE": "Exeter",
    "WOR": "Worcester",    "PLU": "Plumpton",       "UTT": "Uttoxeter",
    "STR": "Stratford",    "BAN": "Bangor-On-Dee",  "MKT": "Market Rasen",
    "HEX": "Hexham",      "CRL": "Carlisle",
}

TIME_RE  = re.compile(r"^\d{1,2}:\d{2}$")
NAP_SYM  = "★"


def _group_words_by_row(words, y_tol=4):
    """Cluster words into rows by y-position."""
    rows = defaultdict(list)
    for w in words:
        key = round(w["top"] / y_tol) * y_tol
        rows[key].append(w)
    return {y: sorted(ws, key=lambda w: w["x0"]) for y, ws in sorted(rows.items())}


def _find_header_row(rows):
    """Return the row dict that contains the race times."""
    for y, words in rows.items():
        texts = [w["text"] for w in words]
        if sum(1 for t in texts if TIME_RE.match(t)) >= 2:
            return y, words
    return None, None


def _build_columns(header_words):
    """Map race time string → centre x-position."""
    cols = {}
    for w in header_words:
        if TIME_RE.match(w["text"]):
            cx = (w["x0"] + w["x1"]) / 2
            cols[w["text"]] = cx
    return cols  # {time_str: x}


def _assign_word_to_col(word, col_xs):
    """Return closest column time for a word by x-position."""
    wx = (word["x0"] + word["x1"]) / 2
    return min(col_xs, key=lambda t: abs(col_xs[t] - wx))


def _extract_tipster_name(words_before_first_col):
    """Join words to form tipster label."""
    return " ".join(w["text"] for w in words_before_first_col).strip()


def parse_selection_box_page(page, col_xs):
    """
    Parse one page of a selection-box PDF.
    Returns: {tipster_label: {race_time: {"horse": str, "is_nap": bool, "meta": str}}}
    """
    words = page.extract_words(x_tolerance=4, y_tolerance=4)
    rows  = _group_words_by_row(words, y_tol=3)

    min_col_x = min(col_xs.values())
    col_times  = sorted(col_xs.keys(), key=lambda t: col_xs[t])

    results = {}

    for y, row_words in rows.items():
        # Skip header row and title rows
        texts = [w["text"] for w in row_words]
        if any(TIME_RE.match(t) for t in texts):
            continue
        if not texts or texts[0] in ("Page",):
            continue

        # Split into prefix (tipster) vs content words
        prefix_words = [w for w in row_words if w["x1"] < min_col_x - 10]
        content_words = [w for w in row_words if w["x0"] >= min_col_x - 10]

        if not content_words:
            continue

        tipster = _extract_tipster_name(prefix_words)
        if not tipster:
            continue

        # Group content words by their nearest column
        col_buckets = defaultdict(list)
        for w in content_words:
            col = _assign_word_to_col(w, col_xs)
            col_buckets[col].append(w)

        race_picks = {}
        for t, bucket in col_buckets.items():
            horse_parts = []
            meta_parts  = []
            is_nap = False
            for w in sorted(bucket, key=lambda w: w["x0"]):
                txt = w["text"]
                if NAP_SYM in txt:
                    is_nap = True
                    txt = txt.replace(NAP_SYM, "").strip()
                # metadata: plain number, parenthetical, or number+parenth like "1(nb)"
                if re.match(r"^\d{1,2}(\([a-z]+\))?$", txt, re.I):
                    meta_parts.append(txt)
                elif re.match(r"^\([a-z]+\)$", txt, re.I):
                    meta_parts.append(txt)
                elif txt:
                    horse_parts.append(txt)

            horse = " ".join(horse_parts).strip()
            meta  = " ".join(meta_parts).strip()
            if horse:
                race_picks[t] = {"horse": horse, "is_nap": is_nap, "meta": meta}

        if race_picks:
            # Merge if tipster appears on multiple y-rows (multi-line render)
            if tipster in results:
                for t, pick in race_picks.items():
                    if t not in results[tipster]:
                        results[tipster][t] = pick
            else:
                results[tipster] = race_picks

    return results


def parse_selection_box_pdf(pdf_path):
    """
    Parse a single F_0010_XX PDF.
    Returns: (course, date_str, {tipster: {time: {horse, is_nap, meta}}})
    """
    name = Path(pdf_path).stem  # e.g. CHS_20260506_00_00_F_0010_XX_Chester
    parts = name.split("_")
    venue_code = parts[0]
    date_raw   = parts[1]           # YYYYMMDD
    date_str   = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"
    course     = VENUE_MAP.get(venue_code, venue_code)

    all_picks = {}  # tipster → {time → pick}
    col_xs    = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=4, y_tolerance=4)
            rows  = _group_words_by_row(words, y_tol=3)

            header_y, header_words = _find_header_row(rows)
            if header_y is None:
                continue

            page_cols = _build_columns(header_words)
            if not col_xs:
                col_xs = page_cols
            else:
                col_xs.update(page_cols)

            page_picks = parse_selection_box_page(page, page_cols)
            for tipster, picks in page_picks.items():
                if tipster not in all_picks:
                    all_picks[tipster] = {}
                all_picks[tipster].update(picks)

    return course, date_str, col_xs, all_picks


def run(date_str):
    """Parse all F_0010 files for a date and write JSON."""
    date_tag  = date_str.replace("-", "")
    pattern   = f"*_{date_tag}_*F_0010*.pdf"
    repo_ingest = DATA_DIR / "incoming_pdfs" / date_str
    search_roots = [DOWNLOADS, repo_ingest]
    pdf_files = []
    for root in search_roots:
        if root.exists():
            pdf_files = sorted(root.glob(pattern))
            if pdf_files:
                break

    if not pdf_files:
        roots = ", ".join(str(p) for p in search_roots)
        print(f"No F_0010 files found for {date_str} in {roots}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} selection-box files for {date_str}")

    output = {"date": date_str, "venues": []}

    for pdf_path in pdf_files:
        course, d, col_xs, picks = parse_selection_box_pdf(pdf_path)
        race_times = sorted(col_xs.keys(), key=lambda t: (int(t.split(":")[0]), int(t.split(":")[1])))
        print(f"  {course}: {len(race_times)} races, {len(picks)} tipsters")

        venue_block = {
            "course":     course,
            "race_times": race_times,
            "tipsters":   picks,
        }
        output["venues"].append(venue_block)

    out_path = DATA_DIR / f"industry_selections_{date_tag}.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWritten: {out_path}")
    return out_path


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else "2026-05-06"
    run(date_arg)
