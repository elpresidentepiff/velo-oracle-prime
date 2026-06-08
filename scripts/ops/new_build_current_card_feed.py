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
    print(
        json.dumps(
            build_current_card_feed(
                execute=args.execute,
                racecard_path=Path(args.racecard_path) if args.racecard_path else None,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
