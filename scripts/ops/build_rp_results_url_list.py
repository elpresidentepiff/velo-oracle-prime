#!/usr/bin/env python3
"""
Build a Racing Post results URL list from an existing racecard capture manifest.

Replaces /racecards/ with /results/ in captured racecard source URLs.
The generated list is fed directly to racing_post_account_collector.py capture.

Usage:
    PYTHONPATH=. python scripts/ops/build_rp_results_url_list.py --date 2026-05-26 --execute

Then capture the results pages:
    PYTHONPATH=. python scripts/ops/racing_post_account_collector.py capture \\
        --url-list data/racing_post_url_lists/rp_results_2026-05-26.txt \\
        --date rp-results-2026-05-26 --execute --headed
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = ROOT / "data" / "racing_post_account_raw"
URL_LIST_ROOT = ROOT / "data" / "racing_post_url_lists"

# Capture folder names to check (in preference order)
MANIFEST_CANDIDATES = [
    "live-full-racepages-{date}",
    "{date}",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _find_manifest(date: str) -> Path | None:
    for pattern in MANIFEST_CANDIDATES:
        folder = RAW_ROOT / pattern.format(date=date)
        manifest = folder / "manifest.json"
        if manifest.exists():
            return manifest
    return None


def build_results_url_list(*, date: str, execute: bool) -> dict:
    manifest_path = _find_manifest(date)
    if not manifest_path:
        checked = [RAW_ROOT / p.format(date=date) for p in MANIFEST_CANDIDATES]
        return {
            "status": "FAIL",
            "error": "No racecard capture manifest found",
            "checked": [str(p) for p in checked],
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    captures = manifest.get("captures", [])

    results_urls: list[str] = []
    skipped: list[str] = []

    for capture in captures:
        src = capture.get("source_url", "")
        if not src:
            continue
        if "/racecards/" not in src:
            skipped.append(src)
            continue
        results_url = src.replace("/racecards/", "/results/")
        results_urls.append(results_url)

    output_path = URL_LIST_ROOT / f"rp_results_{date}.txt"
    payload = {
        "status": "DRY_RUN",
        "date": date,
        "manifest_source": str(manifest_path),
        "racecard_captures": len(captures),
        "results_urls_built": len(results_urls),
        "skipped": skipped,
        "output": str(output_path),
        "urls": results_urls,
    }

    if not execute:
        payload["execute_required"] = True
        return payload

    URL_LIST_ROOT.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(results_urls) + "\n", encoding="utf-8")
    payload["status"] = "PASS"
    payload["generated_at"] = _utc_now()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build RP results URL list from racecard capture manifest."
    )
    parser.add_argument("--date", required=True, help="YYYY-MM-DD race date")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    result = build_results_url_list(date=args.date, execute=args.execute)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
