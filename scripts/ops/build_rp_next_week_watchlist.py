#!/usr/bin/env python3
"""Build a simple archive-only Racing Post next-week watchlist."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "reports"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _lane(dossier: dict[str, Any]) -> str:
    flags = set(dossier.get("archive_flags") or [])
    if dossier.get("wind_surgery"):
        return "wind surgery return"
    if dossier.get("headgear_first_time"):
        return "first-time headgear"
    if "TRAINER_INTENT_SIGNAL" in flags:
        return "trainer intent quote"
    if "PEDIGREE_POSITIVE" in flags:
        return "pedigree positive"
    if int(dossier.get("tip_count") or 0) >= 7:
        return "market hype risk"
    if "INSUFFICIENT_PROFILE" in flags:
        return "unknown/unexposed"
    return "quiet profile positive"


def build(start_date: str | None, end_date: str | None, execute: bool) -> dict[str, Any]:
    day_dirs = sorted(p for p in PARSED_ROOT.glob("20*-*-*") if p.is_dir())
    rows: list[dict[str, Any]] = []
    repeats: dict[str, list[str]] = defaultdict(list)
    for day in day_dirs:
        date = day.name
        if start_date and date < start_date:
            continue
        if end_date and date > end_date:
            continue
        payload = _load(day / "horse_dossiers.json")
        for dossier in payload.get("dossiers") or []:
            horse = dossier.get("horse")
            if not horse:
                continue
            repeats[horse].append(date)
            rows.append({
                "date": date,
                "time": dossier.get("race_time"),
                "course": dossier.get("course"),
                "horse": horse,
                "lane": _lane(dossier),
                "flags": dossier.get("archive_flags") or [],
                "tip_count": dossier.get("tip_count") or 0,
                "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                "velo_scoring_allowed": False,
            })
    for row in rows:
        if len(set(repeats[row["horse"]])) > 1:
            row["lane"] = "future entry repeats"
    rows.sort(key=lambda r: (r["date"], str(r["time"] or ""), -int(r["tip_count"] or 0), r["horse"]))
    payload = {
        "generated_at": _utc_now(),
        "start_date": start_date,
        "end_date": end_date,
        "watchlist_count": len(rows),
        "scoring_impact": "NONE",
        "watchlist": rows,
    }
    if execute:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        out_md = REPORT_ROOT / "rp_next_week_watchlist_latest.md"
        lines = ["# RP Next Week Watchlist", "", f"- Items: `{len(rows)}`", "- Scoring impact: `NONE`", ""]
        for row in rows[:120]:
            lines.append(f"- {row['date']} {row['time']} {row['course']} - **{row['horse']}**: {row['lane']} ({', '.join(row['flags'])})")
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        payload["status"] = "PASS"
        payload["report_path"] = str(out_md)
    else:
        payload["status"] = "DRY_RUN"
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build archive-only RP next-week watchlist.")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.start_date, args.end_date, args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
