#!/usr/bin/env python3
"""Build archive-only Racing Post race dossiers from parsed racecards."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "reports"
POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
RPR_POLICY = "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _race_flags(race: dict[str, Any]) -> list[str]:
    runners = race.get("runners") or []
    flags: list[str] = []
    unknown = sum(1 for r in runners if not r.get("form_figures"))
    headgear = sum(1 for r in runners if r.get("headgear_first_time") or r.get("headgear"))
    wind = sum(1 for r in runners if r.get("wind_surgery"))
    tip_total = sum(int(r.get("newspaper_tip_count") or 0) for r in runners)
    max_tips = max((int(r.get("newspaper_tip_count") or 0) for r in runners), default=0)
    trainers = Counter(r.get("trainer") for r in runners if r.get("trainer"))
    sires = Counter(r.get("sire") for r in runners if r.get("sire"))
    if unknown >= max(2, len(runners) // 3):
        flags.append("UNKNOWN_HEAVY")
    if max_tips >= 7 or (tip_total and max_tips / tip_total >= 0.45):
        flags.append("HYPE_TRAP_RISK")
    if trainers and trainers.most_common(1)[0][1] >= 2:
        flags.append("TRAINER_CLUSTER")
    if sires and sires.most_common(1)[0][1] >= 2:
        flags.append("PEDIGREE_SIGNAL")
    if headgear + wind >= 2:
        flags.append("LOW_CONFIDENCE_ARCHIVE")
    if not flags:
        flags.append("CLEAN_CONTEXT")
    return flags


def build(date: str, execute: bool) -> dict[str, Any]:
    day = PARSED_ROOT / date
    racecard = _load(day / "racecard_injection.json")
    dossiers: list[dict[str, Any]] = []
    for race in racecard.get("races") or []:
        runners = race.get("runners") or []
        trainers = Counter(r.get("trainer") for r in runners if r.get("trainer"))
        sires = Counter(r.get("sire") for r in runners if r.get("sire"))
        tip_total = sum(int(r.get("newspaper_tip_count") or 0) for r in runners)
        max_tips = max((int(r.get("newspaper_tip_count") or 0) for r in runners), default=0)
        dossiers.append({
            "trust_policy": POLICY,
            "velo_scoring_allowed": False,
            "rpr_policy": RPR_POLICY,
            "race_id": race.get("race_id"),
            "course": race.get("course"),
            "race_time": race.get("race_time"),
            "title": race.get("race_title"),
            "race_class": race.get("race_class"),
            "distance_yards": race.get("distance_yards"),
            "going": race.get("going"),
            "runner_count": len(runners),
            "unexposed_horse_count": sum(1 for r in runners if not r.get("form_figures")),
            "headgear_wind_count": sum(1 for r in runners if r.get("headgear_first_time") or r.get("wind_surgery")),
            "trainer_concentration": trainers.most_common(3),
            "sire_pedigree_clusters": sires.most_common(3),
            "forecast_market_concentration": "ARCHIVE_PENDING",
            "newspaper_tip_concentration": {"total_tips": tip_total, "max_tips": max_tips},
            "unknown_profile_count": sum(1 for r in runners if not r.get("horse_id")),
            "rpdc_memory_coverage": "ARCHIVE_PENDING",
            "archive_intelligence_flags": _race_flags(race),
        })
    payload = {
        "date": date,
        "generated_at": _utc_now(),
        "status": "DRY_RUN",
        "trust_policy": POLICY,
        "velo_scoring_allowed": False,
        "rpr_policy": RPR_POLICY,
        "race_dossier_count": len(dossiers),
        "dossiers": dossiers,
    }
    if execute:
        day.mkdir(parents=True, exist_ok=True)
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        out_json = day / "race_dossiers.json"
        out_md = REPORT_ROOT / f"rp_race_dossiers_{date.replace('-', '_')}.md"
        out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [f"# RP Race Dossiers - {date}", "", f"- Races: `{len(dossiers)}`", "- Scoring impact: `NONE`", ""]
        for d in dossiers:
            lines.append(f"- {d['race_time']} {d['course']} - {d['runner_count']} runners: {', '.join(d['archive_intelligence_flags'])}")
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        payload["status"] = "PASS"
        payload["output_path"] = str(out_json)
        payload["report_path"] = str(out_md)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build archive-only RP race dossiers.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.date, args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
