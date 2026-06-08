#!/usr/bin/env python3
"""
Build Racing Post horse profile URL lists from local account captures.

Reads saved HTML only. It does not browse, scrape, or call Racing Post.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = ROOT / "data" / "racing_post_account_raw"
URL_LIST_ROOT = ROOT / "data" / "racing_post_url_lists"
PROFILE_RE = re.compile(r'["\'](?P<href>/profile/horse/\d+/[^"\']+?/(?:form|entries|stats|quotes|pedigree|sales|notes)?[^"\']*)["\']')


def _assert_repo_path(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if ROOT not in resolved.parents and resolved != ROOT:
        raise SystemExit(f"{label} must live under repo root: {ROOT}")
    return resolved


def _normalise_profile_url(href: str, tab: str) -> str:
    url = urljoin("https://www.racingpost.com", href.split("?")[0].rstrip("/"))
    parts = url.split("/")
    try:
        idx = parts.index("horse")
        base = "/".join(parts[: idx + 3])
    except ValueError:
        base = url.rstrip("/")
    return f"{base}/{tab}"


def build_urls(*, capture_date: str, tab: str, include_tabs: list[str], output: Path, execute: bool) -> dict:
    raw_day_dir = _assert_repo_path(RAW_ROOT / capture_date, "raw_day_dir")
    output = _assert_repo_path(output, "output")
    if not raw_day_dir.exists():
        raise SystemExit(f"Missing raw capture day dir: {raw_day_dir}")

    html_files = sorted(raw_day_dir.glob("*.html"))
    urls: dict[str, dict] = {}
    tabs_to_emit = include_tabs or [tab]

    for html_path in html_files:
        html = html_path.read_text(encoding="utf-8", errors="replace")
        for match in PROFILE_RE.finditer(html):
            href = match.group("href")
            form_url = _normalise_profile_url(href, "form")
            horse_key = "/".join(form_url.rstrip("/").split("/")[-3:-1])
            urls.setdefault(
                horse_key,
                {
                    "source_files": [],
                    "urls": [],
                },
            )
            urls[horse_key]["source_files"].append(str(html_path))
            for emit_tab in tabs_to_emit:
                profile_url = _normalise_profile_url(href, emit_tab)
                if profile_url not in urls[horse_key]["urls"]:
                    urls[horse_key]["urls"].append(profile_url)

    flat_urls = sorted({url for item in urls.values() for url in item["urls"]})
    payload = {
        "capture_date": capture_date,
        "html_files_seen": len(html_files),
        "unique_horses": len(urls),
        "url_count": len(flat_urls),
        "tab": tab,
        "include_tabs": tabs_to_emit,
        "output": str(output),
        "urls": flat_urls,
        "execute_required": True,
        "status": "DRY_RUN",
    }
    if execute:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(flat_urls) + ("\n" if flat_urls else ""), encoding="utf-8")
        payload["status"] = "PASS"
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RP profile URL lists from local account captures.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--tab", default="form", choices=["form", "entries", "stats", "quotes", "pedigree", "sales", "notes"])
    parser.add_argument(
        "--include-tab",
        action="append",
        default=[],
        choices=["form", "entries", "stats", "quotes", "pedigree", "sales", "notes"],
        help="Emit one URL per horse per tab. Repeatable. Defaults to --tab only.",
    )
    parser.add_argument("--output", default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    output = Path(args.output) if args.output else URL_LIST_ROOT / f"rp_profiles_{args.date}_{args.tab}.txt"
    payload = build_urls(
        capture_date=args.date,
        tab=args.tab,
        include_tabs=args.include_tab,
        output=output,
        execute=args.execute,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
