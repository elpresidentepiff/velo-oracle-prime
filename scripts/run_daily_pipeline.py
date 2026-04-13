"""
run_daily_pipeline.py
----------------------
VÉLØ daily pipeline orchestrator.

Step 1: Ingest today's racecards + update racing profiles
Step 2: Build RPDC profiles and tag today's runners
Step 3: Run VÉLØ Prime scoring (run_prime_today.py)
Step 4: Run sigma results for yesterday (run_results_sigma.py)

Usage:
    python scripts/run_daily_pipeline.py
    python scripts/run_daily_pipeline.py --skip-sigma    # skip yesterday's results
    python scripts/run_daily_pipeline.py --rpdc-only     # just RPDC refresh, no scoring

Railway cron: run once daily at 08:00 UK time
"""

import argparse
import subprocess
import sys
import os
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run(cmd: list[str], label: str) -> bool:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable] + cmd,
        cwd=str(ROOT),
        capture_output=False,
    )
    ok = result.returncode == 0
    print(f"\n  [{label}] {'OK' if ok else 'FAILED'} (exit {result.returncode})")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-sigma",  action="store_true", help="Skip yesterday's sigma results")
    parser.add_argument("--rpdc-only",   action="store_true", help="Only run RPDC refresh")
    parser.add_argument("--date",        type=str, default="", help="Override scoring date YYYY-MM-DD")
    args = parser.parse_args()

    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    results = {}

    if args.rpdc_only:
        results["rpdc_cards"] = run(
            ["scripts/ingest_racing_profiles.py", "--today-cards", "--rate", "1"],
            "RPDC: ingest today's cards"
        )
        results["rpdc_tags"] = run(
            ["scripts/build_rpdc_profiles.py", "--today"],
            "RPDC: build profiles + tag today"
        )
    else:
        # Step 1: Cards + profiles
        results["cards"] = run(
            ["scripts/ingest_racing_profiles.py", "--today-cards", "--rate", "1"],
            "Step 1: Ingest today's racecards"
        )

        # Step 2: RPDC
        results["rpdc"] = run(
            ["scripts/build_rpdc_profiles.py", "--today"],
            "Step 2: RPDC — build profiles + tag today's runners"
        )

        # Step 3: VÉLØ Prime scoring
        score_cmd = ["scripts/run_prime_today.py"]
        if args.date:
            score_cmd += ["--date", args.date]
        results["scoring"] = run(score_cmd, "Step 3: VÉLØ Prime scoring")

        # Step 4: Sigma results for yesterday
        if not args.skip_sigma:
            results["sigma"] = run(
                ["scripts/run_results_sigma.py", "--date", yesterday],
                f"Step 4: Sigma results for {yesterday}"
            )

    # Summary
    print(f"\n{'='*60}")
    print("  DAILY PIPELINE SUMMARY")
    print(f"{'='*60}")
    all_ok = True
    for step, ok in results.items():
        status = "OK" if ok else "FAILED"
        print(f"  {step:<20} {status}")
        if not ok:
            all_ok = False

    print(f"\n  Overall: {'PASS' if all_ok else 'DEGRADED'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
