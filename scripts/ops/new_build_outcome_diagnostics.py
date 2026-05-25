#!/usr/bin/env python3
"""CLI wrapper for New Build VELO outcome diagnostics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from new_build_velo.outcome_diagnostics import main


if __name__ == "__main__":
    raise SystemExit(main())
