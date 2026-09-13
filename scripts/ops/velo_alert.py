"""Send a VELO operational alert somewhere that survives being ignored.

Why this exists
---------------
Between 2026-09-04 and 2026-09-07 the daily wrapper aborted six consecutive
times on a dead Racing Post session. It was not silent: velo_daily.sh raised a
Windows balloon tip on every abort and recorded ABORTED_SESSION in
velo_daily_status.json each time. Three race days were still lost.

Two reasons, and neither was a missing alert:

  1. A 15-second toast at 07:00 on one machine is a rumour, not an alert. It
     leaves no trace, so an unread one is indistinguishable from one that was
     never raised.
  2. Nothing counted. The status file holds only the LAST run of each phase, so
     the sixth identical abort looked exactly like the first. A system that
     cannot tell day one from day four cannot escalate, and escalation is the
     only thing that would have changed the outcome.

So this sends to Telegram, which persists and reaches a phone, AND it records
its own delivery outcome to disk. An alert that fails to send must not fail
quietly - that just moves the silence one layer down.

Usage:
    velo_alert.py --title "VELO morning did not run" --body "..." [--severity critical]

Never raises. Exit code is 0 on delivery, 1 on failure, and the caller is free
to ignore both - but the attempt is always written to
data/reports/velo_alert_log.jsonl either way.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALERT_LOG = ROOT / "data" / "reports" / "velo_alert_log.jsonl"

SEVERITY_PREFIX = {
    "info": "VELO",
    "warning": "WARNING - VELO",
    "critical": "CRITICAL - VELO",
}


def _load_env() -> None:
    """Reuse the repo's env loader so this behaves like every other script."""
    try:
        sys.path.insert(0, str(ROOT))
        from app.core.runtime_env import load_optional_env_file

        load_optional_env_file(ROOT / ".env")
    except Exception:
        # Fall back to a minimal .env parse rather than give up on the alert.
        env_path = ROOT / ".env"
        if not env_path.exists():
            return
        for line in env_path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _record(entry: dict) -> None:
    try:
        ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ALERT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Disk problems must not turn an alert into a crash.


def send(title: str, body: str, severity: str = "warning") -> bool:
    _load_env()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    prefix = SEVERITY_PREFIX.get(severity, SEVERITY_PREFIX["warning"])
    text = f"{prefix}\n\n{title}\n\n{body}"
    entry = {
        "sent_at": datetime.now().astimezone().isoformat(),
        "severity": severity,
        "title": title,
        "body": body,
        "delivered": False,
        "error": None,
    }

    if not token or not chat_id:
        entry["error"] = "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing from environment"
        _record(entry)
        print(entry["error"], file=sys.stderr)
        return False

    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            entry["delivered"] = 200 <= response.status < 300
            if not entry["delivered"]:
                entry["error"] = f"HTTP {response.status}"
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        entry["error"] = f"{type(exc).__name__}: {exc}"

    _record(entry)
    if entry["delivered"]:
        print(f"Alert delivered: {title}")
    else:
        print(f"Alert NOT delivered ({entry['error']}): {title}", file=sys.stderr)
    return bool(entry["delivered"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a VELO operational alert.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument(
        "--severity", default="warning", choices=sorted(SEVERITY_PREFIX)
    )
    args = parser.parse_args()
    return 0 if send(args.title, args.body, args.severity) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # An alerting path must never be the thing that crashes.
        print(f"velo_alert failed unexpectedly: {exc}", file=sys.stderr)
        sys.exit(1)
