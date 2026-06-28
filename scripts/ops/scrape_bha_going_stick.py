"""
BHA GoingStick Scraper
======================
Captures daily ground conditions from the BHA GoingStick report page
(https://www.britishhorseracing.com/work-bha/going-extra-furlong/).

IMPORTANT: The BHA going page is an Angular SPA. Static HTML fetch gives
page chrome only — actual going data is loaded via a protected API call
made by the Angular app at runtime.

Current mode: STATIC_FETCH — parses any server-rendered content.
If no going data found, outputs status=JS_RENDER_REQUIRED.

To enable full scraping: install playwright (`pip install playwright`) and
add headless render support below. The scraper shell is ready for it.

Output:
  data/bha_going_stick_latest.json    — today's reading (or JS_RENDER_REQUIRED)
  data/bha_going_stick_YYYY_MM_DD.json — dated snapshot

Usage:
    python scripts/ops/scrape_bha_going_stick.py [--date YYYY-MM-DD]
    python scripts/ops/scrape_bha_going_stick.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT_LATEST = DATA / "bha_going_stick_latest.json"

BHA_GOING_URL = "https://www.britishhorseracing.com/work-bha/going-extra-furlong/"
USER_AGENT = "Mozilla/5.0 (compatible; VELO-Research/1.0; +https://velo.racing)"

GOING_STRINGS = {
    "heavy", "soft", "good to soft", "good", "good to firm", "firm",
    "standard", "standard to slow", "slow", "yielding", "yielding to soft",
    "sloppy", "muddy", "fast",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fetch_html(url: str, timeout: int = 20) -> tuple[str, str]:
    """Fetch URL, return (html, error_message). Error is '' on success."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace"), ""
    except urllib.error.HTTPError as e:
        return "", f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return "", str(e)


def _parse_going_table(html: str) -> list[dict[str, Any]]:
    """Try to parse a table or structured data with course/going pairs from HTML."""
    rows = []

    # Look for table rows containing course names and going strings
    # Pattern: <td>Course Name</td><td>Going String</td>
    td_pairs = re.findall(
        r"<tr[^>]*>.*?<td[^>]*>([A-Z][a-zA-Z &\-']+)</td>.*?<td[^>]*>([A-Za-z ]+)</td>.*?</tr>",
        html,
        re.DOTALL | re.I,
    )
    for course, going in td_pairs:
        course = course.strip()
        going = going.strip().lower()
        if going in GOING_STRINGS and len(course) > 2 and len(course) < 40:
            rows.append({"course": course, "going": going, "source": "html_table"})

    # Also try JSON-LD or embedded JSON in script blocks
    json_blocks = re.findall(
        r"<script[^>]*type=[\"']application/json[\"'][^>]*>(.*?)</script>",
        html,
        re.DOTALL | re.I,
    )
    for block in json_blocks:
        try:
            data = json.loads(block.strip())
            # Look for going-related keys
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "going" in str(item).lower():
                        rows.append({"raw": item, "source": "json_block"})
        except (json.JSONDecodeError, ValueError):
            pass

    return rows


def _try_playwright_render(url: str) -> tuple[str, str]:
    """Attempt headless render if playwright is available. Returns (html, error)."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="networkidle", timeout=30000)
            # Wait for going data to load
            try:
                page.wait_for_selector("table", timeout=10000)
            except Exception:
                pass
            html = page.content()
            browser.close()
            return html, ""
    except ImportError:
        return "", "PLAYWRIGHT_NOT_INSTALLED"
    except Exception as e:
        return "", f"PLAYWRIGHT_ERROR:{e}"


def scrape(today: str, dry_run: bool = False) -> dict[str, Any]:
    captured_at = _utc_now()

    # ── Step 1: Static fetch ──────────────────────────────────────────────────
    html, fetch_error = _fetch_html(BHA_GOING_URL)
    render_method = "static_fetch"

    if fetch_error:
        return {
            "date": today,
            "captured_at": captured_at,
            "status": "FETCH_FAILED",
            "error": fetch_error,
            "going_readings": [],
            "render_method": render_method,
        }

    # ── Step 2: Try to parse going data from static HTML ─────────────────────
    readings = _parse_going_table(html)

    # ── Step 3: If no readings, try playwright headless render ────────────────
    if not readings:
        pw_html, pw_error = _try_playwright_render(BHA_GOING_URL)
        if pw_html:
            render_method = "playwright_headless"
            readings = _parse_going_table(pw_html)
        elif pw_error == "PLAYWRIGHT_NOT_INSTALLED":
            pass  # Expected — static-only mode
        else:
            pass  # Playwright error — continue without it

    # ── Assemble result ───────────────────────────────────────────────────────
    status = "OK" if readings else "JS_RENDER_REQUIRED"
    result: dict[str, Any] = {
        "date": today,
        "captured_at": captured_at,
        "status": status,
        "render_method": render_method,
        "going_readings": readings,
        "course_count": len(readings),
        "note": (
            "Going data loaded by Angular app at runtime. "
            "Install playwright for full capture: pip install playwright && playwright install chromium"
        ) if status == "JS_RENDER_REQUIRED" else "",
    }

    if not dry_run:
        OUT_LATEST.write_text(json.dumps(result, indent=2), encoding="utf-8")
        dated_path = DATA / f"bha_going_stick_{today.replace('-', '_')}.json"
        dated_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="BHA GoingStick scraper")
    parser.add_argument("--date", default=date.today().isoformat(), help="Date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Print result, don't write files")
    args = parser.parse_args()

    result = scrape(args.date, dry_run=args.dry_run)
    print(f"Status: {result['status']}")
    print(f"Courses: {result['course_count']}")
    print(f"Render: {result['render_method']}")
    if result["going_readings"]:
        for r in result["going_readings"][:5]:
            print(f"  {r.get('course'):30s} {r.get('going')}")
    else:
        print(f"  {result.get('note', '')}")
    if not args.dry_run:
        print(f"Written: {OUT_LATEST}")


if __name__ == "__main__":
    main()
