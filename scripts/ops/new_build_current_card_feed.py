#!/usr/bin/env python3
"""Build New Build current-card Passport Feed."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.current_card_feed import build_current_card_feed


def main() -> None:
    parser = argparse.ArgumentParser(description="Build current-card Passport Feed for New Build.")
    parser.add_argument("--execute", action="store_true", help="Write feed and reports under data/new_build/.")
    parser.add_argument("--racecard-path", help="Optional standard racecard cache to build the feed from.")
    args = parser.parse_args()
    racecard_path = Path(args.racecard_path) if args.racecard_path else None
    if racecard_path and racecard_path.exists():
        # Standard cache keys the date as 'date'; the feed builder expects
        # 'race_date' (missing key sent it into the full passport bank and
        # produced a stale-dated feed on 2026-06-11 — 9,538 runners labelled
        # 2026_05_26). Normalize into a temp copy; source file untouched.
        rows = json.loads(racecard_path.read_text())
        races = rows if isinstance(rows, list) else rows.get("races", [])
        for r in races:
            if not r.get("race_date") and r.get("date"):
                r["race_date"] = r["date"]
            for runner in r.get("runners", []):
                if not runner.get("race_date") and r.get("race_date"):
                    runner["race_date"] = r["race_date"]
        fixed = racecard_path.with_suffix(".race_date_normalized.json")
        fixed.write_text(json.dumps(rows))
        racecard_path = fixed
    print(
        json.dumps(
            build_current_card_feed(
                execute=args.execute,
                racecard_path=racecard_path,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
