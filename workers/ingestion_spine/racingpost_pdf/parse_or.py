"""
Racing Post PDF Parser - OR Parser
Parse F_0015_OR files (Official Ratings).
"""

import os
import re
from typing import Any

import pdfplumber

from .normalize import normalize_horse_name
from .types import ParseError

_SECTION_RE = re.compile(r"^(?P<off>\d{1,2}\.\d{2})\b")
_HORSE_LINE_RE = re.compile(
    r"^(?P<prefix>.*?)"
    r"(?P<name>[A-Za-z][A-Za-z'&\-\.\s]+?)"
    r"(?:\s+(?P<weight>\d{1,2}-\d{1,2}[A-Za-z0-9]*)|\s+(?P<numbers_no_weight>(?:-?\d+\s*)+))$"
)
_LEAKED_PREFIX_TOKENS = {
    "S", "SD", "G", "GF", "GS", "Y", "YS", "GY", "HY", "SH", "SS",
}


def parse_or_card(pdf_path: str) -> tuple[dict[str, dict[str, dict[str, Any]]], list[ParseError]]:
    """
    Parse OR (Official Ratings) PDF.
    """
    return _parse_rating_card(pdf_path, prefix="or")


def _parse_rating_card(
    pdf_path: str,
    *,
    prefix: str,
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[ParseError]]:
    ratings_map: dict[str, dict[str, dict[str, Any]]] = {}
    errors: list[ParseError] = []

    meeting_date, course_name = _meeting_meta_from_path(pdf_path)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                current_race_id = None
                for raw_line in text.splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("Page "):
                        continue

                    section_match = _SECTION_RE.match(line)
                    if section_match:
                        current_race_id = f"{meeting_date}_{course_name}_{section_match.group('off').replace('.', '')}"
                        ratings_map.setdefault(current_race_id, {})
                        continue

                    if current_race_id is None:
                        continue

                    parsed = _parse_horse_line(line, prefix=prefix)
                    if parsed is None:
                        continue
                    horse_name, payload = parsed
                    ratings_map[current_race_id][horse_name] = payload
    except Exception as exc:
        errors.append(ParseError(severity="error", message=f"Failed to parse {prefix.upper()} PDF: {exc}", location="file"))

    return ratings_map, errors


def _meeting_meta_from_path(pdf_path: str) -> tuple[str, str]:
    filename = os.path.basename(pdf_path)
    parts = filename.split("_")
    meeting_date = f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:8]}"
    course_name = filename.split("_")[-1].replace(".pdf", "")
    return meeting_date, course_name


def _parse_horse_line(line: str, *, prefix: str) -> tuple[str, dict[str, Any]] | None:
    match = _HORSE_LINE_RE.match(line)
    if not match:
        return None

    horse_name = _clean_rating_horse_name(match.group("name"))
    history_tokens = _extract_history_tokens(match.group("prefix"))

    # In F_0015, the rating numbers might be in 'weight' (misidentified)
    # or 'numbers_no_weight'
    raw_nums = match.group("numbers_no_weight") or match.group("weight")
    if not raw_nums:
        return None

    numbers = []
    for piece in raw_nums.split():
        try:
            numbers.append(int(piece))
        except ValueError:
            # Skip pieces like '9-10' which are weights, not ratings
            continue

    if not numbers:
        return None

    # BWL Logic: Find the highest rating they've won off in their history tokens
    # Note: tokens are like '75', '72', '80(1)', '82(1-)'
    # We look for (1) or (1-) markers which indicate a win.
    best_winning_life = None
    win_pattern = re.compile(r"(\d+)\(1-?\)")

    all_prev_ratings = []
    for token in history_tokens:
        win_match = win_pattern.search(token)
        if win_match:
            rating = int(win_match.group(1))
            if best_winning_life is None or rating > best_winning_life:
                best_winning_life = rating

        # Also just collect all numbers to have a general sense of history
        nums = re.findall(r"\d+", token)
        if nums:
            all_prev_ratings.append(int(nums[0]))

    current_or = numbers[0] if len(numbers) >= 1 else None

    payload = {
        f"{prefix}_or_current": current_or,
        f"{prefix}_master": numbers[-1] if numbers else None,
        f"{prefix}_history_tokens": history_tokens,
        f"{prefix}_best_winning_life": best_winning_life,
    }

    if prefix == "or":
        payload["best_winning_life"] = best_winning_life
        if best_winning_life and current_or:
            payload["or_delta_to_best_win"] = current_or - best_winning_life

    return horse_name, payload


def _clean_rating_horse_name(name: str) -> str:
    normalized = normalize_horse_name(name)
    tokens = normalized.split()

    while len(tokens) > 1 and tokens[0] in _LEAKED_PREFIX_TOKENS:
        tokens = tokens[1:]

    # Strip trailing pure-digit tokens (leaked OR/TS/RPR numbers e.g. "COSMIC CONNECTION 123 123")
    while len(tokens) > 1 and re.match(r'^\d+$', tokens[-1]):
        tokens = tokens[:-1]

    return " ".join(tokens)


def _extract_history_tokens(prefix_text: str) -> list[str]:
    tokens: list[str] = []
    # Token format in PDF:  75 80(1) 82(1-) 79
    for piece in prefix_text.split():
        candidate = piece.strip().lower()
        if not candidate or not re.search(r"\d", candidate):
            continue
        tokens.append(candidate)
    return tokens
