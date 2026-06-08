#!/usr/bin/env python3
"""
Build Racing Post racecard URL lists from a local captured racecards index.

Reads saved HTML only. It does not browse or call Racing Post.

Outputs two files:
  - rp_racecards_YYYY-MM-DD.txt         — UK/IRE only, deduplicated by race ID
  - rp_racecards_YYYY-MM-DD_intl.txt    — international only (future use, not fed to VELO)
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = ROOT / "data" / "racing_post_account_raw"
URL_LIST_ROOT = ROOT / "data" / "racing_post_url_lists"

# UK and IRE venue slugs as they appear in Racing Post URLs.
# When a new UK/IRE venue appears, add it here.
UK_IRE_VENUES = {
    "ascot", "ayr", "bath", "beverley", "brighton", "carlisle", "catterick",
    "chelmsford-city", "cheltenham", "chester", "chepstow", "doncaster",
    "epsom", "exeter", "fakenham", "ffos-las", "goodwood", "hamilton",
    "haydock", "hereford", "hexham", "huntingdon", "kempton", "leicester",
    "lingfield", "ludlow", "market-rasen", "musselburgh", "newbury",
    "newcastle", "newmarket", "nottingham", "perth", "plumpton", "pontefract",
    "redcar", "ripon", "salisbury", "sandown", "southwell", "stratford",
    "taunton", "thirsk", "towcester", "uttoxeter", "warwick", "wetherby",
    "wincanton", "windsor", "wolverhampton", "worcester", "yarmouth", "york",
    # Ireland
    "ballinrobe", "bellewstown", "clonmel", "cork", "curragh", "downpatrick",
    "dundalk", "fairyhouse", "galway", "gowran-park", "kilbeggan", "killarney",
    "laytown", "leopardstown", "limerick", "listowel", "naas", "navan",
    "punchestown", "roscommon", "sligo", "thurles", "tipperary", "tralee",
    "tramore", "wexford",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _assert_repo_path(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if ROOT not in resolved.parents and resolved != ROOT:
        raise SystemExit(f"{label} must live under repo root: {ROOT}")
    return resolved


def _race_id_from_url(url: str) -> str | None:
    """Extract the numeric race ID from a RP racecard URL."""
    m = re.search(r"/racecards/\d+/[^/]+/\d{4}-\d{2}-\d{2}/(\d+)", url)
    return m.group(1) if m else None


def _venue_slug_from_url(url: str) -> str | None:
    """Extract the venue slug from a RP racecard URL."""
    m = re.search(r"/racecards/\d+/([^/]+)/\d{4}-\d{2}-\d{2}/\d+", url)
    return m.group(1) if m else None


def _is_race_url(href: str, capture_date: str) -> bool:
    if not href.startswith("/racecards/"):
        return False
    if f"/{capture_date}/" not in href:
        return False
    if href.endswith("/runners-index/"):
        return False
    parts = [p for p in href.split("/") if p]
    return len(parts) >= 5 and parts[0] == "racecards" and parts[3] == capture_date and parts[4].isdigit()


def build_racecard_urls(*, capture_date: str, target_date: str, output: Path, execute: bool) -> dict:
    raw_day_dir = _assert_repo_path(RAW_ROOT / capture_date, "raw_day_dir")
    output = _assert_repo_path(output, "output")
    html_files = sorted(raw_day_dir.glob("*.html"))

    # url -> metadata dict. Keyed by full URL to deduplicate across extraction methods.
    # We further deduplicate by race ID so duplicate links on the index page don't create duplicates.
    urls: dict[str, dict] = {}

    for html_path in html_files:
        html_content = html_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Standard anchors
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].split("?")[0]
            if not _is_race_url(href, target_date):
                continue
            url = urljoin("https://www.racingpost.com", href)
            urls.setdefault(url, {"source_files": [], "text": " ".join(anchor.get_text(" ", strip=True).split())})
            if str(html_path) not in urls[url]["source_files"]:
                urls[url]["source_files"].append(str(html_path))

        # 2. JSON blobs in scripts (Next.js PRELOADED_STATE)
        json_urls = re.findall(r'\"raceUrl\":\"(/racecards/\d+/[^/]+/' + target_date + r'/\d+)\"', html_content)
        for href in json_urls:
            url = urljoin("https://www.racingpost.com", href)
            urls.setdefault(url, {"source_files": [], "text": "JSON_BLOB"})
            if str(html_path) not in urls[url]["source_files"]:
                urls[url]["source_files"].append(str(html_path))

        # 3. Broad regex over raw HTML.
        # Fixes the today/tomorrow paradox: RP index captured on D-1 stores tomorrow's races
        # under today's date key in __NEXT_DATA__, but race URLs always contain the correct date.
        broad_pattern = rf'(?:https?://(?:www\.)?racingpost\.com)?/racecards/(\d+)/([^/"]+)/{re.escape(target_date)}/(\d+)'
        for m in re.finditer(broad_pattern, html_content):
            course_id, slug, race_id = m.groups()
            url = f"https://www.racingpost.com/racecards/{course_id}/{slug}/{target_date}/{race_id}"
            urls.setdefault(url, {"source_files": [], "text": "BROAD_REGEX"})
            if str(html_path) not in urls[url]["source_files"]:
                urls[url]["source_files"].append(str(html_path))

    # Deduplicate by race ID — same race can appear under multiple URLs on the index page.
    seen_race_ids: set[str] = set()
    deduped: dict[str, dict] = {}
    for url in sorted(urls):
        race_id = _race_id_from_url(url)
        if race_id and race_id in seen_race_ids:
            continue
        if race_id:
            seen_race_ids.add(race_id)
        deduped[url] = urls[url]

    # Split into UK/IRE and international.
    uk_ire_urls: list[str] = []
    intl_urls: list[str] = []
    for url in sorted(deduped):
        slug = _venue_slug_from_url(url)
        if slug and slug.lower() in UK_IRE_VENUES:
            uk_ire_urls.append(url)
        else:
            intl_urls.append(url)

    payload = {
        "capture_date": capture_date,
        "target_date": target_date,
        "generated_at": _utc_now(),
        "html_files_seen": len(html_files),
        "uk_ire_url_count": len(uk_ire_urls),
        "international_url_count": len(intl_urls),
        "output": str(output),
        "execute_required": True,
        "status": "DRY_RUN",
    }
    if execute:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(uk_ire_urls) + ("\n" if uk_ire_urls else ""), encoding="utf-8")
        intl_output = output.parent / output.name.replace(".txt", "_intl.txt")
        intl_output.write_text("\n".join(intl_urls) + ("\n" if intl_urls else ""), encoding="utf-8")
        payload["status"] = "PASS"
        payload["intl_output"] = str(intl_output)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RP racecard URL list from local account captures.")
    parser.add_argument("--date", required=True, help="Raw capture date folder")
    parser.add_argument("--target-date", default=None, help="Racecard date to extract. Defaults to --date.")
    parser.add_argument("--output", default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    target_date = args.target_date or args.date
    output = Path(args.output) if args.output else URL_LIST_ROOT / f"rp_racecards_{target_date}.txt"
    payload = build_racecard_urls(capture_date=args.date, target_date=target_date, output=output, execute=args.execute)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
