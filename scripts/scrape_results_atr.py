#!/usr/bin/env python3
"""
Scrape today's results from Sporting Life and build data/results_YYYY_MM_DD.json
in the Racing API format that run_results_sigma.py expects.

Uses the cached racecard (data/racecards_YYYY_MM_DD_standard.json) for
race_ids and horse_ids so sigma matching works correctly.

Usage:
    python scripts/scrape_results_atr.py --date 2026-05-15
"""
import argparse
import json
import re
import time
from pathlib import Path
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

# Courses we want to scrape (lowercase SL name → normalised)
TARGET_COURSES = {
    "york", "newmarket", "newbury", "hamilton", "aintree",
    "leopardstown", "kilbeggan",
    # 2026-05-16 venues
    "bangor-on-dee", "doncaster", "navan", "thirsk", "uttoxeter", "wexford",
    # 2026-05-17 venues
    "hamilton", "naas", "ripon", "stratford",
    # 2026-05-18 venues
    "carlisle", "lingfield", "redcar", "roscommon", "windsor", "wolverhampton",
    # common extras
    "chester", "haydock", "ascot", "goodwood", "sandown", "kempton",
    "nottingham", "pontefract", "redcar", "salisbury", "yarmouth",
    "musselburgh", "ayr", "kelso", "catterick", "chepstow", "exeter",
    "fakenham", "ffos-las", "huntingdon", "leicester", "lingfield",
    "ludlow", "market-rasen", "newcastle", "perth", "plumpton",
    "southwell", "stratford", "taunton", "towcester", "warwick",
    "wetherby", "windsor", "wolverhampton", "worcester",
    "curragh", "cork", "galway", "gowran-park", "limerick", "tipperary",
    "tramore", "roscommon", "naas", "dundalk", "ballinrobe", "sligo",
    "fairyhouse", "down-royal", "clonmel",
}

# RP profile course code → Sporting Life URL slug
RP_COURSE_CODE_TO_SL = {
    "CRL": "carlisle",
    "ROS": "roscommon",
    "LIN": "lingfield",
    "RED": "redcar",
    "WIN": "windsor",
    "WOL": "wolverhampton",
    "AYR": "ayr",
    "ASC": "ascot",
    "BAT": "bath",
    "BEV": "beverley",
    "BRI": "brighton",
    "CAT": "catterick",
    "CHE": "chester",
    "CHM": "chelmsford-city",
    "CHT": "cheltenham",
    "CHW": "chepstow",
    "DON": "doncaster",
    "EPS": "epsom-downs",
    "EXE": "exeter",
    "FAK": "fakenham",
    "FFK": "ffos-las",
    "GOO": "goodwood",
    "HAY": "haydock",
    "HUN": "huntingdon",
    "KEL": "kelso",
    "KEM": "kempton",
    "LEI": "leicester",
    "LEO": "leopardstown",
    "LUD": "ludlow",
    "MKT": "market-rasen",
    "MUS": "musselburgh",
    "NAA": "naas",
    "NAV": "navan",
    "NEW": "newcastle",
    "NMK": "newmarket",
    "NOT": "nottingham",
    "NWB": "newbury",
    "PON": "pontefract",
    "PLU": "plumpton",
    "SAL": "salisbury",
    "SAN": "sandown",
    "SOU": "southwell",
    "TAU": "taunton",
    "THI": "thirsk",
    "WAR": "warwick",
    "WET": "wetherby",
    "WOR": "worcester",
    "YAR": "yarmouth",
    "YOR": "york",
    "COR": "cork",
    "CUR": "curragh",
    "GAL": "galway",
    "GOW": "gowran-park",
    "KIL": "kilbeggan",
    "LIM": "limerick",
    "TIP": "tipperary",
    "TRA": "tramore",
}


def normalise(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'[^a-z0-9 ]', '', name)
    return re.sub(r'\s+', ' ', name).strip()


def sp_to_dec(sp_str: str) -> float:
    if not sp_str:
        return 0.0
    sp_str = str(sp_str).strip().replace("Evs", "1/1").replace("EVS", "1/1")
    if "/" in sp_str:
        try:
            num, den = sp_str.split("/")
            return round(int(num.strip()) / int(den.strip()) + 1, 2)
        except Exception:
            pass
    try:
        return float(sp_str)
    except Exception:
        return 0.0


def _off_time_from_race_id(race_id: str) -> str:
    """Extract off_time from race_id: '2026-05-18_Lingfield_350' → '3:50'."""
    parts = race_id.split("_")
    if len(parts) >= 3 and parts[-1].isdigit():
        t = parts[-1]
        return f"{t[0]}:{t[1:]}" if len(t) == 3 else f"{t[:2]}:{t[2:]}"
    return ""


def _sl_course_from_rp_code(code: str) -> str:
    """Map RP course abbreviation to Sporting Life URL slug."""
    mapped = RP_COURSE_CODE_TO_SL.get(code.upper())
    if mapped:
        return mapped
    # Full-word course names (Lingfield, Redcar, Windsor, Wolverhampton) pass through
    return code.lower()


def load_racecard_from_rp_profile(date: str) -> dict:
    """Build race map from rp_runner_profile_latest.parquet when no racecard cache exists."""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required for RP profile fallback")

    profile_path = ROOT / "data" / "features" / "rp_runner_profile_latest.parquet"
    if not profile_path.exists():
        raise FileNotFoundError(f"RP runner profile not found: {profile_path}")

    rp = pd.read_parquet(profile_path)
    rp_today = rp[rp["race_date"].astype(str) == date].copy()
    if rp_today.empty:
        raise ValueError(f"No RP profile rows for {date}")

    races: dict = {}
    for race_id, group in rp_today.groupby("race_id"):
        race_id = str(race_id)
        parts = race_id.split("_")
        rp_course_code = parts[1] if len(parts) >= 3 else ""
        sl_course = _sl_course_from_rp_code(rp_course_code)
        off_time = _off_time_from_race_id(race_id)

        runners = []
        for _, row in group.iterrows():
            def _val(v):
                try:
                    return "" if (v is None or (hasattr(v, '__class__') and v.__class__.__name__ == 'NAType')) else str(v)
                except Exception:
                    return ""
            horse_norm = re.sub(r"[^a-z0-9]", "", (_val(row.get("horse"))).lower())
            horse_id = _val(row.get("horse_id")) or f"RP_{horse_norm}"
            runners.append({
                "horse_id": horse_id,
                "horse": _val(row.get("horse")),
                "sp": "",
                "sp_dec": 0.0,
                "position": "",
                "draw": "",
                "number": "",
                "jockey": _val(row.get("jockey")),
                "jockey_id": "",
                "trainer": _val(row.get("trainer")),
                "trainer_id": "",
                "age": "",
                "or": _val(row.get("current_or")),
                "rpr": _val(row.get("current_rpr")),
                "tsr": _val(row.get("current_ts")),
            })

        name_to_runner = {normalise(r["horse"]): r for r in runners}
        races[race_id] = {
            "race_id":   race_id,
            "course":    sl_course,
            "course_id": "",
            "date":      date,
            "off":       off_time,
            "off_24h":   off_time,
            "off_dt":    "",
            "race_name": "",
            "type":      "",
            "class":     "",
            "dist":      "",
            "dist_f":    "",
            "going":     "",
            "surface":   "",
            "jumps":     False,
            "region":    "GB",
            "runners":   runners,
            "_name_to_runner": name_to_runner,
        }

    return races


def load_racecard(date: str) -> dict:
    path = ROOT / "data" / f"racecards_{date.replace('-', '_')}_standard.json"
    if not path.exists():
        print(f"  [WARN] No racecard cache for {date} — trying RP runner profile fallback")
        races = load_racecard_from_rp_profile(date)
        print(f"  [RP PROFILE] Built {len(races)} races from rp_runner_profile_latest.parquet")
        return races

    d = json.loads(path.read_text())
    cards = d.get("racecards", d) if isinstance(d, dict) else d

    races = {}
    for card in cards:
        rid = card.get("race_id") or card.get("id", "")
        runners = card.get("runners", [])
        name_to_runner = {normalise(r.get("horse", "")): r for r in runners}
        # off_time is like "4:35" (short) — normalise to HH:MM 24h
        off_raw = card.get("off_time") or ""
        off_dt = card.get("off_dt") or ""
        # Derive 24h time from off_dt if available
        if off_dt:
            m = re.search(r'T(\d{2}:\d{2})', off_dt)
            off_24h = m.group(1) if m else off_raw
        else:
            off_24h = off_raw
        races[rid] = {
            "race_id":   rid,
            "course":    card.get("course", ""),
            "course_id": card.get("course_id", ""),
            "date":      card.get("date", date),
            "off":       off_raw,
            "off_24h":   off_24h,
            "off_dt":    off_dt,
            "race_name": card.get("race_name", ""),
            "type":      card.get("type", ""),
            "class":     str(card.get("race_class", "")),
            "dist":      card.get("distance", ""),
            "dist_f":    card.get("distance_f", ""),
            "going":     card.get("going", ""),
            "surface":   card.get("surface", ""),
            "jumps":     card.get("jumps", False),
            "region":    card.get("region", "GB"),
            "runners":   runners,
            "_name_to_runner": name_to_runner,
        }
    return races


def get_sl_race_links(date: str, session: requests.Session) -> list:
    """Fetch SL daily results page and return list of race detail links for target courses."""
    url = f"https://www.sportinglife.com/racing/results/{date}"
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if f"/racing/results/{date}/" in href and "#" not in href:
            # Extract course from URL: /racing/results/DATE/COURSE/ID/SLUG
            parts = href.strip("/").split("/")
            if len(parts) >= 5:
                course = parts[3].lower()  # e.g. "york"
                if course in TARGET_COURSES and href not in seen:
                    seen.add(href)
                    links.append({"course": course, "url": "https://www.sportinglife.com" + href})

    return links


def fetch_race_detail(url: str, session: requests.Session) -> list:
    """Fetch SL race detail page and return list of ride dicts."""
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
    except Exception as e:
        print(f"    [SL] request error: {e}")
        return []
    if resp.status_code != 200:
        print(f"    [SL] HTTP {resp.status_code} for {url}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    nd = soup.find("script", id="__NEXT_DATA__")
    if not nd:
        return []
    try:
        d = json.loads(nd.string)
        race = d.get("props", {}).get("pageProps", {}).get("race", {})
        return race.get("rides", [])
    except Exception:
        return []


def rides_to_runners(rides: list, name_to_runner: dict) -> list:
    """Convert SL rides to Racing API runner format, injecting horse_ids from racecard."""
    runners = []
    for ride in rides:
        horse_name = ride.get("horse", {}).get("name", "")
        norm = normalise(horse_name)
        card_runner = name_to_runner.get(norm, {})

        status = ride.get("ride_status", "RUNNER")
        pos_int = ride.get("finish_position")

        # SL encodes finish_position=0 for non-finishers (fell/PU/UR/BD) even when
        # ride_status="RUNNER". Only positions >= 1 are valid finishing positions.
        if status == "NON_RUNNER":
            pos_str = "NR"
        elif status == "VOID":
            pos_str = "VOID"
        elif status in ("FALLEN", "PULLED_UP", "UNSEATED_RIDER", "BROUGHT_DOWN",
                        "REFUSED", "CARRIED_OUT", "SLIPPED_UP"):
            pos_str = status
        elif pos_int is not None and pos_int > 0:
            pos_str = str(pos_int)
        elif pos_int == 0:
            pos_str = "DNF"  # non-finisher coded as 0 in SL — exclude from result sorting
        else:
            pos_str = ""

        betting = ride.get("betting", {})
        sp_str = betting.get("current_odds", "")
        sp_dec = sp_to_dec(sp_str)

        jockey_info = ride.get("jockey", {})
        trainer_info = ride.get("trainer", {})

        runners.append({
            "horse_id":   card_runner.get("horse_id", ""),
            "horse":      card_runner.get("horse") or horse_name,
            "sp":         sp_str,
            "sp_dec":     sp_dec,
            "position":   pos_str,
            "draw":       str(ride.get("draw_number", "")),
            "number":     str(ride.get("cloth_number", "")),
            "jockey":     jockey_info.get("name", "") if isinstance(jockey_info, dict) else "",
            "jockey_id":  "",
            "trainer":    trainer_info.get("name", "") if isinstance(trainer_info, dict) else "",
            "trainer_id": "",
            "age":        str(ride.get("horse", {}).get("age", "")),
            "or":         str(ride.get("official_rating", "")),
            "rpr":        "",
            "tsr":        "",
        })
    return runners


def match_race_to_racecard(sl_horse_names: set, sl_course: str, race_map: dict,
                           matched_ids: set) -> dict | None:
    """Find best racecard match by course + horse name overlap (timezone-safe)."""
    course_norm = sl_course.lower()
    candidates = [
        info for info in race_map.values()
        if info["course"].lower() == course_norm
        and info["race_id"] not in matched_ids
    ]
    if not candidates:
        return None

    best_card = None
    best_overlap = 0
    for c in candidates:
        card_names = set(c["_name_to_runner"].keys())
        overlap = len(card_names & sl_horse_names)
        if overlap > best_overlap:
            best_overlap = overlap
            best_card = c

    # Require at least 2 name matches or >40% of runners
    if best_card and best_overlap >= 2:
        return best_card
    if best_card and best_overlap >= 1 and len(sl_horse_names) <= 4:
        return best_card
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-05-15")
    args = parser.parse_args()
    date = args.date

    print(f"\nVELO RESULTS SCRAPER (Sporting Life) — {date}")
    print("=" * 60)

    print("\nLoading racecard cache...")
    race_map = load_racecard(date)
    courses = sorted(set(v["course"].lower() for v in race_map.values()))
    print(f"  {len(race_map)} races across: {', '.join(courses)}")

    session = requests.Session()

    print("\nFetching race links from Sporting Life...")
    race_links = get_sl_race_links(date, session)
    print(f"  Found {len(race_links)} race detail links for target courses")

    results = []
    matched_race_ids = set()

    for item in race_links:
        url = item["url"]
        sl_course = item["course"]

        # Extract SL race time from URL parts for display
        url_parts = url.split("/")
        sl_race_id = url_parts[7] if len(url_parts) > 7 else "?"
        print(f"\n  [{sl_course}] {sl_race_id} → {url.split('/')[-1][:40]}")

        rides = fetch_race_detail(url, session)
        if not rides:
            print("    no rides data")
            time.sleep(0.5)
            continue

        # Build normalised horse name set from rides for matching
        sl_horse_names = {normalise(r.get("horse", {}).get("name", "")) for r in rides}
        sl_horse_names.discard("")

        print(f"    rides={len(rides)} horses={len(sl_horse_names)}")

        # Match to racecard by horse name overlap (timezone-safe)
        card = match_race_to_racecard(sl_horse_names, sl_course, race_map, matched_race_ids)
        if not card:
            print(f"    [NO MATCH] course={sl_course} horses={list(sl_horse_names)[:3]}")
            time.sleep(0.5)
            continue

        matched_race_ids.add(card["race_id"])
        runners = rides_to_runners(rides, card["_name_to_runner"])

        # Find winner + top3
        finishers = sorted(
            [r for r in runners if r["position"].isdigit()],
            key=lambda r: int(r["position"])
        )
        winner = finishers[0] if finishers else {}
        top3 = finishers[:3]

        result = {
            "race_id":     card["race_id"],
            "date":        card["date"],
            "region":      card["region"],
            "course":      card["course"],
            "course_id":   card["course_id"],
            "off":         card["off"],
            "off_dt":      card["off_dt"],
            "race_name":   card["race_name"],
            "type":        card["type"],
            "class":       card["class"],
            "dist":        card["dist"],
            "dist_f":      card["dist_f"],
            "going":       card["going"],
            "surface":     card["surface"],
            "jumps":       card["jumps"],
            "runners":     runners,
            "non_runners": [],
        }
        results.append(result)

        horse_id_match = sum(1 for r in runners if r["horse_id"])
        print(f"    MATCHED → {card['race_id']} {card['course']} {card['off']}  "
              f"winner={winner.get('horse','?')} SP={winner.get('sp','?')}  "
              f"horse_ids={horse_id_match}/{len(runners)}")

        time.sleep(1.0)

    out_path = ROOT / "data" / f"results_{date.replace('-', '_')}.json"
    out_path.write_text(json.dumps({"results": results}, indent=2))

    print(f"\n{'='*60}")
    print(f"Matched: {len(results)} / {len(race_map)} races")
    print(f"Written: {out_path}")
    if len(results) > 0:
        print(f"\nRun sigma: python scripts/run_results_sigma.py --date {date}")
    else:
        print("\nWARNING: 0 races scraped — check scraper output above")


if __name__ == "__main__":
    main()
