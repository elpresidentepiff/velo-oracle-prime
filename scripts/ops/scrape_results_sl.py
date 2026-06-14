#!/usr/bin/env python3
"""
Scrape today's race results from Sporting Life and write
data/results_YYYY-MM-DD.json in the Racing API format expected by sigma.

SL times are UTC. VELO race_ids use BST (UTC+1) in H.MM format.
Horse IDs use the VELO convention: rp_{VENUE}_{name.lower().replace(' ','_')}

Usage:
    source venv/bin/activate
    PYTHONPATH=. python scripts/ops/scrape_results_sl.py --date 2026-05-20
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]

BST = timezone(timedelta(hours=1))

# Map SL course shortcodes to VELO venue codes (they differ for some)
SL_TO_VELO = {
    "FFL": "FFO",
    "GOW": "GOW",
    "AYR": "AYR",
    "WAR": "WAR",
    "YAR": "YAR",
    "HAY": "HAY",
    "MUS": "MUS",
    "CAT": "CAT",
    "CHP": "CHP",
    "CHS": "CHE",   # Chester — SL uses CHS, VELO uses CHE
    "STH": "STH",
    "LIM": "LIM",
    "CHE": "CHE",
    "GWD": "GOO",   # legacy SL code
    "GWO": "GOO",   # actual SL code for Goodwood
    "NMK": "NMK",
    "NEW": "NEW",
    "LEI": "LEI",
    "NOT": "NOT",
    "PON": "PON",
    "RIP": "RIP",
    "SAN": "SAN",
    "WIN": "WIN",
    "WOL": "WOL",
    "BEV": "BEV",
    "BRI": "BRI",
    "CAR": "CAR",
    "CHM": "CHM",
    "DON": "DON",
    "EPS": "EPS",
    "EXE": "EXE",
    "FFO": "FFO",
    "FLK": "FLK",
    "HAM": "HAM",
    "HER": "HER",
    "KEM": "KEM",
    "LIN": "LIN",
    "NAA": "NAA",
    "COR": "COR",
    "CUR": "CUR",
    "FTH": "FTH",
    "GAL": "GAL",
    "KIL": "KIL",
    "LEO": "LEO",
    "NAV": "NAV",
    "TIP": "TIP",
    "TRA": "TRA",
    "BTH": "BAT",   # SL code for Bath
    "WOR": "WOR",   # Worcester
    "DPT": "DPT",   # Downpatrick
    "SAL": "SAL",   # Salisbury
    "CHT": "CHP",   # Chepstow alternate
    "NCS": "NEW",   # Newcastle alternate
    "GWK": "GOW",   # Gowran alternate
    "RHO": "RHO",   # Rotherham/Redcar alternate
    "ASC": "ASC",   # Ascot
    "CRT": "CRT",   # Cartmel
    "KEB": "KEL",   # Kelso
    "LUD": "LUD",   # Ludlow
    "TAU": "TAU",   # Taunton
    "UTT": "UTT",   # Uttoxeter
    "STR": "STR",   # Stratford
    "PLU": "PLU",   # Plumpton
    "MKT": "MKT",   # Market Rasen
    "HEX": "HEX",   # Hexham
    "PER": "PER",   # Perth
    "AIN": "AIN",   # Aintree
    "WEX": "WEX",   # Wexford
    "SLI": "SLI",   # Sligo
    "FAI": "FAI",   # Fairyhouse
    "CLO": "CLO",   # Clonmel
    "NAS": "NAA",   # Naas alternate
    "PAT": "PAT",   # Punchestown alternate
    "DRO": "DRO",   # Down Royal
    "BAL": "BAL",   # Ballinrobe
    "KLB": "KLB",   # Kilbeggan
    "LEP": "LEO",   # Leopardstown alternate
    "WDR": "WDR",   # Windsor
    "YOR": "YOR",   # York
    "CUR": "CUR",
    "HUN": "HUN",   # Huntingdon
    "RED": "RED",   # Redcar
    "BAN": "BAN",   # Bangor-on-Dee alternate
    "BLN": "BAL",   # Ballinrobe
    "SOU": "SOU",   # Southwell
    "CHF": "CHM",   # Chelmsford alternate (fixed to CHM)
    "WND": "WDR",   # Windsor alternate
    "NWC": "NEW",   # Newcastle alternate 2
    "WTH": "WET",   # Wetherby (SL uses WTH, VELO uses WET)
}

# Some Sporting Life meetings do not expose course_shortcode. Keep this small and
# explicit so we only admit venues that VELO actually predicted for.
SL_COURSE_NAME_TO_VELO = {
    "Bangor-on-Dee": "BAN",
    "Dundalk": "DUN",
    "Wetherby": "WET",
    "Chelmsford City": "CHM",
}

# Irish venues (for region field)
IRE_VENUES = {"GOW", "LIM", "COR", "CUR", "FTH", "GAL", "KIL", "LEO", "NAA", "NAV", "TIP", "TRA", "BAL", "DUN"}

# Venues to include (filter out non-VELO venues)
VELO_VENUES = {
    "AYR", "FFO", "GOW", "WAR", "YAR",
    "HAY", "MUS", "CAT", "CHP", "STH", "LIM",
    "CHE", "GOO", "NMK", "NEW", "LEI", "NOT", "PON",
    "RIP", "SAN", "WIN", "WOL", "BEV", "BRI", "CAR",
    "CHM", "DON", "EPS", "EXE", "FLK", "HAM", "HER",
    "KEM", "LIN", "NAA", "COR", "CUR", "FTH", "GAL",
    "KIL", "LEO", "NAV", "TIP", "TRA",
    # Additional UK/IRE venues
    "BAT", "WOR", "DPT", "SAL", "ASC", "KEL", "LUD",
    "TAU", "UTT", "STR", "PLU", "MKT", "HEX", "PER",
    "AIN", "WEX", "SLI", "FAI", "CLO", "DRO", "BAL",
    "KLB", "RHO", "PAT", "BAN", "CRT", "WDR", "YOR",
    "HUN", "RED", "SOU", "DUN", "WET",
}


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def _horse_id(venue: str, name: str) -> str:
    return f"rp_{venue}_{_slug(name)}"


def _sp_dec(odds_str: str) -> float:
    """Convert fractional odds like '13/2' or '30/100' to decimal."""
    if not odds_str:
        return 0.0
    try:
        if "/" in str(odds_str):
            num, den = str(odds_str).split("/")
            return round(int(num) / int(den) + 1, 2)
        return float(odds_str)
    except Exception:
        return 0.0


def _utc_to_bst_hhmm(time_str: str) -> str:
    """'13:12' UTC → '2.12' BST (H.MM, no leading zero, 12h implicit)."""
    h, m = map(int, time_str.split(":"))
    bst_h = h + 1  # BST = UTC+1
    if bst_h >= 13:
        bst_h -= 12  # 13→1, 14→2, etc. (afternoon races are 1-9 PM)
    return f"{bst_h}.{m:02d}"


def fetch_sl_results(date: str) -> list[dict]:
    """Fetch race results from Sporting Life for given date (YYYY-MM-DD)."""
    url = f"https://www.sportinglife.com/racing/results/{date}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    nd = soup.find("script", id="__NEXT_DATA__")
    if not nd or not nd.string:
        raise RuntimeError("__NEXT_DATA__ not found in Sporting Life page")

    data = json.loads(nd.string)
    return data["props"]["pageProps"]["meetings"]


def build_results_json(meetings: list[dict], date: str) -> dict:
    """Convert SL meetings → Racing API results format for sigma."""
    results = []

    for meeting in meetings:
        races = meeting.get("races", [])
        if not races:
            continue

        sl_code = races[0].get("course_shortcode", "")
        sl_course_name = races[0].get("course_name", "")
        velo_venue = SL_TO_VELO.get(sl_code, sl_code) or SL_COURSE_NAME_TO_VELO.get(sl_course_name, "")

        if velo_venue not in VELO_VENUES:
            print(f"  [SKIP-VENUE] {sl_course_name} ({sl_code}) -> {velo_venue}")
            continue

        ms = meeting.get("meeting_summary", {})
        going = ms.get("going", "")

        for race in races:
            stage = race.get("race_stage", "")
            if stage == "ABANDONED":
                print(f"  [SKIP] {velo_venue} {race.get('time','?')} — ABANDONED")
                continue
            if stage not in ("WEIGHEDIN", "RESULT", "FINAL"):
                print(f"  [SKIP] {velo_venue} {race.get('time','?')} — stage={stage}")
                continue

            sl_time = race.get("time", "")
            if not sl_time:
                continue

            bst_time = _utc_to_bst_hhmm(sl_time)
            date_nodash = date.replace("-", "")
            race_id = f"rp_{velo_venue}_{date_nodash}_{bst_time}"

            top_horses = race.get("top_horses", [])
            if not top_horses:
                print(f"  [WARN] {race_id} — no top_horses data")
                continue

            # Build runner list from top 3
            runners = []
            for h in top_horses:
                pos = h.get("position")
                if pos is None:
                    continue
                name = h.get("name", "")
                odds = h.get("odds", "")
                runners.append(
                    {
                        "horse_id": _horse_id(velo_venue, name),
                        "horse": name,
                        "sp": odds,
                        "sp_dec": _sp_dec(odds),
                        "position": str(pos),
                        "draw": "",
                        "number": "",
                        "jockey": "",
                        "jockey_id": "",
                        "trainer": "",
                        "trainer_id": "",
                        "age": "",
                        "or": "",
                        "rpr": "",
                        "tsr": "",
                    }
                )

            if not runners:
                print(f"  [WARN] {race_id} — no finishers parsed")
                continue

            winner = next((r for r in runners if r["position"] == "1"), runners[0])

            results.append(
                {
                    "race_id": race_id,
                    "date": date,
                    "region": "IRE" if velo_venue in IRE_VENUES else "GB",
                    "course": race.get("course_name", velo_venue),
                    "course_id": "",
                    "off": bst_time,
                    "off_dt": "",
                    "race_name": race.get("name", ""),
                    "type": "Flat",
                    "class": race.get("race_class", ""),
                    "dist": race.get("distance", ""),
                    "dist_f": "",
                    "going": going,
                    "surface": "Turf",
                    "jumps": False,
                    "runners": runners,
                    "non_runners": [],
                }
            )

    return {"results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(BST).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    print(f"Scraping results for {args.date} from Sporting Life...")
    meetings = fetch_sl_results(args.date)
    print(f"  Meetings found: {len(meetings)}")

    results = build_results_json(meetings, args.date)
    races = results["results"]
    print(f"  VELO races built: {len(races)}")

    out_path = ROOT / "data" / f"results_{args.date.replace('-', '_')}.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"  Saved: {out_path}")

    print("\nRaces:")
    for r in races:
        winner = next((h["horse"] for h in r["runners"] if h["position"] == "1"), "?")
        print(f"  {r['race_id']:<40} winner={winner}")


if __name__ == "__main__":
    main()
