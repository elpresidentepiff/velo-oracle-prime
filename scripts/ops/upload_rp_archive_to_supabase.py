#!/usr/bin/env python3
"""Upload local RP archive artifacts to Supabase archive tables only."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from rp_supabase_archive_common import (
    PARSED_ROOT,
    REPORT_ROOT,
    RPR_POLICY,
    SupabaseRest,
    fetch_openapi,
    filter_columns,
    load_json,
    norm_key,
    sha256_json,
    table_columns,
    utc_now,
)


PARSER_VERSION = "rp_archive_supabase_loader_v1"


def _date_dirs(from_date: str, to_date: str) -> list[Path]:
    return [p for p in sorted(PARSED_ROOT.glob("20*-*-*")) if p.is_dir() and from_date <= p.name <= to_date]


def _race_key(date: str, race: dict[str, Any]) -> str:
    return f"rp_archive:{date}:{race.get('race_id') or norm_key(str(race.get('course')) + str(race.get('race_time')))}"


def _bundle_key(date: str, course: Any) -> str:
    return f"rp_archive:{date}:{norm_key(course)}"


def _runner_no(index: int, runner: dict[str, Any]) -> int:
    value = runner.get("start_number")
    try:
        return int(value)
    except (TypeError, ValueError):
        return index + 1


def _time_only(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    if "T" in text:
        text = text.split("T", 1)[1]
    text = text.split("+", 1)[0].split("Z", 1)[0]
    if len(text) == 5:
        text = f"{text}:00"
    return text[:8]


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text in {"-", "—", "None", "null"}:
        return None
    digits = "".join(ch for ch in text if ch.isdigit() or ch == "-")
    if not digits or digits == "-":
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _with_policy(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.setdefault("trust_policy", "ARCHIVE_CONTEXT_ONLY_NOT_SCORING")
    out.setdefault("velo_scoring_allowed", False)
    out.setdefault("rpr_policy", RPR_POLICY)
    out.setdefault("rp_rpr_velo_allowed", False)
    return out


def build_rows(from_date: str, to_date: str, columns: dict[str, list[str]]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for day in _date_dirs(from_date, to_date):
        date = day.name
        race_payload = load_json(day / "racecard_injection.json", {})
        races = race_payload.get("races") or []
        courses: dict[str, dict[str, Any]] = {}
        for race in races:
            course = race.get("course")
            bundle = _bundle_key(date, course)
            courses.setdefault(bundle, {
                "course": course,
                "venue_code": str(race.get("course_id") or norm_key(course)),
                "races": 0,
                "runners": 0,
                "files": set(),
            })
            courses[bundle]["races"] += 1
            courses[bundle]["runners"] += len(race.get("runners") or [])
            if race.get("raw_source_file"):
                courses[bundle]["files"].add(race["raw_source_file"])
            race_key = _race_key(date, race)
            rows["rp_racecards"].append(filter_columns({
                "race_key": race_key,
                "bundle_key": bundle,
                "source_date": date,
                "venue_code": race.get("course_id"),
                "course_name": course,
                "off_time": _time_only(race.get("race_time")),
                "race_name": race.get("race_title"),
                "race_type": race.get("race_type"),
                "distance_text": (
                    f"{race.get('distance_yards')}y"
                    if race.get("distance_yards") is not None
                    else (f"{race.get('distance_furlongs')}f" if race.get("distance_furlongs") is not None else "UNKNOWN")
                ),
                "distance_yards": race.get("distance_yards"),
                "distance_furlongs": race.get("distance_furlongs"),
                "class_band": race.get("race_class") or race.get("rating_band"),
                "going": race.get("going"),
                "prize": race.get("prize_money"),
                "runners_count": len(race.get("runners") or []),
                "raw_bundle": _with_policy(race),
            }, columns["rp_racecards"]))
            for idx, runner in enumerate(race.get("runners") or []):
                rn = _runner_no(idx, runner)
                rows["rp_runner_profiles"].append(filter_columns({
                    "race_key": race_key,
                    "runner_number": rn,
                    "horse_name": runner.get("horse"),
                    "cloth_no": _int_or_none(runner.get("start_number")),
                    "age": _int_or_none(runner.get("age")),
                    "sex": runner.get("sex_colour"),
                    "weight": runner.get("weight_stones") or runner.get("weight_lbs"),
                    "days_since_run": _int_or_none(runner.get("days_since_last_run")),
                    "trainer_name": runner.get("trainer"),
                    "jockey_name": runner.get("jockey"),
                    "owner_name": runner.get("owner"),
                    "draw": _int_or_none(runner.get("draw")),
                    "headgear": runner.get("headgear"),
                    "form_figures": runner.get("form_figures"),
                    "or_current": _int_or_none(runner.get("official_rating")),
                    "rpr_current": _int_or_none(runner.get("rp_rpr_archive_only")),
                    "ts_current": _int_or_none(runner.get("topspeed")),
                    "raw_runner_bundle": _with_policy(runner),
                }, columns["rp_runner_profiles"]))
                rows["rp_runner_signals"].append(filter_columns({
                    "race_key": race_key,
                    "runner_number": rn,
                    "horse_name": runner.get("horse"),
                    "days_since_run": _int_or_none(runner.get("days_since_last_run")),
                    "cash_run_flag": False,
                    "trainer_positive_flag": bool(runner.get("trainer_rtf")),
                    "spotlight_present_flag": bool(runner.get("spotlight_comment")),
                    "comment_present_flag": bool(runner.get("diomed_comment") or runner.get("spotlight_comment")),
                    "signal_summary": f"tips={runner.get('newspaper_tip_count') or 0}; archive_only=true",
                    "signal_version": PARSER_VERSION,
                    "raw_signal_payload": _with_policy(runner),
                }, columns["rp_runner_signals"]))
                if runner.get("horse_id") and runner.get("horse"):
                    rows["rp_entity_aliases"].append(filter_columns({
                        "entity_type": "horse",
                        "rp_id": str(runner.get("horse_id")),
                        "alias_type": "rp_archive_horse_name",
                        "alias_value": runner.get("horse"),
                        "match_score": 1,
                        "verified": True,
                    }, columns["rp_entity_aliases"]))
        for bundle, info in courses.items():
            rows["rp_meetings"].append(filter_columns({
                "bundle_key": bundle,
                "source_date": date,
                "venue_code": info["venue_code"],
                "course_name": info["course"],
                "parser_version": PARSER_VERSION,
                "parse_success": True,
                "races_count": info["races"],
                "runners_count": info["runners"],
                "input_files": sorted(info["files"]),
                "warnings": [],
                "errors": [],
                "raw_report": _with_policy({"source_date": date, "course": info["course"], "races": info["races"], "runners": info["runners"]}),
            }, columns["rp_meetings"]))
        # Archive full parsed payloads for traceability.
        for filename in ["racecard_injection.json", "horse_dossiers.json", "race_dossiers.json"]:
            path = day / filename
            if path.exists():
                payload = load_json(path, {})
                rows["raw_payload_archive"].append(filter_columns({
                    "endpoint": f"local_rp_archive/{filename}",
                    "request_params": {"source_path": str(path), "policy": RPR_POLICY},
                    "race_date": date,
                    "pulled_at": utc_now(),
                    "payload_json": _with_policy(payload),
                    "checksum": sha256_json(payload),
                    "parse_status": "PASS",
                    "parser_version": PARSER_VERSION,
                }, columns["raw_payload_archive"]))

    for filename in ["horse_identity_bridge.json", "rp_archive_outcome_bridge.json"]:
        path = PARSED_ROOT / filename
        if path.exists():
            payload = load_json(path, {})
            rows["raw_payload_archive"].append(filter_columns({
                "endpoint": f"local_rp_archive/{filename}",
                "request_params": {"source_path": str(path), "policy": RPR_POLICY},
                "race_date": to_date,
                "pulled_at": utc_now(),
                "payload_json": _with_policy(payload),
                "checksum": sha256_json(payload),
                "parse_status": "PASS",
                "parser_version": PARSER_VERSION,
            }, columns["raw_payload_archive"]))
            if filename == "horse_identity_bridge.json":
                for item in payload.get("bridge") or []:
                    if item.get("rp_horse_id") and item.get("rp_horse_name"):
                        rows["rp_entity_aliases"].append(filter_columns({
                            "entity_type": "horse",
                            "rp_id": str(item.get("rp_horse_id")),
                            "alias_type": "identity_bridge_horse_name",
                            "alias_value": item.get("rp_horse_name"),
                            "match_score": item.get("identity_confidence") or 0,
                            "verified": item.get("classification") == "IDENTITY_CONFIRMED",
                        }, columns["rp_entity_aliases"]))
    return rows


def _upsert_rows(client: SupabaseRest, rows: dict[str, list[dict[str, Any]]]) -> dict[str, Counter]:
    results: dict[str, Counter] = {}
    key_map = {
        "rp_meetings": ["bundle_key"],
        "rp_racecards": ["race_key"],
        "rp_runner_profiles": ["race_key", "runner_number", "horse_name"],
        "rp_runner_signals": ["race_key", "runner_number", "horse_name"],
        "rp_entity_aliases": ["entity_type", "rp_id", "alias_type", "alias_value"],
        "raw_payload_archive": ["checksum"],
    }
    table_order = [
        "rp_meetings",
        "rp_racecards",
        "rp_runner_profiles",
        "rp_runner_signals",
        "rp_entity_aliases",
        "raw_payload_archive",
    ]
    for table in table_order:
        table_rows = rows.get(table, [])
        counter: Counter = Counter()
        for row in table_rows:
            filters = {key: row.get(key) for key in key_map[table] if row.get(key) is not None}
            if not filters:
                counter["skipped_no_key"] += 1
                continue
            status = client.upsert_by_filter(table, row, filters)
            counter[status] += 1
        results[table] = counter
    return results


def run(from_date: str, to_date: str, execute: bool) -> dict[str, Any]:
    spec = fetch_openapi()
    columns = {table: table_columns(spec, table) for table in [
        "rp_meetings", "rp_racecards", "rp_runner_profiles", "rp_runner_signals", "rp_entity_aliases", "raw_payload_archive"
    ]}
    rows = build_rows(from_date, to_date, columns)
    rpr_count = sum(1 for row in rows["rp_runner_profiles"] if row.get("rpr_current"))
    payload: dict[str, Any] = {
        "generated_at": utc_now(),
        "from_date": from_date,
        "to_date": to_date,
        "mode": "execute" if execute else "dry-run",
        "row_counts": {table: len(items) for table, items in rows.items()},
        "rpr_archive_only_fields_count": rpr_count,
        "forbidden_table_touch_count": 0,
        "rpr_policy": RPR_POLICY,
        "scoring_impact": "NONE",
    }
    if execute:
        client = SupabaseRest()
        run_row = {
            "run_type": "rp_archive_supabase_load",
            "target_id": f"{from_date}:{to_date}",
            "target_name": "rp_archive_tables_only",
            "started_at": utc_now(),
            "records_fetched": sum(payload["row_counts"].values()),
            "records_written": 0,
            "status": "RUNNING",
            "error_note": None,
        }
        run_insert = client.insert("rp_ingestion_runs", run_row)[0]
        upload = _upsert_rows(client, rows)
        written = sum(c.get("inserted", 0) + c.get("updated", 0) for c in upload.values())
        client.patch("rp_ingestion_runs", {"id": run_insert["id"]}, {
            "finished_at": utc_now(),
            "records_written": written,
            "status": "PASS",
        })
        payload["upload_result"] = {table: dict(counter) for table, counter in upload.items()}
        payload["ingestion_run_id"] = run_insert["id"]
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = "execute" if execute else "dry_run"
    out = REPORT_ROOT / f"rp_supabase_archive_upload_{suffix}_latest.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload RP archive artifacts to Supabase archive tables.")
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    run(args.from_date, args.to_date, execute=args.execute)


if __name__ == "__main__":
    main()
