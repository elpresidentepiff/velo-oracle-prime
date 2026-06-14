#!/usr/bin/env python3
"""
Parse pasted Racing Post statistics table text into structured rows.

This is for operator-provided/account-visible text exports. It does not browse
Racing Post, log in, or call any API.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_ROOT = ROOT / "data" / "racing_post_account_pastes"
DEFAULT_OUTPUT_ROOT = ROOT / "data" / "racing_post_account_parsed"
RANK_RE = re.compile(r"^\d+$")
PROFILE_MARKERS = {"View horse profile", "View sire profile", "View trainer profile"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _assert_repo_path(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if ROOT not in resolved.parents and resolved != ROOT:
        raise SystemExit(f"{label} must live under repo root: {ROOT}")
    return resolved


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line or line in PROFILE_MARKERS:
            continue
        if line == "Filter":
            continue
        lines.append(line)
    return lines


def _is_rank(line: str) -> bool:
    return bool(RANK_RE.fullmatch(line))


def _parse_money(value: str) -> float | None:
    value = value.replace("£", "").replace(",", "").strip()
    try:
        return float(value)
    except ValueError:
        return None


def _parse_percent(value: str) -> float | None:
    try:
        return float(value.replace("%", "").strip())
    except ValueError:
        return None


def _parse_record(value: str) -> tuple[int | None, int | None]:
    if "-" not in value:
        return None, None
    left, right = value.split("-", 1)
    try:
        return int(left), int(right)
    except ValueError:
        return None, None


def _parse_float(value: str) -> float | None:
    try:
        return float(value.replace("+", "").strip())
    except ValueError:
        return None


def parse_statistics_text(text: str, *, source_file: str | None = None, capture_date: str | None = None) -> dict[str, Any]:
    lines = _clean_lines(text)
    header = None
    rows: list[dict[str, Any]] = []
    idx = 0
    if lines and not _is_rank(lines[0]):
        header = lines[0]
        idx = 1

    while idx < len(lines):
        if not _is_rank(lines[idx]):
            idx += 1
            continue
        rank = int(lines[idx])
        chunk = lines[idx + 1 : idx + 13]
        if len(chunk) < 11:
            break

        horse_name = chunk[0]
        age = chunk[1]
        sex = chunk[2]
        country = chunk[3]
        record = chunk[4]
        strike_rate_text = chunk[5]
        sire = chunk[6]
        trainer = chunk[7]
        prize_money_text = chunk[8]
        profit_loss_text = chunk[9]
        rating_text = chunk[10]

        wins, runs = _parse_record(record)
        rows.append(
            {
                "source": "racing_post_statistics_paste",
                "source_file": source_file,
                "capture_date": capture_date,
                "rank": rank,
                "horse_name": horse_name,
                "age": int(age) if age.isdigit() else age,
                "sex": sex,
                "country": country,
                "record": record,
                "wins": wins,
                "runs": runs,
                "strike_rate_pct": _parse_percent(strike_rate_text),
                "sire_name": sire,
                "trainer_name": trainer,
                "prize_money": _parse_money(prize_money_text),
                "profit_loss": _parse_float(profit_loss_text),
                "rating": int(rating_text) if rating_text.isdigit() else rating_text,
                "requires_audit": True,
            }
        )
        idx += 12

    return {
        "generated_at": _utc_now(),
        "source": "racing_post_statistics_paste",
        "capture_date": capture_date,
        "source_file": source_file,
        "header": header,
        "rows_count": len(rows),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse pasted Racing Post statistics table text.")
    parser.add_argument("--input", required=True, help="Text file under repo root")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--output", default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    input_path = _assert_repo_path(Path(args.input), "input")
    output_path = (
        _assert_repo_path(Path(args.output), "output")
        if args.output
        else DEFAULT_OUTPUT_ROOT / args.date / "statistics_horses.json"
    )
    payload = parse_statistics_text(
        input_path.read_text(encoding="utf-8", errors="replace"),
        source_file=str(input_path),
        capture_date=args.date,
    )
    payload["status"] = "DRY_RUN"
    payload["output_path"] = str(output_path)
    payload["execute_required"] = True
    if args.execute:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        payload["status"] = "PASS"
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
