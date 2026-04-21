#!/usr/bin/env python3.11
"""
VÉLØ O_0006 Form Detailed Parser
=================================
Parses the Racing Post "form" PDF (O_0006_XX) which contains the richest
per-horse data available:

  Per horse:
    - Horse name, weight, draw
    - Trainer + Jockey + Owner + Breeder
    - Trainer 14-day record (rtf%)
    - Sire, Dam, G Sire with awd (avg winning distance) and aei (earnings index)
    - Sales price
    - Breeding commentary
    - Lifetime stats table: Wins/Pcs/Runs/RPR by:
        Life, 2026, Dist, Crs, Class, GF-Hd, GS-Hvy, 6-15rns, 9-1to9-7
    - Last run details: date, course, type, distance, going, position,
        beaten distance, jockey, weight, SP, comment, OR, TS, RPR
    - NOTE-BOOK entries (expert analysis)

  Per race:
    - Race title, class, prize money, distance, age restriction
    - Going description
"""

import re
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


def parse_form_detailed_pdf(path: Path) -> dict:
    """
    Parse O_0006 Form Detailed PDF using text extraction.

    Returns:
        dict with:
            "race_time": str,
            "race_title": str,
            "race_class": str,
            "prize_money": str,
            "distance": str,
            "going": str,
            "horses": [
                {
                    "horse_name": str,
                    "weight": str,
                    "draw": int | None,
                    "age_sex_colour": str,
                    "trainer": str,
                    "trainer_14d_record": str,
                    "trainer_rtf_pct": int | None,
                    "jockey": str,
                    "owner": str,
                    "breeder": str,
                    "sire": str,
                    "sire_awd": str | None,
                    "sire_aei": float | None,
                    "dam": str,
                    "dam_awd": str | None,
                    "g_sire": str,
                    "sales_price": str | None,
                    "breeding_commentary": str,
                    "stats": {
                        "life": {"wins": int, "pcs": int, "runs": int, "rpr": int},
                        "season": {...},
                        "dist": {...},
                        "course": {...},
                        "class": {...},
                        "gf_hd": {...},
                        "gs_hvy": {...},
                        "runs_6_15": {...},
                        "weight_range": {...},
                    },
                    "last_runs": [
                        {
                            "date": str,
                            "course": str,
                            "type": str,
                            "distance": str,
                            "going": str,
                            "draw": int | None,
                            "position": str,
                            "runners": int | None,
                            "beaten_by": str,
                            "weight": str,
                            "sp": str,
                            "jockey": str,
                            "comment": str,
                            "or_rating": int | None,
                            "ts_rating": int | None,
                            "rpr_rating": int | None,
                        }
                    ],
                    "notebook": str | None,
                    # Computed signals
                    "cd_proven": bool,
                    "cdg_proven": bool,
                    "course_wins": int,
                    "dist_wins": int,
                    "trainer_hot": bool,
                    "first_time_out": bool,
                    "lightly_raced": bool,
                }
            ]
    """
    if not pdfplumber:
        raise ImportError("pdfplumber required")

    with pdfplumber.open(str(path)) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    return _parse_form_text(full_text)


def _parse_form_text(text: str) -> dict:
    """Parse the extracted text into structured data."""
    result = {
        "race_time": "",
        "race_title": "",
        "race_class": "",
        "prize_money": "",
        "distance": "",
        "going": "",
        "horses": [],
    }

    lines = text.split("\n")
    if not lines:
        return result

    # Parse race header
    # Line 1: "formpontefract 21.04.26"
    # Line 2: "1.42 Racing TV Sky Channel 424 EBF Restricted Novice Stakes..."
    # Line 3: "(GBB Race) (Class 5) £8,000 Total Race Value 5f 3y"
    for line in lines[:5]:
        time_match = re.match(r"^(\d+\.\d{2})\s+(.+)", line)
        if time_match:
            result["race_time"] = time_match.group(1)
            result["race_title"] = time_match.group(2).strip()

        class_match = re.search(r"\(Class\s+(\d+)\)", line)
        if class_match:
            result["race_class"] = f"Class {class_match.group(1)}"

        prize_match = re.search(r"£([\d,]+)\s+Total Race Value", line)
        if prize_match:
            result["prize_money"] = f"£{prize_match.group(1)}"

        dist_match = re.search(r"(\d+f\s+\d+y|\d+f)\s+(\d+y)", line)
        if not dist_match:
            dist_match = re.search(r"Value\s+(\d+f(?:\s+\d+y)?)\s+(\d+y)", line)
        if not dist_match:
            # Simple: "5f 3y" at end
            dist_match2 = re.search(r"(\d+f)\s+(\d+y)$", line.strip())
            if dist_match2:
                result["distance"] = dist_match2.group(1)

        going_match = re.search(r"(GD-SFT|GOOD|GD-FM|GD|SFT|HVY|FM|STD)", line)
        if going_match:
            result["going"] = going_match.group(1)

    # Split text into horse blocks
    # Each horse starts with: "HorseName weight Drawn N" followed by age/sex/colour
    horse_pattern = re.compile(
        r"^([A-Z][A-Za-z'\s]+?)\s+(\d+-\d+)\s+Drawn\s+(\d+)\s+(.+?)$",
        re.MULTILINE,
    )

    horse_starts = list(horse_pattern.finditer(text))

    for idx, match in enumerate(horse_starts):
        start = match.start()
        end = horse_starts[idx + 1].start() if idx + 1 < len(horse_starts) else len(text)
        block = text[start:end]

        horse = _parse_horse_block(block, match)
        if horse:
            result["horses"].append(horse)

    return result


def _parse_horse_block(block: str, header_match) -> dict:
    """Parse a single horse's text block."""
    horse = {
        "horse_name": header_match.group(1).strip(),
        "weight": header_match.group(2).strip(),
        "draw": int(header_match.group(3)),
        "age_sex_colour": header_match.group(4).strip(),
    }

    lines = block.split("\n")

    # Parse trainer line: "Trainer: Name 14-days: W-P-R rtf% NN"
    trainer_match = re.search(
        r"Trainer:\s+(.+?)\s+14-days:\s+([\d-]+)\s+rtf%\s+(\d+)",
        block,
    )
    if trainer_match:
        horse["trainer"] = trainer_match.group(1).strip()
        horse["trainer_14d_record"] = trainer_match.group(2)
        horse["trainer_rtf_pct"] = int(trainer_match.group(3))
    else:
        trainer_match2 = re.search(r"Trainer:\s+(.+?)(?:\s+14-days|\n)", block)
        horse["trainer"] = trainer_match2.group(1).strip() if trainer_match2 else ""
        horse["trainer_14d_record"] = ""
        horse["trainer_rtf_pct"] = None

    # Parse jockey
    jockey_match = re.search(r"Jockey:\s+(.+?)(?:\s+Dam:|\n)", block)
    horse["jockey"] = jockey_match.group(1).strip() if jockey_match else ""

    # Parse owner
    owner_match = re.search(r"Owner:\s+(.+?)(?:\s+G Sire:|\n)", block)
    horse["owner"] = owner_match.group(1).strip() if owner_match else ""

    # Parse breeder
    breeder_match = re.search(r"Breeder:\s+(.+?)(?:\s+Sales:|\n)", block)
    horse["breeder"] = breeder_match.group(1).strip() if breeder_match else ""

    # Parse sire with awd and aei
    sire_match = re.search(r"Sire:\s+(.+?)(?:\s+\(awd:|$)", block)
    horse["sire"] = sire_match.group(1).strip() if sire_match else ""
    sire_awd = re.search(r"Sire:.*?\(awd:\s*([\d.]+f?)", block)
    horse["sire_awd"] = sire_awd.group(1) if sire_awd else None
    sire_aei = re.search(r"Sire:.*?aei:\s*([\d.]+)", block)
    horse["sire_aei"] = float(sire_aei.group(1)) if sire_aei else None

    # Parse dam
    dam_match = re.search(r"Dam:\s+(.+?)(?:\s+\(awd:|$)", block)
    horse["dam"] = dam_match.group(1).strip() if dam_match else ""

    # Parse G Sire
    gsire_match = re.search(r"G Sire:\s+(.+?)(?:\s+\(awd:|$)", block)
    horse["g_sire"] = gsire_match.group(1).strip() if gsire_match else ""

    # Parse sales price
    sales_match = re.search(r"Sales:\s+(.+?)(?:\n|$)", block)
    horse["sales_price"] = sales_match.group(1).strip() if sales_match else None

    # Parse stats table
    # Format: "Life W P R RPR  GF-Hd W P R RPR"
    #         "2026 W P R RPR  G     W P R RPR"
    #         "Dist W P R RPR  GS-Hvy W P R RPR"
    #         "Crs  W P R RPR  6-15rns W P R RPR"
    #         "Class W P R RPR 9-1to9-7 W P R RPR"
    horse["stats"] = _parse_stats(block)

    # Parse last run details
    # Format: "date crs type £,000dist/gng dw pos/rn btn winner/second (weight) wgt sp jockey comment OR TS RPR"
    # Actual: "1911 P 10Apr Thsk cls4Md 65.0g 8 5/8 81/2lWhere Love Lives (9-7) 9-7 13/2 David Nolan no impression... - 56 59"
    horse["last_runs"] = _parse_last_runs(block)

    # Parse NOTE-BOOK
    notebook_match = re.search(r"NOTE-BOOK\s*\n(.+?)(?:\n[A-Z][a-z]|\Z)", block, re.DOTALL)
    horse["notebook"] = notebook_match.group(1).strip() if notebook_match else None

    # Parse breeding commentary (the paragraph after sales/breeder info)
    # It's the text between the header info and the stats table
    breeding_lines = []
    in_breeding = False
    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue
        # Start after Sales line
        if "Sales:" in line_s or "Breeder:" in line_s:
            in_breeding = True
            continue
        # Stop at stats table or run details
        if in_breeding:
            if re.match(r"^(Life|Wins|date\s+crs|NOTE-BOOK|\d{4}\s+[A-Z])", line_s):
                break
            if "Wins Plcs Runs RPR" in line_s:
                break
            breeding_lines.append(line_s)

    horse["breeding_commentary"] = " ".join(breeding_lines[:5]).strip()

    # Compute derived signals
    stats = horse["stats"]

    # C/D proven: has won at this course AND distance
    course_wins = stats.get("course", {}).get("wins", 0)
    dist_wins = stats.get("dist", {}).get("wins", 0)
    horse["course_wins"] = course_wins
    horse["dist_wins"] = dist_wins
    horse["cd_proven"] = course_wins > 0 and dist_wins > 0

    # CDG proven: add going
    gf_wins = stats.get("gf_hd", {}).get("wins", 0)
    gs_wins = stats.get("gs_hvy", {}).get("wins", 0)
    horse["cdg_proven"] = horse["cd_proven"] and (gf_wins > 0 or gs_wins > 0)

    # Trainer hot: rtf% >= 50
    horse["trainer_hot"] = (horse.get("trainer_rtf_pct") or 0) >= 50

    # First time out: life runs == 0
    life_runs = stats.get("life", {}).get("runs", 0)
    horse["first_time_out"] = life_runs == 0

    # Lightly raced: <= 3 lifetime runs
    horse["lightly_raced"] = life_runs <= 3

    return horse


def _parse_stats(block: str) -> dict:
    """Parse the lifetime stats table from the text block."""
    stats = {}

    # Pattern: "Category W P R RPR"
    # The stats appear in pairs across two columns
    # Left: Life/2026/Dist/Crs/Class  Right: GF-Hd/G/GS-Hvy/6-15rns/9-1to9-7

    stat_patterns = [
        ("life", r"Life\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"),
        ("season", r"2026\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"),
        ("dist", r"Dist\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"),
        ("course", r"Crs\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"),
        ("class", r"Class\s+\d+\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"),
        ("gf_hd", r"GF-Hd\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"),
        ("good", r"\bG\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"),
        ("gs_hvy", r"GS-Hvy\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"),
        ("runs_6_15", r"6-15rns\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"),
        ("weight_range", r"9-1\s+to\s+9-7\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"),
    ]

    for key, pattern in stat_patterns:
        m = re.search(pattern, block)
        if m:
            stats[key] = {
                "wins": int(m.group(1)),
                "pcs": int(m.group(2)),
                "runs": int(m.group(3)),
                "rpr": int(m.group(4)),
            }
        else:
            stats[key] = {"wins": 0, "pcs": 0, "runs": 0, "rpr": 0}

    return stats


def _parse_last_runs(block: str) -> list:
    """Parse last run detail lines."""
    runs = []

    # Look for run lines: start with a 4-digit number (race code) or date pattern
    # Format: "1911 P 10Apr Thsk cls4Md 65.0g 8 5/8 ..."
    run_pattern = re.compile(
        r"(\d{4})\s+([A-Z]?)\s*(\d+\w+)\s+(\w+)\s+(cls\d\w+)\s+"
        r"([\d.]+\w+)\s+(\d+)\s+([\d/]+)\s+(.+?)\s+"
        r"(\d+-\d+)\s+([\d/]+)\s+(.+?)\s{2,}(.+?)\s+"
        r"(?:OR\s+)?(-|\d+)\s+(\d+)\s+(\d+)",
    )

    # Simpler pattern for the actual format
    for line in block.split("\n"):
        line = line.strip()
        # Match lines starting with 4-digit race code
        m = re.match(r"^(\d{4})\s+", line)
        if m:
            run = {"raw": line}

            # Extract OR, TS, RPR from end of line
            end_match = re.search(r"(-|\d+)\s+(\d+)\s+(\d+)\s*$", line)
            if end_match:
                or_val = end_match.group(1)
                run["or_rating"] = int(or_val) if or_val != "-" else None
                run["ts_rating"] = int(end_match.group(2))
                run["rpr_rating"] = int(end_match.group(3))

            # Extract comment (text before OR/TS/RPR)
            comment_match = re.search(
                r"(?:David Nolan|George Wood|Hollie Doyle|[A-Z][a-z]+\s+[A-Z][a-z]+)\s+(.+?)(?:\s+-?\s*\d+\s+\d+\s*$)",
                line,
            )
            if comment_match:
                run["comment"] = comment_match.group(1).strip()

            runs.append(run)

    return runs


# ─── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python form_detailed_parser.py <path_to_O_0006_pdf>")
        sys.exit(1)

    path = Path(sys.argv[1])
    result = parse_form_detailed_pdf(path)

    print(f"\n{'='*90}")
    print(f"  FORM DETAILED: {result['race_time']} — {result['race_title'][:60]}")
    print(f"  {result['race_class']}  {result['prize_money']}  {result['distance']}  Going: {result['going']}")
    print(f"{'='*90}")

    for h in result["horses"]:
        name = h.get("horse_name", "?")
        wgt = h.get("weight", "?")
        draw = h.get("draw", "?")
        trainer = h.get("trainer", "?")[:25]
        jockey = h.get("jockey", "?")[:20]
        rtf = h.get("trainer_rtf_pct") or "?"
        sire = h.get("sire", "?")[:20]

        stats = h.get("stats", {})
        life = stats.get("life", {})
        dist = stats.get("dist", {})
        course = stats.get("course", {})

        print(f"\n  {name} {wgt} (Draw {draw})")
        print(f"    Trainer: {trainer} (rtf% {rtf})  Jockey: {jockey}")
        print(f"    Sire: {sire}  awd={h.get('sire_awd', '?')}  aei={h.get('sire_aei', '?')}")
        print(f"    Sales: {h.get('sales_price', '?')}")
        print(f"    Life: {life.get('wins',0)}W-{life.get('pcs',0)}P-{life.get('runs',0)}R (RPR {life.get('rpr',0)})")
        print(f"    Dist: {dist.get('wins',0)}W-{dist.get('pcs',0)}P-{dist.get('runs',0)}R")
        print(f"    Course: {course.get('wins',0)}W-{course.get('pcs',0)}P-{course.get('runs',0)}R")

        flags = []
        if h.get("cd_proven"):
            flags.append("C/D PROVEN")
        if h.get("cdg_proven"):
            flags.append("C/D/G PROVEN")
        if h.get("trainer_hot"):
            flags.append("HOT STABLE")
        if h.get("first_time_out"):
            flags.append("DEBUT")
        if h.get("lightly_raced"):
            flags.append("LIGHTLY RACED")
        if flags:
            print(f"    FLAGS: {', '.join(flags)}")

        if h.get("breeding_commentary"):
            print(f"    Breeding: {h['breeding_commentary'][:120]}...")

        if h.get("notebook"):
            print(f"    NOTE-BOOK: {h['notebook'][:120]}...")

        if h.get("last_runs"):
            for run in h["last_runs"][:1]:
                if run.get("comment"):
                    print(f"    Last run: {run['comment'][:100]}")
                if run.get("or_rating") is not None:
                    print(f"    Last OR={run.get('or_rating')} TS={run.get('ts_rating')} RPR={run.get('rpr_rating')}")

    print(f"\n  TOTAL: {len(result['horses'])} horses")
