#!/usr/bin/env python3.11
"""
VÉLØ Unified Racecard PDF Ingestion Pipeline
=============================================
Parses up to 7 Racing Post PDF types and merges them into a single per-horse
intelligence record:

  F_0015_OR  — Official Ratings (OR, best winning OR, highest entered, lowest win, RPR)
  F_0032_TS  — Top Speed ratings (latest TS, distance/course/going best, master TS)
  F_0016_XX  — Spotlight comments (free-text per horse, NLP flags, sentiment)
  F_0011_XX  — Postdata + TS Summary (trainer/going/course/draw/ability flags, adjusted TS)
  O_0006_XX  — Form Detailed (breeding, stats, last run, NOTE-BOOK, trainer rtf%)
  O_0008_XX  — Form Short (subset of O_0006)
  O_0001_XX  — Profile (lifetime C/D/G stats)

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

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber required. pip install pdfplumber")
    sys.exit(1)


# ─── Filename Patterns ───────────────────────────────────────────────────────
# Full-card PDFs: PON_20260421_00_00_F_0015_OR_Pontefract.pdf
FILENAME_F_RE = re.compile(
    r"(?P<code>[A-Z]{3})_(?P<date>\d{8})_\d+_\d+_F_(?P<ftype>\d{4})_(?P<label>[A-Z]{2})_(?P<venue>.+)\.pdf",
    re.IGNORECASE,
)
# Per-race PDFs: PON_20260421_13_42_O_0006_XX_Pontefract.pdf
FILENAME_O_RE = re.compile(
    r"(?P<code>[A-Z]{3})_(?P<date>\d{8})_\d+_\d+_O_(?P<ftype>\d{4})_(?P<label>[A-Z]{2})_(?P<venue>.+)\.pdf",
    re.IGNORECASE,
)


def classify_pdf(path: Path) -> dict:
    """Classify a PDF by its filename pattern."""
    # Try full-card pattern first
    m = FILENAME_F_RE.match(path.name)
    if m:
        label = m.group("label").upper()
        ftype = m.group("ftype")
        if label == "OR" or ftype == "0015":
            pdf_type = "or"
        elif label == "TS" or ftype == "0032":
            pdf_type = "ts"
        elif ftype == "0016":
            pdf_type = "spotlight"
        elif ftype == "0011":
            pdf_type = "postdata"
        else:
            pdf_type = "unknown"
        return {
            "type": pdf_type,
            "code": m.group("code"),
            "date": m.group("date"),
            "venue": m.group("venue"),
            "path": path,
        }

    # Try per-race pattern
    m = FILENAME_O_RE.match(path.name)
    if m:
        ftype = m.group("ftype")
        if ftype == "0006":
            pdf_type = "form_detailed"
        elif ftype == "0008":
            pdf_type = "form_short"
        elif ftype == "0001":
            pdf_type = "profile"
        else:
            pdf_type = "unknown"
        return {
            "type": pdf_type,
            "code": m.group("code"),
            "date": m.group("date"),
            "venue": m.group("venue"),
            "path": path,
        }

    return {"type": "unknown", "path": path}


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

                    # Find horse name — it's in the column that has alphabetic text
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

                    # ── Per-run history: columns BEFORE the horse name ──────────
                    # Each cell before the name contains a run entry like:
                    #   "1 1/2"  = finished 1st, won by 1.5 lengths
                    #   "2 21/4" = finished 2nd, beaten 2.25 lengths
                    #   "07093/4" = finished 0(unplaced), OR was 70, beaten 9.75 lengths
                    # We store them as raw strings for now (right to left = most recent first)
                    run_history_raw = []
                    for ci in range(horse_col - 1, -1, -1):
                        cell_val = (row[ci] or "").strip()
                        if cell_val and cell_val not in ("", "Horse", "Wgt"):
                            run_history_raw.insert(0, cell_val)

                    # Parse each run: extract position and OR where possible
                    # OR PDF format: each run cell is like:
                    #   "07093/4"  -> pos=0, OR=70, beaten 9.75 lengths
                    #   "1 1/2"    -> pos=1, won by 1.5 lengths (no OR shown for wins)
                    #   "2 21/4"   -> pos=2, beaten 2.25 lengths
                    #   "48031/4"  -> pos=4, OR=80, beaten 3.25 lengths
                    # The position is ALWAYS 1 digit. OR is always 2 digits.
                    or_run_history = []
                    for run_str in run_history_raw:
                        clean = run_str.replace(" ", "")
                        # Match: 1-digit pos + 2-digit OR + rest
                        run_match = re.match(r"^(\d)(\d{2})", clean)
                        if run_match:
                            pos = int(run_match.group(1))
                            run_or = int(run_match.group(2))
                            or_run_history.append({"pos": pos, "or": run_or, "raw": run_str})
                        else:
                            # Simple result like "1 1/2" (win) or "2 nk" (place)
                            pos_match = re.match(r"^(\d)", clean)
                            pos = int(pos_match.group(1)) if pos_match else None
                            or_run_history.append({"pos": pos, "or": None, "raw": run_str})

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
                        "or_run_history": or_run_history,  # last N runs: [{pos, or, raw}]
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

                    # ── Per-run TS history: columns BEFORE the horse name ───────
                    # Each cell before the name is a run entry like:
                    #   "2696g"   = pos 2, TS 69, going g(ood)
                    #   "1595s"   = pos 1, TS 59, going s(oft)
                    #   "0316s"   = pos 0 (unplaced), TS 31, going s
                    ts_run_history = []
                    for ci in range(horse_col - 1, -1, -1):
                        cell_val = (row[ci] or "").strip()
                        if cell_val and cell_val not in ("", "Horse", "Wgt"):
                            ts_run_history.insert(0, cell_val)

                    # Parse each TS run entry
                    # TS PDF format: pos(1) + TS(2) + dist(1-2 digits) + going(1-3 chars)
                    # e.g. "2616gf" = pos=2, TS=61, dist=6f, going=gf
                    # e.g. "0277hy" = pos=0, TS=27, dist=7f, going=hy
                    # e.g. "1595s"  = pos=1, TS=59, dist=5f, going=s
                    # e.g. "4318sd" = pos=4, TS=31, dist=8f, going=sd
                    ts_runs_parsed = []
                    for run_str in ts_run_history:
                        # pos(1) + TS(2) + dist(1-2 digits) + going(letters)
                        m = re.match(r"^(\d)(\d{2})(\d{1,2})([a-z]{1,3})", run_str)
                        if m:
                            ts_runs_parsed.append({
                                "pos": int(m.group(1)),
                                "ts": int(m.group(2)),
                                "dist": m.group(3),
                                "going": m.group(4),
                                "raw": run_str
                            })
                        else:
                            ts_runs_parsed.append({"pos": None, "ts": None, "dist": None, "going": None, "raw": run_str})

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
                        "ts_run_history": ts_runs_parsed,  # last N runs: [{pos, ts, going, raw}]
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


def _merge_source(horse: dict, source_horses: dict, name_key: str, skip_keys: set = None):
    """Merge data from a source into the horse dict using fuzzy matching."""
    skip = skip_keys or set()
    src = source_horses.get(name_key)
    if not src:
        for k, v in source_horses.items():
            if _fuzzy_match(name_key, k):
                src = v
                break
    if src:
        for k, v in src.items():
            if k not in skip and v is not None:
                horse[k] = v
    return src is not None


def _normalize_time(t: str) -> str:
    """Normalize race time to dot format: '2:52' -> '2.52', 'unknown' -> 'unknown'."""
    return t.replace(":", ".") if t and t != "unknown" else t


def _normalize_data_keys(data: dict) -> dict:
    """Normalize all time keys in a data dict to dot format."""
    out = {}
    for k, v in data.items():
        nk = _normalize_time(k)
        if nk in out:
            # Merge horses from duplicate time keys
            existing = out[nk].get("horses", [])
            new = v.get("horses", [])
            existing.extend(new)
            out[nk]["horses"] = existing
        else:
            out[nk] = v
    return out


def merge_race_data(
    or_data: dict,
    ts_data: dict,
    spotlight_data: dict,
    postdata_data: dict = None,
    form_data: dict = None,
    cc_data: dict = None,
    rc_data: dict = None,
) -> dict:
    """
    Merge OR, TS, Spotlight, Postdata, Colour Card, Raceform Card, and Form data.
    Returns unified dict keyed by race_time -> list of enriched horse dicts.
    """
    postdata_data = postdata_data or {}
    form_data = form_data or {}
    cc_data = cc_data or {}
    rc_data = rc_data or {}

    # Normalize all time keys to dot format (e.g. '2:52' -> '2.52')
    or_data = _normalize_data_keys(or_data)
    ts_data = _normalize_data_keys(ts_data)
    spotlight_data = _normalize_data_keys(spotlight_data)
    postdata_data = _normalize_data_keys(postdata_data)
    cc_data = _normalize_data_keys(cc_data)
    rc_data = _normalize_data_keys(rc_data)

    all_times = sorted(set(
        list(or_data.keys()) + list(ts_data.keys()) +
        list(spotlight_data.keys()) + list(postdata_data.keys()) +
        list(cc_data.keys()) + list(rc_data.keys())
    ))
    # Remove 'unknown' if present (postdata sometimes has unmatched races)
    all_times = [t for t in all_times if t != "unknown"]

    merged = {}
    for race_time in all_times:
        or_horses = {h["horse_name"].lower(): h for h in or_data.get(race_time, {}).get("horses", [])}
        ts_horses = {h["horse_name"].lower(): h for h in ts_data.get(race_time, {}).get("horses", [])}
        spot_horses = {h["horse_name"].lower(): h for h in spotlight_data.get(race_time, {}).get("horses", [])}
        pd_horses = {h["horse_name"].lower(): h for h in postdata_data.get(race_time, {}).get("horses", [])}
        cc_horses = {h["horse_name"].lower(): h for h in cc_data.get(race_time, {}).get("horses", [])}
        rc_horses = {h["horse_name"].lower(): h for h in rc_data.get(race_time, {}).get("horses", [])}

        # Form data is keyed by race_time from the form parser
        form_horses = {}
        if form_data:
            for fd in form_data:
                ft = _normalize_time(fd.get("race_time", ""))
                if ft == race_time:
                    form_horses = {h["horse_name"].lower(): h for h in fd.get("horses", [])}
                    break

        def _sanitise_name(n: str) -> str:
            """Strip trailing digit sequences from horse names (parser leak defence)."""
            import re as _re
            # Strip trailing digit sequences with space e.g. 'Cosmic Connection 123'
            n = _re.sub(r'(\s+\d+)+$', '', n).strip()
            # Strip directly-concatenated trailing digits e.g. 'Gethegoodtimesroll46'
            # Only strip if the name has at least 6 chars before the digits (avoid stripping
            # legitimate names like 'Scat Daddy' where there are no trailing digits)
            n = _re.sub(r'(?<=[a-zA-Z])\d+$', '', n).strip()
            return n

        def _make_horse_dict(source_dict: dict) -> dict:
            """Re-key a horse dict with sanitised names, merging duplicates."""
            clean = {}
            for raw_name, data in source_dict.items():
                clean_name = _sanitise_name(raw_name)
                if clean_name not in clean:
                    clean[clean_name] = data
                else:
                    # Merge — prefer non-None values from the clean-named entry
                    for k, v in data.items():
                        if k not in clean[clean_name] or clean[clean_name][k] is None:
                            clean[clean_name][k] = v
            return clean

        or_horses = _make_horse_dict(or_horses)
        ts_horses = _make_horse_dict(ts_horses)
        spot_horses = _make_horse_dict(spot_horses)
        pd_horses = _make_horse_dict(pd_horses)
        cc_horses = _make_horse_dict(cc_horses)
        rc_horses = _make_horse_dict(rc_horses)
        form_horses = _make_horse_dict(form_horses)

        all_horse_names = sorted(set(
            list(or_horses.keys()) + list(ts_horses.keys()) +
            list(spot_horses.keys()) + list(pd_horses.keys()) +
            list(form_horses.keys()) + list(cc_horses.keys()) +
            list(rc_horses.keys())
        ))

        race_info = (
            or_data.get(race_time, {}).get("race_info", "") or
            ts_data.get(race_time, {}).get("race_info", "") or
            cc_data.get(race_time, {}).get("race_info", "")
        )

        # Postdata selections
        pd_race = postdata_data.get(race_time, {})
        postdata_pick = pd_race.get("postdata_pick", "")
        topspeed_pick = pd_race.get("topspeed_pick", "")

        # Colour Card race-level data
        cc_race = cc_data.get(race_time, {})
        cc_betting_forecast = cc_race.get("betting_forecast", "")
        cc_spotlight_verdict = cc_race.get("spotlight_verdict", "")

        horses = []
        for name_key in all_horse_names:
            horse = {"horse_name": name_key.title(), "race_time": race_time}

            # Merge OR data (base layer)
            _merge_source(horse, or_horses, name_key, {"horse_name"})

            # Merge TS data (don't overwrite weight/OR from OR source)
            _merge_source(horse, ts_horses, name_key, {"horse_name", "weight", "current_or"})

            # Merge Spotlight data
            _merge_source(horse, spot_horses, name_key, {"horse_name"})

            # Merge Postdata flags
            pd_matched = _merge_source(horse, pd_horses, name_key, {"horse_name"})

            # Merge Colour Card data (jockey, trainer, form string, RPR, C/D flags)
            cc_h = cc_horses.get(name_key)
            if not cc_h:
                for k, v in cc_horses.items():
                    if _fuzzy_match(name_key, k):
                        cc_h = v
                        break
            if cc_h:
                # Only set jockey/trainer if not already set from other sources
                if not horse.get("jockey"):
                    horse["jockey"] = cc_h.get("jockey", "")
                if not horse.get("trainer"):
                    horse["trainer"] = cc_h.get("trainer", "")
                horse["jockey_claim"] = cc_h.get("jockey_claim")
                horse["form_string"] = cc_h.get("form_string", "")
                horse["stall"] = cc_h.get("stall")
                horse["days_since_last_run"] = cc_h.get("days_since_last_run")
                horse["age"] = cc_h.get("age")
                horse["headgear_cc"] = cc_h.get("headgear_cc", "")
                horse["breeding"] = cc_h.get("breeding", "")
                horse["course_winner_cc"] = cc_h.get("course_winner_cc", False)
                horse["dist_winner_cc"] = cc_h.get("dist_winner_cc", False)
                horse["cd_winner_cc"] = cc_h.get("cd_winner_cc", False)
                horse["bf_flag"] = cc_h.get("bf_flag", False)
                # cc_rpr is a cross-check against rpr_master from OR
                if cc_h.get("cc_rpr") and not horse.get("rpr_master"):
                    horse["rpr_master"] = cc_h["cc_rpr"]

            # Merge Raceform Card data (F_0003) — trainer stats, running style, dist/going stats, SP
            rc_h = rc_horses.get(name_key)
            if not rc_h:
                for k, v in rc_horses.items():
                    if _fuzzy_match(name_key, k):
                        rc_h = v
                        break
            if rc_h:
                # Running style (H=Hold-up, P=Prominent, L=Lead, M=Mid-div)
                horse["running_style"] = rc_h.get("running_style", "")
                # Trainer win% over last 14 days — more precise than postdata flag
                if rc_h.get("trainer_win_pct_14d") is not None:
                    horse["trainer_win_pct_14d"] = rc_h["trainer_win_pct_14d"]
                # Trainer going stats
                horse["trainer_gf_hd_w"] = rc_h.get("trainer_gf_hd_w", 0)
                horse["trainer_gf_hd_r"] = rc_h.get("trainer_gf_hd_r", 0)
                horse["trainer_good_w"] = rc_h.get("trainer_good_w", 0)
                horse["trainer_good_r"] = rc_h.get("trainer_good_r", 0)
                horse["trainer_gs_hvy_w"] = rc_h.get("trainer_gs_hvy_w", 0)
                horse["trainer_gs_hvy_r"] = rc_h.get("trainer_gs_hvy_r", 0)
                # Distance and going win records
                horse["rc_dist_wins"] = rc_h.get("dist_wins", 0)
                horse["rc_dist_runs"] = rc_h.get("dist_runs", 0)
                horse["rc_dist_best_or"] = rc_h.get("dist_best_or")
                horse["rc_going_wins"] = rc_h.get("going_wins", 0)
                horse["rc_going_runs"] = rc_h.get("going_runs", 0)
                horse["rc_going_best_or"] = rc_h.get("going_best_or")
                # SP forecast
                if rc_h.get("sp_forecast"):
                    horse["sp_forecast"] = rc_h["sp_forecast"]
                # Non-runner flag
                if rc_h.get("non_runner"):
                    horse["non_runner"] = True
                # OR from raceform card as cross-check (if OR source missing)
                if not horse.get("current_or") and rc_h.get("current_or"):
                    horse["current_or"] = rc_h["current_or"]
                # Jockey from raceform card (if not already set)
                if not horse.get("jockey") and rc_h.get("jockey"):
                    horse["jockey"] = rc_h["jockey"]
                if not horse.get("trainer") and rc_h.get("trainer"):
                    horse["trainer"] = rc_h["trainer"]

            # Merge Form Detailed data
            form_h = form_horses.get(name_key)
            if not form_h:
                for k, v in form_horses.items():
                    if _fuzzy_match(name_key, k):
                        form_h = v
                        break
            if form_h:
                # Prefix form fields to avoid collisions
                horse["form_trainer"] = form_h.get("trainer", "")
                horse["form_jockey"] = form_h.get("jockey", "")
                horse["form_trainer_rtf_pct"] = form_h.get("trainer_rtf_pct")
                horse["form_trainer_14d"] = form_h.get("trainer_14d_record", "")
                horse["form_sire"] = form_h.get("sire", "")
                horse["form_sire_awd"] = form_h.get("sire_awd")
                horse["form_sire_aei"] = form_h.get("sire_aei")
                horse["form_sales_price"] = form_h.get("sales_price")
                horse["form_breeding"] = form_h.get("breeding_commentary", "")
                horse["form_notebook"] = form_h.get("notebook")
                horse["form_stats"] = form_h.get("stats", {})
                horse["form_last_runs"] = form_h.get("last_runs", [])
                horse["form_cd_proven"] = form_h.get("cd_proven", False)
                horse["form_cdg_proven"] = form_h.get("cdg_proven", False)
                horse["form_trainer_hot"] = form_h.get("trainer_hot", False)
                horse["form_first_time_out"] = form_h.get("first_time_out", False)
                horse["form_lightly_raced"] = form_h.get("lightly_raced", False)
                horse["form_course_wins"] = form_h.get("course_wins", 0)
                horse["form_dist_wins"] = form_h.get("dist_wins", 0)

            # Check if this horse is the postdata/topspeed pick
            if postdata_pick and _fuzzy_match(name_key, postdata_pick.lower()):
                horse["is_postdata_pick"] = True
            if topspeed_pick and _fuzzy_match(name_key, topspeed_pick.lower()):
                horse["is_topspeed_pick"] = True

            # ── Compute composite plot signals ────────────────────────────
            _compute_plot_signals(horse)

            horses.append(horse)

        # ── Dedup: remove ghost entries caused by parser artefacts ──────────
        # If two horses in the same race have identical OR+BWL, keep the one
        # whose name starts with a capital letter (no leading non-alpha prefix)
        seen = {}
        deduped = []
        for h in horses:
            key = (h.get("current_or"), h.get("best_winning_life"))
            name = h.get("horse_name", "")
            # Skip entries that are clearly not horse names (e.g. 'G1', 'G2')
            if re.match(r'^G\d+$', name):
                continue
            # Strip leading non-alpha prefix artefacts like 'Xj ', 'Pc '
            clean_name = re.sub(r'^[^A-Z][a-z]?\s+', '', name)
            if clean_name != name:
                h["horse_name"] = clean_name
                name = clean_name
            if key[0] is not None and key in seen:
                # Keep the entry with the longer/cleaner name
                existing = seen[key]
                if len(name) > len(existing.get("horse_name", "")):
                    deduped = [x for x in deduped if x is not existing]
                    seen[key] = h
                    deduped.append(h)
            else:
                seen[key] = h
                deduped.append(h)
        horses = deduped

        merged[race_time] = {
            "race_info": race_info,
            "postdata_pick": postdata_pick,
            "topspeed_pick": topspeed_pick,
            "betting_forecast": cc_betting_forecast,
            "spotlight_verdict": cc_spotlight_verdict,
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

    # 5. TS Trend Signal — is the horse improving or declining?
    ts_hist = horse.get("ts_run_history") or []
    ts_vals = [r["ts"] for r in ts_hist if r.get("ts") and isinstance(r["ts"], (int, float)) and r["ts"] > 0]
    ts_trend_signal = 0.0
    if len(ts_vals) >= 2:
        # Latest TS > previous TS = improving
        if ts_vals[0] > ts_vals[1]:
            ts_trend_signal = 0.15  # Improving
        elif ts_vals[0] < ts_vals[1] - 10:
            ts_trend_signal = -0.1  # Declining sharply
        else:
            ts_trend_signal = 0.05  # Flat/stable
    horse["ts_trend_signal"] = ts_trend_signal

    # 6. OR Trend Drops — consecutive OR drops = longer setup = more deliberate
    or_hist = horse.get("or_run_history") or []
    or_vals = [r["or"] for r in or_hist if r.get("or") and isinstance(r["or"], (int, float)) and r["or"] > 0]
    or_trend_drops = 0
    if len(or_vals) >= 2:
        for i in range(len(or_vals) - 1):
            if or_vals[i] <= or_vals[i + 1]:
                or_trend_drops += 1
            else:
                break
    # More consecutive drops = stronger setup signal (cap at 4)
    or_trend_signal = min(0.15, or_trend_drops * 0.04)
    horse["or_trend_drops"] = or_trend_drops
    horse["or_trend_signal"] = or_trend_signal

    # 7. Trainer Form Signal
    trainer_form = horse.get("trainer_form", "") or ""
    if trainer_form in ("strong_positive", "positive"):
        trainer_signal = 0.10
    elif trainer_form == "negative":
        # Cold stable = could be deliberate plot (Zacony Rebel pattern)
        trainer_signal = 0.0  # Neutral — don't penalise
    else:
        trainer_signal = 0.0
    horse["trainer_form_signal"] = trainer_signal

    # 8. Overall Plot Conviction (composite) — UPGRADED
    # Core: OR delta to winning mark (40%) + OR compression (25%)
    # Supporting: TS trend (15%) + OR trend drops (10%) + trainer form (10%)
    plot_score = horse.get("handicap_plot_score") or 0.0
    compression_score = horse.get("or_compression_score") or 0.0
    spotlight_sent = horse.get("spotlight_sentiment") or 0.0
    # Normalize spotlight sentiment from [-1,1] to [0,1]
    spotlight_norm = (spotlight_sent + 1.0) / 2.0

    # Base conviction from OR signals
    base = (plot_score * 0.40) + (compression_score * 0.25) + (spotlight_norm * 0.10)
    # Add TS trend, OR trend, trainer form bonuses
    bonus = ts_trend_signal + or_trend_signal + trainer_signal
    # Spotlight bonus (if positive comment, small boost)
    if spotlight_sent > 0:
        bonus += 0.05

    horse["plot_conviction"] = round(min(1.0, base + bonus), 3)


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

        print(f"\n  {race_time} - {race.get('race_info', '')}")
        print(f"  {'Horse':<25s} {'OR':>4s} {'BWL':>4s} {'dOR':>4s} {'TS':>4s} {'TSM':>4s} {'RPR':>4s} {'Plot':>5s} {'Comp':>5s} {'Conv':>5s} {'Spot':>5s}")
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
                marker = " [PLOT]"
                plot_candidates += 1
            elif plot is not None and plot >= 0.7:
                marker = " [NEAR]"
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
    """Find all PDF types in a directory by venue and date."""
    date_compact = date.replace("-", "")
    found = {
        "or": None, "ts": None, "spotlight": None,
        "postdata": None, "colour_card": None, "raceform_card": None,
        "form_detailed": [], "form_short": [], "profile": [],
    }

    for f in sorted(directory.glob("*.pdf")):
        if venue.upper() not in f.name.upper():
            continue
        if date_compact not in f.name:
            continue
        info = classify_pdf(f)
        ptype = info["type"]
        if ptype in ("or", "ts", "spotlight", "postdata"):
            found[ptype] = f
        elif ptype == "unknown":
            # F_0012 is classified as unknown — detect by filename
            if "F_0012" in f.name.upper() or "_0012_" in f.name:
                found["colour_card"] = f
            # F_0003 is the Raceform Card
            elif "F_0003" in f.name.upper() or "_0003_" in f.name:
                found["raceform_card"] = f
        elif ptype in ("form_detailed", "form_short", "profile"):
            found[ptype].append(f)

    return found


def main():
    parser = argparse.ArgumentParser(description="VÉLØ Unified Racecard PDF Ingestion (7 PDF types)")
    parser.add_argument("--dir", type=Path, help="Directory containing PDFs")
    parser.add_argument("--venue", type=str, help="Venue code (e.g. PON)")
    parser.add_argument("--date", type=str, help="Race date (YYYY-MM-DD)")
    parser.add_argument("--or", dest="or_pdf", type=Path, help="Official Ratings PDF path")
    parser.add_argument("--ts", type=Path, help="Top Speed PDF path")
    parser.add_argument("--spotlight", type=Path, help="Spotlight PDF path")
    parser.add_argument("--postdata", type=Path, help="Postdata PDF path")
    parser.add_argument("--form", type=Path, nargs="*", help="Form Detailed PDF path(s)")
    parser.add_argument("--dry-run", action="store_true", help="No Supabase write")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "racecard_merged")
    args = parser.parse_args()

    # Import new parsers
    from workers.postdata_parser import parse_postdata_pdf
    from workers.form_detailed_parser import parse_form_detailed_pdf
    from workers.colour_card_parser import parse_colour_card_pdf
    from workers.raceform_card_parser import parse_raceform_card_pdf
    from workers.spotlight_parser_v2 import parse_spotlight_pdf_v2

    # Find PDFs
    if args.dir and args.venue and args.date:
        pdfs = find_pdfs_in_dir(args.dir, args.venue, args.date)
        or_path = pdfs["or"]
        ts_path = pdfs["ts"]
        spot_path = pdfs["spotlight"]
        pd_path = pdfs["postdata"]
        cc_path = pdfs["colour_card"]
        rc_path = pdfs.get("raceform_card")
        form_paths = pdfs["form_detailed"]
        venue = args.venue.upper()
        date = args.date
    else:
        or_path = args.or_pdf
        ts_path = args.ts
        spot_path = args.spotlight
        pd_path = args.postdata
        cc_path = None
        rc_path = None
        form_paths = args.form or []
        venue = "UNKNOWN"
        date = datetime.now().strftime("%Y-%m-%d")

        if or_path:
            info = classify_pdf(or_path)
            venue = info.get("venue", venue)
            raw_date = info.get("date", "")
            if raw_date and len(raw_date) == 8:
                date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"

    print(f"\n  VÉLØ Racecard Ingestion (7-PDF): {venue} {date}")
    print(f"  OR:          {or_path or 'NOT FOUND'}")
    print(f"  TS:          {ts_path or 'NOT FOUND'}")
    print(f"  Spotlight:   {spot_path or 'NOT FOUND'}")
    print(f"  Postdata:    {pd_path or 'NOT FOUND'}")
    print(f"  Colour Card:   {cc_path or 'NOT FOUND'}")
    print(f"  Raceform Card: {rc_path or 'NOT FOUND'}")
    print(f"  Form:          {len(form_paths)} file(s) found")

    # Parse each PDF type
    or_data = parse_or_pdf(or_path) if or_path else {}
    ts_data = parse_ts_pdf(ts_path) if ts_path else {}
    # Use v2 spotlight parser (reads exact F_0016 format with full comments)
    if spot_path:
        try:
            spotlight_data = parse_spotlight_pdf_v2(spot_path)
        except Exception as e:
            print(f"  WARN: spotlight_parser_v2 failed ({e}), falling back to v1")
            spotlight_data = parse_spotlight_pdf(spot_path)
    else:
        spotlight_data = {}
    postdata_data = parse_postdata_pdf(pd_path) if pd_path else {}
    cc_data = parse_colour_card_pdf(cc_path) if cc_path else {}
    rc_data = parse_raceform_card_pdf(rc_path) if rc_path else {}

    # Parse form detailed PDFs (one per race)
    form_data = []
    for fp in form_paths:
        try:
            fd = parse_form_detailed_pdf(fp)
            form_data.append(fd)
        except Exception as e:
            print(f"  WARN: Failed to parse form PDF {fp}: {e}")

    print(f"\n  Parsed: OR={len(or_data)} races, TS={len(ts_data)} races, "
          f"Spotlight={len(spotlight_data)} races, Postdata={len(postdata_data)} races, "
          f"ColourCard={len(cc_data)} races, RaceformCard={len(rc_data)} races, Form={len(form_data)} races")

    # Merge all sources
    merged = merge_race_data(
        or_data, ts_data, spotlight_data,
        postdata_data=postdata_data,
        form_data=form_data,
        cc_data=cc_data,
        rc_data=rc_data,
    )

    # Print summary
    print_summary(merged, venue, date)

    # Save
    out_path = save_output(merged, venue, date, args.output_dir)

    return merged


if __name__ == "__main__":
    main()
