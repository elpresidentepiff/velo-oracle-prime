from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from global_clean_spine_audit import DATA_DIR, STATE_PATH, exact_count, get_sb_client, load_json_file, write_json_file

ARTIFACT_INDEX_PATH = DATA_DIR / "velo_artifact_index.json"


def parse_block_number(name: str) -> int:
    match = re.search(r"OASIS_BLOCK_(\d+)", name)
    return int(match.group(1)) if match else -1


def parse_window_number(name: str) -> int:
    match = re.search(r"window_(\d+)", name, re.IGNORECASE)
    return int(match.group(1)) if match else -1


def load_latest_passed_global_audit() -> tuple[str, dict[str, Any]]:
    latest_name = ""
    latest_payload: dict[str, Any] | None = None
    latest_generated_at = ""
    for path in sorted(DATA_DIR.glob("global_clean_spine_audit_*.json")):
        payload = load_json_file(path)
        if payload.get("decision_gate", {}).get("pass") is not True:
            continue
        generated_at = str(payload.get("generated_at", ""))
        key = (generated_at, path.stem)
        if latest_payload is None or key > (latest_generated_at, latest_name):
            latest_name = path.stem
            latest_payload = payload
            latest_generated_at = generated_at
    if latest_payload is None:
        raise RuntimeError("No passing global clean spine audit artifact found.")
    return latest_name, latest_payload


def build_manifest_status_map(existing_index: dict[str, Any], latest_failed_block: str | None) -> dict[str, str]:
    status_map: dict[str, str] = {}
    for entry in existing_index.get("entries", []):
        if entry.get("type") == "manifest":
            status_map[Path(entry["path"]).name] = str(entry.get("status", "accepted"))
    if latest_failed_block:
        status_map[f"bridge_manifest_{latest_failed_block.lower()}.json"] = "rolled_back"
        status_map[f"bridge_manifest_{latest_failed_block}.json"] = "rolled_back"
    return status_map


def make_entry(path: Path, artifact_type: str, window_or_block: str, status: str, notes: str) -> dict[str, Any]:
    return {
        "path": str(path.resolve()).replace("\\", "/"),
        "type": artifact_type,
        "window_or_block": window_or_block,
        "status": status,
        "notes": notes,
    }


def refresh_artifact_index(state: dict[str, Any], latest_audit_name: str) -> dict[str, Any]:
    existing_index = load_json_file(ARTIFACT_INDEX_PATH) if ARTIFACT_INDEX_PATH.exists() else {"entries": []}
    latest_failed_block = state.get("latest_failed_block")
    manifest_status_map = build_manifest_status_map(existing_index, latest_failed_block)

    entries: list[dict[str, Any]] = []

    for path in sorted(DATA_DIR.glob("bridge_manifest_oasis_block_*.json"), key=lambda p: parse_block_number(p.stem)):
        block = re.search(r"bridge_manifest_(oasis_block_\d+)", path.stem, re.IGNORECASE).group(1).upper()
        status = manifest_status_map.get(path.name, "accepted")
        notes = "Rolled back bridge manifest." if status == "rolled_back" else "Accepted bridge manifest."
        entries.append(make_entry(path, "manifest", block, status, notes))

    for glob_pattern, artifact_type in [
        ("clean_race_candidates_oasis_window_*.jsonl", "candidate_file"),
        ("clean_race_rejections_oasis_window_*.jsonl", "rejection_file"),
        ("clean_race_index_cursor_window_*.json", "cursor"),
    ]:
        for path in sorted(DATA_DIR.glob(glob_pattern), key=lambda p: parse_window_number(p.stem)):
            window = f"WINDOW_{parse_window_number(path.stem):03d}"
            notes = {
                "candidate_file": "Approved discovery candidate file.",
                "rejection_file": "Frozen discovery rejection file.",
                "cursor": "Frozen discovery cursor file.",
            }[artifact_type]
            entries.append(make_entry(path, artifact_type, window, "frozen", notes))

    for path in sorted(DATA_DIR.glob("global_clean_spine_audit_*.json"), key=lambda p: p.stat().st_mtime):
        payload = load_json_file(path)
        status = "accepted" if payload.get("decision_gate", {}).get("pass") is True else "rejected"
        notes = "Reusable global clean spine audit artifact."
        entries.append(make_entry(path, "audit", path.stem, status, notes))
        md_path = path.with_suffix(".md")
        if md_path.exists():
            entries.append(make_entry(md_path, "audit", md_path.stem, status, "Markdown companion to audit artifact."))

    for stem in [
        "etsclv_framework_audit_v1",
        "etsclv_project_audit_v1",
    ]:
        for suffix in (".json", ".md"):
            path = DATA_DIR / f"{stem}{suffix}"
            if path.exists():
                entries.append(make_entry(path, "audit", stem, "accepted", "ETCSLV architecture audit artifact."))

    state_entries = [
        make_entry(STATE_PATH, "state", "current_state", "accepted", "Canonical VELO state file."),
        make_entry(ARTIFACT_INDEX_PATH, "state", "artifact_index", "accepted", "Canonical VELO artifact index."),
    ]
    entries.extend(state_entries)

    for path in sorted(DATA_DIR.glob("oasis_block_*_run.log")):
        block = re.search(r"oasis_block_(\d+)_run", path.stem, re.IGNORECASE)
        block_name = f"OASIS_BLOCK_{int(block.group(1)):03d}" if block else path.stem
        status = "rolled_back" if block_name == latest_failed_block else "accepted"
        notes = "Bridge run log."
        entries.append(make_entry(path, "log", block_name, status, notes))

    for path in sorted(DATA_DIR.glob("oasis_block_*_err.log")):
        block = re.search(r"oasis_block_(\d+)_err", path.stem, re.IGNORECASE)
        block_name = f"OASIS_BLOCK_{int(block.group(1)):03d}" if block else path.stem
        entries.append(make_entry(path, "log", block_name, "rolled_back", "Bridge error log."))

    for path in sorted(DATA_DIR.glob("window_*_discovery_run.log"), key=lambda p: parse_window_number(p.stem)):
        window = f"WINDOW_{parse_window_number(path.stem):03d}"
        entries.append(make_entry(path, "log", window, "frozen", "Discovery run log."))

    artifact_index = {
        "project": "VELO",
        "generated_at": datetime.now(UTC).isoformat(),
        "archive_exhausted": bool(state.get("archive_exhausted", False)),
        "latest_passed_audit": latest_audit_name,
        "latest_passed_block": state.get("latest_passed_block"),
        "latest_failed_block": state.get("latest_failed_block"),
        "entries": entries,
    }
    write_json_file(ARTIFACT_INDEX_PATH, artifact_index)
    return artifact_index


def main() -> None:
    current_state = load_json_file(STATE_PATH) if STATE_PATH.exists() else {}
    latest_audit_name, latest_audit = load_latest_passed_global_audit()
    summary = latest_audit["summary"]
    sb = get_sb_client()

    total_race_results = exact_count(sb, "race_results")
    total_runner_results = exact_count(sb, "runner_results")
    total_hfs = exact_count(sb, "historical_feature_store")

    prior_counts = current_state.get("current_accepted_spine", {})
    prior_approx = int(prior_counts.get("clean_historical_races_integrated_approx", 0) or 0)
    prior_oasis = int(prior_counts.get("accepted_oasis_historical_events", 0) or 0)
    legacy_offset = max(prior_approx - prior_oasis, 0)

    latest_failed_block = current_state.get("latest_failed_block", "OASIS_BLOCK_025")
    blocked_summary = summary.get("U_blocked_block_025_summary", {})

    block_status = "rolled_back" if blocked_summary else current_state.get("failed_block_reason")
    if block_status != "rolled_back" and latest_failed_block == "OASIS_BLOCK_025":
        block_status = "rolled_back"

    state = {
        "project": "VELO",
        "phase": f"{latest_audit_name}_passed_pre_2025_macro",
        "training_status": current_state.get("training_status", "paused"),
        "playbook_e_status": current_state.get("playbook_e_status", "paused"),
        "current_accepted_spine": {
            "race_results": total_race_results,
            "runner_results": total_runner_results,
            "historical_feature_store": total_hfs,
            "clean_historical_races_integrated_approx": int(summary["A_accepted_clean_race_event_count"]) + legacy_offset,
            "accepted_oasis_historical_events": int(summary["A_accepted_clean_race_event_count"]),
            "accepted_oasis_historical_hfs_rows": int(summary["C_accepted_hfs_row_count"]),
        },
        "latest_passed_audit": latest_audit_name,
        "latest_passed_block": current_state.get("latest_passed_block", "OASIS_BLOCK_024"),
        "latest_failed_block": latest_failed_block,
        "failed_block_reason": current_state.get("failed_block_reason", "2025 macro-year mismatch; rolled back"),
        "blocked_block_summary": {
            "bridge_block": blocked_summary.get("bridge_block", latest_failed_block),
            "status": block_status,
            "race_events": int(blocked_summary.get("race_events", 0) or 0),
            "runner_rows": int(blocked_summary.get("runner_rows", 0) or 0),
            "reason": blocked_summary.get("reason", "macro_year_mismatch"),
            "archive_exhausted": bool(blocked_summary.get("archive_exhausted", current_state.get("archive_exhausted", True))),
        },
        "archive_exhausted": bool(blocked_summary.get("archive_exhausted", current_state.get("archive_exhausted", True))),
        "next_required_mission": "build 2025 macro context support, then retry OASIS_BLOCK_025",
        "do_not_do": current_state.get(
            "do_not_do",
            [
                "do not train",
                "do not run Playbook E",
                "do not bridge new rows before approval",
                "do not relax filters",
                "do not use 2025 rows until macro support is fixed",
            ],
        ),
        "roadmap": current_state.get(
            "roadmap",
            [
                "Savepoint + Agent Handoff Pack",
                "ETCSLV Framework Audit",
                "Build 2025 macro context support",
                "Retry OASIS_BLOCK_025",
                "Run Global Clean Spine Audit V3",
                "Decide Playbook G dry-run training gate",
            ],
        ),
        "updated_at": datetime.now(UTC).date().isoformat(),
    }

    write_json_file(STATE_PATH, state)
    artifact_index = refresh_artifact_index(state, latest_audit_name)

    result = {
        "state_path": str(STATE_PATH),
        "artifact_index_path": str(ARTIFACT_INDEX_PATH),
        "latest_passed_audit": latest_audit_name,
        "latest_passed_block": state["latest_passed_block"],
        "latest_failed_block": state["latest_failed_block"],
        "current_accepted_spine": state["current_accepted_spine"],
        "archive_exhausted": state["archive_exhausted"],
        "training_status": state["training_status"],
        "playbook_e_status": state["playbook_e_status"],
        "artifact_entries": len(artifact_index["entries"]),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
