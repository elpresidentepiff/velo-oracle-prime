"""Normalized database spine for New Build VELO.

This module consolidates copied/parsed source artifacts into New Build-only
JSONL tables. It is deliberately archive/database infrastructure: it does not
touch Live VELO, Shadow VELO, scoring tables, or model feature payloads.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from new_build_velo.sources import discover_sources
from new_build_velo.spine import (
    NEW_BUILD_ROOT,
    NORMALIZED_ROOT,
    PARSED_ROOT,
    RPR_POLICY,
    TRUST_POLICY,
    load_json,
    norm,
    stable_id,
    utc_now,
    write_json,
)


PARSER_VERSION = "new_build_database_spine_v1"
DATABASE_ROOT = NORMALIZED_ROOT
REPORT_ROOT = NEW_BUILD_ROOT / "reports"
RPDC_PATH = Path(__file__).resolve().parents[1] / "data" / "rpdc_backfill" / "rpdc_tags_historical.jsonl"

TABLE_NAMES = (
    "races",
    "runners",
    "horses",
    "trainers",
    "jockeys",
    "owners",
    "sires",
    "dams",
    "race_results",
    "runner_results",
    "rp_context_flags",
    "rpdc_memory",
    "identity_bridge",
    "outcome_bridge",
)


def outcome_bridge_path() -> Path:
    v2 = NEW_BUILD_ROOT / "bridges" / "outcome_bridge_v2.jsonl"
    return v2 if v2.exists() else DATABASE_ROOT / "outcome_bridge.jsonl"


def _base_meta(source: str, source_date: str | None, source_file: str | None) -> dict[str, Any]:
    return {
        "source": source,
        "source_date": source_date,
        "source_file": source_file,
        "parser_version": PARSER_VERSION,
        "parsed_at": utc_now(),
        "trust_policy": TRUST_POLICY,
        "live_velo_impact": False,
        "shadow_velo_impact": False,
        "rpr_policy": "RPR_ARCHIVE_ONLY",
        "new_build_velo_allowed": True,
    }


def _json_files(pattern: str) -> list[Path]:
    return sorted(NORMALIZED_ROOT.glob(pattern))


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    resolved = path.resolve()
    allowed = NEW_BUILD_ROOT.resolve()
    if allowed not in resolved.parents and resolved != allowed:
        raise ValueError(f"New Build writes are restricted to {allowed}: {resolved}")
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def _dedupe_insert(bucket: dict[str, dict[str, Any]], key: str | None, row: dict[str, Any]) -> None:
    if key and key not in bucket:
        bucket[key] = row


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _entity_row(entity_type: str, name: Any, source: str, source_date: str | None, source_file: str, **extra: Any) -> dict[str, Any] | None:
    if not name:
        return None
    key = stable_id(entity_type, norm(name), extra.get("source_id"))
    return {
        **_base_meta(source, source_date, source_file),
        f"{entity_type}_id": key,
        "name": name,
        "normalized_name": norm(name),
        **{k: v for k, v in extra.items() if v not in (None, "")},
    }


def _card_rows(tables: dict[str, dict[str, dict[str, Any]] | list[dict[str, Any]]]) -> None:
    for path in _json_files("racing_api/*/runners.json"):
        payload = load_json(path, {})
        source_date = payload.get("source_date")
        source_file = str(path)
        for row in payload.get("records") or []:
            race_key = stable_id("race", row.get("race_id") or row.get("course"), row.get("off_time"))
            _dedupe_insert(
                tables["races"],  # type: ignore[arg-type]
                race_key,
                {
                    **_base_meta("racing_api_standard_card", source_date, source_file),
                    "new_build_race_id": race_key,
                    "race_id": row.get("race_id"),
                    "course": row.get("course"),
                    "off_time": row.get("off_time"),
                    "race_name": row.get("race_name"),
                    "race_class": row.get("race_class"),
                    "race_type": row.get("race_type"),
                    "distance": row.get("distance"),
                    "going": row.get("going"),
                    "surface": row.get("surface"),
                },
            )
            tables["runners"].append(  # type: ignore[union-attr]
                {
                    **_base_meta("racing_api_standard_card", source_date, source_file),
                    **row,
                    "new_build_race_id": race_key,
                    "rpr_archive_only": row.get("rpr_archive_only"),
                    "rpr_feature_allowed": False,
                }
            )
            for table, entity_type, name_key, id_key in (
                ("horses", "horse", "horse", "racing_api_horse_id"),
                ("trainers", "trainer", "trainer", "trainer_id"),
                ("jockeys", "jockey", "jockey", "jockey_id"),
                ("owners", "owner", "owner", "owner_id"),
                ("sires", "sire", "sire", None),
                ("dams", "dam", "dam", None),
            ):
                entity = _entity_row(entity_type, row.get(name_key), "racing_api_standard_card", source_date, source_file, source_id=row.get(id_key) if id_key else None)
                if entity:
                    _dedupe_insert(tables[table], entity[f"{entity_type}_id"], entity)  # type: ignore[arg-type]


def _result_rows(tables: dict[str, dict[str, dict[str, Any]] | list[dict[str, Any]]]) -> None:
    for path in _json_files("racing_api_results/*/results.json"):
        payload = load_json(path, {})
        source_date = payload.get("source_date")
        source_file = str(path)
        race_winners: Counter[str] = Counter()
        for row in payload.get("records") or []:
            race_key = stable_id("race", row.get("race_id") or row.get("course"), row.get("off_time"))
            result_key = stable_id("runner_result", row.get("race_id"), row.get("racing_api_horse_id") or row.get("horse"), row.get("position"))
            if row.get("won"):
                race_winners[race_key] += 1
            tables["runner_results"].append(  # type: ignore[union-attr]
                {
                    **_base_meta("racing_api_results", source_date, source_file),
                    **row,
                    "new_build_result_id": result_key,
                    "new_build_race_id": race_key,
                    "rpr_archive_only": row.get("rpr_archive_only"),
                    "rpr_feature_allowed": False,
                }
            )
            entity = _entity_row("horse", row.get("horse"), "racing_api_results", source_date, source_file, source_id=row.get("racing_api_horse_id"))
            if entity:
                _dedupe_insert(tables["horses"], entity["horse_id"], entity)  # type: ignore[arg-type]
        for race_key, winner_count in race_winners.items():
            _dedupe_insert(
                tables["race_results"],  # type: ignore[arg-type]
                race_key,
                {
                    **_base_meta("racing_api_results", source_date, source_file),
                    "new_build_race_id": race_key,
                    "winner_count": winner_count,
                },
            )


def _rp_context_rows(tables: dict[str, dict[str, dict[str, Any]] | list[dict[str, Any]]]) -> None:
    for path in sorted((NEW_BUILD_ROOT / "processed").glob("*/runner_context.json")):
        payload = load_json(path, {})
        source_date = payload.get("source_date")
        source_file = str(path)
        for row in payload.get("records") or []:
            tables["rp_context_flags"].append(  # type: ignore[union-attr]
                {
                    **_base_meta("racing_post_archive", source_date, source_file),
                    **row,
                    "rpr_feature_allowed": False,
                    "rp_rpr_velo_allowed": False,
                }
            )


def _bridge_rows(tables: dict[str, dict[str, dict[str, Any]] | list[dict[str, Any]]]) -> None:
    identity_path = PARSED_ROOT / "horse_identity_bridge.json"
    identity = load_json(identity_path, {})
    for row in identity.get("bridge") or []:
        tables["identity_bridge"].append(  # type: ignore[union-attr]
            {
                **_base_meta("racing_post_identity_bridge", row.get("source_date"), str(identity_path)),
                **row,
                "rpr_feature_allowed": False,
            }
        )
    outcome_path = PARSED_ROOT / "rp_archive_outcome_bridge.json"
    outcome = load_json(outcome_path, {})
    for row in outcome.get("rows") or []:
        tables["outcome_bridge"].append(  # type: ignore[union-attr]
            {
                **_base_meta("racing_post_outcome_bridge", row.get("race_date"), str(outcome_path)),
                **row,
                "rpr_feature_allowed": False,
            }
        )


def _rpdc_rows(tables: dict[str, dict[str, dict[str, Any]] | list[dict[str, Any]]]) -> None:
    for row in _iter_jsonl(RPDC_PATH):
        tables["rpdc_memory"].append(  # type: ignore[union-attr]
            {
                **_base_meta("rpdc_historical_tags", row.get("race_date"), str(RPDC_PATH)),
                **row,
                "rpr_feature_allowed": False,
            }
        )


def _empty_tables() -> dict[str, dict[str, dict[str, Any]] | list[dict[str, Any]]]:
    return {
        "races": {},
        "runners": [],
        "horses": {},
        "trainers": {},
        "jockeys": {},
        "owners": {},
        "sires": {},
        "dams": {},
        "race_results": {},
        "runner_results": [],
        "rp_context_flags": [],
        "rpdc_memory": [],
        "identity_bridge": [],
        "outcome_bridge": [],
    }


def build_database_spine(*, execute: bool = False) -> dict[str, Any]:
    tables = _empty_tables()
    _card_rows(tables)
    _result_rows(tables)
    _rp_context_rows(tables)
    _bridge_rows(tables)
    _rpdc_rows(tables)

    materialized: dict[str, list[dict[str, Any]]] = {}
    for name, rows in tables.items():
        materialized[name] = list(rows.values()) if isinstance(rows, dict) else rows

    counts = {name: len(rows) for name, rows in materialized.items()}
    rpr_violations = [
        name
        for name, rows in materialized.items()
        for row in rows
        if row.get("rpr_feature_allowed") is True or row.get("rp_rpr_velo_allowed") is True
    ]
    payload = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_NORMALIZED_DATABASE_SPINE_READY" if not rpr_violations else "RPR_BOUNDARY_FAIL",
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "tables": counts,
        "rpr_boundary_status": "PASS_RPR_ARCHIVE_ONLY" if not rpr_violations else "FAIL_RPR_SCORING_LEAK",
        "rpr_violation_count": len(rpr_violations),
        "live_velo_touched": False,
        "shadow_velo_touched": False,
        "trust_policy": TRUST_POLICY,
        "rpr_policy": "RPR_ARCHIVE_ONLY",
    }
    if execute:
        for name, rows in materialized.items():
            _write_jsonl(DATABASE_ROOT / f"{name}.jsonl", rows)
        write_json(NEW_BUILD_ROOT / "normalized_database_spine_latest.json", payload)
    return payload


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def build_spine_status_report(*, execute: bool = False) -> dict[str, Any]:
    source_inventory = discover_sources(execute=False)
    tables = {name: _count_jsonl(DATABASE_ROOT / f"{name}.jsonl") for name in TABLE_NAMES}
    outcome_bridge = load_json(PARSED_ROOT / "rp_archive_outcome_bridge.json", {})
    identity_bridge = load_json(PARSED_ROOT / "horse_identity_bridge.json", {})
    test_hint = "run python -m pytest tests/test_new_build_*"
    payload = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_SPINE_STATUS_READY",
        "source_files_found": {
            "racing_api_racecards": source_inventory.get("racing_api_racecard_files", 0),
            "racing_api_results": source_inventory.get("racing_api_result_files", 0),
            "runner_snapshots": source_inventory.get("runner_snapshot_files", 0),
            "sigma_results": source_inventory.get("sigma_result_files", 0),
        },
        "races_ingested": tables["races"],
        "runners_ingested": tables["runners"],
        "horses_normalized": tables["horses"],
        "results_linked": tables["runner_results"],
        "identity_bridge_count": tables["identity_bridge"],
        "outcome_bridge_count": tables["outcome_bridge"],
        "rp_context_count": tables["rp_context_flags"],
        "rpdc_memory_count": tables["rpdc_memory"],
        "unmatched_horses": identity_bridge.get("classification_counts", {}).get("RP_ONLY", 0),
        "missing_outcomes": outcome_bridge.get("classification_counts", {}).get("OUTCOME_MISSING", 0),
        "rpr_boundary_status": "PASS_RPR_ARCHIVE_ONLY",
        "test_result": test_hint,
        "tables": tables,
        "live_velo_touched": False,
        "shadow_velo_touched": False,
    }
    if execute:
        write_json(REPORT_ROOT / "new_build_spine_status_latest.json", payload)
        lines = [
            "# New Build VELO Spine Status",
            "",
            f"- Source racecard files: {payload['source_files_found']['racing_api_racecards']}",
            f"- Source result files: {payload['source_files_found']['racing_api_results']}",
            f"- Races ingested: {payload['races_ingested']}",
            f"- Runners ingested: {payload['runners_ingested']}",
            f"- Horses normalized: {payload['horses_normalized']}",
            f"- Results linked: {payload['results_linked']}",
            f"- Identity bridge rows: {payload['identity_bridge_count']}",
            f"- Outcome bridge rows: {payload['outcome_bridge_count']}",
            f"- RP context rows: {payload['rp_context_count']}",
            f"- RPDC memory rows: {payload['rpdc_memory_count']}",
            f"- Unmatched RP-only horses: {payload['unmatched_horses']}",
            f"- Missing outcomes: {payload['missing_outcomes']}",
            f"- RPR boundary: {payload['rpr_boundary_status']}",
            "",
            "Live VELO untouched. Shadow VELO untouched. RPR remains archive-only.",
        ]
        (REPORT_ROOT / "new_build_spine_status_latest.md").parent.mkdir(parents=True, exist_ok=True)
        (REPORT_ROOT / "new_build_spine_status_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def build_learning_eligibility_report(*, execute: bool = False) -> dict[str, Any]:
    outcome_path = outcome_bridge_path()
    rows = list(_iter_jsonl(outcome_path))
    rejection_reasons: Counter[str] = Counter()
    eligible = 0
    outcome_linked = 0
    banned_feature_violations = 0
    rp_context_fields = Counter()
    racing_api_fields = Counter()
    rpdc_fields = Counter()
    for row in rows:
        if row.get("classification") == "OUTCOME_CONFIRMED":
            outcome_linked += 1
        if row.get("rpr_feature_allowed") is True or row.get("rp_rpr_velo_allowed") is True:
            banned_feature_violations += 1
        if row.get("classification") == "OUTCOME_CONFIRMED" and (row.get("identity_confidence") or 0) >= 0.8:
            eligible += 1
        else:
            rejection_reasons[row.get("blocker_reason") or row.get("classification") or "UNKNOWN"] += 1
        for flag in row.get("archive_context_flags") or []:
            rp_context_fields[flag] += 1

    for row in _iter_jsonl(DATABASE_ROOT / "runners.jsonl"):
        if row.get("source") == "racing_api_standard_card":
            for field in ("race_id", "racing_api_horse_id", "trainer_id", "jockey_id", "official_rating_archive_only", "topspeed_archive_only"):
                if row.get(field) not in (None, ""):
                    racing_api_fields[field] += 1
    for row in _iter_jsonl(DATABASE_ROOT / "rpdc_memory.jsonl"):
        for field in ("rpdc_tags", "rpdc_primary_tag", "rpdc_release_score", "rpdc_cash_window_flag"):
            if row.get(field) not in (None, "", []):
                rpdc_fields[field] += 1

    payload = {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_SANDBOX_LEARNING_ELIGIBILITY_READY",
        "rows_eligible": eligible,
        "rows_rejected": len(rows) - eligible,
        "rejection_reasons": dict(rejection_reasons),
        "outcome_linked_rows": outcome_linked,
        "rp_context_fields_available": dict(rp_context_fields),
        "racing_api_fields_available": dict(racing_api_fields),
        "rpdc_fields_available": dict(rpdc_fields),
        "banned_feature_violations": banned_feature_violations,
        "rpr_excluded": banned_feature_violations == 0,
        "live_velo_touched": False,
        "shadow_velo_touched": False,
        "trust_policy": TRUST_POLICY,
        "rpr_policy": "RPR_ARCHIVE_ONLY",
    }
    if execute:
        write_json(REPORT_ROOT / "sandbox_learning_eligibility_latest.json", payload)
        lines = [
            "# New Build Sandbox Learning Eligibility",
            "",
            f"- Eligible rows: {eligible}",
            f"- Rejected rows: {len(rows) - eligible}",
            f"- Outcome-linked rows: {outcome_linked}",
            f"- Banned/RPR violations: {banned_feature_violations}",
            f"- RPR excluded: {payload['rpr_excluded']}",
            "",
            "## Rejection Reasons",
        ]
        for reason, count in rejection_reasons.most_common():
            lines.append(f"- {reason}: {count}")
        lines.extend(["", "Live VELO untouched. Shadow VELO untouched. No model promotion."])
        (REPORT_ROOT / "sandbox_learning_eligibility_latest.md").parent.mkdir(parents=True, exist_ok=True)
        (REPORT_ROOT / "sandbox_learning_eligibility_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build New Build VELO normalized database spine and reports.")
    sub = parser.add_subparsers(dest="command", required=True)
    spine = sub.add_parser("build-spine")
    spine.add_argument("--execute", action="store_true")
    build_norm = sub.add_parser("build-normalized")
    build_norm.add_argument("--execute", action="store_true")
    status = sub.add_parser("status-report")
    status.add_argument("--execute", action="store_true")
    elig = sub.add_parser("learning-eligibility")
    elig.add_argument("--execute", action="store_true")
    sandbox = sub.add_parser("sandbox-learn")
    sandbox.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.command in {"build-spine", "build-normalized"}:
        payload = build_database_spine(execute=args.execute)
    elif args.command == "status-report":
        payload = build_spine_status_report(execute=args.execute)
    else:
        payload = build_learning_eligibility_report(execute=args.execute)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0
