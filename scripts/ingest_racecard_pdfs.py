#!/usr/bin/env python3.11
"""
VÉLØ Unified Racecard PDF Ingestion Pipeline
=============================================
Parses three Racing Post PDF types and merges them into a single per-horse
intelligence record:

  F_0015_OR  — Official Ratings (OR, best winning OR, highest entered, lowest win, RPR)
  F_0032_TS  — Top Speed ratings (latest TS, distance/course/going best, master TS)
  F_0016_XX  — Spotlight comments (free-text per horse, NLP flags, sentiment)

Usage:
  # Process all PDFs for a venue/date in a directory
  python scripts/ingest_racecard_pdfs.py --dir data/incoming_pdfs/ --venue PON --date 2026-04-21

  # Process individual files
  python scripts/ingest_racecard_pdfs.py --or data/incoming_pdfs/PON_..._OR_*.pdf \\
                                          --ts data/incoming_pdfs/PON_..._TS_*.pdf \\
                                          --spotlight data/incoming_pdfs/PON_..._XX_*.pdf

  # Dry run (no Supabase write)
  python scripts/ingest_racecard_pdfs.py --dir data/incoming_pdfs/ --venue PON --date 2026-04-21 --dry-run
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber required. pip install pdfplumber")
    sys.exit(1)


# ─── Filename Pattern ────────────────────────────────────────────────────────
# e.g. PON_20260421_00_00_F_0015_OR_Pontefract.pdf
FILENAME_RE = re.compile(
    r"(?P<code>[A-Z]{3})_(?P<date>\d{8})_\d+_\d+_F_(?P<ftype>\d{4})_(?P<label>[A-Z]{2})_(?P<venue>.+)\.pdf",
    re.IGNORECASE,
)


def classify_pdf(path: Path) -> dict:
    """Classify a PDF by its filename pattern."""
    m = FILENAME_RE.match(path.name)
    if not m:
        return {"type": "unknown", "path": path}
    label = m.group("label").upper()
    ftype = m.group("ftype")
    if label == "OR" or ftype == "0015":
        pdf_type = "or"
    elif label == "TS" or ftype == "0032":
        pdf_type = "ts"
    elif label == "XX" or ftype == "0016":
        pdf_type = "spotlight"
    else:
        pdf_type = "unknown"
    return {
        "type": pdf_type,
        "code": m.group("code"),
        "date": m.group("date"),
        "venue": m.group("venue"),
        "path": path,
    }


# ─── OR Parser ───────────────────────────────────────────────────────────────

def _parse_or_value(val: str) -> int | None:
    """Parse an OR/RPR value, stripping whitespace and non-numeric chars."""
    if not val or not val.strip():
        return None
    cleaned = re.sub(r"[^\d]", "", val.strip())
    return int(cleaned) if cleaned else None


def parse_or_pdf(path: Path) -> dict:
    """
    Parse Official Ratings PDF.
    Returns dict keyed by race_time -> list of horse dicts.
    """
    races = {}
    current_race = None

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or not any(row):
                        continue

                    # Detect race header: first cell has time like "1.42"
                    first = (row[0] or "").strip()
                    if re.match(r"^\d+\.\d{2}$", first):
                        current_race = first
                        races[current_race] = {
                            "race_info": (row[1] or "").strip().split("\n")[0] if row[1] else "",
                            "horses": [],
                        }
                        continue

                    if not current_race:
                        continue

                    # Find horse name — it's in the column that has text (usually col 9)
                    horse_name = None
                    horse_col = -1
                    for ci, cell in enumerate(row):
                        val = (cell or "").strip()
                        # Horse names are alphabetic with spaces, not numbers
                        if val and re.match(r"^[A-Z][a-z]", val) and len(val) > 2:
                            horse_name = val
                            horse_col = ci
                            break

                    if not horse_name:
                        continue

                    # Parse weight and OR from the column after horse name
                    wgt_or_str = (row[horse_col + 1] or "").strip() if horse_col + 1 < len(row) else ""
                    wgt = None
                    current_or = None
                    future_or = None

                    # Format: "9-7" or "9-7 59" or "9-10 91"
                    wgt_match = re.match(r"(\d+-\d+)\s*(\d*)\s*(-?\d*)", wgt_or_str)
                    if wgt_match:
                        wgt = wgt_match.group(1)
                        if wgt_match.group(2):
                            current_or = int(wgt_match.group(2))
                        if wgt_match.group(3) and wgt_match.group(3).lstrip("-").isdigit():
                            future_or = int(wgt_match.group(3))

                    # Parse remaining columns for best winning, highest entered, lowest win, RPR
                    # Columns after wgt/or: best_win_12m, best_win_ssn, best_win_life,
                    #                       high_ent_12m, high_ent_ssn, high_ent_life,
                    #                       low_win_ssn, low_win_life, rpr_master
                    remaining = row[horse_col + 2:] if horse_col + 2 < len(row) else []

                    # Clean and parse numeric values
                    vals = [_parse_or_value(v) for v in remaining]

                    # Map to fields based on position
                    horse_data = {
                        "horse_name": horse_name,
                        "weight": wgt,
                        "current_or": current_or,
                        "future_or": future_or,
                        "best_winning_12m": vals[0] if len(vals) > 0 else None,
                        "best_winning_ssn": vals[1] if len(vals) > 1 else None,
                        "best_winning_life": vals[2] if len(vals) > 2 else None,
                        "highest_entered_12m": vals[3] if len(vals) > 3 else None,
                        "highest_entered_ssn": vals[4] if len(vals) > 4 else None,
                        "highest_entered_life": vals[5] if len(vals) > 5 else None,
                        "lowest_win_ssn": vals[6] if len(vals) > 6 else None,
                        "lowest_win_life": vals[7] if len(vals) > 7 else None,
                        "rpr_master": vals[-1] if vals and vals[-1] else None,
                    }

                    # Compute handicap plot signals
                    if current_or and horse_data["best_winning_life"]:
                        horse_data["or_delta_to_best_win"] = current_or - horse_data["best_winning_life"]
                    else:
                        horse_data["or_delta_to_best_win"] = None

                    if current_or and horse_data["lowest_win_life"]:
                        horse_data["or_delta_to_lowest_win"] = current_or - horse_data["lowest_win_life"]
                    else:
                        horse_data["or_delta_to_lowest_win"] = None

                    # Plot flag: at or below best winning mark
                    if horse_data["or_delta_to_best_win"] is not None:
                        horse_data["at_winning_mark"] = horse_data["or_delta_to_best_win"] <= 0
                        horse_data["near_winning_mark"] = horse_data["or_delta_to_best_win"] <= 3
                    else:
                        horse_data["at_winning_mark"] = None
                        horse_data["near_winning_mark"] = None

                    # OR compression: how far has OR dropped from highest entered
                    if current_or and horse_data["highest_entered_life"]:
                        horse_data["or_compression"] = horse_data["highest_entered_life"] - current_or
                    else:
                        horse_data["or_compression"] = None

                    races[current_race]["horses"].append(horse_data)

    return races


# ─── TS Parser ───────────────────────────────────────────────────────────────

def parse_ts_pdf(path: Path) -> dict:
    """
    Parse Top Speed Ratings PDF.
    Returns dict keyed by race_time -> list of horse dicts.
    """
    races = {}
    current_race = None

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or not any(row):
                        continue

                    first = (row[0] or "").strip()
                    if re.match(r"^\d+\.\d{2}$", first):
                        current_race = first
                        races[current_race] = {
                            "race_info": (row[1] or "").strip().split("\n")[0] if row[1] else "",
                            "horses": [],
                        }
                        continue

                    if not current_race:
                        continue

                    # Find horse name
                    horse_name = None
                    horse_col = -1
                    for ci, cell in enumerate(row):
                        val = (cell or "").strip()
                        if val and re.match(r"^[A-Z][a-z]", val) and len(val) > 2:
                            horse_name = val
                            horse_col = ci
                            break

                    if not horse_name:
                        continue

                    # Parse Wgt OR from next column
                    wgt_or_str = (row[horse_col + 1] or "").strip() if horse_col + 1 < len(row) else ""
                    wgt = None
                    current_or = None

                    wgt_match = re.match(r"(\d+-\d+)\s*(\d*)", wgt_or_str)
                    if wgt_match:
                        wgt = wgt_match.group(1)
                        if wgt_match.group(2):
                            current_or = int(wgt_match.group(2))

                    # Remaining columns: future, Ltst, Dist, Crs, Cls+Gf-Hd, G, Gs-Hv, 6-11m, Base, Master
                    remaining = row[horse_col + 2:] if horse_col + 2 < len(row) else []
                    vals = [_parse_or_value(v) for v in remaining]

                    horse_data = {
                        "horse_name": horse_name,
                        "weight": wgt,
                        "current_or": current_or,
                        "ts_latest": vals[0] if len(vals) > 0 else None,
                        "ts_distance": vals[1] if len(vals) > 1 else None,
                        "ts_course": vals[2] if len(vals) > 2 else None,
                        "ts_class_going_hd": vals[3] if len(vals) > 3 else None,
                        "ts_good": vals[4] if len(vals) > 4 else None,
                        "ts_soft_heavy": vals[5] if len(vals) > 5 else None,
                        "ts_6_11m": vals[6] if len(vals) > 6 else None,
                        "ts_base": vals[7] if len(vals) > 7 else None,
                        "ts_master": vals[-1] if vals and vals[-1] else None,
                    }

                    # Compute TS signals
                    if horse_data["ts_latest"] and horse_data["ts_master"]:
                        horse_data["ts_trend"] = horse_data["ts_latest"] - horse_data["ts_master"]
                    else:
                        horse_data["ts_trend"] = None

                    # TS at course/distance vs master — does horse have proven speed here?
                    if horse_data["ts_course"] and horse_data["ts_master"]:
                        horse_data["ts_course_pct"] = round(
                            horse_data["ts_course"] / horse_data["ts_master"] * 100, 1
                        )
                    else:
                        horse_data["ts_course_pct"] = None

                    races[current_race]["horses"].append(horse_data)

    return races


# ─── Spotlight Parser ────────────────────────────────────────────────────────

def parse_spotlight_pdf(path: Path) -> dict:
    """
    Parse Spotlight PDF using the existing ingest_spotlight_pdf logic.
    Returns dict keyed by race_time -> list of horse dicts.
    """
    races = {}

    with pdfplumber.open(str(path)) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    # Split by race headers (time pattern like "1.42" at start of line)
    race_blocks = re.split(r"(?m)^(\d+\.\d{2})\s+", full_text)

    i = 1
    while i < len(race_blocks) - 1:
        race_time = race_blocks[i].strip()
        block = race_blocks[i + 1]
        i += 2

        races[race_time] = {"horses": []}

        # Extract horse comments — pattern: HORSE NAME (trainer) comment text
        # Or: HORSE NAME comment text
        # The spotlight has horse names in bold/caps followed by their comment
        lines = block.split("\n")
        current_horse = None
        current_comment = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this line starts a new horse entry
            # Horse names are typically ALL CAPS or Title Case at the start
            horse_match = re.match(
                r"^([A-Z][A-Z\s']+(?:\([^)]+\))?)\s+(.*)",
                line,
            )
            if horse_match and len(horse_match.group(1).strip()) > 2:
                # Save previous horse
                if current_horse:
                    comment_text = " ".join(current_comment).strip()
                    races[race_time]["horses"].append({
                        "horse_name": _normalize_horse_name(current_horse),
                        "spotlight_comment": comment_text,
                        "spotlight_sentiment": _basic_sentiment(comment_text),
                    })
                current_horse = horse_match.group(1).strip()
                current_comment = [horse_match.group(2)]
            elif current_horse:
                current_comment.append(line)

        # Save last horse
        if current_horse:
            comment_text = " ".join(current_comment).strip()
            races[race_time]["horses"].append({
                "horse_name": _normalize_horse_name(current_horse),
                "spotlight_comment": comment_text,
                "spotlight_sentiment": _basic_sentiment(comment_text),
            })

    # Try to run full NLP if available
    try:
        from workers.spotlight_parser import extract_spotlight_signals
        for race_time, race_data in races.items():
            for horse in race_data["horses"]:
                if horse.get("spotlight_comment"):
                    nlp_result = extract_spotlight_signals(
                        horse["spotlight_comment"],
                        horse["horse_name"],
                    )
                    horse["spotlight_flags"] = nlp_result.get("flags", [])
                    horse["spotlight_score"] = nlp_result.get("sentiment_score", 0)
    except Exception:
        pass

    return races


def _normalize_horse_name(name: str) -> str:
    """Normalize horse name to Title Case."""
    name = re.sub(r"\([^)]+\)", "", name).strip()
    return name.title()


def _basic_sentiment(text: str) -> float:
    """Quick sentiment score from -1 to +1."""
    positive = [
        "progressive", "improving", "well treated", "good form",
        "interesting", "chance", "strong", "impressive", "won well",
        "unexposed", "looks well handicapped", "dropped",
    ]
    negative = [
        "out of form", "disappointing", "struggling", "poor",
        "no chance", "hard to fancy", "regressive", "below par",
    ]
    text_lower = text.lower()
    pos = sum(1 for p in positive if p in text_lower)
    neg = sum(1 for n in negative if n in text_lower)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 2)


# ─── Merger ──────────────────────────────────────────────────────────────────

def _fuzzy_match(name1: str, name2: str) -> bool:
    """Case-insensitive fuzzy match for horse names."""
    n1 = re.sub(r"[^a-z]", "", name1.lower())
    n2 = re.sub(r"[^a-z]", "", name2.lower())
    return n1 == n2 or n1 in n2 or n2 in n1


def merge_race_data(or_data: dict, ts_data: dict, spotlight_data: dict) -> dict:
    """
    Merge OR, TS, and Spotlight data by race time and horse name.
    Returns unified dict keyed by race_time -> list of enriched horse dicts.
    """
    all_times = sorted(set(
        list(or_data.keys()) + list(ts_data.keys()) + list(spotlight_data.keys())
    ))

    merged = {}
    for race_time in all_times:
        or_horses = {h["horse_name"].lower(): h for h in or_data.get(race_time, {}).get("horses", [])}
        ts_horses = {h["horse_name"].lower(): h for h in ts_data.get(race_time, {}).get("horses", [])}
        spot_horses = {h["horse_name"].lower(): h for h in spotlight_data.get(race_time, {}).get("horses", [])}

        # Start with OR as the base (it has the most horses)
        all_horse_names = sorted(set(
            list(or_horses.keys()) + list(ts_horses.keys()) + list(spot_horses.keys())
        ))

        race_info = (
            or_data.get(race_time, {}).get("race_info", "") or
            ts_data.get(race_time, {}).get("race_info", "")
        )

        horses = []
        for name_key in all_horse_names:
            horse = {"horse_name": name_key.title(), "race_time": race_time}

            # Merge OR data
            or_h = or_horses.get(name_key)
            if not or_h:
                # Try fuzzy match
                for k, v in or_horses.items():
                    if _fuzzy_match(name_key, k):
                        or_h = v
                        break
            if or_h:
                horse.update({k: v for k, v in or_h.items() if k != "horse_name"})

            # Merge TS data
            ts_h = ts_horses.get(name_key)
            if not ts_h:
                for k, v in ts_horses.items():
                    if _fuzzy_match(name_key, k):
                        ts_h = v
                        break
            if ts_h:
                for k, v in ts_h.items():
                    if k not in ("horse_name", "weight", "current_or") and v is not None:
                        horse[k] = v

            # Merge Spotlight data
            spot_h = spot_horses.get(name_key)
            if not spot_h:
                for k, v in spot_horses.items():
                    if _fuzzy_match(name_key, k):
                        spot_h = v
                        break
            if spot_h:
                for k, v in spot_h.items():
                    if k != "horse_name" and v is not None:
                        horse[k] = v

            # ── Compute composite plot signals ────────────────────────────
            _compute_plot_signals(horse)

            horses.append(horse)

        merged[race_time] = {
            "race_info": race_info,
            "horses": horses,
        }

    return merged


def _compute_plot_signals(horse: dict):
    """Compute composite plot signals from merged data."""

    # 1. Handicap Plot Score (0.0 to 1.0)
    #    Based on OR delta to best winning mark
    delta = horse.get("or_delta_to_best_win")
    if delta is not None:
        if delta <= 0:
            horse["handicap_plot_score"] = 1.0  # At or below winning mark
        elif delta <= 3:
            horse["handicap_plot_score"] = round(1.0 - (delta / 10.0), 2)  # Near
        elif delta <= 7:
            horse["handicap_plot_score"] = round(0.7 - ((delta - 3) / 20.0), 2)  # Approaching
        else:
            horse["handicap_plot_score"] = max(0.0, round(0.5 - ((delta - 7) / 30.0), 2))
    else:
        horse["handicap_plot_score"] = None

    # 2. OR Compression Score (how far dropped from highest entered)
    compression = horse.get("or_compression")
    if compression is not None and compression > 0:
        horse["or_compression_score"] = min(1.0, round(compression / 15.0, 2))
    else:
        horse["or_compression_score"] = 0.0

    # 3. Speed Confirmation (does TS support the OR?)
    ts_master = horse.get("ts_master")
    rpr = horse.get("rpr_master")
    if ts_master and rpr:
        # If TS master is close to or above RPR, speed is confirmed
        horse["speed_confirmed"] = ts_master >= (rpr - 5)
    else:
        horse["speed_confirmed"] = None

    # 4. Course/Distance Proven
    ts_course = horse.get("ts_course")
    ts_dist = horse.get("ts_distance")
    if ts_course and ts_dist:
        horse["cd_proven"] = True
    else:
        horse["cd_proven"] = False

    # 5. Overall Plot Conviction (composite)
    plot_score = horse.get("handicap_plot_score") or 0.0
    compression_score = horse.get("or_compression_score") or 0.0
    spotlight_sent = horse.get("spotlight_sentiment") or 0.0
    # Normalize spotlight sentiment from [-1,1] to [0,1]
    spotlight_norm = (spotlight_sent + 1.0) / 2.0

    horse["plot_conviction"] = round(
        (plot_score * 0.4) + (compression_score * 0.3) + (spotlight_norm * 0.3),
        3,
    )


# ─── Output ──────────────────────────────────────────────────────────────────

def print_summary(merged: dict, venue: str, date: str):
    """Print a human-readable summary of the merged data."""
    print("=" * 90)
    print(f"  VÉLØ UNIFIED RACECARD: {venue} — {date}")
    print("=" * 90)

    total_horses = 0
    plot_candidates = 0

    for race_time in sorted(merged.keys()):
        race = merged[race_time]
        horses = race["horses"]
        total_horses += len(horses)

        print(f"\n  {race_time} — {race.get('race_info', '')}")
        print(f"  {'Horse':<25s} {'OR':>4s} {'BWL':>4s} {'Δ':>4s} {'TS':>4s} {'TSM':>4s} {'RPR':>4s} {'Plot':>5s} {'Comp':>5s} {'Conv':>5s} {'Spot':>5s}")
        print("  " + "-" * 86)

        for h in horses:
            or_val = h.get("current_or") or ""
            bwl = h.get("best_winning_life") or ""
            delta = h.get("or_delta_to_best_win")
            delta_str = str(delta) if delta is not None else ""
            ts = h.get("ts_latest") or ""
            tsm = h.get("ts_master") or ""
            rpr = h.get("rpr_master") or ""
            plot = h.get("handicap_plot_score")
            plot_str = f"{plot:.2f}" if plot is not None else ""
            comp = h.get("or_compression_score") or 0
            comp_str = f"{comp:.2f}" if comp else ""
            conv = h.get("plot_conviction") or 0
            conv_str = f"{conv:.3f}" if conv else ""
            spot = h.get("spotlight_sentiment") or 0
            spot_str = f"{spot:+.2f}" if spot else ""

            marker = ""
            if plot is not None and plot >= 0.9:
                marker = " ◆ PLOT"
                plot_candidates += 1
            elif plot is not None and plot >= 0.7:
                marker = " ○ near"
                plot_candidates += 1

            name = h.get("horse_name", "?")[:24]
            print(
                f"  {name:<25s} {str(or_val):>4s} {str(bwl):>4s} {delta_str:>4s} "
                f"{str(ts):>4s} {str(tsm):>4s} {str(rpr):>4s} "
                f"{plot_str:>5s} {comp_str:>5s} {conv_str:>5s} {spot_str:>5s}{marker}"
            )

    print("\n" + "=" * 90)
    print(f"  TOTAL: {total_horses} horses across {len(merged)} races")
    print(f"  PLOT CANDIDATES (score >= 0.7): {plot_candidates}")
    print("=" * 90)


def save_output(merged: dict, venue: str, date: str, output_dir: Path):
    """Save merged data as JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"racecard_{venue}_{date}.json"

    output = {
        "venue": venue,
        "date": date,
        "generated_at": datetime.utcnow().isoformat(),
        "races": {},
    }
    for race_time, race_data in merged.items():
        output["races"][race_time] = race_data

    out_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\n  Saved: {out_path}")
    return out_path


# ─── Main ────────────────────────────────────────────────────────────────────

def find_pdfs_in_dir(directory: Path, venue: str, date: str) -> dict:
    """Find OR, TS, and Spotlight PDFs in a directory by venue and date."""
    date_compact = date.replace("-", "")
    found = {"or": None, "ts": None, "spotlight": None}

    for f in sorted(directory.glob("*.pdf")):
        if venue.upper() not in f.name.upper():
            continue
        if date_compact not in f.name:
            continue
        info = classify_pdf(f)
        if info["type"] in found:
            found[info["type"]] = f

    return found


def main():
    parser = argparse.ArgumentParser(description="VÉLØ Unified Racecard PDF Ingestion")
    parser.add_argument("--dir", type=Path, help="Directory containing PDFs")
    parser.add_argument("--venue", type=str, help="Venue code (e.g. PON)")
    parser.add_argument("--date", type=str, help="Race date (YYYY-MM-DD)")
    parser.add_argument("--or", dest="or_pdf", type=Path, help="Official Ratings PDF path")
    parser.add_argument("--ts", type=Path, help="Top Speed PDF path")
    parser.add_argument("--spotlight", type=Path, help="Spotlight PDF path")
    parser.add_argument("--dry-run", action="store_true", help="No Supabase write")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "racecard_merged")
    args = parser.parse_args()

    # Find PDFs
    if args.dir and args.venue and args.date:
        pdfs = find_pdfs_in_dir(args.dir, args.venue, args.date)
        or_path = pdfs["or"]
        ts_path = pdfs["ts"]
        spot_path = pdfs["spotlight"]
        venue = args.venue.upper()
        date = args.date
    else:
        or_path = args.or_pdf
        ts_path = args.ts
        spot_path = args.spotlight
        venue = "UNKNOWN"
        date = datetime.now().strftime("%Y-%m-%d")

        if or_path:
            info = classify_pdf(or_path)
            venue = info.get("venue", venue)
            raw_date = info.get("date", "")
            if raw_date and len(raw_date) == 8:
                date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"

    print(f"\n  VÉLØ Racecard Ingestion: {venue} {date}")
    print(f"  OR:        {or_path or 'NOT FOUND'}")
    print(f"  TS:        {ts_path or 'NOT FOUND'}")
    print(f"  Spotlight: {spot_path or 'NOT FOUND'}")

    # Parse each PDF
    or_data = parse_or_pdf(or_path) if or_path else {}
    ts_data = parse_ts_pdf(ts_path) if ts_path else {}
    spotlight_data = parse_spotlight_pdf(spot_path) if spot_path else {}

    print(f"\n  Parsed: OR={len(or_data)} races, TS={len(ts_data)} races, Spotlight={len(spotlight_data)} races")

    # Merge
    merged = merge_race_data(or_data, ts_data, spotlight_data)

    # Print summary
    print_summary(merged, venue, date)

    # Save
    out_path = save_output(merged, venue, date, args.output_dir)

    return merged


if __name__ == "__main__":
    main()
