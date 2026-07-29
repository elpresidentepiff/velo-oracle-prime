"""
Build data/racecard_merged/racecard_{VENUE}_{date}.json files from the
racing_post_account_parsed injection JSON.

Old VELO's racecard_loader reads these as its 'rp_merged' source.

Usage:
    python scripts/ops/build_racecard_merged_from_injection.py --date 2026-06-01
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import csv
import re

ROOT = Path(__file__).resolve().parents[2]

_BHA_COLLATERAL_LOOKUP: set[str] = set()


def _load_bha_collateral_lookup() -> None:
    """Load horses with the 'collateral' flag from bha_or_diff_latest.csv."""
    global _BHA_COLLATERAL_LOOKUP
    path = ROOT / "data" / "bha_or_diff_latest.csv"
    if not path.exists():
        return

    _suffix_re = re.compile(r"\s*\([A-Z]{2,4}\)\s*$")
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Check for "collateral" in any discipline
                is_coll = any("collateral" in str(row.get(c, "")).lower() for c in 
                            ["Flat Clltrl", "AWT Clltrl", "Chase Clltrl", "Hurdle Clltrl"])
                if is_coll:
                    raw_name = (row.get("Name") or "").strip()
                    norm = _suffix_re.sub("", raw_name).lower().strip()
                    if norm:
                        _BHA_COLLATERAL_LOOKUP.add(norm)
    except Exception as e:
        print(f"  [WARN] BHA collateral load failed: {e}")


def is_collateral_horse(name: str) -> bool:
    """Check if normalized name is in the collateral set."""
    _suffix_re = re.compile(r"\s*\([A-Z]{2,4}\)\s*$")
    norm = _suffix_re.sub("", name or "").lower().strip()
    return norm in _BHA_COLLATERAL_LOOKUP

VENUE_CODE_MAP: dict[str, str] = {
    "gowran park": "GOW",
    "listowel": "LIT",
    "newcastle (aw)": "NCS",
    "newcastle": "NCS",
    "lingfield": "LIN",
    "lingfield (aw)": "LINAW",
    "newbury": "NEW",
    "windsor": "WIN",
    "wolverhampton (aw)": "WOL",
    "haydock": "HAY",
    "ascot": "ASC",
    "york": "YOR",
    "chester": "CHS",
    "newmarket": "NMK",
    "epsom": "EPS",
    "sandown": "SAN",
    "leicester": "LEI",
    "nottingham": "NOT",
    "goodwood": "GOO",
    "beverley": "BEV",
    "ripon": "RIP",
    "hamilton": "HAM",
    "ayr": "AYR",
    "carlisle": "CAR",
    "musselburgh": "MUS",
    "bath": "BAT",
    "brighton": "BRI",
    "fontwell": "FLK",
    "yarmouth": "YAR",
    "salisbury": "SAL",
    "chepstow": "CHP",
    "kempton (aw)": "KEM",
    "kempton": "KEM",
    "chelmsford (aw)": "CMS",
    "chelmsford city (aw)": "CMS",
    "southwell (aw)": "STH",
    "southwell": "STH",
    "pontefract": "PON",
    "doncaster": "DON",
    "thirsk": "THI",
    "redcar": "RED",
    "ffos las": "FFO",
    "worcester": "WOR",
    "stratford": "STR",
    "market rasen": "MAR",
    "huntingdon": "HUN",
    "exeter": "EXE",
    "taunton": "TAU",
    "wincanton": "WIN",
    "plumpton": "PLU",
    "folkestone": "FOL",
    "catterick": "CAT",
    "wetherby": "WET",
    "ludlow": "LUD",
    "hereford": "HER",
    "fakenham": "FAK",
    "hexham": "HEX",
    "perth": "PER",
    "navan": "NAV",
    "naas": "NAA",
    "leopardstown": "LEO",
    "curragh": "CUR",
    "galway": "GAL",
    "killarney": "KLN",
    "kilbeggan": "KLB",
    "ballinrobe": "BAL",
    "bellewstown": "BEL",
    "clonmel": "CLO",
    "dundalk (aw)": "DUN",
    "dundalk": "DUN",
    "fairyhouse": "FAI",
    "cork": "COR",
    "limerick": "LIM",
    "sligo": "SLI",
    "tipperary": "TIP",
    "wexford": "WEX",
    "roscommon": "ROS",
    "down royal": "DRO",
    "downpatrick": "DPT",
    "punchestown": "PUN",
    "thurles": "THU",
    "tramore": "TRA",
    "gowran": "GOW",
    "naas (aw)": "NAA",
    "uttoxeter": "UTT",
}

# Per-horse keys this script itself produces (runner_to_horse()'s output
# schema). Anything else found on an existing on-disk horse dict came from
# a later enrichment pass (ingest_racecard_pdfs.py merging RP PDF data) and
# must survive a rebuild, not just this script's own three PDF-scoring
# placeholders (postdata_score/or_compression_score/plot_conviction, always
# written here as 0.0 since RP's injection JSON never carries them).
_BASE_HORSE_SCHEMA_KEYS = {
    "horse_name", "horse_id", "age", "weight", "draw", "current_or", "ts_master",
    "ts_latest", "rpr_master", "trainer", "trainer_name", "jockey", "jockey_name",
    "headgear", "headgear_first_time", "wind_surgery", "days_since_last_run",
    "form_figures", "spotlight_comment", "diomed_comment", "newspaper_tip_count",
    "is_collateral", "postdata_score", "or_compression_score", "plot_conviction",
    "ts_base", "ts_adjusted", "or_run_history", "ts_run_history",
}
_ZERO_DEFAULT_PDF_FIELDS = ("postdata_score", "or_compression_score", "plot_conviction")


def _load_existing_merged(out_path: Path, date: str) -> dict[str, dict] | None:
    """Load this venue's existing racecard_merged file, keyed by off_time ->
    {horse_name_lower: horse_dict}. Returns None if absent, unreadable, or
    dated differently (never merge across dates)."""
    if not out_path.exists():
        return None
    try:
        existing = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if existing.get("date") != date:
        return None
    by_race: dict[str, dict] = {}
    for off_key, race_blob in (existing.get("races") or {}).items():
        by_race[off_key] = {
            (h.get("horse_name") or "").strip().lower(): h
            for h in (race_blob.get("horses") or [])
            if h.get("horse_name")
        }
    return by_race


def _preserve_pdf_enrichment(new_horse: dict, existing_horse: dict | None) -> bool:
    """Carry forward PDF-derived data from a previous ingest_racecard_pdfs.py
    merge into the freshly RP-rebuilt horse dict, in place. RP-sourced core
    identity fields (horse_id, current_or, etc.) always come from the fresh
    rebuild -- only enrichment this script itself can't produce is preserved.
    Returns True if anything was carried forward."""
    if not existing_horse:
        return False
    changed = False
    for key, value in existing_horse.items():
        if key in _BASE_HORSE_SCHEMA_KEYS:
            continue  # this script owns these; fresh RP value wins
        new_horse[key] = value
        changed = True
    for field in _ZERO_DEFAULT_PDF_FIELDS:
        existing_value = existing_horse.get(field)
        if existing_value not in (None, 0, 0.0):
            new_horse[field] = existing_value
            changed = True
    return changed


def to_off_time_key(iso_ts: str) -> str:
    """Convert ISO timestamp to British H.MM race time key (local time in TS)."""
    try:
        dt = datetime.fromisoformat(iso_ts)
        h = dt.hour
        m = dt.minute
        # Convert 24h to racing display format (1pm-9pm)
        if h > 12:
            h -= 12
        elif h == 0:
            h = 12
        return f"{h}.{m:02d}"
    except Exception:
        return iso_ts


def safe_numeric(val) -> float | None:
    """Return float or None; handles '-', None, empty string."""
    if val is None or val == "-" or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def build_betting_forecast(runners: list[dict]) -> str:
    """Build 'net_odds HorseName, ...' string from runner forecast_odds (decimal)."""
    parts = []
    for r in runners:
        name = r.get("horse") or ""
        if not name or r.get("non_runner"):
            continue
        dec = r.get("forecast_odds")
        if dec is None:
            continue
        try:
            net = round(float(dec) - 1, 3)
            parts.append(f"{net} {name}")
        except (TypeError, ValueError):
            continue
    return ", ".join(parts)


def build_spotlight_verdict(runners: list[dict], top_tips: list[dict]) -> str:
    """Build spotlight verdict string from top tips and runner spotlight comments."""
    if not top_tips:
        return ""
    lines = []
    tipped_ids = {t.get("horse_id"): t.get("tips", 0) for t in top_tips}
    for r in runners:
        if r.get("horse_id") in tipped_ids and r.get("spotlight_comment"):
            tips_count = tipped_ids[r["horse_id"]]
            lines.append(f"{r['horse']} ({tips_count} tips): {r['spotlight_comment']}")
    return " | ".join(lines) if lines else ""


def runner_to_horse(r: dict) -> dict:
    """Map injection runner dict → racecard_merged horse dict."""
    weight_str = None
    if r.get("weight_stones") and r.get("weight_pounds") is not None:
        weight_str = f"{r['weight_stones']}-{r['weight_pounds']}"
    elif r.get("weight_lbs"):
        # Convert lbs to stones-pounds
        total_lbs = int(r["weight_lbs"])
        stones = total_lbs // 14
        pounds = total_lbs % 14
        weight_str = f"{stones}-{pounds}"

    name = r.get("horse") or ""
    or_val = safe_numeric(r.get("official_rating"))
    ts_val = safe_numeric(r.get("topspeed"))
    rpr_val = safe_numeric(r.get("rp_rpr_archive_only"))

    return {
        "horse_name": name,
        "horse_id": r.get("horse_id"),
        "age": r.get("age"),
        "weight": weight_str,
        "draw": r.get("draw"),
        "current_or": or_val,
        "ts_master": ts_val,
        "ts_latest": ts_val,
        "rpr_master": rpr_val,
        "trainer": r.get("trainer"),
        "trainer_name": r.get("trainer"),
        "jockey": r.get("jockey"),
        "jockey_name": r.get("jockey"),
        "headgear": r.get("headgear"),
        "headgear_first_time": r.get("headgear_first_time", False),
        "wind_surgery": r.get("wind_surgery"),
        "days_since_last_run": r.get("days_since_last_run"),
        "form_figures": r.get("form_figures"),
        "spotlight_comment": r.get("spotlight_comment"),
        "diomed_comment": r.get("diomed_comment"),
        "newspaper_tip_count": r.get("newspaper_tip_count"),
        # BHA Intelligence
        "is_collateral": is_collateral_horse(name),
        # Scoring fields absent from RP data
        "postdata_score": 0.0,
        "or_compression_score": 0.0,
        "plot_conviction": 0.0,
        "ts_base": None,
        "ts_adjusted": ts_val,
        "or_run_history": [],
        "ts_run_history": [],
    }


def pick_postdata_horse(top_tips: list[dict]) -> str:
    """Return horse with most newspaper tips as postdata pick."""
    if not top_tips:
        return ""
    best = max(top_tips, key=lambda t: t.get("tips") or 0)
    return best.get("horse") or ""


def pick_topspeed_horse(runners: list[dict]) -> str:
    """Return horse with highest topspeed as topspeed pick."""
    best_name = ""
    best_ts = -1
    for r in runners:
        ts = safe_numeric(r.get("topspeed"))
        if ts is not None and ts > best_ts:
            best_ts = ts
            best_name = r.get("horse") or ""
    return best_name


def main() -> None:
    _load_bha_collateral_lookup()
    parser = argparse.ArgumentParser(description="Build racecard_merged files from injection JSON.")
    parser.add_argument("--date", default="2026-06-01")
    parser.add_argument("--injection-path", default=None, help="Override injection JSON path")
    args = parser.parse_args()

    if args.injection_path:
        injection_path = Path(args.injection_path)
    else:
        # Try both naming conventions: live-full-racepages-{date} and {date}
        candidate_a = ROOT / "data" / "racing_post_account_parsed" / f"live-full-racepages-{args.date}" / "racecard_injection.json"
        candidate_b = ROOT / "data" / "racing_post_account_parsed" / args.date / "racecard_injection.json"
        if candidate_a.exists():
            injection_path = candidate_a
        elif candidate_b.exists():
            injection_path = candidate_b
        else:
            injection_path = candidate_a  # fall through to original error message
    if not injection_path.exists():
        raise SystemExit(f"Injection JSON not found: {injection_path}")

    injection = json.loads(injection_path.read_text(encoding="utf-8"))
    races = injection.get("races", [])

    # Group races by venue code
    by_venue: dict[str, dict[str, dict]] = {}
    venue_names: dict[str, str] = {}

    for race in races:
        course_raw = (race.get("course") or "").strip()
        code = VENUE_CODE_MAP.get(course_raw.lower(), course_raw.upper().replace(" ", "_").replace("(", "").replace(")", ""))
        off_key = to_off_time_key(race.get("race_time") or "")

        if code not in by_venue:
            by_venue[code] = {}
            venue_names[code] = course_raw

        runners = [r for r in (race.get("runners") or []) if not r.get("non_runner")]
        top_tips = race.get("top_newspaper_tips") or []

        race_info = {
            "race_title": race.get("race_title") or "",
            "distance_furlongs": race.get("distance_furlongs"),
            "race_type": race.get("race_type"),
            "category": race.get("category"),
            "going": race.get("going"),
            "going_code": race.get("going_code"),
            "surface": race.get("surface"),
            "prize_money": race.get("prize_money"),
            "country": race.get("country"),
            "race_class": race.get("race_class"),
            "rating_band": race.get("rating_band"),
        }

        by_venue[code][off_key] = {
            "off": off_key,
            "course": course_raw,
            "name": race.get("race_title") or "",
            "distance": str(race.get("distance_furlongs", "")),
            "race_id": race.get("race_id"),
            "race_info": race_info,
            "postdata_pick": pick_postdata_horse(top_tips),
            "topspeed_pick": pick_topspeed_horse(runners),
            "betting_forecast": build_betting_forecast(runners),
            "spotlight_verdict": build_spotlight_verdict(runners, top_tips),
            "top_newspaper_tips": top_tips,
            "newspaper_form_present": race.get("newspaper_form_present", False),
            "horses": [runner_to_horse(r) for r in runners],
        }

    out_dir = ROOT / "data" / "racecard_merged"
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for code, races_dict in sorted(by_venue.items()):
        out_path = out_dir / f"racecard_{code}_{args.date}.json"

        existing_by_race = _load_existing_merged(out_path, args.date)
        preserved_count = 0
        if existing_by_race:
            for off_key, race_blob in races_dict.items():
                existing_horses = existing_by_race.get(off_key) or {}
                if not existing_horses:
                    continue
                for horse in race_blob["horses"]:
                    key = (horse.get("horse_name") or "").strip().lower()
                    existing_horse = existing_horses.get(key)
                    if existing_horse and _preserve_pdf_enrichment(horse, existing_horse):
                        preserved_count += 1

        payload = {
            "venue": venue_names.get(code, code),
            "venue_code": code,
            "date": args.date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "races": races_dict,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(str(out_path))
        preserve_note = f" ({preserved_count} horses kept prior PDF enrichment)" if preserved_count else ""
        print(f"  {code}: {len(races_dict)} races -> {out_path.name}{preserve_note}")

    print(f"\nWrote {len(written)} racecard_merged files for {args.date}")


if __name__ == "__main__":
    main()
