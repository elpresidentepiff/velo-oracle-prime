#!/usr/bin/env python3
"""Build archive-only Racing Post horse dossiers from local parsed captures."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
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


def _load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _index_profiles(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for profile in payload.get("horse_profiles") or []:
        for key in (profile.get("horse_uid"), profile.get("horse_name")):
            if key:
                out[_norm(key)] = profile
    return out


def _racecard_runners(payload: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for race in payload.get("races") or []:
        for runner in race.get("runners") or []:
            rows.append((race, runner))
    return rows


def _flags(race: dict[str, Any], runner: dict[str, Any], profile: dict[str, Any] | None) -> list[str]:
    flags: list[str] = []
    if not profile:
        flags.append("INSUFFICIENT_PROFILE")
    if runner.get("headgear_first_time"):
        flags.append("HEADGEAR_CHANGE_ALERT")
    if runner.get("wind_surgery"):
        flags.append("WIND_SURGERY_ALERT")
    if (runner.get("newspaper_tip_count") or 0) >= 6:
        flags.append("MARKET_OVERHYPE_RISK")
    if profile and (profile.get("entries_count") or 0) > 0:
        flags.append("TRAINER_INTENT_SIGNAL")
    if profile and (profile.get("sire_name") or profile.get("dam_name")):
        flags.append("PEDIGREE_POSITIVE")
    if profile and not flags:
        flags.append("HORSE_DOSSIER_READY")
    return flags


def build(date: str, execute: bool) -> dict[str, Any]:
    day = PARSED_ROOT / date
    profiles_payload = _load(day / "horse_profiles.json", {})
    racecard_payload = _load(day / "racecard_injection.json", {})
    profiles = _index_profiles(profiles_payload)
    dossiers: list[dict[str, Any]] = []
    seen: set[str] = set()

    for race, runner in _racecard_runners(racecard_payload):
        key = _norm(runner.get("horse_id") or runner.get("horse"))
        if key in seen:
            continue
        seen.add(key)
        profile = profiles.get(_norm(runner.get("horse_id"))) or profiles.get(_norm(runner.get("horse")))
        dossier = {
            "trust_policy": POLICY,
            "velo_scoring_allowed": False,
            "rpr_policy": RPR_POLICY,
            "rp_rpr_velo_allowed": False,
            "horse": runner.get("horse"),
            "rp_horse_id": runner.get("horse_id") or (profile or {}).get("horse_uid"),
            "profile_url": runner.get("horse_url") or (profile or {}).get("source_url"),
            "course": race.get("course"),
            "race_time": race.get("race_time"),
            "trainer": runner.get("trainer") or (profile or {}).get("trainer_name"),
            "owner": runner.get("owner") or (profile or {}).get("owner_name"),
            "sire": runner.get("sire") or (profile or {}).get("sire_name"),
            "dam": runner.get("dam") or (profile or {}).get("dam_name"),
            "dam_sire": runner.get("damsire") or (profile or {}).get("dam_sire_name"),
            "age": runner.get("age") or (profile or {}).get("age"),
            "sex_country": runner.get("sex_colour"),
            "country": runner.get("country") or (profile or {}).get("country"),
            "recent_form": runner.get("form_figures"),
            "entries": (profile or {}).get("entries") or [],
            "quotes": (profile or {}).get("quotes") or [],
            "stats": {
                "trainer_last_14_runs": (profile or {}).get("trainer_last_14_runs"),
                "trainer_last_14_wins": (profile or {}).get("trainer_last_14_wins"),
                "trainer_last_14_percent": (profile or {}).get("trainer_last_14_percent"),
            },
            "pedigree": {
                "sire": runner.get("sire") or (profile or {}).get("sire_name"),
                "dam": runner.get("dam") or (profile or {}).get("dam_name"),
                "dam_sire": runner.get("damsire") or (profile or {}).get("dam_sire_name"),
                "breeder": (profile or {}).get("breeder_name"),
            },
            "sales": [],
            "notes": [],
            "rpdc_tags": [],
            "headgear": runner.get("headgear"),
            "headgear_first_time": runner.get("headgear_first_time"),
            "wind_surgery": runner.get("wind_surgery"),
            "days_since_run": runner.get("days_since_last_run"),
            "newspaper_comment": runner.get("diomed_comment"),
            "spotlight_comment": runner.get("spotlight_comment"),
            "tip_count": runner.get("newspaper_tip_count") or 0,
            "official_rating_archive_only": runner.get("official_rating"),
            "topspeed_archive_only": runner.get("topspeed"),
            "rp_rpr_archive_only": runner.get("rp_rpr_archive_only"),
            "archive_flags": _flags(race, runner, profile),
        }
        dossiers.append(dossier)

    summary = {
        "date": date,
        "generated_at": _utc_now(),
        "status": "DRY_RUN",
        "trust_policy": POLICY,
        "velo_scoring_allowed": False,
        "rpr_policy": RPR_POLICY,
        "horse_dossier_count": len(dossiers),
        "profile_matched_count": sum(1 for d in dossiers if "INSUFFICIENT_PROFILE" not in d["archive_flags"]),
        "dossiers": dossiers,
    }
    if execute:
        day.mkdir(parents=True, exist_ok=True)
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        out_json = day / "horse_dossiers.json"
        out_md = REPORT_ROOT / f"rp_horse_dossiers_{date.replace('-', '_')}.md"
        out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [f"# RP Horse Dossiers - {date}", "", f"- Dossiers: `{len(dossiers)}`", f"- Profile matched: `{summary['profile_matched_count']}`", "- Scoring impact: `NONE`", ""]
        for d in dossiers[:40]:
            lines.append(f"- {d['race_time']} {d['course']} - **{d['horse']}**: {', '.join(d['archive_flags'])}")
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        summary["status"] = "PASS"
        summary["output_path"] = str(out_json)
        summary["report_path"] = str(out_md)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build archive-only RP horse dossiers.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.date, args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
