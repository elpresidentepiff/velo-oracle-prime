#!/usr/bin/env python3
"""Audit Supabase archive target tables before loading RP archive data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rp_supabase_archive_common import ARCHIVE_TABLES, REPORT_ROOT, fetch_openapi, table_columns, utc_now


REQUIRED = {
    "rp_ingestion_runs": ["run_type", "target_id", "target_name", "status"],
    "rp_meetings": ["bundle_key", "source_date", "course_name", "races_count", "runners_count", "raw_report"],
    "rp_racecards": ["race_key", "bundle_key", "source_date", "course_name", "off_time", "raw_bundle"],
    "rp_runner_profiles": ["race_key", "runner_number", "horse_name", "rpr_current", "raw_runner_bundle"],
    "rp_runner_signals": ["race_key", "runner_number", "horse_name", "signal_summary", "raw_signal_payload"],
    "rp_entity_aliases": ["entity_type", "rp_id", "alias_value", "match_score", "verified"],
    "raw_payload_archive": ["endpoint", "request_params", "race_date", "payload_json", "checksum", "parse_status"],
}


def build() -> dict[str, Any]:
    spec = fetch_openapi()
    tables = {}
    for table in sorted(ARCHIVE_TABLES):
        cols = table_columns(spec, table)
        missing = [col for col in REQUIRED.get(table, []) if col not in cols]
        tables[table] = {
            "exists": bool(cols),
            "columns": cols,
            "required_fields_missing": missing,
            "safe_to_insert": bool(cols) and not missing,
        }
    return {
        "generated_at": utc_now(),
        "project_ref": "ltbsxbvfsxtnharjvqcm",
        "tables": tables,
        "all_required_safe": all(row["safe_to_insert"] for row in tables.values()),
        "recommended_targets": {
            "racecard_injection.json": ["rp_meetings", "rp_racecards", "rp_runner_profiles", "rp_runner_signals", "raw_payload_archive"],
            "horse_dossiers.json": ["rp_runner_profiles", "rp_entity_aliases", "raw_payload_archive"],
            "race_dossiers.json": ["rp_racecards", "raw_payload_archive"],
            "horse_identity_bridge.json": ["rp_entity_aliases", "raw_payload_archive"],
            "rp_archive_outcome_bridge.json": ["raw_payload_archive"],
        },
    }


def write_reports(payload: dict[str, Any]) -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_ROOT / "rp_supabase_target_audit_latest.json"
    md_path = REPORT_ROOT / "rp_supabase_target_audit_latest.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# RP Supabase Target Audit", "", f"- Project: `{payload['project_ref']}`", f"- All required safe: `{payload['all_required_safe']}`", ""]
    for table, row in payload["tables"].items():
        lines.append(f"## {table}")
        lines.append(f"- Exists: `{row['exists']}`")
        lines.append(f"- Safe to insert: `{row['safe_to_insert']}`")
        lines.append(f"- Missing: `{', '.join(row['required_fields_missing']) or 'none'}`")
        lines.append(f"- Columns: `{', '.join(row['columns'])}`")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["md_path"] = str(md_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Supabase RP archive target tables.")
    parser.parse_args()
    payload = build()
    write_reports(payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
