#!/usr/bin/env python3
"""One-shot cloud probe: can Racing Post be logged into and captured from Railway?

Runs the same three things the laptop does, headless, with RP_EMAIL / RP_PASSWORD
from the environment: auto_login -> session health probe -> racecards index
capture. Prints a JSON verdict (never the password). Exit 0 always so the
verdict is readable in the deploy log; the verdict field says PASS or FAIL.
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ops.check_rp_session_health import probe  # noqa: E402
from scripts.ops.racing_post_account_collector import DEFAULT_PROFILE_DIR, auto_login  # noqa: E402


def main() -> int:
    date = datetime.datetime.now(datetime.timezone.utc)  # noqa: UP017 - container is py3.10.strftime("%Y-%m-%d")
    out: dict = {"date": date, "steps": {}}

    login = auto_login(DEFAULT_PROFILE_DIR, execute=True, headed=False, timeout_s=90)
    out["steps"]["auto_login"] = {
        k: login.get(k) for k in ("status", "final_url", "login_form_still_present", "page_text_head", "reason", "hint") if k in login
    }
    out["steps"]["auto_login"]["email_present"] = login.get("email_present")
    out["steps"]["auto_login"]["password_present"] = login.get("password_present")

    health = probe(DEFAULT_PROFILE_DIR)
    out["steps"]["session_probe"] = {k: health.get(k) for k in ("status", "reason", "is_logged", "http_status", "role")}

    cap = subprocess.run(
        [sys.executable, "scripts/ops/capture_index_headless.py", "--date", date],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    out["steps"]["index_capture"] = {"returncode": cap.returncode, "stdout": cap.stdout[-600:], "stderr": cap.stderr[-600:]}

    ok = (
        out["steps"]["session_probe"].get("status") == "PASS"
        and cap.returncode == 0
        and "WARNING" not in cap.stdout
    )
    out["verdict"] = "PASS" if ok else "FAIL"
    print(json.dumps(out, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
