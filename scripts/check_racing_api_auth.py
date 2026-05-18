"""
Racing API Credential Smoke Test
==================================
Verify RACING_API credentials before race-day execution.
Run this first so a 401 is discovered before any scoring pipeline starts.

Exit codes:
  0 — AUTH_OK
  1 — AUTH_FAIL_401  (credentials stale or rotated — update RACING_API_PASSWORD)
  2 — AUTH_FAIL_OTHER (network issue, DNS, unexpected HTTP status)
  3 — AUTH_MISSING   (env vars not set)

Usage:
    python scripts/check_racing_api_auth.py
"""

import base64
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.runtime_env import load_optional_env_file

_PROBE_URL = "https://api.theracingapi.com/v1/racecards/standard?day=today"
_TIMEOUT = 15


def check_auth() -> tuple[str, int]:
    """Return (status_string, exit_code)."""
    load_optional_env_file(ROOT / ".env")

    user = os.getenv("RACING_API_USERNAME", "").strip()
    password = os.getenv("RACING_API_PASSWORD", "").strip()

    if not user or not password:
        msg = "AUTH_MISSING — RACING_API_USERNAME or RACING_API_PASSWORD not set in env"
        return msg, 3

    creds = base64.b64encode(f"{user}:{password}".encode()).decode()
    req = urllib.request.Request(
        _PROBE_URL,
        headers={
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
            "User-Agent": "VeloPrime/1.0",
        },
    )

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=_TIMEOUT) as resp:
            if resp.status == 200:
                return "AUTH_OK", 0
            return f"AUTH_FAIL_OTHER — unexpected HTTP {resp.status}", 2
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return (
                "AUTH_FAIL_401 — credentials rejected (stale password?). "
                "Update RACING_API_PASSWORD in .env and Railway env vars.",
                1,
            )
        return f"AUTH_FAIL_OTHER — HTTP {e.code} {e.reason}", 2
    except urllib.error.URLError as e:
        return f"AUTH_FAIL_OTHER — network error: {e.reason}", 2
    except Exception as e:
        return f"AUTH_FAIL_OTHER — {e}", 2


if __name__ == "__main__":
    status, code = check_auth()
    print(status)
    sys.exit(code)
