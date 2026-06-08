#!/usr/bin/env python3
"""CLI wrapper for the New Build VELO clean replica loop."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.spine import main


if __name__ == "__main__":
    raise SystemExit(main())

