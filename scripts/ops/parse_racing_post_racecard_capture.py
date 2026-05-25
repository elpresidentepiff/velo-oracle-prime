#!/usr/bin/env python3
"""
Parse captured Racing Post racecard pages into VELO race-day injection JSON.

Reads local account-captured HTML only. It extracts the race page payload that
backs the Newspaper Form / Spotlights / Form controls.
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


def _normalise_runner(runner: dict[str, Any]) -> dict[str, Any]:
    form_figures = "".join(str(item.get("figure", "")) for item in runner.get("formFiguresData") or [])
    return {
        "horse_id": runner.get("horseId"),
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
        "jockey_id": runner.get("jockeyId"),
        "jockey": runner.get("jockeyName"),
        "trainer_id": runner.get("trainerId"),
        "trainer": runner.get("trainerName"),
        "trainer_rtf": runner.get("trainerRtf"),
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
        "runners": [_normalise_runner(runner) for runner in runners],
    }


def parse_capture_day(*, capture_date: str, output_dir: Path, execute: bool) -> dict[str, Any]:
    raw_day_dir = _assert_repo_path(RAW_ROOT / capture_date, "raw_day_dir")
    output_dir = _assert_repo_path(output_dir / capture_date, "output_dir")
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
    payload = {
        "capture_date": capture_date,
        "generated_at": _utc_now(),
        "raw_manifest": str(manifest_path) if manifest_path.exists() else None,
        "races_count": len(races),
        "runners_count": sum(len(race.get("runners") or []) for race in races),
        "races": races,
        "skipped_count": len(skipped),
        "skipped": skipped[:50],
        "status": "DRY_RUN",
        "execute_required": True,
    }
    if execute:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "racecard_injection.json"
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        payload["status"] = "PASS"
        payload["output_path"] = str(out_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse local Racing Post racecard captures for VELO injection.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--output-dir", default=str(PARSED_ROOT))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    payload = parse_capture_day(capture_date=args.date, output_dir=Path(args.output_dir), execute=args.execute)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
