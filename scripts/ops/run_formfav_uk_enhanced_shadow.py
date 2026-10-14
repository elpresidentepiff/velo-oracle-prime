#!/usr/bin/env python3
"""Build a UK/IRE FormFav-enhanced shadow feature card without touching Prime.

Purpose:
- primary card comes from canonical Racing Post capture (local or Supabase);
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
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.formfav_cache_client import build_enrichment_client
from src.velo.formfav_enrichment import enrich_existing_racecards
from src.velo.formfav_uk_features import FEATURE_SCHEMA_VERSION, build_race_shadow_packet
from src.velo.racecard_loader import load_racecards
from src.velo.supabase_racecard_source import (
    SupabaseRacecardError,
    load_supabase_rp_racecards,
)

LONDON = ZoneInfo("Europe/London")


def _default_date() -> str:
    """Return the current UK race day for unattended daily runs.

    The Railway shadow service previously needed a hard-coded ``--date`` and
    was consequently left pinned to 2026-10-13.  The governed local runner
    still passes an explicit date; this default exists only so the cloud cron
    can advance naturally at midnight Europe/London.
    """
    return datetime.now(LONDON).date().isoformat()


def _normalise_country(value: object) -> str:
    key = str(value or "").strip().lower()
    return {"uk": "gb", "eng": "gb", "ire": "ie", "irl": "ie"}.get(key, key)


def _load_primary_races(date_str: str, source: str) -> tuple[list[dict], str]:
    date_tag = date_str.replace("-", "_")
    if source in {"rp", "auto"}:
        races, source_label = load_racecards(date_tag, date_str, ROOT / "data", source="rp")
        if source_label == "rp_merged" and races:
            return races, source_label
        if source == "rp":
            raise RuntimeError(
                f"UK enhanced shadow requires canonical RP merged source; got {source_label!r}"
            )
    try:
        return load_supabase_rp_racecards(date_str), "supabase_races_rp_capture"
    except SupabaseRacecardError:
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--countries", default="gb,ie")
    ap.add_argument(
        "--source",
        choices=("auto", "rp", "supabase"),
        default="auto",
        help="Canonical RP source. auto prefers local merged files then Supabase.",
    )
    ap.add_argument("--persist-artifact", action="store_true")
    args = ap.parse_args()

    date_str = args.date or _default_date()
    countries = {c.strip().lower() for c in args.countries.split(",") if c.strip()}

    races, source_label = _load_primary_races(date_str, args.source)

    enriched, enrich_report = enrich_existing_racecards(
        date_str=date_str,
        races=races,
        countries=countries,
        include_prices=False,
        include_track_bias=True,
        timezone="Europe/London",
        # Cache-first: reuse what the live worker already stored instead of
        # re-calling the shared, rate-limited FormFav key (429 -> zero enrichment).
        client=build_enrichment_client(),
    )

    packets = []
    for race in enriched:
        ff = race.get("_formfav") or {}
        country = _normalise_country(
            ff.get("country") or race.get("country") or race.get("region")
        )
        if country not in countries or not ff:
            continue
        packets.append(build_race_shadow_packet(race))

    runners = [rr for p in packets for rr in p.get("runners", [])]
    def covered(key: str) -> int:
        return sum(1 for rr in runners if rr.get(key) == 1.0)

    races_enriched = len(packets)
    usable = races_enriched > 0 and bool(runners)
    report = {
        "date": date_str,
        "status": "SHADOW_ONLY_ENRICHED" if usable else "SHADOW_NO_USABLE_ENRICHMENT",
        "shadow_only": True,
        "production_influence": False,
        "stake_authorised": False,
        "promotion_eligible": False,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "countries": sorted(countries),
        "primary_source": source_label,
        "enrichment_source": "formfav",
        "races_primary": len(races),
        "races_in_scope": enrich_report.get("races_in_scope", 0),
        "races_matched": enrich_report.get("races_matched", 0),
        "races_enriched": races_enriched,
        "races_unmatched": enrich_report.get("races_unmatched", 0),
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

    if not usable:
        print(
            "[FORMFAV-UK] FAIL_CLOSED: no race received usable FormFav shadow enrichment",
            file=sys.stderr,
            flush=True,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
