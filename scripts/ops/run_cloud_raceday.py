#!/usr/bin/env python3
"""Cloud-native VELO race-day bootstrap for Railway cron.

The laptop is not part of this path.

Flow:
  1. Fetch the authenticated Racing API Standard card for the London race date.
  2. Persist that card to the container's scratch data directory with explicit
     source provenance.
  3. Build the dated New Build passport feed from the checked-in passport bank.
  4. Execute the canonical Prime scorer, which persists durable truth to Supabase.

Racing Post HTML/PDF data may enrich later runs, but is not an execution
dependency for the baseline daily Railway run.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.racecard_loader import fetch_api_racecards

LONDON = ZoneInfo("Europe/London")


def _date_today_london() -> str:
    return datetime.now(LONDON).date().isoformat()


def _write_api_cache(date_str: str, races: list[dict]) -> Path:
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / f"racecards_{date_str.replace('-', '_')}_standard.json"
    temp = target.with_suffix(".json.tmp")
    payload = {
        "_velo_source": "racing_api_standard",
        "_requested_date": date_str,
        "_fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "_runtime": "railway-cloud-raceday",
        "racecards": races,
    }
    temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, target)
    return target


def _run(label: str, command: list[str]) -> None:
    print(f"\n[CLOUD] {label}: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Race date YYYY-MM-DD; defaults to Europe/London today")
    parser.add_argument("--no-notify", action="store_true", help="Disable Telegram sends from Prime")
    args = parser.parse_args()

    date_str = args.date or _date_today_london()
    print(f"VELO CLOUD RACEDAY — {date_str}", flush=True)
    print("executor=Railway source=RacingAPI-Standard durable_truth=Supabase", flush=True)

    races = fetch_api_racecards(date_str)
    runner_count = sum(len(r.get("runners", [])) for r in races)
    if not races or runner_count == 0:
        raise RuntimeError(f"Racing API card unusable: races={len(races)} runners={runner_count}")

    cache_path = _write_api_cache(date_str, races)
    print(
        f"[CLOUD] card ready: races={len(races)} runners={runner_count} cache={cache_path.name}",
        flush=True,
    )

    # Prime's readiness contract requires the dated passport feed before
    # scoring. Build it inside this same ephemeral Railway container.
    _run(
        "passport feed",
        [
            sys.executable,
            "scripts/ops/new_build_current_card_feed.py",
            "--execute",
            "--racecard-path",
            str(cache_path),
        ],
    )

    feed_path = (
        ROOT
        / "data"
        / "new_build"
        / "current_cards"
        / f"current_card_passport_feed_{date_str.replace('-', '_')}.jsonl"
    )
    if not feed_path.exists() or feed_path.stat().st_size == 0:
        raise RuntimeError(f"Passport readiness feed missing/empty after build: {feed_path}")

    score_cmd = [
        sys.executable,
        "scripts/ops/run_prime_today.py",
        "--date",
        date_str,
        "--source",
        "cache",
        "--allow-missing-pdfs",
    ]
    if args.no_notify:
        score_cmd.append("--no-notify")
    _run("Prime scoring", score_cmd)

    print(f"\n[CLOUD] PASS — Railway completed canonical scoring for {date_str}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n[CLOUD] FAIL — {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise
