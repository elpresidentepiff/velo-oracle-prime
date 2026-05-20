from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def get_commit_sha() -> str:
    for key in ("RAILWAY_GIT_COMMIT_SHA", "GIT_COMMIT_SHA", "COMMIT_SHA"):
        value = (os.getenv(key) or "").strip()
        if value:
            return value[:40]
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def _telegram_truth_path(date_str: str) -> Path:
    return DATA / f"telegram_delivery_truth_{date_str.replace('-', '_')}.json"


def append_telegram_event(
    *,
    date_str: str,
    service: str,
    event_type: str,
    sent: bool,
    notify_enabled: bool,
    message_preview: str,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = _telegram_truth_path(date_str)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {"date": date_str, "events": []}
    else:
        payload = {"date": date_str, "events": []}

    event = {
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "service": service,
        "event_type": event_type,
        "sent": bool(sent),
        "notify_enabled": bool(notify_enabled),
        "message_preview": (message_preview or "")[:240],
        "error": (error or "")[:240] if error else None,
        "extra": extra or {},
    }
    payload.setdefault("events", []).append(event)

    service_events = [row for row in payload["events"] if row.get("service") == service]
    sent_count = sum(1 for row in service_events if row.get("sent"))
    failed_count = sum(1 for row in service_events if row.get("notify_enabled") and not row.get("sent"))
    payload.setdefault("summary", {})[service] = {
        "events": len(service_events),
        "sent_count": sent_count,
        "failed_count": failed_count,
        "notify_enabled_any": any(row.get("notify_enabled") for row in service_events),
        "status": (
            "DISABLED"
            if not any(row.get("notify_enabled") for row in service_events)
            else "PASS"
            if failed_count == 0 and sent_count > 0
            else "FAIL"
        ),
        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return event


def telegram_truth_status(date_str: str) -> dict[str, Any]:
    path = _telegram_truth_path(date_str)
    if not path.exists():
        return {"status": "UNTRACKED", "path": str(path), "summary": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "ERROR", "path": str(path), "summary": {}}
    summary = payload.get("summary", {})
    if not summary:
        status = "UNTRACKED"
    elif all(row.get("status") == "DISABLED" for row in summary.values()):
        status = "DISABLED"
    elif any(row.get("status") == "FAIL" for row in summary.values()):
        status = "FAIL"
    elif any(row.get("status") == "PASS" for row in summary.values()):
        status = "PASS"
    else:
        status = "UNTRACKED"
    return {"status": status, "path": str(path), "summary": summary}
