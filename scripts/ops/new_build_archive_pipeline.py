#!/usr/bin/env python3
"""CLI wrapper for the clean New Build VELO archive pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.archive_pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
