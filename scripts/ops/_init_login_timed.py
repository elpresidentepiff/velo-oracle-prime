"""Timed init-login: opens RP in headed browser, waits 90s for manual login, then saves profile."""
import time, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from scripts.ops.racing_post_account_collector import _import_playwright, DEFAULT_PROFILE_DIR, DEFAULT_LOGIN_URL

WAIT_SECONDS = 120

sync_playwright = _import_playwright()
profile_dir = Path(DEFAULT_PROFILE_DIR)
profile_dir.mkdir(parents=True, exist_ok=True)

print(f"Opening Racing Post login page. You have {WAIT_SECONDS} seconds to log in...")
with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=False,
        viewport={"width": 1280, "height": 750},
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = browser.new_page()
    page.goto(DEFAULT_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
    for i in range(WAIT_SECONDS, 0, -10):
        print(f"  {i}s remaining — log in now...")
        time.sleep(10)
    print("Saving profile and closing browser...")
    browser.close()

print("Done. Profile saved.")
