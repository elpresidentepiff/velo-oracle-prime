#!/usr/bin/env python3
"""Cloud-owned Racing Post capture and governed race-day handoff.

This is the Railway replacement for the laptop-only browser step.  It logs in
with the already-configured Railway RP credentials, captures the RP index and
tomorrow card, builds the normal URL lists, captures every listed race page,
then hands the raw capture to the canonical runner with ``--skip-capture``.
The canonical runner still owns FormFav-first readiness, parsing, validation,
scoring, Supabase persistence, and all existing gates.

No Racing API is used here.  The only live card source is Racing Post HTML.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LONDON = ZoneInfo("Europe/London")
PROFILE = ROOT / "data" / "browser_profiles" / "racing_post_account"
RAW = ROOT / "data" / "racing_post_account_raw"


def _run(label: str, command: list[str]) -> None:
    print(f"\n[CLOUD-RP] {label}: {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")


def _capture_index_and_tomorrow(date_str: str) -> None:
    """Use the same persistent context for login and capture.

    Racing Post login state is not reliable after closing a fresh container
    context, so this deliberately keeps one context alive for both operations.
    """
    from playwright.sync_api import sync_playwright

    from scripts.ops.rp_cloud_probe import cloud_capture, cloud_login

    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.firefox.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=True,
            viewport={"width": 1400, "height": 1000},
            firefox_user_prefs={"gfx.webrender.enabled": False, "gfx.webrender.all": False},
        )
        login = cloud_login(context)
        print(f"[CLOUD-RP] login status={login.get('status')}", flush=True)
        if login.get("status") != "PASS":
            context.close()
            raise RuntimeError(f"Racing Post cloud login failed: {login.get('reason') or login}")
        capture = cloud_capture(context, date_str)
        context.close()

    bad = [
        label
        for label, info in capture.items()
        if info.get("error") or int(info.get("kb") or 0) < 50
    ]
    if bad:
        raise RuntimeError(f"Racing Post cloud index capture failed/small: {bad}")
    print(f"[CLOUD-RP] index capture PASS pages={len(capture)}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Race date YYYY-MM-DD; defaults to London today")
    parser.add_argument("--no-notify", action="store_true")
    args = parser.parse_args()
    date_str = args.date or datetime.now(LONDON).date().isoformat()
    print(f"VELO CLOUD RP RACEDAY — {date_str}", flush=True)
    print("executor=Railway source=RacingPost-HTML durable_truth=Supabase", flush=True)

    _capture_index_and_tomorrow(date_str)

    _run(
        "build UK/IRE race URL list",
        [
            sys.executable,
            "scripts/ops/build_racing_post_racecard_url_list.py",
            "--date",
            date_str,
            "--target-date",
            date_str,
            "--execute",
        ],
    )
    url_list = ROOT / "data" / "racing_post_url_lists" / f"rp_racecards_{date_str}.txt"
    if not url_list.exists() or not url_list.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"No Racing Post race URLs built for {date_str}: {url_list}")

    _run(
        "capture UK/IRE race pages",
        [
            sys.executable,
            "scripts/ops/racing_post_account_collector.py",
            "capture",
            "--date",
            date_str,
            "--url-list",
            str(url_list),
            "--profile-dir",
            str(PROFILE),
            "--output-dir",
            str(RAW),
            "--delay-seconds",
            os.getenv("RP_CLOUD_CAPTURE_DELAY_SECONDS", "1.5"),
            "--execute",
        ],
    )

    # Preserve the canonical supplementary capture path for venues that the
    # hand-maintained jurisdiction allowlist classifies as international.
    intl_list = ROOT / "data" / "racing_post_url_lists" / f"rp_racecards_{date_str}_intl.txt"
    if intl_list.exists() and intl_list.read_text(encoding="utf-8").strip():
        _run(
            "capture supplementary RP pages",
            [
                sys.executable,
                "scripts/ops/racing_post_account_collector.py",
                "capture",
                "--date",
                date_str,
                "--url-list",
                str(intl_list),
                "--profile-dir",
                str(PROFILE),
                "--output-dir",
                str(RAW),
                "--delay-seconds",
                os.getenv("RP_CLOUD_CAPTURE_DELAY_SECONDS", "1.5"),
                "--execute",
            ],
        )

    score = [
        sys.executable,
        "scripts/ops/run_full_raceday.py",
        "--date",
        date_str,
        "--execute",
        "--skip-capture",
    ]
    if args.no_notify:
        score.append("--no-notify")
    _run("canonical FormFav-first parse/score/persist", score)
    print(f"\n[CLOUD-RP] PASS — canonical race-day pipeline completed for {date_str}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
