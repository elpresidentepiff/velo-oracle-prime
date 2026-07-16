#!/usr/bin/env python3
"""
VELO Racing Post account collector.

This is not an API client and not a stealth scraper. It uses a persistent local
browser profile that the operator logs into manually, then captures only the
Racing Post URLs explicitly provided in a URL list.

Rules:
- no credentials in code
- no proxy rotation
- no captcha bypass
- no hidden endpoint mining
- raw first, parse later
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_DIR = ROOT / "data" / "browser_profiles" / "racing_post_account"
DEFAULT_RAW_DIR = ROOT / "data" / "racing_post_account_raw"
DEFAULT_LOGIN_URL = "https://www.racingpost.com/"
DEFAULT_ALLOWED_DOMAINS = {"racingpost.com", "www.racingpost.com"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_")[:80] or "page"


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write via a temp file + os.replace so a kill signal mid-write can
    never leave the target (e.g. manifest.json) truncated/corrupted -- a
    plain write_text() can be interrupted partway and zero the file out."""
    tmp_path = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def _load_urls(path: Path) -> list[str]:
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_capture_files(
    *,
    page,
    day_dir: Path,
    source_url: str,
    label: str,
    screenshot: bool,
    http_status: int | None = None,
) -> dict:
    page_hash = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:12]
    capture_stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    stem = f"{capture_stamp}_{_safe_slug(label)}_{page_hash}"
    html_path = day_dir / f"{stem}.html"
    meta_path = day_dir / f"{stem}.json"
    png_path = day_dir / f"{stem}.png"

    html = page.content()
    title = page.title()
    final_url = page.url
    html_sha256 = _sha256_text(html)
    html_path.write_text(html, encoding="utf-8")
    if screenshot:
        page.screenshot(path=str(png_path), full_page=True)

    meta = {
        "source_url": source_url,
        "final_url": final_url,
        "title": title,
        "status": "PASS",
        "error": None,
        "http_status": http_status,
        "url_sha256": hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
        "html_sha256": html_sha256,
        "started_at": _utc_now(),
        "finished_at": _utc_now(),
        "html_path": str(html_path),
        "screenshot_path": str(png_path) if screenshot and png_path.exists() else None,
        "collector": "racing_post_account_collector_v1",
        "raw_first": True,
        "credentials_in_code": False,
        "manual_operator_capture": True,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def _assert_repo_path(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if ROOT not in resolved.parents and resolved != ROOT:
        raise SystemExit(f"{label} must live under repo root: {ROOT}")
    return resolved


def _assert_allowed_url(url: str, allowed_domains: set[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SystemExit(f"Unsupported URL scheme: {url}")
    host = (parsed.netloc or "").lower()
    if host not in allowed_domains:
        raise SystemExit(f"URL host not allowed: {host}. Allowed: {sorted(allowed_domains)}")


def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - environment dependent
        raise SystemExit(f"Playwright import failed. Install optional ScrapeGraphAI tooling first: {exc}") from exc
    return sync_playwright


def init_login(profile_dir: Path, login_url: str, *, execute: bool, wait_seconds: int = 120) -> dict:
    profile_dir = _assert_repo_path(profile_dir, "profile_dir")
    payload = {
        "mode": "init-login",
        "status": "DRY_RUN",
        "profile_dir": str(profile_dir),
        "login_url": login_url,
        "operator_action": "Run with --execute, log in manually, then press Enter in the terminal.",
    }
    if not execute:
        return payload

    sync_playwright = _import_playwright()
    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        # Firefox works reliably on WSLg; Chromium crashes due to GPU init issues
        browser = p.firefox.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1400, "height": 1000},
        )
        page = browser.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
        if sys.stdin.isatty():
            input("Log in to Racing Post in the opened browser, then press Enter here to save the profile...")
        else:
            # No real interactive stdin (e.g. invoked via a non-interactive
            # pass-through session). Give the operator a fixed window to log
            # in in the visible browser window instead of blocking on input().
            print(
                f"No interactive terminal detected — waiting {wait_seconds}s for you to log in "
                "to Racing Post in the opened browser window, then saving automatically.",
                flush=True,
            )
            step = 15
            remaining = wait_seconds
            while remaining > 0:
                sleep_for = min(step, remaining)
                time.sleep(sleep_for)
                remaining -= sleep_for
                print(f"  {remaining}s remaining before profile save...", flush=True)
        browser.close()

    payload["status"] = "PASS"
    payload["saved_at"] = _utc_now()
    payload["wait_seconds_used"] = wait_seconds if not sys.stdin.isatty() else None
    return payload


def capture_urls(
    *,
    url_list: Path,
    capture_date: str,
    profile_dir: Path,
    output_dir: Path,
    allowed_domains: set[str],
    delay_seconds: float,
    screenshot: bool,
    headed: bool,
    execute: bool,
    batch_size: int = 0,
) -> dict:
    url_list = _assert_repo_path(url_list, "url_list")
    profile_dir = _assert_repo_path(profile_dir, "profile_dir")
    output_dir = _assert_repo_path(output_dir, "output_dir")
    urls = _load_urls(url_list)
    for url in urls:
        _assert_allowed_url(url, allowed_domains)

    day_dir = output_dir / capture_date
    payload = {
        "mode": "capture",
        "status": "DRY_RUN",
        "url_count": len(urls),
        "url_list": str(url_list),
        "profile_dir": str(profile_dir),
        "output_dir": str(day_dir),
        "allowed_domains": sorted(allowed_domains),
        "execute_required": True,
    }
    if not execute:
        return payload

    if not profile_dir.exists():
        raise SystemExit(f"Browser profile missing. Run init-login first: {profile_dir}")

    sync_playwright = _import_playwright()
    day_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = day_dir / "manifest.json"
    existing_captures: list[dict] = []
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            existing_captures = existing.get("captures", []) or []
        except Exception:
            existing_captures = []
    completed_urls = {
        item.get("source_url")
        for item in existing_captures
        if item.get("status") == "PASS"
        and item.get("source_url")
        and item.get("html_path")
        and Path(item["html_path"]).exists()
    }
    captures: list[dict] = []
    batch_captured = 0

    with sync_playwright() as p:
        # Use Firefox profile if profile_dir contains Firefox markers, else Chromium
        _is_firefox_profile = (profile_dir / "prefs.js").exists() or "firefox" in str(profile_dir).lower()
        if _is_firefox_profile:
            browser = p.firefox.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=not headed,
                viewport={"width": 1400, "height": 1000},
            )
        else:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=not headed,
                viewport={"width": 1400, "height": 1000},
                args=["--ignore-certificate-errors", "--disable-dev-shm-usage", "--disable-gpu", "--use-gl=swiftshader"],
            )
        page = browser.new_page()
        for idx, url in enumerate(urls, start=1):
            if url in completed_urls:
                continue
            if batch_size > 0 and batch_captured >= batch_size:
                print(f"\n[BATCH] Reached limit of {batch_size} URLs. Run again with same --date to continue from where this left off.")
                break
            parsed = urlparse(url)
            page_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
            stem = f"{idx:03d}_{_safe_slug(parsed.path)}_{page_hash}"
            html_path = day_dir / f"{stem}.html"
            meta_path = day_dir / f"{stem}.json"
            png_path = day_dir / f"{stem}.png"

            started_at = _utc_now()
            status = "PASS"
            error = None
            title = ""
            final_url = url
            http_status = None
            html_sha256 = None
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)
                title = page.title()
                final_url = page.url
                http_status = response.status if response else None
                html = page.content()
                html_sha256 = _sha256_text(html)
                html_path.write_text(html, encoding="utf-8")
                if http_status is not None and http_status >= 400:
                    status = "FAIL"
                    error = f"HTTP {http_status}"
                if screenshot:
                    page.screenshot(path=str(png_path), full_page=True)
            except Exception as exc:  # pragma: no cover - network/browser dependent
                status = "FAIL"
                error = str(exc)

            meta = {
                "source_url": url,
                "final_url": final_url,
                "title": title,
                "status": status,
                "error": error,
                "http_status": http_status,
                "url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
                "html_sha256": html_sha256,
                "started_at": started_at,
                "finished_at": _utc_now(),
                "html_path": str(html_path) if html_path.exists() else None,
                "screenshot_path": str(png_path) if screenshot and png_path.exists() else None,
                "collector": "racing_post_account_collector_v1",
                "raw_first": True,
                "credentials_in_code": False,
            }
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            captures.append(meta)
            batch_captured += 1

            # Write the manifest after every capture, not just at the end of
            # the whole batch. A killed/timed-out process (e.g. a wrapper
            # tool's own timeout) used to lose all progress from this run,
            # since dedup on the next invocation only reads what's already
            # in manifest.json -- causing repeated re-attempts of the same
            # URLs instead of resuming past them. Root cause of the
            # 2026-07-08 passport-bank capture appearing stuck at a fixed
            # count across multiple "successful" resumed runs.
            captures_by_url = {
                item.get("source_url"): item
                for item in existing_captures + captures
                if item.get("source_url")
            }
            all_captures = [captures_by_url[u] for u in urls if u in captures_by_url]
            manifest = {
                "capture_date": capture_date,
                "generated_at": _utc_now(),
                "url_count": len(all_captures),
                "latest_url_count": len(urls),
                "captures": all_captures,
            }
            _atomic_write_json(manifest_path, manifest)

            if delay_seconds > 0 and batch_captured < len(urls):
                time.sleep(delay_seconds)
        browser.close()

    payload.update({"status": "PASS", "manifest": str(manifest_path), "captures": captures})
    return payload


def manual_capture(
    *,
    capture_date: str,
    start_url: str,
    label: str,
    profile_dir: Path,
    output_dir: Path,
    allowed_domains: set[str],
    screenshot: bool,
    execute: bool,
    headless: bool = False,
) -> dict:
    _assert_allowed_url(start_url, allowed_domains)
    profile_dir = _assert_repo_path(profile_dir, "profile_dir")
    output_dir = _assert_repo_path(output_dir, "output_dir")
    day_dir = output_dir / capture_date
    payload = {
        "mode": "manual-capture",
        "status": "DRY_RUN",
        "start_url": start_url,
        "label": label,
        "profile_dir": str(profile_dir),
        "output_dir": str(day_dir),
        "operator_action": "Run with --execute, navigate/filter/click in the browser, then press Enter to capture the current page.",
    }
    if not execute:
        return payload

    if not profile_dir.exists():
        raise SystemExit(f"Browser profile missing. Run init-login first: {profile_dir}")

    sync_playwright = _import_playwright()
    day_dir.mkdir(parents=True, exist_ok=True)
    _is_firefox_profile = (profile_dir / "prefs.js").exists() or "firefox" in str(profile_dir).lower()
    with sync_playwright() as p:
        if _is_firefox_profile:
            browser = p.firefox.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                viewport={"width": 1400, "height": 1000},
            )
        else:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                viewport={"width": 1400, "height": 1000},
                args=["--ignore-certificate-errors", "--disable-dev-shm-usage", "--disable-gpu", "--use-gl=swiftshader"],
            )
        page = browser.new_page()
        response = page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
        if not headless:
            print("Browser opened. Navigate/filter/click to the exact page you want captured.")
            input("When the Racing Post page is ready, press Enter here to capture the current page...")
        else:
            page.wait_for_timeout(5000)
        meta = _write_capture_files(
            page=page,
            day_dir=day_dir,
            source_url=start_url,
            label=label,
            screenshot=screenshot,
            http_status=response.status if response else None,
        )
        browser.close()

    manifest_path = day_dir / "manifest.json"
    existing_captures: list[dict] = []
    if manifest_path.exists():
        try:
            existing_captures = (json.loads(manifest_path.read_text(encoding="utf-8")).get("captures") or [])
        except Exception:
            existing_captures = []
    all_captures = existing_captures + [meta]
    manifest = {
        "capture_date": capture_date,
        "generated_at": _utc_now(),
        "url_count": len(all_captures),
        "latest_url_count": 1,
        "captures": all_captures,
    }
    _atomic_write_json(manifest_path, manifest)
    payload.update({"status": "PASS", "manifest": str(manifest_path), "capture": meta})
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Account-backed Racing Post page capture for VELO.")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("init-login", help="Open a persistent browser profile for manual login.")
    login.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    login.add_argument("--login-url", default=DEFAULT_LOGIN_URL)
    login.add_argument("--execute", action="store_true")
    login.add_argument("--wait-seconds", type=int, default=120,
        help="When stdin is not a real TTY (e.g. non-interactive pass-through session), "
             "wait this long for manual login instead of blocking on input().")

    capture = sub.add_parser("capture", help="Capture explicitly listed Racing Post URLs.")
    capture.add_argument("--url-list", required=True)
    capture.add_argument("--date", required=True, help="YYYY-MM-DD")
    capture.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    capture.add_argument("--output-dir", default=str(DEFAULT_RAW_DIR))
    capture.add_argument("--allow-domain", action="append", default=[])
    capture.add_argument("--delay-seconds", type=float, default=8.0)
    capture.add_argument("--screenshot", action="store_true")
    capture.add_argument("--headed", action="store_true")
    capture.add_argument("--batch-size", type=int, default=0,
        help="Capture N URLs then exit cleanly. 0 = no limit. Use for long lists to avoid tool timeouts.")
    capture.add_argument("--execute", action="store_true")

    manual = sub.add_parser("manual-capture", help="Open a page, let the operator interact, then capture current page.")
    manual.add_argument("--date", required=True, help="YYYY-MM-DD")
    manual.add_argument("--start-url", required=True)
    manual.add_argument("--label", default="manual_capture")
    manual.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    manual.add_argument("--output-dir", default=str(DEFAULT_RAW_DIR))
    manual.add_argument("--allow-domain", action="append", default=[])
    manual.add_argument("--screenshot", action="store_true")
    manual.add_argument("--headless", action="store_true", help="Run headless (no browser UI); auto-captures without user input. Use when display/headed mode is unavailable.")
    manual.add_argument("--execute", action="store_true")

    args = parser.parse_args()
    if args.command == "init-login":
        payload = init_login(Path(args.profile_dir), args.login_url, execute=args.execute, wait_seconds=args.wait_seconds)
    elif args.command == "manual-capture":
        allowed = set(DEFAULT_ALLOWED_DOMAINS)
        allowed.update(args.allow_domain or [])
        payload = manual_capture(
            capture_date=args.date,
            start_url=args.start_url,
            label=args.label,
            profile_dir=Path(args.profile_dir),
            output_dir=Path(args.output_dir),
            allowed_domains=allowed,
            screenshot=args.screenshot,
            execute=args.execute,
            headless=args.headless,
        )
    else:
        allowed = set(DEFAULT_ALLOWED_DOMAINS)
        allowed.update(args.allow_domain or [])
        payload = capture_urls(
            url_list=Path(args.url_list),
            capture_date=args.date,
            profile_dir=Path(args.profile_dir),
            output_dir=Path(args.output_dir),
            allowed_domains=allowed,
            delay_seconds=args.delay_seconds,
            screenshot=args.screenshot,
            headed=args.headed,
            execute=args.execute,
            batch_size=args.batch_size,
        )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
