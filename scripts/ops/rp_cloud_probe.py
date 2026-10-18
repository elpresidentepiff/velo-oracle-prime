#!/usr/bin/env python3
"""One-shot cloud probe: can Racing Post be logged into and captured from Railway?

Runs the same three things the laptop does, headless, with RP_EMAIL / RP_PASSWORD
from the environment: auto_login -> session health probe -> racecards index
capture. Prints a JSON verdict (never the password). Exit 0 always so the
verdict is readable in the deploy log; the verdict field says PASS or FAIL.
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ops.check_rp_session_health import probe  # noqa: E402
from scripts.ops.racing_post_account_collector import DEFAULT_PROFILE_DIR  # noqa: E402


def login_page_diag() -> dict:
    """What does the sign-in page look like from this network? No credentials used."""
    from playwright.sync_api import sync_playwright

    from scripts.ops.racing_post_account_collector import RP_AUTH_LOGIN_URL

    d: dict = {}
    try:
        with sync_playwright() as p:
            b = p.firefox.launch(headless=True)
            page = b.new_page(viewport={"width": 1400, "height": 1000})
            resp = page.goto(RP_AUTH_LOGIN_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(6000)
            html = page.content()
            d["http_status"] = resp.status if resp else None
            d["final_url"] = page.url
            d["title"] = page.title()
            d["email_field"] = page.locator("#email").count()
            d["password_field"] = page.locator("#password").count()
            d["consent_banner"] = page.locator("#truste-consent-button").count()
            d["iframes"] = [f.url[:90] for f in page.frames][:8]
            low = html.lower()
            d["markers"] = [m for m in ("captcha", "datadome", "cloudflare", "access denied", "blocked", "px-captcha", "challenge") if m in low]
            try:
                d["body_head"] = " ".join(page.inner_text("body")[:400].split())
            except Exception:
                d["body_head"] = ""
            b.close()
    except Exception as exc:  # diagnostic only
        d["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return d


def cloud_login() -> dict:
    """Sign in on a fresh profile: dismiss the consent dialog, then type the credentials.

    A fresh container has no saved consent cookie, so Racing Post shows its cookie
    dialog over the form. Cloud-only; the laptop's auto_login is untouched.
    """
    import os

    from playwright.sync_api import sync_playwright

    from scripts.ops.racing_post_account_collector import RP_AUTH_LOGIN_URL

    email = (os.getenv("RP_EMAIL") or "").strip()
    password = os.getenv("RP_PASSWORD") or ""
    d: dict = {"email_present": bool(email), "password_present": bool(password)}
    if not (email and password):
        d["status"] = "SKIPPED_NO_CREDENTIALS"
        return d
    DEFAULT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            b = p.firefox.launch_persistent_context(
                user_data_dir=str(DEFAULT_PROFILE_DIR), headless=True,
                viewport={"width": 1400, "height": 1000},
                firefox_user_prefs={"gfx.webrender.enabled": False, "gfx.webrender.all": False},
            )
            page = b.new_page()
            page.goto(RP_AUTH_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)
            d["buttons_before"] = page.evaluate(
                "[...document.querySelectorAll('button,a[role=button]')].slice(0,14)"
                ".map(e => (e.id || '') + '|' + (e.innerText || '').trim().slice(0, 28))"
            )
            d["covered_by"] = page.evaluate(
                "(() => { const e = document.querySelector('#email'); if (!e) return 'no #email';"
                " const r = e.getBoundingClientRect();"
                " const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);"
                " return t ? (t.tagName + '#' + (t.id || '') + '.' + String(t.className).slice(0, 40)) : 'none'; })()"
            )
            d["consent_clicked"] = page.evaluate(
                "(() => { for (const s of ['#truste-consent-button', '#truste-consent-required']) {"
                " const e = document.querySelector(s); if (e) { e.click(); return s; } } return null; })()"
            )
            page.wait_for_timeout(3000)
            page.evaluate(
                "document.querySelectorAll('#truste-consent-track, #consent_blackbar, .truste_overlay, "
                ".truste_box_overlay, #truste-consent-content').forEach(e => e.remove())"
            )
            d["covered_by_after"] = page.evaluate(
                "(() => { const e = document.querySelector('#email'); if (!e) return 'no #email';"
                " const r = e.getBoundingClientRect();"
                " const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);"
                " return t ? (t.tagName + '#' + (t.id || '')) : 'none'; })()"
            )
            page.click("#email", force=True, timeout=20000)
            page.type("#email", email, delay=25)
            page.click("#password", force=True, timeout=20000)
            page.type("#password", password, delay=25)
            page.locator("#password").blur()
            page.wait_for_timeout(500)
            page.locator('button[type="submit"]').first.click(force=True, timeout=20000)
            page.wait_for_timeout(8000)
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            d["final_url"] = page.url
            d["login_form_still_present"] = bool(page.locator("#password").count())
            try:
                d["page_text_head"] = " ".join(page.inner_text("body")[:300].split())
            except Exception:
                pass
            d["rp_authenticated_cookie"] = any(c["name"] == "rp_authenticated" for c in b.cookies())
            b.close()
        d["status"] = "PASS" if (d["rp_authenticated_cookie"] and not d["login_form_still_present"]) else "FAIL"
    except Exception as exc:
        d["status"] = "FAIL"
        d["reason"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return d


def main() -> int:
    date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")  # noqa: UP017 - container is py3.10
    out: dict = {"date": date, "steps": {}}

    out["steps"]["login_page"] = login_page_diag()
    print("STEP login_page:", json.dumps(out["steps"]["login_page"], default=str), flush=True)

    login = cloud_login()
    out["steps"]["auto_login"] = login
    print("STEP auto_login:", json.dumps(out["steps"]["auto_login"], default=str), flush=True)
    health = probe(DEFAULT_PROFILE_DIR)
    out["steps"]["session_probe"] = {k: health.get(k) for k in ("status", "reason", "is_logged", "http_status", "role")}

    print("STEP session_probe:", json.dumps(out["steps"]["session_probe"], default=str), flush=True)
    cap = subprocess.run(
        [sys.executable, "scripts/ops/capture_index_headless.py", "--date", date],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    out["steps"]["index_capture"] = {"returncode": cap.returncode, "stdout": cap.stdout[-600:], "stderr": cap.stderr[-600:]}

    ok = (
        out["steps"]["session_probe"].get("status") == "PASS"
        and cap.returncode == 0
        and "WARNING" not in cap.stdout
    )
    out["verdict"] = "PASS" if ok else "FAIL"
    print(json.dumps(out, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
