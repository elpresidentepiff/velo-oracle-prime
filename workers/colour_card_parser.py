#!/usr/bin/env python3.11
"""
VÉLØ Colour Card Parser — F_0012_XX
====================================
Parses the Racing Post Colour Card PDF (F_0012).

Horse data is sometimes split across two lines:
  Line A: "8 4P5223 HATOS 23"                          (stall form name days)
  Line B: "8 11-12t Freddie Mitchell (3) 89 106 103"   (age weight jockey OR TS RPR)
  OR single line: "1 221141 BALLYNAHEER 19 D CD 7 12-0tp Jonathan Burke 107 99 108"

Returns dict: race_time -> {race_info, horses, betting_forecast, spotlight_verdict}
Each horse dict has: horse_name, stall, form_string, days_since_last_run, age, weight,
  headgear_cc, jockey, jockey_claim, cc_or, cc_ts, cc_rpr, trainer, breeding,
  course_winner_cc, dist_winner_cc, cd_winner_cc, bf_flag
"""

import re
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    raise ImportError("pdfplumber required: pip install pdfplumber")


# ─── Patterns ─────────────────────────────────────────────────────────────────

RACE_TIME_RE = re.compile(r"^(\d{1,2}\.\d{2})\s+(.+)")

# Full single-line horse row (all data on one line)
# "1 221141 BALLYNAHEER 19 D CD 7 12-0tp Jonathan Burke 107 99 108"
HORSE_FULL_RE = re.compile(
    r"^(\d{1,2})\s+"                                    # stall
    r"([\w\-\/]+)\s+"                                    # form
    r"([A-Z][A-Z\s\'\.]+?)\s+"                          # NAME (caps)
    r"(\d+)?\s*"                                         # days since (optional)
    r"((?:(?:C|D|CD|BF)\s+)*)"                          # flags
    r"(\d+)\s+"                                          # age
    r"(\d+\-\d+[a-z0-9]*)\s+"                          # weight+gear
    r"(.+?)\s+"                                          # jockey
    r"(\d{2,3})\s+([\-\d]+)\s+([\-\d]+)\s*$"           # OR TS RPR
)

# Part-A: stall + form + NAME + days (no OR/TS/RPR at end)
HORSE_PART_A_RE = re.compile(
    r"^(\d{1,2})\s+"                                    # stall
    r"([\w\-\/]+)\s+"                                    # form
    r"([A-Z][A-Z\s\'\.]+?)\s*"                          # NAME (caps)
    r"(\d+)?\s*"                                         # days since (optional)
    r"((?:(?:C|D|CD|BF)\s+)*)"                          # flags
    r"\s*$"
)

# Part-B: age + weight + jockey + OR TS RPR
HORSE_PART_B_RE = re.compile(
    r"^(\d+)\s+"                                         # age
    r"(\d+\-\d+[a-z0-9]*)\s+"                          # weight+gear
    r"(.+?)\s+"                                          # jockey
    r"(\d{2,3})\s+([\-\d]+)\s+([\-\d]+)\s*$"           # OR TS RPR
)

# Breeding line: starts with colour/sex code
BREEDING_RE = re.compile(r"^(?:b|ch|gr|ro|br|bl)\s+(?:g|m|c|f|h)\s+", re.IGNORECASE)

# Trainer/owner line: two or more words, no numbers
TRAINER_RE = re.compile(r"^[A-Za-z\s\'\.\,\&\(\)\-]+$")

# Stall-owner-trainer line: (stall) OWNER NAME  T Surname
# e.g. "(6) Homecroft Wealth Racing R Teal"
STALL_LINE_RE = re.compile(r"^\((\d+)\)\s+(.+)$")


def _extract_trainer_from_stall_line(text: str) -> tuple[str, str]:
    """Return (owner, trainer) from '(stall) OWNER T Surname' text.

    Trainer in RP colour cards is always the last 2 words (Initial Surname).
    E.g. 'Homecroft Wealth Racing R Teal' → owner='Homecroft Wealth Racing', trainer='R Teal'
    """
    words = text.strip().split()
    if len(words) >= 2:
        return " ".join(words[:-2]), " ".join(words[-2:])
    if words:
        return "", words[-1]
    return "", ""

FORECAST_RE = re.compile(r"^Betting forecast:\s*(.+)", re.IGNORECASE)
SPOTLIGHT_RE = re.compile(r"^SPOTLIGHT VERDICT\s+(.*)", re.IGNORECASE)
PREV_WINNER_RE = re.compile(r"^\d{4}\s+\(\d+\s+ran\)")
HEADER_RE = re.compile(r"^colourcard\w+\s+\d{2}\.\d{2}\.\d{2}$", re.IGNORECASE)
PAGE_RE = re.compile(r"^Page\s+\d+$", re.IGNORECASE)
CHANNEL_RE = re.compile(r"^(?:SKY|ITV|ATR|RUK)$")
CONDITIONS_RE = re.compile(r"^For\s+\d+yo|^Weights\s+\d+|^Penalty value")


def _parse_int(val: str) -> int | None:
    if not val or val.strip() in ('-', ''):
        return None
    cleaned = re.sub(r"[^\d]", "", val.strip())
    return int(cleaned) if cleaned else None


def _extract_headgear(weight_str: str) -> tuple[str, str]:
    m = re.match(r"(\d+\-\d+)([a-z0-9]*)", weight_str)
    if m:
        return m.group(1), m.group(2)
    return weight_str, ""


def _extract_claim(jockey_str: str) -> tuple[str, int | None]:
    m = re.search(r"\((\d+)\)\s*$", jockey_str.strip())
    if m:
        return jockey_str[:m.start()].strip(), int(m.group(1))
    return jockey_str.strip(), None


def _extract_cd_flags(flags_str: str) -> dict:
    f = flags_str.upper()
    return {
        "course_winner": bool(re.search(r"\bC\b", f)),
        "dist_winner": bool(re.search(r"\bD\b", f)),
        "both_cd": "CD" in f,
        "bf_flag": "BF" in f,
    }


def _make_horse(stall, form_str, name, days, flags_str, age, weight_raw, jockey_raw, or_val, ts_val, rpr_val):
    weight, headgear = _extract_headgear(weight_raw)
    jockey, claim = _extract_claim(jockey_raw)
    cd = _extract_cd_flags(flags_str or "")
    return {
        "horse_name": name.strip().title(),
        "stall": stall,
        "form_string": form_str,
        "days_since_last_run": _parse_int(str(days)) if days else None,
        "age": _parse_int(str(age)) if age else None,
        "weight": weight,
        "headgear_cc": headgear,
        "jockey": jockey,
        "jockey_claim": claim,
        "cc_or": _parse_int(str(or_val)) if or_val else None,
        "cc_ts": _parse_int(str(ts_val)) if ts_val else None,
        "cc_rpr": _parse_int(str(rpr_val)) if rpr_val else None,
        "course_winner_cc": cd["course_winner"],
        "dist_winner_cc": cd["dist_winner"],
        "cd_winner_cc": cd["both_cd"],
        "bf_flag": cd["bf_flag"],
        "trainer": "",
        "owner": "",
        "breeding": "",
    }


def parse_colour_card_pdf(path: Path) -> dict:
    races = {}
    current_race = None
    current_horse = None
    pending_part_a = None   # holds partial horse data waiting for Part-B line
    sub_line = 0            # sub-line counter within current horse block
    in_spotlight = False
    pending_spotlight = []

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for raw_line in text.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue

                # Skip boilerplate
                if HEADER_RE.match(line) or PAGE_RE.match(line) or CHANNEL_RE.match(line):
                    continue
                if CONDITIONS_RE.match(line):
                    continue
                if PREV_WINNER_RE.match(line):
                    continue
                # Skip column header
                if re.match(r"^No\.\s+Form\s+Horse", line):
                    continue

                # ── Race time header ──────────────────────────────────────────
                m = RACE_TIME_RE.match(line)
                if m:
                    h_str, mn_str = m.group(1).split(".")
                    if 1 <= int(h_str) <= 23 and 0 <= int(mn_str) <= 59:
                        # Flush pending spotlight
                        if in_spotlight and current_race and pending_spotlight:
                            races[current_race]["spotlight_verdict"] = " ".join(pending_spotlight).strip()
                            in_spotlight = False
                            pending_spotlight = []

                        current_race = m.group(1)
                        races[current_race] = {
                            "race_info": m.group(2).strip(),
                            "horses": [],
                            "betting_forecast": "",
                            "spotlight_verdict": "",
                        }
                        current_horse = None
                        pending_part_a = None
                        sub_line = 0
                        continue

                if not current_race:
                    continue

                # ── Spotlight verdict ─────────────────────────────────────────
                m = SPOTLIGHT_RE.match(line)
                if m:
                    in_spotlight = True
                    pending_spotlight = [m.group(1)] if m.group(1) else []
                    continue

                if in_spotlight:
                    if FORECAST_RE.match(line) or (RACE_TIME_RE.match(line) and not re.search(r"£", line[:30])):
                        races[current_race]["spotlight_verdict"] = " ".join(pending_spotlight).strip()
                        in_spotlight = False
                        pending_spotlight = []
                        # Fall through
                    else:
                        pending_spotlight.append(line)
                        continue

                # ── Betting forecast ──────────────────────────────────────────
                m = FORECAST_RE.match(line)
                if m:
                    races[current_race]["betting_forecast"] = m.group(1).strip()
                    pending_part_a = None
                    current_horse = None
                    continue

                # ── Try full single-line horse row ────────────────────────────
                m = HORSE_FULL_RE.match(line)
                if m:
                    pending_part_a = None
                    h = _make_horse(
                        int(m.group(1)), m.group(2), m.group(3),
                        m.group(4), m.group(5),
                        m.group(6), m.group(7), m.group(8),
                        m.group(9), m.group(10), m.group(11)
                    )
                    races[current_race]["horses"].append(h)
                    current_horse = h
                    sub_line = 1
                    continue

                # ── Try Part-A (name line without OR/TS/RPR) ─────────────────
                m = HORSE_PART_A_RE.match(line)
                if m:
                    pending_part_a = {
                        "stall": int(m.group(1)),
                        "form": m.group(2),
                        "name": m.group(3),
                        "days": m.group(4),
                        "flags": m.group(5),
                    }
                    current_horse = None
                    sub_line = 0
                    continue

                # ── Try Part-B (age/weight/jockey/OR/TS/RPR) ─────────────────
                if pending_part_a:
                    m = HORSE_PART_B_RE.match(line)
                    if m:
                        h = _make_horse(
                            pending_part_a["stall"],
                            pending_part_a["form"],
                            pending_part_a["name"],
                            pending_part_a["days"],
                            pending_part_a["flags"],
                            m.group(1), m.group(2), m.group(3),
                            m.group(4), m.group(5), m.group(6)
                        )
                        races[current_race]["horses"].append(h)
                        current_horse = h
                        pending_part_a = None
                        sub_line = 1
                        continue

                # ── Sub-lines for current horse ───────────────────────────────
                if current_horse and sub_line >= 1:
                    # Breeding line
                    if BREEDING_RE.match(line):
                        current_horse["breeding"] = line
                        sub_line += 1
                        continue

                    # Stall-owner-trainer line: "(6) Homecroft Wealth Racing R Teal"
                    # Must come before TRAINER_RE check — this line has digits.
                    m_stall = STALL_LINE_RE.match(line)
                    if m_stall:
                        owner_trainer_text = m_stall.group(2)
                        owner, trainer = _extract_trainer_from_stall_line(owner_trainer_text)
                        if not current_horse["owner"]:
                            current_horse["owner"] = owner
                        if not current_horse["trainer"]:
                            current_horse["trainer"] = trainer
                        sub_line += 1
                        continue

                    # Trainer/owner line (no digits, just names)
                    if TRAINER_RE.match(line) and not re.search(r"\d", line):
                        parts = re.split(r"\s{2,}", line)
                        if len(parts) >= 2:
                            current_horse["owner"] = parts[0].strip()
                            current_horse["trainer"] = parts[-1].strip()
                        elif len(parts) == 1:
                            if not current_horse["trainer"]:
                                current_horse["trainer"] = parts[0].strip()
                        sub_line += 1
                        continue

        # Final flush
        if in_spotlight and current_race and pending_spotlight:
            races[current_race]["spotlight_verdict"] = " ".join(pending_spotlight).strip()

    return races


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python colour_card_parser.py <path_to_F_0012.pdf>")
        sys.exit(1)
    result = parse_colour_card_pdf(Path(sys.argv[1]))
    total = 0
    for rt in sorted(result.keys()):
        race = result[rt]
        n = len(race["horses"])
        total += n
        print(f"\n{rt} — {race['race_info'][:60]}")
        print(f"  Horses: {n}")
        for h in race["horses"]:
            print(f"    {h['horse_name']:25} OR={h['cc_or']} TS={h['cc_ts']} RPR={h['cc_rpr']} "
                  f"J={h['jockey'][:20]:20} T={h['trainer'][:20]:20} form={h['form_string']}")
        if race["betting_forecast"]:
            print(f"  Forecast: {race['betting_forecast'][:100]}")
        if race["spotlight_verdict"]:
            print(f"  Spotlight: {race['spotlight_verdict'][:100]}")
    print(f"\nTOTAL: {total} horses")
