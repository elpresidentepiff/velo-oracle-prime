"""
Racing Post PDF Parser - Spotlight Parser
Parse F_0016_XX files (standalone spotlight comments + race verdicts).
"""

from __future__ import annotations

import re
from typing import Any

import pdfplumber

from .normalize import normalize_horse_name
from .types import ParseError, Race

_OFF_TIME_RE = re.compile(r"^(?P<off>\d{1,2}\.\d{2})\b")
_RUNNER_HEADER_RE = re.compile(r"^(?P<name>.+?)\s+\d+\s+\d{1,2}-\d{1,2}[a-z0-9]*\b", re.IGNORECASE)


def parse_spotlight_card(
    pdf_path: str,
    races: list[Race],
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[ParseError]]:
    """
    Parse standalone spotlight PDF using the XX backbone races as anchors.

    Returns:
        Tuple of (spotlight_map, errors)
        spotlight_map: {race_id: {runner_name: payload}}
    """
    spotlight_map: dict[str, dict[str, dict[str, Any]]] = {}
    errors: list[ParseError] = []
    races_by_off_time = {_format_off_time(race): race for race in races}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for _page_num, page in enumerate(pdf.pages, start=1):
                lines = [line.strip() for line in (page.extract_text() or "").splitlines() if line and line.strip()]
                off_time = _extract_off_time(lines)
                if not off_time:
                    continue

                race = races_by_off_time.get(off_time)
                if race is None:
                    continue

                spotlight_map[race.race_id] = _parse_spotlight_page(lines, race)
    except Exception as exc:
        errors.append(
            ParseError(
                severity="error",
                message=f"Failed to parse spotlight PDF: {exc}",
                location="spotlight_file",
            )
        )

    return spotlight_map, errors


def _parse_spotlight_page(lines: list[str], race: Race) -> dict[str, dict[str, Any]]:
    verdict = _extract_spotlight_verdict(lines)
    body_lines = _extract_runner_body(lines)
    header_rows = _extract_runner_headers(body_lines, race)

    payloads: dict[str, dict[str, Any]] = {}
    for index, (line_idx, runner_name, header_line) in enumerate(header_rows):
        end_idx = header_rows[index + 1][0] if index + 1 < len(header_rows) else len(body_lines)
        comment_lines = [line.strip() for line in body_lines[line_idx + 1 : end_idx] if line.strip()]
        comment = " ".join(comment_lines).strip() or None
        payloads[runner_name] = {
            "comment": comment,
            "spotlight_race_verdict": verdict,
            "spotlight_header_line": header_line,
            "spotlight_file_source": "0016_XX",
        }

    # Every runner can still inherit the race verdict, even if their prose block failed to parse.
    if verdict:
        for runner in race.runners:
            runner_name = normalize_horse_name(runner.name)
            payload = payloads.setdefault(runner_name, {})
            payload.setdefault("spotlight_race_verdict", verdict)
            payload.setdefault("spotlight_file_source", "0016_XX")

    return payloads


def _extract_off_time(lines: list[str]) -> str | None:
    for line in lines:
        match = _OFF_TIME_RE.match(line)
        if match:
            return match.group("off")
    return None


def _extract_runner_body(lines: list[str]) -> list[str]:
    start_idx = next((idx + 1 for idx, line in enumerate(lines) if line == "Trainer Jockey SP OR TS RPR"), None)
    if start_idx is None:
        return []

    body: list[str] = []
    for line in lines[start_idx:]:
        if line.startswith("SPOTLIGHT VERDICT") or line.startswith("Page "):
            break
        body.append(line)
    return body


def _extract_spotlight_verdict(lines: list[str]) -> str | None:
    verdict_idx = next((idx for idx, line in enumerate(lines) if line.startswith("SPOTLIGHT VERDICT")), None)
    if verdict_idx is None:
        return None

    verdict_lines: list[str] = []
    first_line = lines[verdict_idx]
    _, _, remainder = first_line.partition("SPOTLIGHT VERDICT")
    if remainder.strip():
        verdict_lines.append(remainder.strip())

    for line in lines[verdict_idx + 1 :]:
        if line.startswith("Page "):
            break
        verdict_lines.append(line.strip())

    verdict = " ".join(part for part in verdict_lines if part)
    verdict = " ".join(verdict.split())
    return verdict or None


def _extract_runner_headers(body_lines: list[str], race: Race) -> list[tuple[int, str, str]]:
    headers: list[tuple[int, str, str]] = []
    name_map = {normalize_horse_name(runner.name): runner.name for runner in race.runners}

    for index, line in enumerate(body_lines):
        runner_name = _match_runner_header(line, name_map)
        if runner_name is not None:
            headers.append((index, runner_name, line))

    return headers


def _match_runner_header(line: str, name_map: dict[str, str]) -> str | None:
    match = _RUNNER_HEADER_RE.match(line)
    if not match:
        return None

    normalized_header = normalize_horse_name(match.group("name"))
    if normalized_header in name_map:
        return normalized_header

    for candidate in sorted(name_map, key=len, reverse=True):
        if normalized_header.startswith(candidate):
            return candidate
    return None


def _format_off_time(race: Race) -> str:
    return f"{race.off_time.hour}.{race.off_time.minute:02d}"
