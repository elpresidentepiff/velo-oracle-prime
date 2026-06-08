#!/usr/bin/env python3
"""CLI wrapper for New Build VELO sandbox evaluator."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.evaluator import main


if __name__ == "__main__":
    raise SystemExit(main())
