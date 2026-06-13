from __future__ import annotations
from bs4 import BeautifulSoup
#!/usr/bin/env python3
"""
Parse Racing Post results capture HTML into normalized result truth.

Reads local HTML captured by racing_post_account_collector.py from the
rp-results-{date} capture directory. Extracts race results from __NEXT_DATA__,
normalizes runner positions and SPs, and writes to:

    data/results/rp_results_{date}.json

Horse IDs use the real Racing Post numeric horse ID (horseId from __NEXT_DATA__).
This matches the IDs in the injection JSON and racecard_loader, so RPDC, sigma,
and racing_horse_runs all resolve to the same horse across the full pipeline.
Synthetic rp_{VENUE}_{slug} is used only as a fallback when no real ID is found.

Usage:
    PYTHONPATH=. python scripts/ops/parse_rp_results_capture.py --date 2026-05-26 --execute
    PYTHONPATH=. python scripts/ops/parse_rp_results_capture.py --date 2026-05-26 --capture-date rp-results-2026-05-26 --execute
"""


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
    "wetherby": "WET",
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
        raw = str(sp_str).strip().lower()
        normalized = re.sub(r"(?:jf|f)$", "", raw).strip()
        if normalized in {"evens", "evs", "even"}:
            return 2.0
        cleaned = re.sub(r"[^0-9./]", "", normalized)
        if "/" in cleaned:
            num, den = cleaned.split("/", 1)
            return round(int(num) / int(den) + 1, 2)
        return round(float(cleaned), 2)
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



def race_id_from_html(path: Path) -> str:
    html = path.read_text(errors="ignore")
    m = re.search(r"\"raceId\":\"(\d+)\"", html)
    if m: return m.group(1)
    return ""
def _load_next_data(html_path: Path) -> dict[str, Any] | None:
    try:
        html = html_path.read_text(encoding="utf-8", errors="replace")
        match = NEXT_RE.search(html)
        if match:
            return json.loads(match.group(1))
        
        # Fallback to window.horseData
        match = re.search(r"window\.horseData\s*=\s*({.*?});", html, re.S)
        if match:
            data = json.loads(match.group(1))
            # Put it directly where _parse_result_page can find it if NEXT_DATA fails
            return {"_horseData": data}
        return None
    except Exception:
        return None


def _slug_from_url(url: str) -> str:
    """Extract course slug from RP URL: /results/{course_id}/{slug}/{date}/{race_id}/"""
    parts = [p for p in url.split("/") if p]
    if "results" in parts:
        i = parts.index("results")
        if len(parts) > i + 2:
            return parts[i + 2]
    if "racecards" in parts:
        i = parts.index("racecards")
        if len(parts) > i + 2:
            return parts[i + 2]
    return ""


def _canonical_url(html_path: Path) -> str:
    try:
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
        link = soup.find("link", rel=lambda v: v and "canonical" in v)
        return str(link.get("href") or "") if link else ""
    except Exception:
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


def _load_injection_index(date: str) -> dict[str, dict[str, Any]]:
    """Fallback index from injection JSON: race_id → {course, venue_code, race_time_raw}.
    Used when racecard_merged has race_id=None (no direct lookup possible).
    Also mines the morning racecard URL list + racecard_merged to cover race_ids
    that the injection parser may have skipped (e.g. late-added races).
    """
    idx: dict[str, dict[str, Any]] = {}
    parsed_root = ROOT / "data" / "racing_post_account_parsed"
    if parsed_root.exists():
        for label_dir in sorted(parsed_root.iterdir()):
            if date not in label_dir.name:
                continue
            injection_path = label_dir / "racecard_injection.json"
            if not injection_path.exists():
                continue
            try:
                data = json.loads(injection_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            races = data if isinstance(data, list) else data.get("races", data.get("racecards", []))
            for race in races:
                if not isinstance(race, dict):
                    continue
                race_id = str(race.get("race_id") or "")
                if not race_id or race_id in idx:
                    continue
                course = race.get("course") or ""
                slug = _slug_from_url(race.get("source_url") or "")
                venue_code = _get_venue(slug, course) or ""
                idx[race_id] = {
                    "course": course,
                    "venue_code": venue_code,
                    "race_time_raw": race.get("race_time") or "",
                }

    # Supplement: mine morning racecard URL list for race_ids not in injection.
    # Cross-reference with racecard_merged to resolve off_time for those races.
    url_list = ROOT / "data" / "racing_post_url_lists" / f"rp_racecards_{date}.txt"
    merged_dir = ROOT / "data" / "racecard_merged"
    if url_list.exists() and merged_dir.exists():
        # Build slug→{off_time: True} map from racecard_merged (keyed by off_time).
        # Also build a per-venue off_times list for cross-reference.
        venue_off_map: dict[str, list[str]] = {}  # venue_code → sorted off_times in merged
        venue_slug_to_name: dict[str, str] = {}
        date_tag = date.replace("-", "_")
        # Try both date format patterns in merged filenames
        for pattern in [f"racecard_*_{date}.json", f"racecard_*_{date_tag}.json"]:
            for path in sorted(merged_dir.glob(pattern)):
                try:
                    mdata = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                venue_code = mdata.get("venue_code") or ""
                course_name = mdata.get("venue") or mdata.get("course") or ""
                slug_key = path.stem.split("_")[1].lower() if "_" in path.stem else ""
                races_m = mdata.get("races") or {}
                off_list = sorted(races_m.keys()) if isinstance(races_m, dict) else []
                if venue_code:
                    venue_off_map[venue_code] = off_list
                    venue_slug_to_name[slug_key] = (venue_code, course_name)

        # Parse morning URL list to find race_ids not yet in idx
        import re as _re
        url_re = _re.compile(r'/racecards/(\d+)/([^/]+)/[^/]+/(\d+)')
        known_race_ids_by_venue: dict[str, list[str]] = {}
        extra_race_ids: list[tuple[str, str, str]] = []  # (race_id, course_slug, course_id_str)
        for line in url_list.read_text(encoding="utf-8").splitlines():
            m = url_re.search(line.strip())
            if not m:
                continue
            _course_id, course_slug, race_id = m.group(1), m.group(2), m.group(3)
            v_code = _get_venue(course_slug, "")
            known_race_ids_by_venue.setdefault(v_code, []).append(race_id)
            if race_id not in idx:
                extra_race_ids.append((race_id, course_slug, _course_id))

        # For each extra race_id, resolve off_time by comparing against known race_ids
        # already resolved in idx for the same venue, then assigning remaining off_times.
        for race_id, course_slug, _course_id in extra_race_ids:
            if race_id in idx:
                continue
            v_code = _get_venue(course_slug, "")
            course_name = ""
            for slug_key, (vc, cn) in venue_slug_to_name.items():
                if slug_key == course_slug.lower() or vc == v_code:
                    course_name = cn
                    break
            all_off_times = venue_off_map.get(v_code, [])
            # Find off_times already assigned to this venue
            assigned = {
                v["race_time_raw"]
                for rid, v in idx.items()
                if v.get("venue_code") == v_code
            }
            all_known_rids = known_race_ids_by_venue.get(v_code, [])
            already_indexed = [r for r in all_known_rids if r in idx]
            unindexed_rids = [r for r in all_known_rids if r not in idx]
            # off_times not yet used by known indexed race_ids → map to unindexed
            # Use dot-time format to match racecard_merged keys
            def _dot_time(off: str) -> str:
                """Convert 'H.MM' to ISO-like for sorting; keep as-is for now."""
                return off
            used_off_times: set[str] = set()
            for rid in already_indexed:
                rt = idx[rid].get("race_time_raw", "")
                # Convert ISO race_time to dot_time (H.MM BST)
                try:
                    from datetime import datetime, timezone, timedelta
                    dt = datetime.fromisoformat(rt)
                    dt_bst = dt.astimezone(timezone(timedelta(hours=1)))
                    h12 = dt_bst.hour - 12 if dt_bst.hour > 12 else dt_bst.hour
                    used_off_times.add(f"{h12}.{dt_bst.minute:02d}")
                except Exception:
                    pass
            free_off_times = [o for o in all_off_times if o not in used_off_times]
            if len(unindexed_rids) == 1 and len(free_off_times) == 1:
                # Unambiguous assignment
                off = free_off_times[0]
                # Build synthetic ISO time from dot-time + date for race_time_raw
                try:
                    h, m2 = off.split(".")
                    race_time_raw = f"{date}T{int(h):02d}:{int(m2):02d}:00+01:00"
                except Exception:
                    race_time_raw = ""
                idx[race_id] = {
                    "course": course_name,
                    "venue_code": v_code,
                    "race_time_raw": race_time_raw,
                }
    return idx


def _load_racecard_index(date: str) -> dict[str, dict[str, Any]]:
    """
    Index same-day RP racecard cache by RP raceId.

    Current RP result captures expose finish order in window.horseData, but only
    include horse IDs. The racecard cache is also RP-derived and gives us the
    stable identity layer needed for Sigma matching.
    """
    idx: dict[str, dict[str, Any]] = {}
    card_dir = ROOT / "data" / "racecard_merged"
    for path in sorted(card_dir.glob(f"racecard_*_{date}.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        venue = data.get("venue") or ""
        venue_code = data.get("venue_code") or ""
        races = data.get("races") or {}
        if not isinstance(races, dict):
            continue
        for off, race in races.items():
            if not isinstance(race, dict):
                continue
            race_id = str(race.get("race_id") or "")
            if not race_id:
                continue
            horses = race.get("horses") or []
            horses_by_uid = {
                str(h.get("horse_id")): h
                for h in horses
                if isinstance(h, dict) and h.get("horse_id")
            }
            idx[race_id] = {
                "venue": venue,
                "venue_code": venue_code,
                "off": str(off),
                "race_info": race.get("race_info") or {},
                "horses_by_uid": horses_by_uid,
            }
    return idx


def _load_readiness_index(date: str) -> dict[str, dict[str, Any]]:
    date_tag = date.replace("-", "_")
    path = ROOT / "data" / "new_build" / "reports" / f"two_lane_readiness_{date_tag}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    scorecards = data.get("race_day_scorecards") or []
    return {
        str(r.get("race_id")): r
        for r in scorecards
        if isinstance(r, dict) and r.get("race_id")
    }


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
    # Handle "1 " or " 1"
    if re.match(r"^\s*(\d+)", s):
        return re.match(r"^\s*(\d+)", s).group(1)
    if s in DNF_POSITIONS:
        return s
    return s


def _parse_runner(
    runner: dict[str, Any],
    venue: str,
    horse_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    # Handle horseData nesting
    if "runnerInfo" in runner:
        info = runner["runnerInfo"]
        runner = runner.copy()
        runner.update(info)

    horse_rp_uid = runner.get("horseId") or runner.get("horse_id") or ""
    card_horse = (horse_lookup or {}).get(str(horse_rp_uid), {})

    horse_name = (
        runner.get("horseName")
        or runner.get("horse")
        or runner.get("name")
        or card_horse.get("horse_name")
        or ""
    )

    # Finishing position — RP results pages use finishingPosition
    pos = _parse_position(
        runner.get("outcomeCode")
        or runner.get("finishingPosition")
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
        or card_horse.get("sp")
        or ""
    )
    sp_decimal = runner.get("bspDecimal") or runner.get("startingPriceDecimal") or 0.0
    if not sp_decimal:
        sp_decimal = _sp_dec(str(sp_raw))

    non_runner = bool(runner.get("nonRunner") or runner.get("non_runner"))

    velo_id = _velo_horse_id(venue, horse_name) if venue and horse_name else ""
    _real_rp_id = str(horse_rp_uid) if horse_rp_uid else ""

    return {
        "horse_id": _real_rp_id or velo_id,
        "horse_rp_uid": _real_rp_id,
        "horse": horse_name,
        "position": pos,
        "sp": str(sp_raw),
        "sp_dec": float(sp_decimal),
        "non_runner": non_runner,
        "draw": runner.get("draw", "") or card_horse.get("draw", ""),
        "jockey": runner.get("jockeyName") or runner.get("jockey") or card_horse.get("jockey_name") or card_horse.get("jockey") or "",
        "trainer": runner.get("trainerName") or runner.get("trainer") or card_horse.get("trainer_name") or card_horse.get("trainer") or "",
    }


def _scrape_table_horse_lookup(html_path: Path) -> dict[str, dict[str, Any]]:
    """Fallback identity layer for legacy RP result pages.

    Some RP result captures expose only horse IDs and positions in
    window.horseData. The visible result table still contains the horse names,
    SPs, jockeys and trainers, so use it to resolve those IDs without leaving
    the RP source universe.
    """
    lookup: dict[str, dict[str, Any]] = {}

    def clean(text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        return re.sub(r"\s+right$", "", text, flags=re.I).strip()

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    for row in soup.select('tr[data-test-selector="table-row"]'):
        link = row.find("a", href=lambda h: h and "/profile/horse/" in h)
        if not link:
            continue
        m = re.search(r"/profile/horse/(\d+)/", link.get("href") or "")
        if not m:
            continue
        uid = m.group(1)
        price = row.select_one(".rp-horseTable__horse__price")
        jockey = row.select_one('[data-test-selector="link-jockeyName"]')
        trainer = row.select_one('[data-test-selector="link-trainerName"]')
        draw = row.select_one(".rp-horseTable__pos__draw")
        lookup[uid] = {
            "horse_name": clean(link.get_text(" ", strip=True)),
            "sp": clean(price.get_text(" ", strip=True)) if price else "",
            "jockey_name": clean(jockey.get_text(" ", strip=True)) if jockey else "",
            "trainer_name": clean(trainer.get_text(" ", strip=True)) if trainer else "",
            "draw": re.sub(r"[^0-9]", "", draw.get_text(" ", strip=True)) if draw else "",
        }
    return lookup


def _parse_result_page(
    html_path: Path,
    source_url: str,
    racecard_index: dict[str, dict[str, Any]],
    readiness_index: dict[str, dict[str, Any]],
    injection_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    source_url = source_url or _canonical_url(html_path)
    next_data = _load_next_data(html_path)
    if not next_data:
        return None

    page_data = _find_result_data(next_data)
    if not page_data and "_horseData" in next_data:
        hd = next_data["_horseData"]
        page_data = {
            "race": {"raceId": hd.get("raceId")},
            "runners": hd.get("items", [])
        }
    
    if not page_data:
        # Fallback: Scrape table directly using BeautifulSoup
        try:
            soup = BeautifulSoup(html_path.read_text(errors="ignore"), "html.parser")
            rows = soup.find_all("tr")
            runners_table = []
            for r in rows:
                text = r.get_text()
                match = re.search(r"(\d+)\s*\(\d+\)", text)
                if match:
                    pos = match.group(1)
                    link = r.find("a", href=lambda h: h and "/profile/horse/" in h)
                    if link:
                        name = link.get_text().strip()
                        uid = link["href"].split("/")[3]
                        sp_m = re.search(r"(\d+/\d+[A-Z]?)", text)
                        sp = sp_m.group(1) if sp_m else "??/?"
                        runners_table.append({
                            "horseName": name,
                            "horseId": uid,
                            "outcomeCode": pos,
                            "startingPrice": sp
                        })
            if runners_table:
                page_data = {
                    "race": {"raceId": str(race_id_from_html(html_path))},
                    "runners": runners_table
                }
        except: pass
    
    if not page_data:
        return None

    race = page_data.get("race") or {}
    runners_raw = page_data.get("runners") or []

    race_id = str(race.get("raceId") or "")
    if not race_id:
        return None

    card_meta = racecard_index.get(race_id, {})
    ready_meta = readiness_index.get(race_id, {})
    inj_meta = (injection_index or {}).get(race_id, {})
    race_info = card_meta.get("race_info") or {}
    # Field-level merge: card_meta is the base (rich pre-race data),
    # table_lookup overlays live results values (SP, final jockey/trainer).
    # Must NOT do a uid-level .update() because cards have sp=None which
    # overwrites the real SP found in the results table.
    _table_lk = dict(_scrape_table_horse_lookup(html_path))
    _card_lk = card_meta.get("horses_by_uid") or {}
    horse_lookup: dict[str, dict[str, Any]] = {}
    for uid in set(list(_table_lk.keys()) + list(_card_lk.keys())):
        base = dict(_card_lk.get(uid) or {})
        for k, v in (_table_lk.get(uid) or {}).items():
            if v:  # table value wins when non-empty (SP, jockey, trainer, draw)
                base[k] = v
        horse_lookup[uid] = base

    # Course info
    course_name = (
        race.get("courseStyleName")
        or race.get("courseName")
        or ready_meta.get("course")
        or card_meta.get("venue")
        or inj_meta.get("course")
        or ""
    )
    course_id = str(race.get("courseId") or "")
    course_slug = _slug_from_url(source_url)
    venue = _get_venue(course_slug, course_name) or card_meta.get("venue_code") or inj_meta.get("venue_code") or ""

    # Race time → BST H.MM
    race_time_raw = (
        race.get("raceTime")
        or race.get("startTime")
        or ready_meta.get("off_time")
        or card_meta.get("off")
        or inj_meta.get("race_time_raw")
        or ""
    )
    off_bst = _bst_hhmm(race_time_raw) if race_time_raw else ""

    # Status — results pages should show R/C; racecard shows O
    status = race.get("status") or "RESULT"

    runners = [
        _parse_runner(r, venue, horse_lookup)
        for r in runners_raw
        if isinstance(r, dict)
    ]
    seen_uids = {r.get("horse_rp_uid") for r in runners if r.get("horse_rp_uid")}
    for uid, card_horse in horse_lookup.items():
        if uid in seen_uids:
            continue
        horse_name = card_horse.get("horse_name") or card_horse.get("horse") or ""
        runners.append({
            "horse_id": uid or (_velo_horse_id(venue, horse_name) if venue and horse_name else ""),
            "horse_rp_uid": uid,
            "horse": horse_name,
            "position": "NR",
            "sp": "",
            "sp_dec": 0.0,
            "non_runner": True,
            "draw": card_horse.get("draw", ""),
            "jockey": card_horse.get("jockey_name") or card_horse.get("jockey") or "",
            "trainer": card_horse.get("trainer_name") or card_horse.get("trainer") or "",
        })

    # Sort by position (numeric first, then DNF)
    def _sort_key(r: dict) -> tuple:
        p = r["position"]
        return (0, int(p)) if p.isdigit() else (1, p)

    runners.sort(key=_sort_key)
    
    # DEBUG
    # print(f"DEBUG {race_id}: first runner position is {runners[0]["position"] if runners else "NONE"}")

    finishers = [r for r in runners if r["position"].isdigit() and not r["non_runner"]]
    winner = finishers[0] if finishers else {}
    if not winner and runners:
        w_list = [r for r in runners if str(r.get("position")).strip() == "1"]
        winner = w_list[0] if w_list else {}
    top3 = finishers[:3] if finishers else runners[:3]

    return {
        "race_id": race_id,
        "course_id": course_id,
        "course_slug": course_slug,
        "course": course_name,
        "venue": venue,
        "off": off_bst,
        "race_time_raw": race_time_raw,
        "race_name": race.get("raceTitle") or race.get("raceName") or ready_meta.get("race_title") or race_info.get("race_title") or "",
        "race_class": race.get("raceClass") or race_info.get("race_class") or "",
        "going": race.get("going") or race_info.get("going") or "",
        "distance_f": race.get("distanceFurlongs") or race_info.get("distance_furlongs") or "",
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
    racecard_index = _load_racecard_index(date)
    readiness_index = _load_readiness_index(date)
    injection_index = _load_injection_index(date)

    for html_path in html_files:
        source_url = url_by_html.get(str(html_path), "")
        parsed = _parse_result_page(html_path, source_url, racecard_index, readiness_index, injection_index)
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
        "racecard_indexed": len(racecard_index),
        "readiness_indexed": len(readiness_index),
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
