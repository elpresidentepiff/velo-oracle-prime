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
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ops.bounded_subprocess import StepTimeout, run_bounded, timeout_from_env  # noqa: E402

LONDON = ZoneInfo("Europe/London")
PROFILE = ROOT / "data" / "browser_profiles" / "racing_post_account"
RAW = ROOT / "data" / "racing_post_account_raw"


_DEFAULT_STEP_TIMEOUT_SECONDS = 900  # 15 min for one capture step: generous for a full RP capture
# pass, finite so a stale session or network stall fails loud instead of hanging a cron container
# forever (incident 2026-11-13: two manual runs sat at run_state='running' for 20+ min each).

# The last step is not one step: run_full_raceday.py runs about 35 of its own (parse, FormFav,
# passport top-up, scoring, every shadow lane, scorecard and artifact persist) and bounds each of
# them itself. Giving it the 15-minute capture limit killed the 2026-11-14 run 20 seconds before
# the canonical scorecards were persisted: scoring had finished, eight model lanes were lost. On a
# 36-race Saturday the passport top-up alone takes 12 minutes. This limit only has to catch a
# runner that stops making progress altogether.
_ORCHESTRATOR_TIMEOUT_SECONDS = 5400

# The service that owns the scheduled morning run (docs/current/PLATFORM_CONTROL_REGISTER.md).
# Two Railway services held the same 07:00 cron and this same start command; on 2026-11-14 both
# ran, competed for Racing Post (256 of 400 passport requests answered HTTP 406 in one of them)
# and raced each other to score the day.
_DEFAULT_MORNING_OWNER = "velo-rp-capture"


def _run(label: str, command: list[str], env: dict[str, str] | None = None, timeout: float | None = None) -> None:
    print(f"\n[CLOUD-RP] {label}: {' '.join(command)}", flush=True)
    try:
        returncode = run_bounded(
            label,
            command,
            cwd=ROOT,
            env={**os.environ, **env} if env else None,
            timeout=timeout or _DEFAULT_STEP_TIMEOUT_SECONDS,
        )
    except StepTimeout as exc:
        raise RuntimeError(
            f"{exc} (with every process it started). For a capture step this is usually a stale "
            f"RP session or a network stall: re-authenticate the Railway browser profile if it recurs."
        ) from exc
    if returncode:
        raise RuntimeError(f"{label} failed with exit code {returncode}")


def _not_the_morning_owner(
    rescore_reason: str | None, environ: dict[str, str] | os._Environ[str] = os.environ
) -> str | None:
    """Why this scheduled run must stand down, or None when it may proceed.

    Only a scheduled run on a Railway service other than the owner stands down. A run outside
    Railway (the laptop, CI) has no service name and proceeds. An authorised rescore proceeds on
    any service: it is a person asking for a rerun, and the rescore variable lives on
    velo-prime-scoring. VELO_MORNING_OWNER_SERVICE moves ownership without a code change.
    """
    service = (environ.get("RAILWAY_SERVICE_NAME") or "").strip()
    owner = (environ.get("VELO_MORNING_OWNER_SERVICE") or "").strip() or _DEFAULT_MORNING_OWNER
    if not service or service == owner or (rescore_reason or "").strip():
        return None
    return (
        f"service '{service}' is not the scheduled morning owner ('{owner}'); standing down so "
        f"the day is captured and scored once"
    )


def _trigger_source(rescore_reason: str | None, environ: dict[str, str] | os._Environ[str] = os.environ) -> str:
    """What the pipeline_runs row records as having started this run.

    The scoring service has no TRIGGER_SOURCE variable, so without this every scheduled morning run
    would be written as ``manual`` (the scorer's default) and the ledger could not tell the 07:00 cron
    from a hand-started run. An explicit TRIGGER_SOURCE still wins; an authorised rescore is a person
    asking for a rerun, not the schedule.
    """
    explicit = (environ.get("TRIGGER_SOURCE") or "").strip()
    if explicit:
        return explicit
    return "railway_manual" if (rescore_reason or "").strip() else "railway_cron"


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
    parser.add_argument(
        "--authorised-rescore-reason",
        default=os.getenv("VELO_AUTHORISED_RESCORE_REASON"),
        help="Explicit incident/reason forwarded to the governed scorer; prior PASS rows are preserved.",
    )
    parser.add_argument(
        "--capture-only",
        action="store_true",
        help="capture and archive published RP cards, then stop before parsing/scoring",
    )
    args = parser.parse_args()
    date_str = args.date or datetime.now(LONDON).date().isoformat()
    print(f"VELO CLOUD RP RACEDAY — {date_str}", flush=True)
    stand_down = _not_the_morning_owner(args.authorised_rescore_reason)
    if stand_down:
        print(f"[CLOUD-RP] SKIP — {stand_down}", flush=True)
        return 0
    print("executor=Railway source=RacingPost-HTML durable_truth=Supabase", flush=True)

    # FormFav is a mandatory pre-race enrichment gate.  Run it before opening
    # the Racing Post capture path so a cloud run cannot silently score from a
    # stale or missing enrichment packet.
    _run(
        "FormFav readiness gate",
        [
            sys.executable,
            "scripts/ops/formfav_readiness.py",
            "--date",
            date_str,
            "--countries",
            "gb,ie",
        ],
    )

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

    if args.capture_only:
        print(f"\n[CLOUD-RP] PASS — capture-only preparation completed for {date_str}", flush=True)
        return 0

    score = [
        sys.executable,
        "scripts/ops/run_full_raceday.py",
        "--date",
        date_str,
        "--execute",
        "--skip-capture",
    ]
    if args.authorised_rescore_reason:
        score.extend(["--authorised-rescore-reason", args.authorised_rescore_reason])
    if args.no_notify:
        score.append("--no-notify")
    _run(
        "canonical FormFav-first parse/score/persist",
        score,
        env={"TRIGGER_SOURCE": _trigger_source(args.authorised_rescore_reason)},
        timeout=timeout_from_env("RP_CLOUD_ORCHESTRATOR_TIMEOUT_SECONDS", _ORCHESTRATOR_TIMEOUT_SECONDS),
    )
    print(f"\n[CLOUD-RP] PASS — canonical race-day pipeline completed for {date_str}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
