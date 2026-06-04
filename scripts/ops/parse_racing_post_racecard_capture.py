#!/usr/bin/env python3
"""
Parse captured Racing Post racecard pages into VELO race-day injection JSON.

Reads local account-captured HTML only. It extracts the race page payload that
backs the Newspaper Form / Spotlights / Form controls.

Selection priority for raw capture folder:
  1. --capture-label if provided (explicit override)
  2. live-full-racepages-{date}  (preferred full-card label)
  3. {date} folder — only accepted if it contains >1 course; rejected otherwise
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
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
NEXT_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)

_IRE_COUNTRY_CODES = {"IRE", "IRL"}
_IRE_COURSE_IDS = {
    "152", "153", "154", "155", "156", "157", "158", "159", "160",
    "161", "162", "163", "164", "165", "166", "167", "168",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _assert_repo_path(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if ROOT not in resolved.parents and resolved != ROOT:
        raise SystemExit(f"{label} must live under repo root: {ROOT}")
    return resolved


def _load_next_data(html_path: Path) -> dict[str, Any] | None:
    html = html_path.read_text(encoding="utf-8", errors="replace")
    match = NEXT_RE.search(html)
    if not match:
        return None
    return json.loads(match.group(1))


def _get_race_page_data(next_data: dict[str, Any]) -> dict[str, Any] | None:
    return (
        next_data.get("props", {})
        .get("pageProps", {})
        .get("initialState", {})
        .get("racePage", {})
        .get("data")
    )


def _normalise_runner(runner: dict[str, Any], forecast_map: dict[int, float] | None = None) -> dict[str, Any]:
    form_figures = "".join(str(item.get("figure", "")) for item in runner.get("formFiguresData") or [])
    horse_id = runner.get("horseId")
    return {
        "horse_id": horse_id,
        "horse": runner.get("horseName"),
        "horse_url": runner.get("horseUrl"),
        "start_number": runner.get("startNumber"),
        "draw": runner.get("draw"),
        "age": runner.get("age"),
        "country": runner.get("countryOrigin"),
        "sex_colour": runner.get("colorSex"),
        "weight_lbs": runner.get("weightCarried"),
        "weight_stones": runner.get("formattedWeightStones"),
        "weight_pounds": runner.get("formattedWeightPounds"),
        "official_rating": runner.get("officialRatingToday"),
        "topspeed": runner.get("rpTopspeed"),
        "rp_rpr_archive_only": runner.get("rpPostmark"),
        "rp_rpr_velo_allowed": False,
        "forecast_odds": runner.get("forecastOddsValue"),
        "rp_morning_price": forecast_map.get(horse_id) if (forecast_map and horse_id) else None,
        "jockey_id": runner.get("jockeyId"),
        "jockey": runner.get("jockeyName"),
        "jockey_first_time": runner.get("jockeyFirstTime", False),
        "trainer_id": runner.get("trainerId"),
        "trainer": runner.get("trainerName"),
        "trainer_rtf": runner.get("trainerRtf"),
        "new_trainer_races": runner.get("newTrainerRacesCount"),
        "owner": runner.get("ownerName"),
        "sire": runner.get("sireName"),
        "dam": runner.get("damName"),
        "damsire": runner.get("damsireName"),
        "headgear": runner.get("horseHeadGear"),
        "headgear_first_time": runner.get("horseHeadGearFirstTime"),
        "gelding_first_time": runner.get("geldingFirstTime"),
        "wind_surgery": runner.get("windSurgery"),
        "days_since_last_run": runner.get("daysSinceLastRun"),
        "form_figures": form_figures,
        "badges": runner.get("badges") or [],
        "compact_badges": runner.get("compactBadges") or [],
        "spotlight_comment": runner.get("spotlight"),
        "diomed_comment": runner.get("diomed"),
        "newspaper_tip_count": runner.get("numberOfTips"),
        "non_runner": runner.get("nonRunner"),
        "irish_reserve": runner.get("irishReserve"),
    }


def _num(value: Any, default: int = -1) -> int | float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalise_race(html_path: Path, capture: dict[str, Any] | None = None) -> dict[str, Any] | None:
    next_data = _load_next_data(html_path)
    if not next_data:
        return None
    race_page = _get_race_page_data(next_data)
    if not race_page or not race_page.get("race") or not race_page.get("runners"):
        return None

    race = race_page["race"]
    runners = race_page.get("runners") or []
    tabs = race_page.get("tabsContent") or {}
    
    bf = (race_page.get("raceDetails") or {}).get("bettingForecast") or []
    forecast_map: dict[int, float] = {}
    for entry in bf:
        odds_val = entry.get("oddsValue")
        for h in entry.get("horses") or []:
            hid = h.get("horseId")
            if hid and odds_val is not None:
                forecast_map[hid] = float(odds_val)

    top_tips = sorted(
        [
            {
                "horse_id": r.get("horseId"),
                "horse": r.get("horseName"),
                "tips": r.get("numberOfTips") or 0,
                "rp_rpr_archive_only": r.get("rpPostmark"),
                "topspeed": r.get("rpTopspeed"),
                "official_rating": r.get("officialRatingToday"),
            }
            for r in runners
        ],
        key=lambda row: (_num(row["tips"], 0), str(row["horse"] or "")),
        reverse=True,
    )

    return {
        "source": "racing_post_account_racecard_capture",
        "raw_source_file": str(html_path),
        "html_sha256": capture.get("html_sha256") if capture else None,
        "source_url": capture.get("source_url") if capture else None,
        "final_url": capture.get("final_url") if capture else None,
        "parsed_at": _utc_now(),
        "requires_audit": True,
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
        "race_id": race.get("raceId"),
        "course": race.get("courseStyleName") or race.get("courseName"),
        "course_id": race.get("courseId"),
        "country": race.get("countryCode"),
        "race_time": race.get("raceTime"),
        "race_title": race.get("raceTitle"),
        "race_class": race.get("raceClass"),
        "race_type": race.get("raceTypeDesc"),
        "category": race.get("category"),
        "rating_band": race.get("officialRatingBandDesc"),
        "distance_yards": race.get("distanceYards"),
        "distance_furlongs": race.get("distanceFurlongs"),
        "going": race.get("going"),
        "going_code": race.get("goingCode"),
        "surface": race.get("surfaceType"),
        "stalls": race.get("stalls"),
        "declared_runners": race.get("declaredRunners"),
        "number_of_runners": race.get("numberOfRunners"),
        "prize_money": race.get("formattedTotalPrizeMoney"),
        "newspaper_form_present": True,
        "tabs_available": {
            "verdict": tabs.get("verdict") is not None,
            "tips": tabs.get("tips") is not None,
            "postdata": tabs.get("postdata") is not None,
            "official_ratings": tabs.get("officialRatings") is not None,
            "rpr_ratings": tabs.get("rprRatings") is not None,
            "topspeed_ratings": tabs.get("topspeedRatings") is not None,
            "stats": tabs.get("stats") is not None,
            "quotes": bool(tabs.get("quotes")),
        },
        "top_newspaper_tips": top_tips[:5],
        "runners": [_normalise_runner(runner, forecast_map) for runner in runners],
    }


def _resolve_capture_dir(date: str, capture_label: str | None) -> Path:
    """
    Return the raw capture directory to parse.

    Priority:
      1. capture_label if provided (explicit override — must exist)
      2. live-full-racepages-{date}
      3. {date} folder — only if it contains >1 unique course (partial guard)
    """
    if capture_label:
        d = RAW_ROOT / capture_label
        if not d.exists():
            raise SystemExit(
                f"CAPTURE_LABEL_NOT_FOUND: {d}\n"
                f"Available folders for {date}: "
                + str([p.name for p in sorted(RAW_ROOT.iterdir()) if date in p.name])
            )
        return d

    preferred = RAW_ROOT / f"live-full-racepages-{date}"
    if preferred.exists():
        return preferred

    date_dir = RAW_ROOT / date
    if not date_dir.exists():
        raise SystemExit(
            f"NO_CAPTURE_FOLDER: tried {preferred.name} and {date_dir.name}, neither exists.\n"
            f"Run the collector with --date live-full-racepages-{date} first."
        )

    # Partial guard: reject single-course folders
    manifest_path = date_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        urls = [c.get("source_url", "") for c in manifest.get("captures", [])]
        courses: set[str] = set()
        for url in urls:
            m = re.search(r"/racecards/\d+/([^/]+)/", url)
            if m:
                courses.add(m.group(1))
        if len(courses) <= 1:
            available = [p.name for p in sorted(RAW_ROOT.iterdir()) if date in p.name]
            raise SystemExit(
                f"PARTIAL_CAPTURE_REJECTED: folder '{date}' contains only 1 course ({courses}).\n"
                f"Use --capture-label to specify the full-card folder.\n"
                f"Available for {date}: {available}"
            )

    return date_dir


def _clean_rating(value: Any) -> Any:
    if value is None or value == "" or value == "-":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_off_time(race_time: str | None) -> str | None:
    if not race_time:
        return None
    try:
        dt = datetime.fromisoformat(race_time)
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return None


def _injection_runner_to_standard(run: dict[str, Any]) -> dict[str, Any]:
    horse_id = run.get("horse_id")
    return {
        "horse": run.get("horse"),
        "horse_id": str(horse_id) if horse_id is not None else None,
        "age": run.get("age"),
        "sex": run.get("sex_colour"),
        "lbs": run.get("weight_lbs"),
        "draw": run.get("draw"),
        "trainer": run.get("trainer"),
        "trainer_id": str(run["trainer_id"]) if run.get("trainer_id") is not None else None,
        "jockey": run.get("jockey"),
        "jockey_id": str(run["jockey_id"]) if run.get("jockey_id") is not None else None,
        "ofr": _clean_rating(run.get("official_rating")),
        "official_rating": _clean_rating(run.get("official_rating")),
        "rp_rpr_archive_only": run.get("rp_rpr_archive_only"),
        "rp_rpr_velo_allowed": False,
        "form": run.get("form_figures") or "",
        "last_run": run.get("days_since_last_run"),
        "odds": run.get("forecast_odds"),
        "spotlight": run.get("spotlight_comment"),
        "comment": run.get("diomed_comment"),
        "headgear": run.get("headgear"),
        "owner": run.get("owner"),
        "sire": run.get("sire"),
        "dam": run.get("dam"),
        "damsire": run.get("damsire"),
        "newspaper_tip_count": run.get("newspaper_tip_count"),
        "headgear_first_time": run.get("headgear_first_time"),
        "gelding_first_time": run.get("gelding_first_time"),
        "wind_surgery": run.get("wind_surgery"),
        "horse_url": run.get("horse_url"),
        "_rp_archive_raw": run,
    }


def _injection_race_to_standard(race: dict[str, Any], date_str: str) -> dict[str, Any]:
    dist_f = race.get("distance_furlongs")
    distance_str = f"{dist_f}f" if dist_f else None
    country = race.get("country") or ""
    course_id = str(race.get("course_id") or "")
    region = "IRE" if (country in _IRE_COUNTRY_CODES or course_id in _IRE_COURSE_IDS) else country or "GB"

    runners_raw = [r for r in (race.get("runners") or []) if not r.get("non_runner")]
    runners_std = [_injection_runner_to_standard(r) for r in runners_raw]

    return {
        "race_id": str(race["race_id"]) if race.get("race_id") is not None else None,
        "course": race.get("course"),
        "course_id": course_id,
        "date": date_str,
        "off_time": _extract_off_time(race.get("race_time")),
        "race_name": race.get("race_title"),
        "distance": distance_str,
        "distance_f": dist_f,
        "going": race.get("going"),
        "surface": race.get("surface"),
        "type": race.get("race_type"),
        "race_class": str(race["race_class"]) if race.get("race_class") is not None else None,
        "rating_band": race.get("rating_band"),
        "prize": race.get("prize_money"),
        "field_size": race.get("declared_runners") or len(runners_std),
        "region": region,
        "runners": runners_std,
        "source": "racing_post_account_full_racepages",
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
        "rp_rpr_velo_allowed": False,
        "_rp_source_url": race.get("source_url"),
        "_rp_raw_source_file": race.get("raw_source_file"),
    }


def parse_capture_day(
    *,
    capture_date: str,
    capture_label: str | None = None,
    output_dir: Path,
    execute: bool,
    write_standard_cache: bool = False,
) -> dict[str, Any]:
    raw_day_dir = _resolve_capture_dir(capture_date, capture_label)
    _assert_repo_path(raw_day_dir, "raw_day_dir")
    output_dir = _assert_repo_path(output_dir / (capture_label or capture_date), "output_dir")
    manifest_path = raw_day_dir / "manifest.json"
    manifest = {}
    by_html_path: dict[str, dict[str, Any]] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for capture in manifest.get("captures", []):
            if capture.get("html_path"):
                by_html_path[str(Path(capture["html_path"]))] = capture

    races: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for html_path in sorted(raw_day_dir.glob("*.html")):
        parsed = _normalise_race(html_path, by_html_path.get(str(html_path)))
        if parsed:
            races.append(parsed)
        else:
            skipped.append({"file": str(html_path), "reason": "NOT_RACECARD_PAYLOAD"})

    races.sort(key=lambda row: (str(row.get("race_time") or ""), str(row.get("race_id") or "")))

    courses_found = sorted(set(r.get("course") for r in races if r.get("course")))
    payload = {
        "capture_date": capture_date,
        "capture_label": capture_label or (capture_label if capture_label else f"live-full-racepages-{capture_date}" if (RAW_ROOT / f"live-full-racepages-{capture_date}") == raw_day_dir else capture_date),
        "raw_dir_used": str(raw_day_dir),
        "generated_at": _utc_now(),
        "raw_manifest": str(manifest_path) if manifest_path.exists() else None,
        "races_count": len(races),
        "runners_count": sum(len(race.get("runners") or []) for race in races),
        "courses_found": courses_found,
        "races": races,
        "skipped_count": len(skipped),
        "skipped": skipped[:50],
        "status": "DRY_RUN",
        "execute_required": True,
    }
    if execute:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "racecard_injection.json"
        
        payload["status"] = "PASS"
        payload["execute_required"] = False
        payload["output_path"] = str(out_path)
        
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        if write_standard_cache:
            standard_races = [_injection_race_to_standard(r, capture_date) for r in races]
            date_tag = capture_date.replace("-", "_")
            cache_path = ROOT / "data" / f"racecards_{date_tag}_standard.json"
            cache_path.write_text(json.dumps(standard_races, indent=2, ensure_ascii=False), encoding="utf-8")
            payload["standard_cache_path"] = str(cache_path)
            payload["standard_cache_races"] = len(standard_races)
            payload["standard_cache_runners"] = sum(len(r.get("runners") or []) for r in standard_races)

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse local Racing Post racecard captures for VELO injection.")
    parser.add_argument("--date", required=True, help="Calendar date YYYY-MM-DD")
    parser.add_argument(
        "--capture-label",
        default=None,
        help="Raw capture folder name under data/racing_post_account_raw/ (e.g. live-full-racepages-2026-05-27). "
             "If omitted: prefers live-full-racepages-{date}, then rejects partial single-course {date} folder.",
    )
    parser.add_argument("--output-dir", default=str(PARSED_ROOT))
    parser.add_argument(
        "--write-standard-cache",
        action="store_true",
        help="Also write data/racecards_{date}_standard.json in loader-compatible format.",
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    payload = parse_capture_day(
        capture_date=args.date,
        capture_label=args.capture_label,
        output_dir=Path(args.output_dir),
        execute=args.execute,
        write_standard_cache=args.write_standard_cache,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
