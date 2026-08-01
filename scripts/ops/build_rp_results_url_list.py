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
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = ROOT / "data" / "racing_post_account_raw"
URL_LIST_ROOT = ROOT / "data" / "racing_post_url_lists"
COVERAGE_THRESHOLD = 0.95

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


def _expected_race_count(date: str, manifest_path: Path) -> tuple[int, str]:
    """Independently establish how many races this date SHOULD produce.

    The capture manifest is a per-batch receipt written fresh by each
    collector run, so a later single-URL capture into the same label dir
    silently replaces a full morning manifest (root-caused 2026-07-31:
    a 1-URL Saratoga capture clobbered 2026-07-30's 37-race manifest, and
    Step 10A reported PASS while building one URL). Never trust the
    manifest's own count as its own check -- corroborate it against
    sources the collector does not overwrite.
    """
    url_list = URL_LIST_ROOT / f"rp_racecards_{date}.txt"
    if url_list.exists():
        lines = [ln for ln in url_list.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            return len(lines), f"rp_racecards_{date}.txt"

    # Fallback: the per-race racecard JSONs the morning capture left on disk.
    # Unique filenames, so unlike manifest.json these are never clobbered.
    card_files = list(manifest_path.parent.glob("*racecards*.json"))
    if card_files:
        return len(card_files), f"{manifest_path.parent.name}/*racecards*.json"

    return 0, "UNKNOWN"


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

    expected_races, expected_source = _expected_race_count(date, manifest_path)
    coverage = (len(results_urls) / expected_races) if expected_races else None

    output_path = URL_LIST_ROOT / f"rp_results_{date}.txt"
    payload = {
        "status": "DRY_RUN",
        "date": date,
        "capture_label": manifest_path.parent.name,
        "manifest_source": str(manifest_path),
        "racecard_captures": len(captures),
        "results_urls_built": len(results_urls),
        "expected_races": expected_races,
        "expected_races_source": expected_source,
        "coverage_ratio": round(coverage, 4) if coverage is not None else None,
        "coverage_threshold": COVERAGE_THRESHOLD,
        "duplicate_urls_removed": len(captures) - len(results_urls) - len(skipped),
        "skipped": skipped,
        "output": str(output_path),
        "urls": results_urls,
    }

    # Completeness gate -- mirrors sigma's 0.95 rule, but fires HERE, at the
    # first step of the evening, instead of three steps downstream.
    if expected_races == 0:
        payload["completeness_check"] = "UNVERIFIED_NO_EXPECTED_SOURCE"
    elif coverage < COVERAGE_THRESHOLD:
        payload["status"] = "FAIL"
        payload["completeness_check"] = "BLOCKED_INCOMPLETE_URL_LIST"
        payload["error"] = (
            f"Built {len(results_urls)} results URLs but {expected_races} races are "
            f"expected for {date} (source: {expected_source}). The capture manifest at "
            f"{manifest_path} is likely stale or clobbered by a later partial capture. "
            f"Not writing {output_path} -- a short list would silently blank sigma."
        )
        payload["recovery"] = (
            f"sed 's#/racecards/#/results/#' {URL_LIST_ROOT / f'rp_racecards_{date}.txt'} "
            f"> {output_path}   # then rerun EOD with --skip-results-capture=false"
        )
        return payload
    else:
        payload["completeness_check"] = "PASS"

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
    # Exit non-zero on failure so run_full_raceday_eod.py's critical=True check
    # actually stops the chain. Before 2026-07-31 this always exited 0, so even
    # the pre-existing "No racecard capture manifest found" FAIL was reported as
    # a passing step by the orchestrator.
    if result.get("status") not in ("PASS", "DRY_RUN"):
        sys.exit(1)


if __name__ == "__main__":
    main()
