"""
Racing Post PDF Parser - Postdata Parser
Parse F_0011_XX files (Postdata summary sheet).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import pdfplumber

from .normalize import normalize_horse_name
from .types import ParseError, Race


_OFF_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
_PICK_LINE_RE = re.compile(r"^POSTDATA\s+(?P<postdata>.+?)\s+TOPSPEED\s+(?P<topspeed>.+)$", re.IGNORECASE)


def parse_postdata_card(
    pdf_path: str,
    races: list[Race],
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[ParseError]]:
    """
    Parse Postdata PDF using the XX backbone races as anchors.

    Returns:
        Tuple of (postdata_map, errors)
        postdata_map: {race_id: {runner_name: payload}}
    """
    postdata_map: dict[str, dict[str, dict[str, Any]]] = {}
    errors: list[ParseError] = []
    races_by_off_time = {_format_off_time(race): race for race in races}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for section in _extract_postdata_sections(page):
                    off_time = section["off_time"]
                    race = races_by_off_time.get(off_time)
                    if race is None:
                        continue
                    parsed = _parse_postdata_section(section["lines"], race)
                    if parsed:
                        postdata_map[race.race_id] = parsed
    except Exception as exc:
        errors.append(
            ParseError(
                severity="error",
                message=f"Failed to parse postdata PDF: {exc}",
                location="postdata_file",
            )
        )

    return postdata_map, errors


def _extract_postdata_sections(page: pdfplumber.page.Page) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for side in ("left", "right"):
        lines = _extract_column_lines(page, side=side)
        current_off_time: str | None = None
        current_lines: list[str] = []

        for line in lines:
            if _OFF_TIME_RE.match(line):
                if current_off_time and current_lines:
                    sections.append({"off_time": current_off_time, "lines": current_lines})
                current_off_time = line
                current_lines = []
                continue

            if current_off_time is not None:
                current_lines.append(line)

        if current_off_time and current_lines:
            sections.append({"off_time": current_off_time, "lines": current_lines})
    return sections


def _extract_column_lines(page: pdfplumber.page.Page, *, side: str) -> list[str]:
    midpoint = page.width / 2
    words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False)
    if side == "left":
        selected = [word for word in words if word["x0"] < midpoint - 5]
    else:
        selected = [word for word in words if word["x0"] >= midpoint - 5]

    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for word in selected:
        grouped[round(word["top"], 1)].append(word)

    lines: list[str] = []
    for top in sorted(grouped):
        parts = sorted(grouped[top], key=lambda item: item["x0"])
        line = " ".join(part["text"] for part in parts).strip()
        if line:
            lines.append(line)
    return lines


def _parse_postdata_section(lines: list[str], race: Race) -> dict[str, dict[str, Any]]:
    pick_line = next((line for line in lines if line.startswith("POSTDATA ") and " TOPSPEED " in line), None)
    postdata_pick_name = None
    topspeed_pick_name = None

    if pick_line:
        match = _PICK_LINE_RE.match(" ".join(pick_line.split()))
        if match:
            postdata_pick_name = _canonicalize_pick_name(match.group("postdata"), race)
            topspeed_pick_name = _canonicalize_pick_name(match.group("topspeed"), race)

    runner_rows: dict[str, dict[str, Any]] = {}
    for idx, line in enumerate(lines):
        runner_name = _match_runner_line(line, race)
        if runner_name is None:
            continue

        flags_line = _extract_flags_line(lines, idx)
        latest_rating = _extract_latest_rating(line)
        runner_rows[runner_name] = {
            "postdata_row": line,
            "postdata_flags_raw": flags_line,
            "postdata_positive_count": flags_line.count("✓") if flags_line else 0,
            "postdata_negative_count": flags_line.count("✘") if flags_line else 0,
            "postdata_unknown_count": flags_line.count("?") if flags_line else 0,
            "postdata_latest_rating": latest_rating,
            "postdata_pick_name": postdata_pick_name,
            "topspeed_pick_name": topspeed_pick_name,
            "postdata_file_source": "0011_XX",
        }

    for runner in race.runners:
        runner_name = normalize_horse_name(runner.name)
        payload = runner_rows.setdefault(runner_name, {"postdata_file_source": "0011_XX"})
        payload["postdata_pick_name"] = postdata_pick_name
        payload["topspeed_pick_name"] = topspeed_pick_name
        payload["postdata_pick"] = bool(postdata_pick_name and runner_name == postdata_pick_name)
        payload["topspeed_pick"] = bool(topspeed_pick_name and runner_name == topspeed_pick_name)

    return runner_rows


def _extract_flags_line(lines: list[str], index: int) -> str | None:
    if index == 0:
        return None
    candidate = lines[index - 1].strip()
    if not candidate:
        return None
    if any(char in candidate for char in ("✓", "✘", "?")) and "POSTDATA " not in candidate:
        return candidate
    return None


def _match_runner_line(line: str, race: Race) -> str | None:
    normalized_line = normalize_horse_name(line)
    if not re.search(r"-?\d+\s*$", line):
        return None

    for runner in sorted(race.runners, key=lambda item: len(item.name), reverse=True):
        runner_name = normalize_horse_name(runner.name)
        if runner_name in normalized_line:
            return runner_name
    return None


def _extract_latest_rating(line: str) -> int | None:
    numbers = re.findall(r"-?\d+", line)
    if not numbers:
        return None
    return int(numbers[-1])


def _canonicalize_pick_name(name: str, race: Race) -> str | None:
    normalized = normalize_horse_name(name)
    for runner in race.runners:
        runner_name = normalize_horse_name(runner.name)
        if normalized == runner_name:
            return runner_name
    for runner in race.runners:
        runner_name = normalize_horse_name(runner.name)
        if normalized in runner_name or runner_name in normalized:
            return runner_name
    return normalized or None


def _format_off_time(race: Race) -> str:
    return f"{race.off_time.hour}:{race.off_time.minute:02d}"
