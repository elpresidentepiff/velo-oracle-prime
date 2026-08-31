#!/usr/bin/env python3
"""
check_rp_session_health.py

Lightweight live probe of the saved Racing Post browser profile's login
state. Fetches a single cheap page (a horse profile) with the existing
persistent Chromium/Firefox context, headless, and checks the embedded
window.PRELOADED_STATE.isLogged flag -- the same field
parse_racing_post_account_capture.py records as account_is_logged after
the fact. Root cause of the 2026-07-08 passport-bank capture failure
(146 attempts, 92% HTTP 406) was a logged-out session that nothing
checked for until the scrape queue had already been burned through.

Wired into velo_session_start_check.py as Step 11 so a dead session is
caught at the START of the day, not discovered mid-scrape.

No writes, no scoring, no Supabase, no Telegram. Read-only probe.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULT_PROFILE_DIR = ROOT / "data" / "browser_profiles" / "racing_post_account"
PROBE_URL = "https://www.racingpost.com/profile/horse/4057201/a-dublin-job/form"
PRELOADED_RE = re.compile(r"window\.PRELOADED_STATE\s*=\s*(\{.*?\});", re.S)

# Racing Post moved the horse-profile pages to Next.js, so window.PRELOADED_STATE
# no longer exists and the regex above matches nothing. The probe then returned
# NO_PRELOADED_STATE_FOUND for every profile, logged in or not - a detector that
# always says FAIL is no better than no detector, and this one exists to catch
# the dead-session scrape failure of 2026-07-08.
#
# The login flag still ships in the page payload, so read it directly. Verified
# 2026-08-28 against a genuinely logged-out profile (isLogged false, RDSP cookie
# rp_package="Unauthorized").
ISLOGGED_RE = re.compile(r'"isLogged"\s*:\s*(true|false)')

# ...and then RP changed again. Verified 2026-08-31 against a session that was
# demonstrably live - the header rendered the account holder's name and every
# form table the capture needs - while the payload still carried
# "isLogged": false. Reading that flag alone now produces a FALSE NEGATIVE,
# which is worse than the stale-regex bug it replaced: this probe gates the
# 07:00 and 22:00 scheduled runs, so a wrong FAIL silently cancels the day.
#
# Two independent signals decide it now, both of which a logged-out profile
# fails. `rp_authenticated` is empty when logged out (observed 2026-08-28
# alongside RDSP rp_package="Unauthorized") and "1" when logged in; and a
# logged-out page offers a sign-in affordance, which a live one never does.
# isLogged is still reported, as diagnosis rather than as the verdict.
SIGNED_OUT_MARKERS = ("Sign in", "Sign In", "SIGN IN", "Log in", "Log In", "LOG IN")

# A revalidated page comes back 304 with a body served from cache. That is a
# healthy response, not a failure, and treating it as one produced a second
# false FAIL on top of the stale regex.
OK_HTTP = (200, 304)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def probe(profile_dir: Path, timeout_s: int = 20) -> dict:
    result = {
        "generated_at": _utc_now(),
        "profile_dir": str(profile_dir),
        "probe_url": PROBE_URL,
    }
    if not profile_dir.exists():
        result.update(status="FAIL", reason="PROFILE_DIR_MISSING", is_logged=None, http_status=None)
        return result

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result.update(status="FAIL", reason="PLAYWRIGHT_NOT_INSTALLED", is_logged=None, http_status=None)
        return result

    is_firefox = (profile_dir / "prefs.js").exists() or "firefox" in str(profile_dir).lower()

    try:
        with sync_playwright() as p:
            if is_firefox:
                browser = p.firefox.launch_persistent_context(
                    user_data_dir=str(profile_dir), headless=True,
                    viewport={"width": 1400, "height": 1000},
                )
            else:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir), headless=True,
                    viewport={"width": 1400, "height": 1000},
                    args=["--ignore-certificate-errors", "--disable-dev-shm-usage", "--disable-gpu", "--use-gl=swiftshader"],
                )
            page = browser.new_page()
            resp = page.goto(PROBE_URL, wait_until="domcontentloaded", timeout=timeout_s * 1000)
            html = page.content()
            http_status = resp.status if resp else None
            try:
                body_text = page.evaluate("document.body.innerText") or ""
            except Exception:
                body_text = ""
            auth_cookie = next(
                (c["value"] for c in browser.cookies() if c["name"] == "rp_authenticated"),
                "",
            )
            browser.close()
    except Exception as e:
        result.update(status="FAIL", reason=f"BROWSER_ERROR: {e}", is_logged=None, http_status=None)
        return result

    state = {}
    match = PRELOADED_RE.search(html)
    if match:
        try:
            state = json.loads(match.group(1))
        except Exception as e:
            result.update(status="FAIL", reason=f"STATE_PARSE_ERROR: {e}", is_logged=None, http_status=http_status)
            return result
    else:
        flag = ISLOGGED_RE.search(html)
        if not flag:
            result.update(status="FAIL", reason="NO_LOGIN_FLAG_FOUND", is_logged=None, http_status=http_status)
            return result
        state = {"isLogged": flag.group(1) == "true"}

    is_logged = state.get("isLogged")
    role = state.get("userRole")

    authenticated = (auth_cookie or "").strip() == "1"
    offers_sign_in = any(marker in body_text for marker in SIGNED_OUT_MARKERS)
    http_ok = http_status in OK_HTTP
    live = authenticated and not offers_sign_in and http_ok

    if live:
        reason = None
    elif not http_ok:
        reason = f"UNEXPECTED_HTTP_{http_status}"
    elif not authenticated:
        reason = "SESSION_LOGGED_OUT"
    else:
        reason = "SIGN_IN_OFFERED"

    result.update(
        http_status=http_status,
        is_logged=is_logged,
        user_role=role,
        authenticated_cookie=authenticated,
        offers_sign_in=offers_sign_in,
        status="PASS" if live else "FAIL",
        reason=reason,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    result = probe(Path(args.profile_dir), timeout_s=args.timeout)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
