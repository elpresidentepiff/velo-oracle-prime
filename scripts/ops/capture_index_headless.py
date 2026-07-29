#!/usr/bin/env python3
"""Headless capture of RP racecards index + date page to get ALL UK venues.

Captures two pages per run and writes to data/racing_post_account_raw/{date}/
so build_racing_post_racecard_url_list.py picks them up automatically.

Pages captured:
  1. https://www.racingpost.com/racecards          — featured races (fast)
  2. https://www.racingpost.com/racecards/YYYY-MM-DD — ALL venues for date
"""
import argparse
import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "data" / "browser_profiles" / "racing_post_account"

parser = argparse.ArgumentParser()
parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today UTC)")
args = parser.parse_args()

date = args.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

# Primary output: where URL builder expects HTML files
OUT_DIR = ROOT / "data" / "racing_post_account_raw" / date
OUT_DIR.mkdir(parents=True, exist_ok=True)

is_firefox = (PROFILE / "prefs.js").exists()

PAGES = [
    ("rp-index", "https://www.racingpost.com/racecards"),
    ("rp-all-races", f"https://www.racingpost.com/racecards/{date}"),
]

with sync_playwright() as p:
    if is_firefox:
        browser = p.firefox.launch_persistent_context(
            user_data_dir=str(PROFILE), headless=True,
            viewport={"width": 1400, "height": 1000},
        )
    else:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), headless=True,
            viewport={"width": 1400, "height": 1000},
            args=["--disable-gpu", "--use-gl=swiftshader"],
        )

    for label, url in PAGES:
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        html = page.content()
        page.close()
        out = OUT_DIR / f"{label}.html"
        out.write_text(html, encoding="utf-8")
        size_kb = out.stat().st_size // 1024
        status = "OK" if size_kb >= 50 else "WARNING: small — session may have expired"
        print(f"[{label}] {size_kb} KB — {status}")

    browser.close()

print(f"\nCapture complete: {OUT_DIR}")
