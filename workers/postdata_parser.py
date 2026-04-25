#!/usr/bin/env python3.11
"""
VÉLØ F_0011 Postdata + Top Speed Summary Parser
================================================
Parses the Racing Post "postdata" PDF (F_0011_XX) which contains a single-page
overview of the entire card with two data blocks per horse:

  POSTDATA: Trainer Form, Going, Distance, Course, Draw, Ability, Recent Form
            (values: ✓/✓✓ = positive, ✘ = negative, ? = uncertain, - = neutral/no data)

  TOPSPEED: Latest TS, Best TS with date/venue/distance/going, Adjusted TS

The ✓/✘/? flags are INTENT SIGNALS:
  - ✓✓ on TRAINER FORM = trainer in excellent form (hot stable)
  - ✘ on TRAINER FORM = cold stable
  - ? on COURSE = horse hasn't run here (new course test)
  - ? on GOING = unproven on today's going
  - ✘ on RECENT FORM = poor recent form (but could be deliberate for plot)

The last row of each table contains POSTDATA and TOPSPEED selections:
  "POSTDATA Savvy Victory TOPSPEED Savvy Victory"
"""

import re
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


# ─── Flag Mapping ─────────────────────────────────────────────────────────────

FLAG_MAP = {
    "✓✓": "strong_positive",
    "✓": "positive",
    "✘": "negative",
    "?": "uncertain",
    "-": "neutral",
    "": "no_data",
}

FLAG_SCORE = {
    "strong_positive": 1.0,
    "positive": 0.7,
    "uncertain": 0.3,
    "neutral": 0.0,
    "negative": -0.5,
    "no_data": 0.0,
}

# Column indices — determined dynamically per table.
# Flat cards have 8 cols (with DRAW), NH cards have 7 cols (no DRAW).
# The TS data column is always the last column.
COL_TRAINER_FORM = 0
COL_GOING = 1
COL_DIST = 2
COL_COURSE = 3
# COL_DRAW / COL_ABILITY / COL_RECENT_FORM / COL_TS_DATA are set per-table


def _detect_columns(header_row: list) -> dict:
    """Detect column layout based on header count.

    Returns dict with keys: has_draw, col_draw, col_ability, col_recent_form, col_ts_data.
    """
    ncols = len(header_row)
    # Check if any header cell contains 'DRAW'
    has_draw = any("DRAW" in (c or "").upper() for c in header_row)
    if has_draw or ncols >= 8:
        return {
            "has_draw": True,
            "col_draw": 4,
            "col_ability": 5,
            "col_recent_form": 6,
            "col_ts_data": 7,
        }
    else:
        # NH / no-draw layout: 7 cols
        return {
            "has_draw": False,
            "col_draw": None,
            "col_ability": 4,
            "col_recent_form": 5,
            "col_ts_data": 6,
        }


def _parse_flag(val: str) -> str:
    """Convert a cell value to a flag label."""
    val = (val or "").strip()
    # Handle double ticks (sometimes merged)
    if "✓✓" in val:
        return "strong_positive"
    if "✓" in val:
        return "positive"
    if "✘" in val:
        return "negative"
    if "?" in val:
        return "uncertain"
    if val == "-":
        return "neutral"
    return "no_data"


def _parse_ts_cell(cell: str) -> dict:
    """
    Parse the combined horse name + TS data cell.
    Format: "Speeding Bullet 6464-Sep 05 Hayd 5.0g 64"
    Or:     "b1 Fuji Mountain 3086-Jun 15 Haml 6.0gs 86"
    Or:     "Charlie Darling 60- 0"
    Or:     "Town Queen -- 0"
    """
    cell = (cell or "").strip()
    if not cell:
        return {}

    # Strip leading headgear codes like "b1", "t1", "v1", "h1", "p1", "e1"
    headgear_code = None
    hg_match = re.match(r"^([btvhpec]\d?)\s+", cell, re.IGNORECASE)
    if hg_match:
        headgear_code = hg_match.group(1)
        cell = cell[hg_match.end():]

    # Try to parse: HorseName TS_LATEST TS_BEST-Date Venue Dist+Going ADJUSTED
    # Pattern: name digits digits-Mon DD Venue Dist.Going digits
    # Name group: letters, spaces, apostrophes, hyphens ONLY — no digits
    m = re.match(
        r"^([A-Za-z][A-Za-z'\-\.\s]+?)\s+(\d+)\s*(\d+)-(\w{3})\s+(\d{2})\s+(\w+)\s+([\d.]+)([\w]*)\s+(\d+)$",
        cell,
    )
    if m:
        return {
            "horse_name": m.group(1).strip(),
            "headgear_code": headgear_code,
            "ts_latest": int(m.group(2)),
            "ts_best": int(m.group(3)),
            "ts_best_month": m.group(4),
            "ts_best_day": int(m.group(5)),
            "ts_best_venue": m.group(6),
            "ts_best_dist_going": m.group(7) + m.group(8),
            "ts_adjusted": int(m.group(9)),
        }

    # Simpler pattern: name digits-Mon DD Venue Dist+Going digits (no latest separate)
    m2 = re.match(
        r"^([A-Za-z][A-Za-z'\-\.\s]+?)\s+-?(\d+)-(\w{3})\s+(\d{2})\s+(\w+)\s+([\d.]+)([\w]*)\s+(\d+)$",
        cell,
    )
    if m2:
        return {
            "horse_name": m2.group(1).strip(),
            "headgear_code": headgear_code,
            "ts_latest": None,
            "ts_best": int(m2.group(2)),
            "ts_best_month": m2.group(3),
            "ts_best_day": int(m2.group(4)),
            "ts_best_venue": m2.group(5),
            "ts_best_dist_going": m2.group(6) + m2.group(7),
            "ts_adjusted": int(m2.group(8)),
        }

    # Minimal pattern: name digits- digits or name -- digits
    m3 = re.match(r"^([A-Za-z][A-Za-z'\-\.\s]+?)\s+(\d+)-\s*(\d+)$", cell)
    if m3:
        return {
            "horse_name": m3.group(1).strip(),
            "headgear_code": headgear_code,
            "ts_latest": int(m3.group(2)),
            "ts_best": None,
            "ts_adjusted": int(m3.group(3)),
        }

    # Just name and -- 0
    m4 = re.match(r"^([A-Za-z][A-Za-z'\-\.\s]+?)\s+--\s*(\d+)$", cell)
    if m4:
        return {
            "horse_name": m4.group(1).strip(),
            "headgear_code": headgear_code,
            "ts_latest": None,
            "ts_best": None,
            "ts_adjusted": int(m4.group(2)),
        }

    # Fallback: just extract horse name
    name_match = re.match(r"^([A-Za-z][\w\s']+)", cell)
    if name_match:
        return {
            "horse_name": name_match.group(1).strip(),
            "headgear_code": headgear_code,
        }

    return {"raw": cell, "headgear_code": headgear_code}


def _parse_header(header_row: list) -> dict:
    """Parse the header row to extract race time, going, and distance."""
    info = {}

    # Going from col 1 header: "GOING\nG" or "GOING\nGS"
    going_cell = (header_row[COL_GOING] or "").strip()
    going_match = re.search(r"GOING\n(.+)", going_cell)
    if going_match:
        info["going"] = going_match.group(1).strip()

    # Distance from col 2 header: "DIST\n5.0f" or "DIST\n21.6f"
    dist_cell = (header_row[COL_DIST] or "").strip()
    dist_match = re.search(r"DIST\n([\d.]+f?)", dist_cell)
    if dist_match:
        info["distance_f"] = dist_match.group(1).strip()

    # Race time from last column header: "5:05 Topspeed Ratings..."
    ts_header = (header_row[-1] or "").strip()
    time_match = re.search(r"(\d+:\d{2})", ts_header)
    if time_match:
        info["race_time"] = time_match.group(1)

    return info


def _parse_selections(cell: str) -> dict:
    """Parse the POSTDATA/TOPSPEED selection row."""
    cell = (cell or "").strip()
    result = {}
    pd_match = re.search(r"POSTDATA\s+(.+?)\s+TOPSPEED", cell)
    if pd_match:
        result["postdata_pick"] = pd_match.group(1).strip()
    ts_match = re.search(r"TOPSPEED\s+(.+)$", cell)
    if ts_match:
        result["topspeed_pick"] = ts_match.group(1).strip()
    return result


def parse_postdata_pdf(path: Path) -> dict:
    """
    Parse F_0011 Postdata PDF.

    Returns:
        dict keyed by race_time -> {
            "going": str,
            "distance_f": str,
            "postdata_pick": str,
            "topspeed_pick": str,
            "horses": [
                {
                    "horse_name": str,
                    "headgear_code": str | None,
                    "trainer_form": str,  # flag label
                    "going_flag": str,
                    "distance_flag": str,
                    "course_flag": str,
                    "draw_flag": str,
                    "ability_flag": str,
                    "recent_form_flag": str,
                    "postdata_score": float,  # composite -1 to +1
                    "ts_latest": int | None,
                    "ts_best": int | None,
                    "ts_adjusted": int | None,
                    "ts_best_venue": str | None,
                    "ts_best_dist_going": str | None,
                    ...
                }
            ]
        }
    """
    if not pdfplumber:
        raise ImportError("pdfplumber required")

    races = {}

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue

                header = table[0]
                # Check if this is a postdata table (has TRAINER header)
                first_header = (header[0] or "").strip()
                if "TRAINER" not in first_header and "FORM" not in first_header:
                    continue

                # Detect column layout (Flat vs NH)
                cols = _detect_columns(header)

                # Parse header for race info
                race_info = _parse_header(header)
                race_time = race_info.get("race_time", "unknown")

                horses = []
                selections = {}

                for row in table[1:]:
                    if not row or not any(row):
                        continue

                    first_cell = (row[0] or "").strip()

                    # Check for selection row
                    if "POSTDATA" in first_cell and "TOPSPEED" in first_cell:
                        selections = _parse_selections(first_cell)
                        continue

                    # Parse horse row
                    ts_col = cols["col_ts_data"] if cols["col_ts_data"] < len(row) else len(row) - 1

                    ts_data = _parse_ts_cell(row[ts_col] if ts_col < len(row) else "")
                    if not ts_data.get("horse_name"):
                        continue

                    # Parse flags — use detected column layout
                    flags = {
                        "trainer_form": _parse_flag(row[COL_TRAINER_FORM] if COL_TRAINER_FORM < len(row) else ""),
                        "going_flag": _parse_flag(row[COL_GOING] if COL_GOING < len(row) else ""),
                        "distance_flag": _parse_flag(row[COL_DIST] if COL_DIST < len(row) else ""),
                        "course_flag": _parse_flag(row[COL_COURSE] if COL_COURSE < len(row) else ""),
                        "draw_flag": _parse_flag(row[cols["col_draw"]] if cols["has_draw"] and cols["col_draw"] < len(row) else ""),
                        "ability_flag": _parse_flag(row[cols["col_ability"]] if cols["col_ability"] < len(row) else ""),
                        "recent_form_flag": _parse_flag(row[cols["col_recent_form"]] if cols["col_recent_form"] < len(row) else ""),
                    }

                    # Compute composite postdata score (-1 to +1)
                    # Weight: trainer_form=0.2, going=0.15, distance=0.15, course=0.15,
                    #         draw=0.05, ability=0.15, recent_form=0.15
                    weights = {
                        "trainer_form": 0.20,
                        "going_flag": 0.15,
                        "distance_flag": 0.15,
                        "course_flag": 0.15,
                        "draw_flag": 0.05,
                        "ability_flag": 0.15,
                        "recent_form_flag": 0.15,
                    }
                    score = sum(
                        FLAG_SCORE.get(flags[k], 0.0) * w
                        for k, w in weights.items()
                    )
                    flags["postdata_score"] = round(score, 3)

                    # Compute intent signals
                    intent_signals = []

                    # Hot stable: trainer form is strong positive
                    if flags["trainer_form"] == "strong_positive":
                        intent_signals.append("hot_stable")

                    # Cold stable: trainer form is negative
                    if flags["trainer_form"] == "negative":
                        intent_signals.append("cold_stable")

                    # New course test: course is uncertain
                    if flags["course_flag"] == "uncertain":
                        intent_signals.append("new_course_test")

                    # Unproven going: going is uncertain
                    if flags["going_flag"] == "uncertain":
                        intent_signals.append("unproven_going")

                    # Education profile: multiple uncertain flags
                    uncertain_count = sum(
                        1 for v in flags.values()
                        if isinstance(v, str) and v == "uncertain"
                    )
                    if uncertain_count >= 3:
                        intent_signals.append("education_run_profile")

                    # Plot profile: poor recent form BUT positive ability
                    if (flags["recent_form_flag"] in ("negative",) and
                            flags["ability_flag"] in ("strong_positive", "positive")):
                        intent_signals.append("hidden_ability")

                    # All systems go: all positive/strong positive
                    positive_count = sum(
                        1 for v in flags.values()
                        if isinstance(v, str) and v in ("positive", "strong_positive")
                    )
                    if positive_count >= 5:
                        intent_signals.append("all_systems_go")

                    flags["intent_signals"] = intent_signals

                    horse = {**ts_data, **flags}
                    horses.append(horse)

                races[race_time] = {
                    "going": race_info.get("going", ""),
                    "distance_f": race_info.get("distance_f", ""),
                    **selections,
                    "horses": horses,
                }

    return races


# ─── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python postdata_parser.py <path_to_F_0011_pdf>")
        sys.exit(1)

    path = Path(sys.argv[1])
    result = parse_postdata_pdf(path)

    total_horses = 0
    for race_time in sorted(result.keys()):
        race = result[race_time]
        horses = race["horses"]
        total_horses += len(horses)

        print(f"\n  {race_time} — {race.get('distance_f', '')} {race.get('going', '')}")
        print(f"  Picks: POSTDATA={race.get('postdata_pick', '?')}  TOPSPEED={race.get('topspeed_pick', '?')}")
        print(f"  {'Horse':<25s} {'TrnF':>5s} {'Going':>5s} {'Dist':>5s} {'Crs':>5s} {'Draw':>5s} {'Abil':>5s} {'Form':>5s} {'Score':>6s} {'TSAdj':>5s} Intent")
        print("  " + "-" * 110)

        for h in horses:
            name = h.get("horse_name", "?")[:24]
            hg = f"[{h['headgear_code']}]" if h.get("headgear_code") else ""
            tf = h.get("trainer_form", "")[:5]
            gf = h.get("going_flag", "")[:5]
            df = h.get("distance_flag", "")[:5]
            cf = h.get("course_flag", "")[:5]
            dr = h.get("draw_flag", "")[:5]
            ab = h.get("ability_flag", "")[:5]
            rf = h.get("recent_form_flag", "")[:5]
            sc = h.get("postdata_score", 0)
            ts = h.get("ts_adjusted") or ""
            intent = ", ".join(h.get("intent_signals", []))

            print(f"  {name+hg:<25s} {tf:>5s} {gf:>5s} {df:>5s} {cf:>5s} {dr:>5s} {ab:>5s} {rf:>5s} {sc:>6.3f} {str(ts):>5s} {intent}")

    print(f"\n  TOTAL: {total_horses} horses across {len(result)} races")
