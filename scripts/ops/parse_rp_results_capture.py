#!/usr/bin/env python3
"""
Parse Racing Post results capture HTML into normalized result truth.

Reads local HTML captured by racing_post_account_collector.py from the
rp-results-{date} capture directory. Extracts race results from __NEXT_DATA__,
normalizes runner positions and SPs, and writes to:

    data/results/rp_results_{date}.json

Horse IDs use the same rp_{VENUE}_{slug} formula as the SL scraper and VELO
predictions, so sigma can match directly by race_id without course/time fallback.

Usage:
    PYTHONPATH=. python scripts/ops/parse_rp_results_capture.py --date 2026-05-26 --execute
    PYTHONPATH=. python scripts/ops/parse_rp_results_capture.py --date 2026-05-26 --capture-date rp-results-2026-05-26 --execute
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = ROOT / "data" / "racing_post_account_raw"
OUT_DIR = ROOT / "data" / "results"

NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

# RP course URL slug → VELO venue code
RP_SLUG_TO_VELO: dict[str, str] = {
    "leicester": "LEI",
    "redcar": "RED",
    "bath": "BAT",
    "lingfield": "LIN",
    "lingfield-aw": "LIN",
    "plumpton": "PLU",
    "goodwood": "GOO",
    "newmarket": "NMK",
    "newmarket-rowley": "NMK",
    "newmarket-july": "NMK",
    "newcastle": "NEW",
    "newcastle-aw": "NEW",
    "ascot": "ASC",
    "york": "YOR",
    "sandown": "SAN",
    "windsor": "WDR",
    "kempton": "KEM",
    "kempton-aw": "KEM",
    "wolverhampton": "WOL",
    "wolverhampton-aw": "WOL",
    "chelmsford": "CHM",
    "chelmsford-aw": "CHM",
    "carlisle": "CAR",
    "chester": "CHE",
    "nottingham": "NOT",
    "pontefract": "PON",
    "ripon": "RIP",
    "beverley": "BEV",
    "catterick": "CAT",
    "hamilton": "HAM",
    "haydock": "HAY",
    "musselburgh": "MUS",
    "ayr": "AYR",
    "warwick": "WAR",
    "yarmouth": "YAR",
    "brighton": "BRI",
    "epsom": "EPS",
    "chepstow": "CHP",
    "salisbury": "SAL",
    "southwell": "SOU",
    "southwell-aw": "SOU",
    "huntingdon": "HUN",
    "hexham": "HEX",
    "kelso": "KEL",
    "perth": "PER",
    "stratford": "STR",
    "uttoxeter": "UTT",
    "taunton": "TAU",
    "ludlow": "LUD",
    "market-rasen": "MKT",
    "aintree": "AIN",
    "cartmel": "CRT",
    "worcester": "WOR",
    "ffos-las": "FFO",
    "bangor-on-dee": "BAN",
    "hereford": "HER",
    "exeter": "EXE",
    "fontwell": "FLK",
    "wincanton": "WIN",
    # Irish
    "dundalk-aw": "DUN",
    "dundalk": "DUN",
    "ballinrobe": "BAL",
    "galway": "GAL",
    "leopardstown": "LEO",
    "leopardstown-aw": "LEO",
    "curragh": "CUR",
    "navan": "NAV",
    "cork": "COR",
    "naas": "NAA",
    "gowran": "GOW",
    "gowran-park": "GOW",
    "tipperary": "TIP",
    "tramore": "TRA",
    "killarney": "KIL",
    "fairyhouse": "FAI",
    "wexford": "WEX",
    "clonmel": "CLO",
    "sligo": "SLI",
    "down-royal": "DRO",
    "downpatrick": "DPT",
    "punchestown": "PAT",
    "limerick": "LIM",
    "bellewstown": "HER",
    "kilbeggan": "KLB",
    "roscommon": "RHO",
    "listowel": "LIM",
    "thurles": "TIP",
}

# RP course name → VELO code (fallback when slug not in map)
RP_COURSENAME_TO_VELO: dict[str, str] = {
    "dundalk (a.w)": "DUN",
    "dundalk aw": "DUN",
    "dundalk": "DUN",
    "ballinrobe": "BAL",
    "leicester": "LEI",
    "redcar": "RED",
    "bath": "BAT",
    "lingfield (aw)": "LIN",
    "lingfield": "LIN",
    "plumpton": "PLU",
}

DNF_POSITIONS = {"NR", "WD", "PU", "F", "BD", "UR", "SU", "RO", "REF", "DSQ"}

# These capture folder names are checked in order for a given date
CAPTURE_CANDIDATES = [
    "rp-results-{date}",
    "rp_results_{date}",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _velo_horse_id(venue: str, horse_name: str) -> str:
    return f"rp_{venue}_{_slug(horse_name)}"


def _sp_dec(sp_str: str) -> float:
    if not sp_str:
        return 0.0
    try:
        if "/" in str(sp_str):
            num, den = str(sp_str).split("/", 1)
            return round(int(num) / int(den) + 1, 2)
        return round(float(sp_str), 2)
    except Exception:
        return 0.0


def _bst_hhmm(dt_str: str) -> str:
    """ISO datetime or HH:MM → BST H.MM (no leading zero, 12h afternoon)."""
    try:
        if "T" in dt_str:
            # e.g. "2026-05-26T17:07:00+01:00"
            dt = datetime.fromisoformat(dt_str)
            h, m = dt.hour, dt.minute  # already BST if +01:00
        else:
            h, m = map(int, dt_str.split(":"))
        if h >= 13:
            h -= 12
        return f"{h}.{m:02d}"
    except Exception:
        return dt_str


def _load_next_data(html_path: Path) -> dict[str, Any] | None:
    try:
        html = html_path.read_text(encoding="utf-8", errors="replace")
        match = NEXT_RE.search(html)
        if not match:
            return None
        return json.loads(match.group(1))
    except Exception:
        return None


def _slug_from_url(url: str) -> str:
    """Extract course slug from RP URL: /results/{course_id}/{slug}/{date}/{race_id}/"""
    parts = [p for p in url.split("/") if p]
    if len(parts) >= 4 and parts[0] in ("results", "racecards"):
        return parts[2]
    return ""


def _get_venue(course_slug: str, course_name: str) -> str:
    if course_slug:
        v = RP_SLUG_TO_VELO.get(course_slug.lower())
        if v:
            return v
    if course_name:
        v = RP_COURSENAME_TO_VELO.get(course_name.lower())
        if v:
            return v
    return ""


def _find_result_data(next_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Try multiple known NEXT_DATA paths for result race data.
    RP results pages may use resultPage or racePage depending on app version.
    """
    ist = next_data.get("props", {}).get("pageProps", {}).get("initialState", {})
    if not ist:
        return None

    candidates = [
        # Results page primary path
        ist.get("resultPage", {}).get("data"),
        ist.get("result", {}).get("data"),
        ist.get("resultRacePage", {}).get("data"),
        # Racecards path (used on results pages too in some RP builds)
        ist.get("racePage", {}).get("data"),
    ]
    for c in candidates:
        if c and c.get("race"):
            return c
    return None


def _parse_position(val: Any) -> str:
    """Normalize finishing position from RP result runner."""
    if val is None:
        return ""
    s = str(val).strip().upper()
    if s.isdigit():
        return s
    if s in DNF_POSITIONS:
        return s
    # Some RP pages encode position as dict or int
    return s


def _parse_runner(runner: dict[str, Any], venue: str) -> dict[str, Any]:
    horse_name = (
        runner.get("horseName")
        or runner.get("horse")
        or runner.get("name")
        or ""
    )
    horse_rp_uid = runner.get("horseId") or runner.get("horse_id") or ""

    # Finishing position — RP results pages use finishingPosition
    pos = _parse_position(
        runner.get("finishingPosition")
        or runner.get("position")
        or runner.get("finishPosition")
        or runner.get("finishing_position")
    )

    # SP — try multiple field names
    sp_raw = (
        runner.get("startingPrice")
        or runner.get("startingPriceText")
        or runner.get("sp")
        or runner.get("spRaw")
        or ""
    )
    sp_decimal = runner.get("bspDecimal") or runner.get("startingPriceDecimal") or 0.0
    if not sp_decimal:
        sp_decimal = _sp_dec(str(sp_raw))

    non_runner = bool(runner.get("nonRunner") or runner.get("non_runner"))

    velo_id = _velo_horse_id(venue, horse_name) if venue and horse_name else ""

    return {
        "horse_id": velo_id,
        "horse_rp_uid": str(horse_rp_uid) if horse_rp_uid else "",
        "horse": horse_name,
        "position": pos,
        "sp": str(sp_raw),
        "sp_dec": float(sp_decimal),
        "non_runner": non_runner,
        "draw": runner.get("draw", ""),
        "jockey": runner.get("jockeyName") or runner.get("jockey") or "",
        "trainer": runner.get("trainerName") or runner.get("trainer") or "",
    }


def _parse_result_page(
    html_path: Path, source_url: str
) -> dict[str, Any] | None:
    next_data = _load_next_data(html_path)
    if not next_data:
        return None

    page_data = _find_result_data(next_data)
    if not page_data:
        return None

    race = page_data.get("race") or {}
    runners_raw = page_data.get("runners") or []

    race_id = str(race.get("raceId") or "")
    if not race_id:
        return None

    # Course info
    course_name = race.get("courseStyleName") or race.get("courseName") or ""
    course_id = str(race.get("courseId") or "")
    course_slug = _slug_from_url(source_url)
    venue = _get_venue(course_slug, course_name)

    # Race time → BST H.MM
    race_time_raw = race.get("raceTime") or race.get("startTime") or ""
    off_bst = _bst_hhmm(race_time_raw) if race_time_raw else ""

    # Status — results pages should show R/C; racecard shows O
    status = race.get("status") or ""

    runners = [_parse_runner(r, venue) for r in runners_raw if isinstance(r, dict)]

    # Sort by position (numeric first, then DNF)
    def _sort_key(r: dict) -> tuple:
        p = r["position"]
        return (0, int(p)) if p.isdigit() else (1, p)

    runners.sort(key=_sort_key)

    finishers = [r for r in runners if r["position"].isdigit() and not r["non_runner"]]
    winner = finishers[0] if finishers else {}
    top3 = finishers[:3]

    return {
        "race_id": race_id,
        "course_id": course_id,
        "course_slug": course_slug,
        "course": course_name,
        "venue": venue,
        "off": off_bst,
        "race_time_raw": race_time_raw,
        "race_name": race.get("raceTitle") or race.get("raceName") or "",
        "race_class": race.get("raceClass") or "",
        "going": race.get("going") or "",
        "distance_f": race.get("distanceFurlongs") or "",
        "field_size": len(runners),
        "status": status,
        "winner_horse": winner.get("horse", ""),
        "winner_id": winner.get("horse_id", ""),
        "winner_rp_uid": winner.get("horse_rp_uid", ""),
        "winner_sp": winner.get("sp_dec", 0.0),
        "top3_ids": [r["horse_id"] for r in top3],
        "top3_rp_uids": [r["horse_rp_uid"] for r in top3],
        "top3_names": [r["horse"] for r in top3],
        "runners": runners,
        "source": "racing_post",
        "source_url": source_url,
        "raw_file": str(html_path),
    }


def _find_capture_dir(date: str) -> Path | None:
    for pattern in CAPTURE_CANDIDATES:
        d = RAW_ROOT / pattern.format(date=date)
        if d.exists():
            return d
    return None


def parse_results(
    *, date: str, capture_date: str | None, execute: bool
) -> dict[str, Any]:
    cap_date = capture_date or f"rp-results-{date}"
    cap_dir = RAW_ROOT / cap_date
    if not cap_dir.exists():
        # Try auto-discovery
        found = _find_capture_dir(date)
        if found:
            cap_dir = found
            cap_date = found.name
        else:
            return {
                "status": "FAIL",
                "error": f"Capture directory not found: {cap_dir}",
                "hint": f"Run: python scripts/ops/racing_post_account_collector.py capture "
                        f"--url-list data/racing_post_url_lists/rp_results_{date}.txt "
                        f"--date rp-results-{date} --execute --headed",
            }

    html_files = sorted(cap_dir.glob("*.html"))
    manifest_path = cap_dir / "manifest.json"
    manifest: dict = {}
    url_by_html: dict[str, str] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for cap in manifest.get("captures", []):
            if cap.get("html_path"):
                url_by_html[cap["html_path"]] = cap.get("source_url", "")

    results: list[dict[str, Any]] = []
    parse_errors: list[dict] = []

    for html_path in html_files:
        source_url = url_by_html.get(str(html_path), "")
        parsed = _parse_result_page(html_path, source_url)
        if parsed:
            if not parsed.get("winner_horse"):
                parse_errors.append({
                    "file": html_path.name,
                    "race_id": parsed.get("race_id"),
                    "reason": "NO_WINNER_FOUND — page may be pre-race or have no result data",
                    "status": parsed.get("status"),
                })
            else:
                results.append(parsed)
        else:
            parse_errors.append({
                "file": html_path.name,
                "reason": "NO_RESULT_DATA_IN_NEXT_DATA",
            })

    results.sort(key=lambda r: (r.get("off") or "", r.get("race_id") or ""))

    payload: dict[str, Any] = {
        "source": "racing_post",
        "date": date,
        "capture_date": cap_date,
        "capture_dir": str(cap_dir),
        "generated_at": _utc_now(),
        "html_files_seen": len(html_files),
        "races_parsed": len(results),
        "parse_errors": len(parse_errors),
        "parse_error_details": parse_errors,
        "results": results,
    }

    if not execute:
        payload["status"] = "DRY_RUN"
        return payload

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"rp_results_{date.replace('-', '_')}.json"
    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["status"] = "PASS"
    payload["output"] = str(out_file)
    print(f"  Wrote: {out_file}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse RP results captures into normalized result truth for Sigma."
    )
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    parser.add_argument(
        "--capture-date",
        default=None,
        help="Capture folder name under racing_post_account_raw/ (default: rp-results-{date})",
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    result = parse_results(
        date=args.date,
        capture_date=args.capture_date,
        execute=args.execute,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
