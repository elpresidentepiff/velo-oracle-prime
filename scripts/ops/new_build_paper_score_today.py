#!/usr/bin/env python3
"""Build New Build paper-only champion scores for current cards."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.paper_scorer import build_paper_predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Build paper-only New Build predictions for current cards.")
    parser.add_argument("--execute", action="store_true", help="Write paper prediction artifacts.")
    parser.add_argument("--no-refresh-feed", action="store_true", help="Use existing current-card feed without refreshing.")
    parser.add_argument("--racecard-path", help="Score a specific standard racecard cache instead of archive upcoming cards.")
    parser.add_argument("--official-verdict-path", help="Compare paper race IDs against official Live VELO verdicts.")
    parser.add_argument("--final-card", action="store_true", help="Write final-card paper artifact names.")
    args = parser.parse_args()
    print(
        json.dumps(
            build_paper_predictions(
                execute=args.execute,
                refresh_feed=not args.no_refresh_feed,
                racecard_path=Path(args.racecard_path) if args.racecard_path else None,
                official_verdict_path=Path(args.official_verdict_path) if args.official_verdict_path else None,
                final_card=args.final_card,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
