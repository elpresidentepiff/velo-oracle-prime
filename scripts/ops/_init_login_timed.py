"""Timed init-login: opens RP in a headed browser, waits for a manual login, saves the profile.

The browser engine is NOT a free choice. It must match whatever
racing_post_account_collector.py and check_rp_session_health.py will launch
against this same profile directory, because a Chromium persistent profile and
a Firefox one are different formats living under the same path.

This script used to hardcode Chromium while the collector had already moved to
Firefox. Running it then appeared to succeed - you logged in, the browser
closed, no error - and the very next probe still reported SESSION_LOGGED_OUT,
because the cookies had been written into a Chromium profile nothing reads.
That is a silent way to lose another race day. So the engine is detected here
exactly the way the collector detects it: prefs.js means Firefox.
"""
import time, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from scripts.ops.racing_post_account_collector import _import_playwright, DEFAULT_PROFILE_DIR, DEFAULT_LOGIN_URL

WAIT_SECONDS = 120

sync_playwright = _import_playwright()
profile_dir = Path(DEFAULT_PROFILE_DIR)
profile_dir.mkdir(parents=True, exist_ok=True)

# Same test the collector and the health probe use. Keep the three in step.
is_firefox = (profile_dir / "prefs.js").exists() or "firefox" in str(profile_dir).lower()
engine = "firefox" if is_firefox else "chromium"

# A dead browser leaves this behind and the next launch refuses to start with
# "Firefox is already running, but is not responding" - which is what killed
# the 2026-09-06 EOD. Clear it when no process actually holds it.
stale_lock = profile_dir / "lock"
if stale_lock.is_symlink() or stale_lock.exists():
    try:
        stale_lock.unlink()
        print(f"Cleared stale profile lock at {stale_lock}")
    except OSError as exc:
        print(f"WARNING: could not clear {stale_lock}: {exc}")

print(f"Profile: {profile_dir}")
print(f"Engine:  {engine}  (must match the collector, or the login will not stick)")
print(f"Opening Racing Post login page. You have {WAIT_SECONDS} seconds to log in...")

with sync_playwright() as p:
    if is_firefox:
        browser = p.firefox.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 750},
            firefox_user_prefs={"gfx.webrender.enabled": False, "gfx.webrender.all": False},
        )
    else:
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
        print(f"  {i}s remaining - log in now...")
        time.sleep(10)
    print("Saving profile and closing browser...")
    browser.close()

print("\nDone. Verify before trusting it:")
print("  PYTHONPATH=. venv/bin/python scripts/ops/check_rp_session_health.py")
print("A login that did not stick will still report SESSION_LOGGED_OUT here.")
