#!/usr/bin/env python3
"""Retired Racing API race-day entry point — fail closed.

This filename remains as a compatibility tombstone so stale Railway commands,
old bookmarks, or external schedulers produce an explicit governance failure
instead of an import error or, worse, silently restoring a retired supplier.

The governed cloud entry point is ``scripts/ops/rp_cloud_raceday.py``.
No supplier client, credentials, scoring module, or persistence code is
imported here.
"""
from __future__ import annotations

import sys


RETIRED_MESSAGE = (
    "BLOCKED: scripts/ops/run_cloud_raceday.py is retired by ONE_TRUTH. "
    "Use scripts/ops/rp_cloud_raceday.py with authenticated Racing Post evidence."
)


def main() -> int:
    print(RETIRED_MESSAGE, file=sys.stderr, flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
