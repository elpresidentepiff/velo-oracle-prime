"""Source discovery and Racing API normalization for New Build VELO."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from new_build_velo.spine import (
    NEW_BUILD_ROOT,
    NORMALIZED_ROOT,
    RPR_POLICY,
    SCORING_ALLOWED,
    TRUST_POLICY,
    norm,
    stable_id,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
RACECARD_RE = re.compile(r"racecards_(\d{4})_(\d{2})_(\d{2})_standard\.json$")
RESULTS_RE = re.compile(r"results_(\d{4})_(\d{2})_(\d{2})\.json$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _payload_rows(payload: Any, key: str) -> list[Any]:
    if isinstance(payload, dict):
        rows = payload.get(key) or []
        return rows if isinstance(rows, list) else []
    if isinstance(payload, list):
        return payload
    return []


def _date_from_match(match: re.Match[str]) -> str:
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def discover_sources(*, execute: bool = False) -> dict[str, Any]:
    racecards = []
    for path in sorted(ROOT.glob("data/racecards_*_standard.json")):
        match = RACECARD_RE.match(path.name)
        if match:
            payload = load_json(path, {})
            racecards.append(
                {
                    "date": _date_from_match(match),
                    "path": str(path),
                    "races": len(payload.get("racecards") or []),
                    "bytes": path.stat().st_size,
                }
            )

    results = []
    for path in sorted(ROOT.glob("data/results_*.json")):
        match = RESULTS_RE.match(path.name)
        if match:
            payload = load_json(path, {})
            rows = _payload_rows(payload, "results")
            results.append(
                {
                    "date": _date_from_match(match),
                    "path": str(path),
                    "races": len(rows),
                    "bytes": path.stat().st_size,
                }
            )

    rp_parsed = []
    parsed_root = ROOT / "data" / "racing_post_account_parsed"
    for day in sorted(p for p in parsed_root.glob("20*-*-*") if p.is_dir()):
        racecard = load_json(day / "racecard_injection.json", {})
        hp = load_json(day / "horse_profiles.json", {})
        rp_parsed.append(
            {
                "date": day.name,
                "races": len(racecard.get("races") or []),
                "runners": sum(len(race.get("runners") or []) for race in racecard.get("races") or []),
                "horse_profiles": len(hp.get("horse_profiles") or []),
            }
        )

    inventory = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_SOURCE_INVENTORY_READY",
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": SCORING_ALLOWED,
        "rpr_policy": RPR_POLICY,
        "racing_api_racecard_files": len(racecards),
        "racing_api_racecard_races": sum(row["races"] for row in racecards),
        "racing_api_result_files": len(results),
        "racing_api_result_races": sum(row["races"] for row in results),
        "runner_snapshot_files": len(list(ROOT.glob("data/runner_snapshots_*.jsonl"))),
        "sigma_result_files": len(list((ROOT / "data" / "sigma_results").glob("sigma_results_*.json"))),
        "rp_parsed_dates": len(rp_parsed),
        "rp_parsed_races": sum(row["races"] for row in rp_parsed),
        "rp_parsed_runners": sum(row["runners"] for row in rp_parsed),
        "raceform_clean_available": (ROOT / "data" / "raceform_clean.parquet").exists(),
        "raceform_v17_available": (ROOT / "data" / "raceform_v17_features.parquet").exists(),
        "rpdc_historical_available": (ROOT / "data" / "rpdc_backfill" / "rpdc_tags_historical.jsonl").exists(),
        "racecards": racecards,
        "results": results,
        "rp_parsed": rp_parsed,
    }
    if execute:
        write_json(NEW_BUILD_ROOT / "source_inventory_latest.json", inventory)
    return inventory


def racecard_dates() -> list[str]:
    dates: list[str] = []
    for path in sorted(ROOT.glob("data/racecards_*_standard.json")):
        match = RACECARD_RE.match(path.name)
        if match:
            dates.append(_date_from_match(match))
    return dates


def result_dates() -> list[str]:
    dates: list[str] = []
    for path in sorted(ROOT.glob("data/results_*.json")):
        match = RESULTS_RE.match(path.name)
        if match:
            dates.append(_date_from_match(match))
    return dates


def ingest_racing_api_card(source_date: str, *, execute: bool = False) -> dict[str, Any]:
    path = ROOT / "data" / f"racecards_{source_date.replace('-', '_')}_standard.json"
    payload = load_json(path, {})
    records: list[dict[str, Any]] = []
    for race in payload.get("racecards") or []:
        for runner in race.get("runners") or []:
            records.append(
                {
                    "new_build_runner_id": stable_id(source_date, race.get("race_id"), runner.get("horse_id") or runner.get("horse")),
                    "source": "racing_api_standard_card",
                    "source_date": source_date,
                    "race_id": race.get("race_id"),
                    "course": race.get("course"),
                    "off_time": race.get("off_dt") or race.get("off_time"),
                    "race_name": race.get("race_name"),
                    "race_class": race.get("race_class"),
                    "race_type": race.get("type"),
                    "distance": race.get("distance"),
                    "going": race.get("going"),
                    "surface": race.get("surface"),
                    "horse": runner.get("horse"),
                    "normalized_name": norm(runner.get("horse")),
                    "racing_api_horse_id": runner.get("horse_id"),
                    "trainer": runner.get("trainer"),
                    "trainer_id": runner.get("trainer_id"),
                    "jockey": runner.get("jockey"),
                    "jockey_id": runner.get("jockey_id"),
                    "owner": runner.get("owner"),
                    "owner_id": runner.get("owner_id"),
                    "sire": runner.get("sire"),
                    "dam": runner.get("dam"),
                    "dam_sire": runner.get("damsire"),
                    "age": runner.get("age"),
                    "sex": runner.get("sex"),
                    "country": runner.get("region"),
                    "draw": runner.get("draw"),
                    "headgear": runner.get("headgear"),
                    "wind_surgery": runner.get("wind_surgery"),
                    "days_since_run": runner.get("last_run"),
                    "form_figures": runner.get("form"),
                    "official_rating_archive_only": runner.get("ofr"),
                    "topspeed_archive_only": runner.get("ts"),
                    "rpr_archive_only": runner.get("rpr"),
                    "rpr_policy": RPR_POLICY,
                    "velo_scoring_allowed": False,
                    "trust_policy": TRUST_POLICY,
                }
            )
    out = {
        "generated_at": utc_now(),
        "source": "racing_api_standard_card",
        "source_date": source_date,
        "stage": "ingest_racing_api_card",
        "status": "PASS" if records else "NO_RACING_API_CARD_ROWS",
        "race_count": len({row["race_id"] for row in records if row.get("race_id")}),
        "runner_count": len(records),
        "records": records,
        "velo_scoring_allowed": False,
        "rpr_policy": RPR_POLICY,
    }
    if execute:
        write_json(NORMALIZED_ROOT / "racing_api" / source_date / "runners.json", out)
    return out


def ingest_racing_api_results(source_date: str, *, execute: bool = False) -> dict[str, Any]:
    path = ROOT / "data" / f"results_{source_date.replace('-', '_')}.json"
    payload = load_json(path, {})
    records: list[dict[str, Any]] = []
    for race in _payload_rows(payload, "results"):
        for runner in race.get("runners") or []:
            pos_raw = runner.get("position")
            try:
                pos = int(pos_raw)
            except (TypeError, ValueError):
                pos = None
            records.append(
                {
                    "new_build_result_id": stable_id(source_date, race.get("race_id"), runner.get("horse_id") or runner.get("horse"), pos_raw),
                    "source": "racing_api_results",
                    "source_date": source_date,
                    "race_id": race.get("race_id"),
                    "course": race.get("course"),
                    "off_time": race.get("off_dt") or race.get("off"),
                    "horse": runner.get("horse"),
                    "normalized_name": norm(runner.get("horse")),
                    "racing_api_horse_id": runner.get("horse_id"),
                    "position": pos,
                    "won": pos == 1,
                    "framed": pos is not None and pos <= 3,
                    "sp": runner.get("sp_dec") or runner.get("sp"),
                    "jockey": runner.get("jockey"),
                    "trainer": runner.get("trainer"),
                    "rpr_archive_only": runner.get("rpr"),
                    "ts_archive_only": runner.get("tsr"),
                    "comment_archive_only": runner.get("comment"),
                    "trust_policy": TRUST_POLICY,
                    "velo_scoring_allowed": False,
                    "rpr_policy": RPR_POLICY,
                }
            )
    out = {
        "generated_at": utc_now(),
        "source": "racing_api_results",
        "source_date": source_date,
        "stage": "ingest_racing_api_results",
        "status": "PASS" if records else "NO_RACING_API_RESULT_ROWS",
        "race_count": len({row["race_id"] for row in records if row.get("race_id")}),
        "runner_count": len(records),
        "winner_count": sum(1 for row in records if row["won"]),
        "records": records,
        "velo_scoring_allowed": False,
        "rpr_policy": RPR_POLICY,
    }
    if execute:
        write_json(NORMALIZED_ROOT / "racing_api_results" / source_date / "results.json", out)
    return out


def ingest_all_cards(*, execute: bool = False) -> dict[str, Any]:
    reports = [ingest_racing_api_card(day, execute=execute) for day in racecard_dates()]
    payload = {
        "generated_at": utc_now(),
        "stage": "ingest_all_cards",
        "status": "PASS",
        "file_count": len(reports),
        "race_count": sum(report.get("race_count") or 0 for report in reports),
        "runner_count": sum(report.get("runner_count") or 0 for report in reports),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": False,
        "rpr_policy": RPR_POLICY,
        "reports": reports,
    }
    if execute:
        write_json(NEW_BUILD_ROOT / "ingest_all_cards_latest.json", payload)
    return payload


def ingest_all_results(*, execute: bool = False) -> dict[str, Any]:
    reports = [ingest_racing_api_results(day, execute=execute) for day in result_dates()]
    payload = {
        "generated_at": utc_now(),
        "stage": "ingest_all_results",
        "status": "PASS",
        "file_count": len(reports),
        "race_count": sum(report.get("race_count") or 0 for report in reports),
        "runner_count": sum(report.get("runner_count") or 0 for report in reports),
        "winner_count": sum(report.get("winner_count") or 0 for report in reports),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": False,
        "rpr_policy": RPR_POLICY,
        "reports": reports,
    }
    if execute:
        write_json(NEW_BUILD_ROOT / "ingest_all_results_latest.json", payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="New Build VELO source discovery and structured source ingest.")
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--execute", action="store_true")
    card = sub.add_parser("ingest-card")
    card.add_argument("--date", required=True)
    card.add_argument("--execute", action="store_true")
    cards = sub.add_parser("ingest-all-cards")
    cards.add_argument("--execute", action="store_true")
    res = sub.add_parser("ingest-results")
    res.add_argument("--date", required=True)
    res.add_argument("--execute", action="store_true")
    results = sub.add_parser("ingest-all-results")
    results.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "inventory":
        output = discover_sources(execute=args.execute)
    elif args.command == "ingest-card":
        output = ingest_racing_api_card(args.date, execute=args.execute)
    elif args.command == "ingest-all-cards":
        output = ingest_all_cards(execute=args.execute)
    elif args.command == "ingest-results":
        output = ingest_racing_api_results(args.date, execute=args.execute)
    else:
        output = ingest_all_results(execute=args.execute)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0
