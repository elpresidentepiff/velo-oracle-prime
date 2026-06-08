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

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _find_manifest(date: str, capture_label: str | None = None) -> Path | None:
    if capture_label:
        manifest = RAW_ROOT / capture_label / "manifest.json"
        return manifest if manifest.exists() else None

    candidates = list(RAW_ROOT.glob(f"live-full-racepages-{date}*/manifest.json"))
    date_manifest = RAW_ROOT / date / "manifest.json"
    if date_manifest.exists():
        candidates.append(date_manifest)
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.parent.name))


def build_results_url_list(*, date: str, execute: bool, capture_label: str | None = None) -> dict:
    manifest_path = _find_manifest(date, capture_label)
    if not manifest_path:
        return {
            "status": "FAIL",
            "error": "No racecard capture manifest found",
            "capture_label": capture_label,
            "checked_glob": str(RAW_ROOT / f"live-full-racepages-{date}*" / "manifest.json"),
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    captures = manifest.get("captures", [])

    results_urls: list[str] = []
    seen_results_urls: set[str] = set()
    skipped: list[str] = []

    for capture in captures:
        src = capture.get("source_url", "")
        if not src:
            continue
        if "/racecards/" not in src:
            skipped.append(src)
            continue
        results_url = src.replace("/racecards/", "/results/")
        if results_url in seen_results_urls:
            continue
        seen_results_urls.add(results_url)
        results_urls.append(results_url)

    output_path = URL_LIST_ROOT / f"rp_results_{date}.txt"
    payload = {
        "status": "DRY_RUN",
        "date": date,
        "capture_label": manifest_path.parent.name,
        "manifest_source": str(manifest_path),
        "racecard_captures": len(captures),
        "results_urls_built": len(results_urls),
        "duplicate_urls_removed": len(captures) - len(results_urls) - len(skipped),
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
    parser.add_argument(
        "--capture-label",
        default=None,
        help="Exact morning race-page capture label. Defaults to newest matching manifest.",
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    result = build_results_url_list(
        date=args.date,
        execute=args.execute,
        capture_label=args.capture_label,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
