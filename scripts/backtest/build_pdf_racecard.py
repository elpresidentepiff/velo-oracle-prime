#!/usr/bin/env python3
"""
Build data/racecards_YYYY_MM_DD_standard.json from merged PDF racecard JSONs.
Generates stable synthetic race_id / horse_id values so run_prime_today.py
can score races when the Racing API subscription is unavailable.

Usage:
    python scripts/build_pdf_racecard.py --date 2026-05-16
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

VENUE_MAP = {
    "UTT": ("Uttoxeter",       "GB", "jumps"),
    "NBY": ("Newbury",         "GB", "flat"),
    "NMK": ("Newmarket",       "GB", "flat"),
    "NAV": ("Navan",           "IE", "flat"),
    "WEX": ("Wexford",         "IE", "jumps"),
    "THI": ("Thirsk",          "GB", "flat"),
    "BAN": ("Bangor-On-Dee",   "GB", "jumps"),
    "DON": ("Doncaster",       "GB", "flat"),
    "HAM": ("Hamilton",        "GB", "flat"),
    "NAA": ("Naas",            "IE", "flat"),
    "RIP": ("Ripon",           "GB", "flat"),
    "STR": ("Stratford",       "GB", "jumps"),
    # extend as needed
    "ASC": ("Ascot",           "GB", "flat"),
    "AYR": ("Ayr",             "GB", "flat"),
    "CHE": ("Chelmsford",      "GB", "flat"),
    "CHS": ("Chester",         "GB", "flat"),
    "GOO": ("Goodwood",        "GB", "flat"),
    "HAY": ("Haydock",         "GB", "flat"),
    "KEL": ("Kelso",           "GB", "jumps"),
    "KEM": ("Kempton",         "GB", "flat"),
    "LEO": ("Leopardstown",    "IE", "flat"),
    "MUS": ("Musselburgh",     "GB", "flat"),
    "NOT": ("Nottingham",      "GB", "flat"),
    "PON": ("Pontefract",      "GB", "flat"),
    "RED": ("Redcar",          "GB", "flat"),
    "SAL": ("Salisbury",       "GB", "flat"),
    "SAN": ("Sandown",         "GB", "flat"),
    "YAR": ("Yarmouth",        "GB", "flat"),
    "YOR": ("York",            "GB", "flat"),
}


def stable_id(prefix: str, *parts: str) -> str:
    key = "|".join(parts)
    h = hashlib.md5(key.encode()).hexdigest()[:8]
    return f"{prefix}_{h}"


def time_to_24h(t: str, date: str) -> tuple[str, str]:
    """Convert '1:42' or '13:42' → ('13:42', 'YYYY-MM-DDTHH:MM:00+01:00')."""
    t = t.strip().replace(".", ":")
    try:
        h, m = t.split(":")
        h, m = int(h), int(m)
    except Exception:
        return t, ""
    # Assume times < 10 are PM (13:xx+) in UK racing context
    if h < 10:
        h += 12
    off_str = f"{h:02d}:{m:02d}"
    off_dt = f"{date}T{off_str}:00+01:00"
    return off_str, off_dt


def convert_venue(venue_code: str, date: str, merged: dict) -> list:
    """Convert one venue's merged racecard dict to a list of Racing API style race dicts."""
    course_name, region, surface_type = VENUE_MAP.get(venue_code, (venue_code, "GB", "flat"))
    jumps = surface_type == "jumps"

    races_out = []
    for race_time_key, race in merged.get("races", {}).items():
        off_str, off_dt = time_to_24h(race_time_key, date)
        race_id = stable_id("pdf", venue_code, date, race_time_key)

        # Extract race class/dist from race_info string
        race_info_str = race.get("race_info", "") or ""
        dist_m = re.search(r'(\d+m\s*\d*f?|\d+f)', race_info_str)
        dist = dist_m.group(0).strip() if dist_m else ""
        class_m = re.search(r'Class\s*(\d)', race_info_str, re.I)
        race_class = int(class_m.group(1)) if class_m else ""

        runners = []
        for h in race.get("horses", []):
            name = h.get("horse_name", "")
            if not name:
                continue
            horse_id = stable_id("hrs", name.lower())
            jockey_raw = h.get("jockey") or ""
            trainer_raw = h.get("trainer") or ""
            runners.append({
                "horse_id":   horse_id,
                "horse":      name,
                "age":        str(h.get("age", "")),
                "sex":        "",
                "sex_code":   "",
                "draw":       str(h.get("stall", "")),
                "number":     str(h.get("stall", "")),
                "lbs":        0,
                "ofr":        h.get("current_or") or "",
                "rpr":        h.get("rpr_master") or "",
                "ts":         h.get("ts_master") or h.get("ts_latest") or "",
                "headgear":   h.get("headgear_cc", ""),
                "jockey":     {"name": jockey_raw, "id": stable_id("jky", jockey_raw.lower())} if jockey_raw else "",
                "jockey_id":  stable_id("jky", jockey_raw.lower()) if jockey_raw else "",
                "trainer":    {"name": trainer_raw, "id": stable_id("trn", trainer_raw.lower())} if trainer_raw else "",
                "trainer_id": stable_id("trn", trainer_raw.lower()) if trainer_raw else "",
                "form":       h.get("form_string", ""),
                "last_run":   h.get("days_since_last_run") or "",
                "spotlight":  h.get("spotlight_comment", ""),
                "odds":       [],
                "trainer_rtf": h.get("trainer_form", ""),
                # Extra intelligence fields
                "ts_latest":  h.get("ts_latest") or "",
                "ts_master":  h.get("ts_master") or "",
                "plot_conviction": h.get("plot_conviction") or "",
                "postdata_score": h.get("postdata_score") or 0,
            })

        if not runners:
            continue

        races_out.append({
            "race_id":       race_id,
            "course":        course_name,
            "course_id":     stable_id("crs", venue_code),
            "date":          date,
            "off_time":      off_str,
            "off_dt":        off_dt,
            "off":           None,
            "race_name":     race_info_str[:80],
            "distance":      dist,
            "distance_f":    dist,
            "distance_round": dist,
            "region":        region,
            "race_class":    race_class,
            "type":          "Chase" if jumps else "Flat",
            "age_band":      "",
            "rating_band":   "",
            "going":         "",
            "going_detailed":"",
            "surface":       "Turf",
            "jumps":         jumps,
            "field_size":    len(runners),
            "runners":       runners,
            "big_race":      False,
            "is_abandoned":  False,
            "tip":           race.get("postdata_pick", ""),
            "verdict":       race.get("spotlight_verdict", ""),
            "betting_forecast": race.get("betting_forecast", ""),
            "race_status":   "Active",
            "_source":       "pdf_racecard",
        })

    return races_out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-05-16")
    args = parser.parse_args()
    date = args.date
    date_tag = date.replace("-", "_")

    merged_dir = ROOT / "data" / "racecard_merged"
    pattern = f"racecard_*_{date}.json"
    files = sorted(merged_dir.glob(pattern))

    if not files:
        print(f"No merged racecard files found for {date} in {merged_dir}")
        return

    print(f"\nBuilding synthetic racecard for {date}")
    print(f"Found {len(files)} venue files:")

    all_races = []
    for f in files:
        parts = f.stem.split("_")
        venue_code = parts[1] if len(parts) >= 3 else "UNK"
        merged = json.loads(f.read_text())
        races = convert_venue(venue_code, date, merged)
        course = VENUE_MAP.get(venue_code, (venue_code,))[0]
        print(f"  {venue_code} ({course}): {len(races)} races, "
              f"{sum(len(r['runners']) for r in races)} runners")
        all_races.extend(races)

    out = {
        "racecards": all_races,
        "total":     len(all_races),
        "limit":     500,
        "skip":      0,
        "query":     [],
        "_source":   "pdf_racecard_synthetic",
    }

    out_path = ROOT / "data" / f"racecards_{date_tag}_standard.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWritten: {out_path}")
    print(f"Total: {len(all_races)} races")
    print(f"\nReady: python scripts/run_prime_today.py --date {date}")


if __name__ == "__main__":
    main()
