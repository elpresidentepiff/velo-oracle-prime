#!/usr/bin/env python3
"""
fetch_rp_meeting_pdfs.py — download today's RP ratings-sheet PDFs.

THE GAP THIS CLOSES
-------------------
auto_ingest_pdf_inbox.py has always been able to discover, stage and ingest the
six-to-eight RP sheets per venue -- it runs in the morning orchestrator every
day. What nothing ever did was DOWNLOAD them. That was a human copying files
into OneDrive, and the moment the habit lapsed the step kept exiting 0 on an
empty inbox. Measured 2026-09-04: the newest file in the inbox was dated
2026-08-04, so the pipeline had been running on no sheets for a month, and the
readiness gate that used to catch it had been demoted to warn-only on
2026-08-02 (correctly -- it was blocking whole days over a non-perishable
input, but that removed the last alarm).

Cost of the gap, measured across every merged racecard, a day with sheets
(2026-08-04) against a day without (2026-09-03):

    postdata_score    59% -> 0%
    plot_conviction   77% -> 0%
    or_run_history    67% -> 0%

Those are not decorative. run_prime_today.py reads plot_conviction into the
score and emits a PDF_PLOT_CONVICTION reason; the High-Conviction panel keys
off postdata_score >= 0.70. With the field pinned at 0 the criterion cannot
fire at all.

WHERE THE SHEETS LIVE
---------------------
Every racecard page carries a "Newspaper Form Plus" tab
(data-testid=RaceLevelControls__PrimaryTab__newspaper-form-plus). Clicking it
renders a table of PDF links pointing at:

    https://www.rp-assets.com/pdfs/auto/{code}/{VEN}_{YYYYMMDD}_{HH}_{MM}_{F|O}_{code}_{TYPE}_{Course}.pdf

Meeting-level sheets use _00_00_; per-race profiles carry the off time. Those
filenames are byte-for-byte what auto_ingest_pdf_inbox.py's contract expects,
so downloading them into the inbox needs no renaming.

The URLs are harvested rather than constructed -- the venue code and course
display name in the filename are RP's, and guessing them would be one more
thing to silently get wrong. The PDFs themselves need no auth (verified: plain
HTTP 200), so only the harvest uses the logged-in browser profile.

F_ VERSUS O_ (READ THIS BEFORE MOVING THE STEP)
-----------------------------------------------
Race day carries the final set, F_: 0003 CARD, 0010 SELECTION BOX,
0011 POSTDATA, 0012 SPOTLIGHT, 0015_OR OFFICIAL RATINGS, 0015_PM,
0016 RP RATINGS, 0032_TS TOPSPEED.

The day before, only the overnight set exists, O_, and it is five of eight:
0003, 0012, 0015_OR, 0015_PM, 0032_TS. Missing are 0010, 0011 and 0016 --
and 0011 is postdata, the field that matters most here. So an evening fetch is
a head start, never a substitute. This step belongs in the MORNING run, ahead
of auto_ingest_pdf_inbox.py.

Note also that ingest_racecard_pdfs.classify_pdf() only maps O_ codes
0001/0006/0008; an O_0015_OR meeting sheet classifies as "unknown" and is
dropped. Overnight sheets are downloaded and reported here, but they will not
ingest until that classifier routes on the 4-digit code instead of the F/O
marker. Deliberately left alone: merging provisional overnight ratings into a
card is an operator decision, not a parser detail.

This step never fails the day. No sheets, a dead session, a 404 on one venue --
all of it degrades to a warning and a report, exactly as a missing inbox did.

Usage:
    PYTHONPATH=. venv/bin/python scripts/ops/fetch_rp_meeting_pdfs.py --date 2026-09-04
    PYTHONPATH=. venv/bin/python scripts/ops/fetch_rp_meeting_pdfs.py --date 2026-09-04 --execute
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULT_INBOX = Path("/mnt/c/Users/puror/OneDrive/Documents/horses for courses")
DEFAULT_PROFILE_DIR = ROOT / "data" / "browser_profiles" / "racing_post_account"
URL_LIST_DIR = ROOT / "data" / "racing_post_url_lists"
REPORT_DIR = ROOT / "data" / "reports"

TAB_SELECTOR = '[data-testid="RaceLevelControls__PrimaryTab__newspaper-form-plus"]'
PDF_RE = re.compile(r'https://[^"\'\s]+\.pdf', re.IGNORECASE)
RACECARD_URL_RE = re.compile(r"/racecards/(\d+)/([a-z0-9\-]+)/(\d{4}-\d{2}-\d{2})/(\d+)")

# The meeting-level sheets the ingest layer knows how to parse.
EXPECTED_CODES = ("0003", "0010", "0011", "0012", "0015", "0016", "0032")
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def venue_urls(date: str) -> list[tuple[str, str]]:
    """One racecard URL per venue: [(slug, url)], from the morning URL list."""
    path = URL_LIST_DIR / f"rp_racecards_{date}.txt"
    if not path.exists():
        return []
    first: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = RACECARD_URL_RE.search(line)
        if not m:
            continue
        first.setdefault(m.group(2), line)
    return sorted(first.items())


def harvest(date: str, profile_dir: Path, timeout_s: int, per_race: bool) -> dict[str, Any]:
    """{slug: [pdf urls]} scraped from each venue's Newspaper Form Plus tab."""
    from playwright.sync_api import sync_playwright

    found: dict[str, list[str]] = {}
    errors: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.firefox.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=True,
            viewport={"width": 1500, "height": 1100},
            firefox_user_prefs={"gfx.webrender.enabled": False, "gfx.webrender.all": False},
        )
        page = browser.new_page()
        for slug, url in venue_urls(date):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
                page.wait_for_timeout(3000)
                tab = page.locator(TAB_SELECTOR)
                if not tab.count():
                    errors[slug] = "NO_NEWSPAPER_FORM_TAB"
                    continue
                tab.first.click(timeout=timeout_s * 1000)
                page.wait_for_timeout(5000)
                urls = sorted(set(PDF_RE.findall(page.content())))
                if not per_race:
                    urls = [u for u in urls if "_00_00_" in u]
                found[slug] = urls
                print(f"  {slug:<22} {len(urls)} sheet(s)")
            except Exception as exc:
                errors[slug] = f"{type(exc).__name__}: {exc}"[:160]
                print(f"  {slug:<22} [WARN] {errors[slug]}")
        browser.close()
    return {"found": found, "errors": errors}


def download(url: str, dest: Path, timeout_s: int) -> str:
    """-> 'downloaded' | 'skipped' | 'failed: reason'. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status != 200:
                return f"failed: HTTP {resp.status}"
            body = resp.read()
    except Exception as exc:
        return f"failed: {type(exc).__name__}"
    if not body.startswith(b"%PDF"):
        return "failed: NOT_A_PDF"
    if dest.exists() and dest.stat().st_size == len(body):
        return "skipped"
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(body)
    os.replace(tmp, dest)
    return "downloaded"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--execute", action="store_true", help="Download (omit for dry run)")
    ap.add_argument("--inbox", type=Path, default=None, help="Override inbox folder")
    ap.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE_DIR)
    ap.add_argument("--timeout-seconds", type=int, default=60)
    ap.add_argument("--include-per-race", action="store_true",
                    help="Also fetch the per-race O_0001 profile PDFs (28+ per venue; nothing ingests them yet).")
    args = ap.parse_args()

    inbox = args.inbox or Path(os.getenv("VELO_PDF_INBOX", str(DEFAULT_INBOX)))
    print(f"FETCH RP MEETING PDFS — {args.date}")
    print(f"  inbox: {inbox}")

    venues = venue_urls(args.date)
    if not venues:
        print(f"  [WARN] No racecard URL list for {args.date} "
              f"({URL_LIST_DIR / f'rp_racecards_{args.date}.txt'} missing) — run Step 2 first. Nothing to fetch.")
        return 0
    print(f"  {len(venues)} venue(s): {', '.join(s for s, _ in venues)}\n")

    result = harvest(args.date, args.profile_dir, args.timeout_seconds, args.include_per_race)
    found, errors = result["found"], result["errors"]

    all_urls = [u for urls in found.values() for u in urls]
    overnight = [u for u in all_urls if re.search(r"_\d\d_\d\d_O_", u)]
    codes_seen: dict[str, set[str]] = {}
    for slug, urls in found.items():
        codes_seen[slug] = {m.group(1) for u in urls if (m := re.search(r"_[FO]_(\d{4})_", u))}

    print(f"\n  {len(all_urls)} sheet URL(s) across {len(found)} venue(s)"
          f"{f', {len(overnight)} are OVERNIGHT (O_)' if overnight else ''}")
    for slug in sorted(codes_seen):
        missing = [c for c in EXPECTED_CODES if c not in codes_seen[slug]]
        if missing:
            print(f"  [WARN] {slug}: missing sheet code(s) {', '.join(missing)}")

    outcomes: dict[str, int] = {}
    files: list[dict[str, str]] = []
    if not args.execute:
        print("\n  [DRY RUN] pass --execute to download")
    else:
        inbox.mkdir(parents=True, exist_ok=True)
        for slug, urls in sorted(found.items()):
            for url in urls:
                name = url.rsplit("/", 1)[-1]
                status = download(url, inbox / name, args.timeout_seconds)
                outcomes[status.split(":")[0]] = outcomes.get(status.split(":")[0], 0) + 1
                files.append({"venue": slug, "file": name, "status": status})
        print(f"\n  {', '.join(f'{v} {k}' for k, v in sorted(outcomes.items())) or 'nothing to do'}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "date": args.date,
        "generated_at": _utc_now(),
        "inbox": str(inbox),
        "executed": args.execute,
        "venues": len(venues),
        "sheets_found": len(all_urls),
        "overnight_sheets": len(overnight),
        "codes_by_venue": {k: sorted(v) for k, v in codes_seen.items()},
        "harvest_errors": errors,
        "outcomes": outcomes,
        "files": files,
    }
    out = REPORT_DIR / f"rp_meeting_pdfs_{args.date.replace('-', '_')}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  Report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
