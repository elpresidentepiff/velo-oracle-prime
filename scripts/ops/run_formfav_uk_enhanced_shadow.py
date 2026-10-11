#!/usr/bin/env python3
"""Build a UK/IRE FormFav-enhanced shadow feature card without touching Prime.

Purpose:
- primary card comes from the existing Racing API;
- FormFav enriches only as a second source;
- extracts pace/form/class/track-bias features with data-quality gates;
- persists only a shadow report artifact;
- never writes velo_verdicts or changes production rankings.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.formfav_enrichment import enrich_existing_racecards
from src.velo.formfav_uk_features import FEATURE_SCHEMA_VERSION, build_race_shadow_packet
from src.velo.racecard_loader import fetch_api_racecards

LONDON = ZoneInfo("Europe/London")


def _default_date() -> str:
    return (datetime.now(LONDON).date() + timedelta(days=1)).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--countries", default="gb,ie")
    ap.add_argument("--persist-artifact", action="store_true")
    args = ap.parse_args()

    date_str = args.date or _default_date()
    countries = {c.strip().lower() for c in args.countries.split(",") if c.strip()}

    races = fetch_api_racecards(date_str)
    enriched, enrich_report = enrich_existing_racecards(
        date_str=date_str,
        races=races,
        countries=countries,
        include_prices=False,
        include_track_bias=True,
        timezone="Europe/London",
    )

    packets = []
    for race in enriched:
        ff = race.get("_formfav") or {}
        country = str(ff.get("country") or race.get("country") or race.get("region") or "").lower()
        if country not in countries:
            continue
        packets.append(build_race_shadow_packet(race))

    runners = [rr for p in packets for rr in p.get("runners", [])]
    def covered(key: str) -> int:
        return sum(1 for rr in runners if rr.get(key) == 1.0)

    report = {
        "date": date_str,
        "status": "SHADOW_ONLY_NO_PRODUCTION_INFLUENCE",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "countries": sorted(countries),
        "primary_source": "racing_api_standard",
        "enrichment_source": "formfav",
        "races_primary": len(races),
        "races_enriched": len(packets),
        "runners": len(runners),
        "training_eligible_runners": sum(1 for rr in runners if rr.get("ff_training_eligible") == 1.0),
        "identity_mismatches": sum(1 for rr in runners if rr.get("ff_identity_name_match") != 1.0),
        "draw_conflicts": sum(1 for rr in runners if rr.get("ff_draw_conflict") == 1.0),
        "coverage": {
            "speed_map": covered("ff_speedmap_present"),
            "pace_scenario": covered("ff_pace_scenario_present"),
            "class_profile": covered("ff_class_profile_present"),
            "class_fit": covered("ff_class_fit_present"),
            "track_bias": covered("ff_track_bias_present"),
            "form": covered("ff_form_present"),
            "overall_stats": covered("ff_overall_present"),
            "track_stats": covered("ff_track_present"),
            "distance_stats": covered("ff_distance_present"),
            "track_distance_stats": covered("ff_track_distance_present"),
            "condition_stats": covered("ff_condition_present"),
        },
        "mean_quality_score": (
            round(sum(float(rr.get("ff_quality_score") or 0.0) for rr in runners) / len(runners), 4)
            if runners else 0.0
        ),
        "enrichment_audit": enrich_report,
        "races": packets,
    }

    out = ROOT / "data" / "reports" / f"formfav_uk_shadow_features_{date_str.replace('-', '_')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": report["status"],
        "date": date_str,
        "schema": FEATURE_SCHEMA_VERSION,
        "races": report["races_enriched"],
        "runners": report["runners"],
        "eligible": report["training_eligible_runners"],
        "identity_mismatches": report["identity_mismatches"],
        "draw_conflicts": report["draw_conflicts"],
        "coverage": report["coverage"],
        "mean_quality": report["mean_quality_score"],
        "track_bias_calls_ok": enrich_report.get("track_bias_calls_ok", 0),
        "errors": enrich_report.get("errors", []),
        "output": str(out.relative_to(ROOT)),
    }, indent=2), flush=True)

    if args.persist_artifact:
        cmd = [
            sys.executable,
            "scripts/ops/persist_daily_artifacts.py",
            "--kind", "reports",
            "--date", date_str,
            "--execute",
        ]
        done = subprocess.run(cmd, cwd=ROOT, check=False)
        if done.returncode != 0:
            raise RuntimeError(f"artifact persistence failed: {done.returncode}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
