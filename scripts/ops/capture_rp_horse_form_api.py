#!/usr/bin/env python3
"""
VÉLØ — Racing Post horse form capture (JSON API)
=================================================
Replaces the HTML scrape of horse profile pages for the passport bank.

WHY THIS EXISTS
---------------
Racing Post migrated horse profiles from a server-rendered
window.PRELOADED_STATE app to Next.js during the 2026-08-05..08-31 outage.
The passport bank last grew on 2026-08-04. Every night since captured 500
pages, parsed 0, and reported success.

The HTML is no longer usable at any wait duration. The saved DOM carries
__NEXT_DATA__ in which horseProfile.form.data is null and isLoading is true:
form history is fetched client-side after hydration. Probed at 2.5s, 8s and
15s on a logged-in profile, the form table never renders and the row count
never moves off 5 (page furniture). There is nothing to scrape.

What the page fetches instead is a clean JSON API, and that is what this
script collects:

    /api/horse-profile/form?horseId=      last 5 runs, 53 fields each
    /api/horse-profile/record?horseId=    lifetime record per discipline
    /api/profile/horse/<id>               identity / breeding

THE ONE NON-OBVIOUS REQUIREMENT
-------------------------------
The API 406s unless the request is made from the horse's own profile page.
A Referer header alone is not enough — measured over 5 sample horses, an
explicit Referer returned 200 on 3, while navigating first returned 200 on 5.
So this navigates to each horse's page and issues the request from that page
context, which costs a page load per horse and is the price of the data.

WHAT CHANGES FOR THE PASSPORT
-----------------------------
This is a trade, not a clean win, and the passport builder should know it:

  - The form endpoint returns the LAST 5 RUNS only. It is hard-capped: every
    pagination parameter that could be guessed was tried (cutRaceDate,
    cut_race_date, cutDate, raceDate, beforeDate, before, toDate,
    nextCutRaceDate, cutRaceDatetime, maxRaceDate, endDate, offset, page,
    skip, all, limit, pageSize) and all returned the identical 5 runs.
    nextCutRaceDate is returned but no accepted parameter consumes it.
    The old HTML scrape averaged 11.3 runs per horse, so last-6 windows
    (avg_beaten_margin_last6) degrade to 5. last-3 and last-5 are unaffected.

  - Career totals get BETTER. The record endpoint gives authoritative
    lifetime starts/wins/places/prize/best_rpr/best_ts per discipline, which
    the row-counting scrape only ever approximated from the runs it happened
    to capture.

Verified against Bow Echo (7947753): record reports 6 starts, 6 wins, and
the form endpoint returns 5 of those 6 runs.

BOUNDARY
--------
Raw-first, matching racing_post_account_collector.py: this writes the API
responses to disk verbatim and parses nothing. Mapping into the passport
shape is parse_rp_form_history_api.py's job. No scoring change, no Supabase
writes, no Telegram.

Usage:
    python scripts/ops/capture_rp_horse_form_api.py \\
        --date passport-bank-2026-09-03 \\
        --url-list data/racing_post_url_lists/passport_bank_next_batch_latest.txt \\
        --execute
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = ROOT / "data" / "racing_post_account_raw"
DEFAULT_PROFILE = ROOT / "data" / "browser_profiles" / "racing_post_account"

API_FORM = "https://www.racingpost.com/api/horse-profile/form?horseId={hid}"
API_RECORD = "https://www.racingpost.com/api/horse-profile/record?horseId={hid}"
API_PROFILE = "https://www.racingpost.com/api/profile/horse/{hid}"

HORSE_URL_RE = re.compile(r"/profile/horse/(\d+)/([^/?#]+)")

# A capture run that reaches fewer than this share of its horses has hit a
# site change, a dead session or a block — not a quiet night. Same doctrine as
# the parse-rate floor in parse_racing_post_account_capture.py: silence is the
# one outcome a scraper must never be allowed.
MIN_SUCCESS_RATE = 0.50


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_horse_url(url: str) -> tuple[str, str] | None:
    m = HORSE_URL_RE.search(url)
    return (m.group(1), m.group(2)) if m else None


def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit(
            "playwright is not installed in this environment. "
            "Install it before running the passport capture."
        ) from exc
    return sync_playwright


def capture(url_list: Path, capture_date: str, raw_dir: Path, profile_dir: Path,
            delay_seconds: float, limit: int | None, execute: bool) -> dict:
    urls = [ln.strip() for ln in url_list.read_text(encoding="utf-8").splitlines() if ln.strip()]
    horses: list[tuple[str, str, str]] = []
    unparsed: list[str] = []
    for u in urls:
        parsed = _parse_horse_url(u)
        if parsed:
            horses.append((parsed[0], parsed[1], u))
        else:
            unparsed.append(u)
    if limit:
        horses = horses[:limit]

    out_dir = raw_dir / capture_date
    payload: dict = {
        "mode": "horse_form_api_capture",
        "capture_date": capture_date,
        "generated_at": _utc_now(),
        "url_list": str(url_list),
        "output_dir": str(out_dir),
        "horses_requested": len(horses),
        "urls_unparsed": len(unparsed),
        "collector": "capture_rp_horse_form_api_v1",
        "raw_first": True,
        "credentials_in_code": False,
        "captures": [],
    }

    if not execute:
        payload["status"] = "DRY_RUN"
        payload["execute_required"] = True
        return payload

    out_dir.mkdir(parents=True, exist_ok=True)
    sync_playwright = _import_playwright()
    ok = 0

    with sync_playwright() as p:
        ctx = p.firefox.launch_persistent_context(str(profile_dir), headless=True)
        page = ctx.new_page()
        try:
            for idx, (hid, slug, url) in enumerate(horses, start=1):
                rec: dict = {"horse_id": hid, "slug": slug, "source_url": url,
                             "started_at": _utc_now()}
                try:
                    # The navigation is not optional — the API rejects requests
                    # that do not originate from the horse's own profile page.
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)

                    form_res = page.request.get(API_FORM.format(hid=hid))
                    rec["form_http_status"] = form_res.status
                    if form_res.status != 200:
                        rec["status"] = f"FORM_HTTP_{form_res.status}"
                        payload["captures"].append(rec)
                        continue

                    form_json = form_res.json()
                    record_json = None
                    profile_json = None
                    # Career record and identity are useful but must never sink
                    # a horse whose form we already hold.
                    try:
                        r = page.request.get(API_RECORD.format(hid=hid))
                        if r.status == 200:
                            record_json = r.json()
                    except Exception:
                        pass
                    try:
                        r = page.request.get(API_PROFILE.format(hid=hid))
                        if r.status == 200:
                            profile_json = r.json()
                    except Exception:
                        pass

                    doc = {
                        "captured_at": _utc_now(),
                        "capture_date": capture_date,
                        "horse_id": int(hid),
                        "slug": slug,
                        "source_url": url,
                        "form": form_json,
                        "record": record_json,
                        "profile": profile_json,
                    }
                    fp = out_dir / f"horse_{hid}.json"
                    fp.write_text(json.dumps(doc, indent=2, ensure_ascii=False),
                                  encoding="utf-8")

                    n_runs = len((form_json or {}).get("form") or {})
                    rec.update({"status": "PASS", "runs": n_runs, "json_path": str(fp)})
                    ok += 1
                except Exception as exc:
                    rec["status"] = f"ERROR_{type(exc).__name__}"
                    rec["error"] = str(exc)[:300]
                rec["finished_at"] = _utc_now()
                payload["captures"].append(rec)

                if idx % 50 == 0:
                    print(f"  {idx}/{len(horses)} horses, {ok} captured", flush=True)
                if delay_seconds:
                    time.sleep(delay_seconds)
        finally:
            ctx.close()

    payload["horses_captured"] = ok
    payload["total_runs"] = sum(c.get("runs", 0) for c in payload["captures"])
    rate = ok / len(horses) if horses else 0.0
    payload["success_rate"] = round(rate, 4)

    if not horses:
        payload["status"] = "FAIL_NO_HORSE_URLS"
        payload["failure_reason"] = (
            f"url list {url_list} produced no parseable horse profile URLs "
            f"({len(unparsed)} unparsed line(s))"
        )
    elif rate < MIN_SUCCESS_RATE:
        from collections import Counter
        reasons = Counter(c.get("status") for c in payload["captures"]).most_common(3)
        payload["status"] = "FAIL_CAPTURE_RATE_COLLAPSED"
        payload["failure_reason"] = (
            f"captured {ok}/{len(horses)} ({rate:.1%}) horses, below the "
            f"{MIN_SUCCESS_RATE:.0%} floor; statuses: {reasons}"
        )
    else:
        payload["status"] = "PASS"

    (out_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["manifest"] = str(out_dir / "manifest.json")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True, help="Capture tag, e.g. passport-bank-2026-09-03")
    ap.add_argument("--url-list", required=True)
    ap.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    ap.add_argument("--profile-dir", default=str(DEFAULT_PROFILE))
    ap.add_argument("--delay-seconds", type=float, default=1.2)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    payload = capture(
        url_list=Path(args.url_list),
        capture_date=args.date,
        raw_dir=Path(args.raw_dir),
        profile_dir=Path(args.profile_dir),
        delay_seconds=args.delay_seconds,
        limit=args.limit,
        execute=args.execute,
    )

    summary = {k: v for k, v in payload.items() if k != "captures"}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nHORSE_FORM_API_CAPTURE {payload.get('status')} "
          f"horses={payload.get('horses_captured', 0)}/{payload.get('horses_requested', 0)} "
          f"runs={payload.get('total_runs', 0)}")

    status = payload.get("status", "")
    if status.startswith("FAIL"):
        print(f"\n[FAIL] {status}: {payload.get('failure_reason', '')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
