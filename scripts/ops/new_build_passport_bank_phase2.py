#!/usr/bin/env python3
"""Build Passport Bank Phase 2 coverage, queue, and feature bridge."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.passport_bank import run_phase2


def main() -> None:
    parser = argparse.ArgumentParser(description="Build New Build Passport Bank Phase 2 artifacts.")
    parser.add_argument("--execute", action="store_true", help="Write reports, queue, and feature parquet.")
    args = parser.parse_args()
    print(json.dumps(run_phase2(execute=args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
