"""
VÉLØ Spotlight Parser v2
=========================
Correctly parses F_0016_XX Spotlight PDFs.

Format per horse:
  Horse Name  Age  Weight  Trainer  Jockey  SP  OR  TS  RPR
  Comment line 1
  Comment line 2 (continuation)
  ...

Race header:
  HH.MM Race Title...

Spotlight verdict:
  SPOTLIGHT VERDICT text...
"""

import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber required.")
    sys.exit(1)


# Matches a horse header line: Name (Title Case words) followed by age digit, weight, trainer, jockey, SP, OR, TS, RPR
# e.g. "Only One Blue 4 10-11p M Comley Tom Broughton (5) 12-1 108 110 121"
# The key: starts with Title Case name, then a digit (age), then weight like 10-11
HORSE_HEADER_RE = re.compile(
    r"^([A-Z][A-Za-z'\s]+?)\s+(\d+)\s+(\d{1,2}-\d{1,2}[a-z]*)\s+(.+?)\s+(\d+[-\/]\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$"
)

# Simpler fallback: Title Case name followed by age and weight
HORSE_SIMPLE_RE = re.compile(
    r"^([A-Z][A-Za-z'\s\(\)]+?)\s+(\d+)\s+(\d{1,2}-\d{1,2})"
)

# Race time header: HH.MM followed by race title
RACE_TIME_RE = re.compile(r"^(\d{1,2}\.\d{2})\s+\S")

# Spotlight verdict line
VERDICT_RE = re.compile(r"^SPOTLIGHT VERDICT\s+(.*)", re.IGNORECASE)

# Lines to skip
SKIP_PATTERNS = [
    re.compile(r"^spotlight[a-z]+\s+\d{2}\.\d{2}\.\d{2}", re.IGNORECASE),  # "spotlightsandown 25.04.26"
    re.compile(r"^Trainer\s+Jockey\s+SP", re.IGNORECASE),  # header row
    re.compile(r"^For\s+\d+yo"),  # race conditions
    re.compile(r"^Weights\s+raised"),
    re.compile(r"^Minimum\s+weight"),
    re.compile(r"^Penalties\s+after"),
    re.compile(r"^Page\s+\d+$"),
    re.compile(r"^\d{1,2}st\s+£"),  # prize money
    re.compile(r"^£\d+"),
]


def _should_skip(line):
    for pat in SKIP_PATTERNS:
        if pat.match(line):
            return True
    return False


def _is_race_header(line):
    return bool(RACE_TIME_RE.match(line))


def _is_horse_header(line):
    """Check if line starts a new horse entry."""
    # Must start with a capital letter word
    if not line or not line[0].isupper():
        return False
    # Must contain a digit (age) followed by weight pattern somewhere
    return bool(HORSE_SIMPLE_RE.match(line))


def _parse_horse_header(line):
    """Extract horse name from header line."""
    m = HORSE_SIMPLE_RE.match(line)
    if m:
        name = m.group(1).strip()
        # Clean up trailing punctuation
        name = re.sub(r'\s+$', '', name)
        return name
    return None


def parse_spotlight_pdf_v2(path) -> dict:
    """
    Parse F_0016 Spotlight PDF.
    Returns dict keyed by race_time -> {race_info, spotlight_verdict, horses: [{horse_name, spotlight_comment}]}
    """
    if path is None:
        return {}

    races = {}
    current_race = None
    current_race_time = None
    current_horse = None
    current_comment_lines = []
    current_verdict_lines = []
    in_verdict = False

    full_text = ""
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"

    lines = full_text.split("\n")

    def save_current_horse():
        nonlocal current_horse, current_comment_lines
        if current_horse and current_race_time:
            comment = " ".join(current_comment_lines).strip()
            races[current_race_time]["horses"].append({
                "horse_name": current_horse,
                "spotlight_comment": comment,
            })
        current_horse = None
        current_comment_lines = []

    def save_verdict():
        nonlocal current_verdict_lines, in_verdict
        if current_race_time and current_verdict_lines:
            verdict = " ".join(current_verdict_lines).strip()
            races[current_race_time]["spotlight_verdict"] = verdict
        current_verdict_lines = []
        in_verdict = False

    for line in lines:
        line = line.rstrip()
        if not line:
            continue

        if _should_skip(line):
            continue

        # Check for race header
        if _is_race_header(line):
            save_current_horse()
            save_verdict()
            # Extract race time
            m = RACE_TIME_RE.match(line)
            current_race_time = m.group(1)
            race_info = line[len(current_race_time):].strip()
            # Clean up race info (remove truncated parts)
            race_info = re.sub(r'\s+', ' ', race_info)
            races[current_race_time] = {
                "race_info": race_info,
                "spotlight_verdict": "",
                "horses": [],
            }
            in_verdict = False
            continue

        if not current_race_time:
            continue

        # Check for spotlight verdict
        m_verdict = VERDICT_RE.match(line)
        if m_verdict:
            save_current_horse()
            in_verdict = True
            current_verdict_lines = [m_verdict.group(1)]
            continue

        if in_verdict:
            # Check if this is a new race (stops verdict)
            if _is_race_header(line):
                save_verdict()
                m = RACE_TIME_RE.match(line)
                current_race_time = m.group(1)
                race_info = line[len(current_race_time):].strip()
                races[current_race_time] = {
                    "race_info": race_info,
                    "spotlight_verdict": "",
                    "horses": [],
                }
                in_verdict = False
            elif _is_horse_header(line):
                # Verdict ended, new horse
                save_verdict()
                save_current_horse()
                name = _parse_horse_header(line)
                if name:
                    current_horse = name
                    current_comment_lines = []
            else:
                # Continue verdict
                current_verdict_lines.append(line.strip())
            continue

        # Check for horse header
        if _is_horse_header(line):
            save_current_horse()
            name = _parse_horse_header(line)
            if name:
                current_horse = name
                current_comment_lines = []
            continue

        # Comment continuation line
        if current_horse:
            stripped = line.strip()
            if stripped:
                current_comment_lines.append(stripped)

    # Save last horse and verdict
    save_current_horse()
    save_verdict()

    return races


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python spotlight_parser_v2.py <pdf_path>")
        sys.exit(1)

    path = Path(sys.argv[1])
    races = parse_spotlight_pdf_v2(path)

    total = 0
    for race_time, race in sorted(races.items()):
        horses = race["horses"]
        total += len(horses)
        print(f"\n{race_time} — {race['race_info'][:60]}")
        if race.get("spotlight_verdict"):
            print(f"  VERDICT: {race['spotlight_verdict'][:120]}...")
        for h in horses:
            comment = h.get("spotlight_comment", "")
            print(f"  {h['horse_name']}: {comment[:100]}")

    print(f"\nTOTAL: {total} horses across {len(races)} races")
