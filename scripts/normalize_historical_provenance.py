"""
Metadata-only provenance normalization for accepted historical OASIS rows.

This pass does not bridge, reconstruct HFS, or retrain anything. It only
normalizes governance / provenance metadata on already-accepted historical rows.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from dotenv import load_dotenv
from supabase import Client, create_client


ROOT = Path(__file__).resolve().parent.parent

EXPECTED_SOURCE = "historical_raceform"
EXPECTED_BRIDGE_VERSION = "RACEFORM_BRIDGE_V1"
EXPECTED_DISCOVERY_VERSION = "CLEAN_INDEX_V1"
EXPECTED_SIGNAL_CONTRACT_VERSION = "HISTORICAL_SIGNAL_PROXY_V1"
EXPECTED_MPI_SOURCE = "archive_proxy_market_rank_v1"
EXPECTED_CHAOS_SOURCE = "archive_proxy_market_entropy_going_v1"
EXPECTED_EVENT_IDENTITY_CONTRACT = "race_id_course_race_date"
EXPECTED_TRAINING_ELIGIBLE = "pending_global_training_gate"
EXPECTED_RECONSTRUCTION_VERSION = "V17_B1"


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    for noisy_logger in ("httpx", "httpcore", "postgrest", "supabase"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


LOG = logging.getLogger("normalize_historical_provenance")


def get_sb_client() -> Client:
    load_dotenv(ROOT / ".env", override=False)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials missing.")
    return create_client(url, key)


def batched(items: List[Any], size: int) -> Iterable[List[Any]]:
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def build_event_key(race_id: Any, course: Any, race_date: Any) -> str:
    return f"{str(race_id)}|{str(course or '').strip()}|{str(race_date or '')[:10]}"


def fetch_all_races(sb: Client) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    offset = 0
    page_size = 1000
    while True:
        batch = sb.table("races").select("*").range(offset, offset + page_size - 1).execute().data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def fetch_hfs_rows(sb: Client, race_ids: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for chunk in batched(race_ids, 25):
        rows.extend(
            sb.table("historical_feature_store")
            .select("*")
            .in_("race_id", chunk)
            .eq("reconstruction_version", EXPECTED_RECONSTRUCTION_VERSION)
            .execute()
            .data
            or []
        )
    return rows


def race_year(race_date: str | None) -> int | None:
    if not race_date:
        return None
    try:
        return int(str(race_date)[:4])
    except (TypeError, ValueError):
        return None


def change_if_needed(target: Dict[str, Any], key: str, expected: Any, changes: Dict[str, Dict[str, Any]]) -> None:
    current = target.get(key)
    if current != expected:
        changes[key] = {"from": current, "to": expected}
        target[key] = expected


def analyze_scope(
    race_rows: List[Dict[str, Any]],
    hfs_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    accepted_races: List[Dict[str, Any]] = []
    excluded_2025_gap = 0
    excluded_missing_course_or_date = 0

    for row in race_rows:
        raw = row.get("raw") or {}
        if not isinstance(raw, dict):
            continue
        if raw.get("source") != EXPECTED_SOURCE:
            continue
        if raw.get("is_historical_backfill") is not True:
            continue

        course = row.get("course") or raw.get("course")
        race_date = str(row.get("date") or raw.get("race_date") or "")[:10]
        if not course or not race_date:
            excluded_missing_course_or_date += 1
            continue

        year = race_year(race_date)
        if year is None:
            excluded_missing_course_or_date += 1
            continue
        if year >= 2025:
            excluded_2025_gap += 1
            continue
        if year < 2017:
            excluded_missing_course_or_date += 1
            continue

        event_key = build_event_key(row.get("race_id"), course, race_date)
        accepted_races.append(
            {
                "row": row,
                "race_id": str(row.get("race_id")),
                "course": course,
                "race_date": race_date,
                "event_key": event_key,
                "jurisdiction": raw.get("jurisdiction"),
            }
        )

    accepted_race_ids = {r["race_id"] for r in accepted_races}
    event_key_counter = Counter(r["event_key"] for r in accepted_races)
    duplicate_event_key_count = sum(count - 1 for count in event_key_counter.values() if count > 1)

    accepted_hfs: List[Dict[str, Any]] = []
    hfs_missing_course_or_date = 0
    hfs_macro_mismatch_excluded = 0
    macro_mismatch_race_ids: set[str] = set()
    accepted_race_meta = {r["race_id"]: r for r in accepted_races}

    for row in hfs_rows:
        race_id = str(row.get("race_id"))
        meta = accepted_race_meta.get(race_id)
        if meta is None:
            continue
        race_date = meta["race_date"]
        course = meta["course"]
        if not race_date or not course:
            hfs_missing_course_or_date += 1
            continue
        feature_json = row.get("feature_json") or {}
        if not isinstance(feature_json, dict):
            feature_json = {}
        macro_year_used = feature_json.get("macro_year_used")
        try:
            if int(macro_year_used) != int(race_date[:4]):
                hfs_macro_mismatch_excluded += 1
                macro_mismatch_race_ids.add(race_id)
                continue
        except (TypeError, ValueError):
            hfs_macro_mismatch_excluded += 1
            macro_mismatch_race_ids.add(race_id)
            continue
        accepted_hfs.append(
            {
                "row": row,
                "race_id": race_id,
                "horse_id": str(row.get("horse_id")),
                "course": course,
                "race_date": race_date,
                "event_key": meta["event_key"],
            }
        )

    race_updates: List[Dict[str, Any]] = []
    race_missing_event_identity = 0
    race_missing_data_owner = 0
    race_missing_training = 0

    for item in accepted_races:
        if item["race_id"] in macro_mismatch_race_ids:
            continue
        row = dict(item["row"])
        raw = dict(row.get("raw") or {})
        if raw.get("event_identity_contract") != EXPECTED_EVENT_IDENTITY_CONTRACT:
            race_missing_event_identity += 1
        if raw.get("data_owner_confirmed") is not True:
            race_missing_data_owner += 1
        if raw.get("training_eligible") != EXPECTED_TRAINING_ELIGIBLE:
            race_missing_training += 1

        changes: Dict[str, Dict[str, Any]] = {}
        change_if_needed(raw, "event_key", item["event_key"], changes)
        change_if_needed(raw, "event_identity_contract", EXPECTED_EVENT_IDENTITY_CONTRACT, changes)
        change_if_needed(raw, "data_owner_confirmed", True, changes)
        change_if_needed(raw, "training_eligible", EXPECTED_TRAINING_ELIGIBLE, changes)
        change_if_needed(raw, "source", EXPECTED_SOURCE, changes)
        change_if_needed(raw, "bridge_version", EXPECTED_BRIDGE_VERSION, changes)
        change_if_needed(raw, "discovery_version", EXPECTED_DISCOVERY_VERSION, changes)
        change_if_needed(raw, "signal_contract_version", EXPECTED_SIGNAL_CONTRACT_VERSION, changes)
        change_if_needed(raw, "course", item["course"], changes)
        change_if_needed(raw, "race_date", item["race_date"], changes)
        change_if_needed(raw, "source_table", "raceform", changes)
        change_if_needed(raw, "source_race_id", item["race_id"], changes)

        if changes:
            row["raw"] = raw
            race_updates.append(
                {
                    "race_id": item["race_id"],
                    "event_key": item["event_key"],
                    "updated_row": row,
                    "changes": changes,
                }
            )

    hfs_updates: List[Dict[str, Any]] = []
    hfs_missing_event_identity = 0
    hfs_missing_data_owner = 0
    hfs_missing_training = 0

    for item in accepted_hfs:
        row = dict(item["row"])
        feature_json = dict(row.get("feature_json") or {})
        if feature_json.get("event_identity_contract") != EXPECTED_EVENT_IDENTITY_CONTRACT:
            hfs_missing_event_identity += 1
        if feature_json.get("data_owner_confirmed") is not True:
            hfs_missing_data_owner += 1
        if feature_json.get("training_eligible") != EXPECTED_TRAINING_ELIGIBLE:
            hfs_missing_training += 1

        changes: Dict[str, Dict[str, Any]] = {}
        change_if_needed(feature_json, "event_key", item["event_key"], changes)
        change_if_needed(feature_json, "event_identity_contract", EXPECTED_EVENT_IDENTITY_CONTRACT, changes)
        change_if_needed(feature_json, "data_owner_confirmed", True, changes)
        change_if_needed(feature_json, "training_eligible", EXPECTED_TRAINING_ELIGIBLE, changes)
        change_if_needed(feature_json, "source", EXPECTED_SOURCE, changes)
        change_if_needed(feature_json, "bridge_version", EXPECTED_BRIDGE_VERSION, changes)
        change_if_needed(feature_json, "discovery_version", EXPECTED_DISCOVERY_VERSION, changes)
        change_if_needed(feature_json, "signal_contract_version", EXPECTED_SIGNAL_CONTRACT_VERSION, changes)
        change_if_needed(feature_json, "mpi_source", EXPECTED_MPI_SOURCE, changes)
        change_if_needed(feature_json, "chaos_bloom_source", EXPECTED_CHAOS_SOURCE, changes)

        if changes:
            row["feature_json"] = feature_json
            hfs_updates.append(
                {
                    "race_id": item["race_id"],
                    "horse_id": item["horse_id"],
                    "event_key": item["event_key"],
                    "updated_row": row,
                    "changes": changes,
                }
            )

    sample_updates: List[Dict[str, Any]] = []
    for item in race_updates[:10]:
        sample_updates.append(
            {
                "kind": "race",
                "race_id": item["race_id"],
                "event_key": item["event_key"],
                "changes": item["changes"],
            }
        )
    for item in hfs_updates[:10]:
        sample_updates.append(
            {
                "kind": "hfs",
                "race_id": item["race_id"],
                "horse_id": item["horse_id"],
                "event_key": item["event_key"],
                "changes": item["changes"],
            }
        )

    return {
        "accepted_races": accepted_races,
        "accepted_hfs": accepted_hfs,
        "macro_mismatch_race_ids": sorted(macro_mismatch_race_ids),
        "race_updates": race_updates,
        "hfs_updates": hfs_updates,
        "dry_run": {
            "accepted_historical_races_scanned": len(accepted_races),
            "accepted_hfs_rows_scanned": len(accepted_hfs),
            "race_level_rows_missing_event_identity_contract": race_missing_event_identity,
            "race_level_rows_missing_data_owner_confirmed": race_missing_data_owner,
            "race_level_rows_missing_training_eligible": race_missing_training,
            "hfs_rows_missing_event_identity_contract": hfs_missing_event_identity,
            "hfs_rows_missing_data_owner_confirmed": hfs_missing_data_owner,
            "hfs_rows_missing_training_eligible": hfs_missing_training,
            "rows_excluded_due_to_2025_macro_gap": excluded_2025_gap,
            "rows_excluded_due_to_missing_race_date_or_course": excluded_missing_course_or_date + hfs_missing_course_or_date,
            "rows_excluded_due_to_macro_year_mismatch": hfs_macro_mismatch_excluded,
            "duplicate_event_key_count": duplicate_event_key_count,
            "proposed_race_level_updates": len(race_updates),
            "proposed_hfs_feature_json_updates": len(hfs_updates),
            "sample_proposed_updates": sample_updates[:20],
        },
    }


def doctrine_provenance_readback(accepted_races: List[Dict[str, Any]], accepted_hfs: List[Dict[str, Any]]) -> Dict[str, Any]:
    signal_ok = 0
    mpi_source_ok = 0
    chaos_source_ok = 0
    event_contract_ok = 0
    data_owner_ok = 0
    training_ok = 0
    source_ok = 0
    bridge_ok = 0
    discovery_ok = 0

    for item in accepted_hfs:
        feature_json = item["row"].get("feature_json") or {}
        if not isinstance(feature_json, dict):
            feature_json = {}
        if feature_json.get("signal_contract_version") == EXPECTED_SIGNAL_CONTRACT_VERSION:
            signal_ok += 1
        if feature_json.get("mpi_source") == EXPECTED_MPI_SOURCE:
            mpi_source_ok += 1
        if feature_json.get("chaos_bloom_source") == EXPECTED_CHAOS_SOURCE:
            chaos_source_ok += 1
        if feature_json.get("event_identity_contract") == EXPECTED_EVENT_IDENTITY_CONTRACT:
            event_contract_ok += 1
        if feature_json.get("data_owner_confirmed") is True:
            data_owner_ok += 1
        if feature_json.get("training_eligible") == EXPECTED_TRAINING_ELIGIBLE:
            training_ok += 1
        if feature_json.get("source") == EXPECTED_SOURCE:
            source_ok += 1
        if feature_json.get("bridge_version") == EXPECTED_BRIDGE_VERSION:
            bridge_ok += 1
        if feature_json.get("discovery_version") == EXPECTED_DISCOVERY_VERSION:
            discovery_ok += 1

    race_event_contract_ok = 0
    race_data_owner_ok = 0
    race_training_ok = 0
    race_source_ok = 0
    race_bridge_ok = 0
    race_discovery_ok = 0
    race_signal_ok = 0
    for item in accepted_races:
        raw = item["row"].get("raw") or {}
        if not isinstance(raw, dict):
            raw = {}
        if raw.get("event_identity_contract") == EXPECTED_EVENT_IDENTITY_CONTRACT:
            race_event_contract_ok += 1
        if raw.get("data_owner_confirmed") is True:
            race_data_owner_ok += 1
        if raw.get("training_eligible") == EXPECTED_TRAINING_ELIGIBLE:
            race_training_ok += 1
        if raw.get("source") == EXPECTED_SOURCE:
            race_source_ok += 1
        if raw.get("bridge_version") == EXPECTED_BRIDGE_VERSION:
            race_bridge_ok += 1
        if raw.get("discovery_version") == EXPECTED_DISCOVERY_VERSION:
            race_discovery_ok += 1
        if raw.get("signal_contract_version") == EXPECTED_SIGNAL_CONTRACT_VERSION:
            race_signal_ok += 1

    return {
        "doctrine": {
            "signal_contract_version_complete": f"{signal_ok}/{len(accepted_hfs)}",
            "mpi_source_complete": f"{mpi_source_ok}/{len(accepted_hfs)}",
            "chaos_bloom_source_complete": f"{chaos_source_ok}/{len(accepted_hfs)}",
            "race_level_signal_contract_complete": f"{race_signal_ok}/{len(accepted_races)}",
        },
        "provenance": {
            "event_identity_contract_complete_hfs": f"{event_contract_ok}/{len(accepted_hfs)}",
            "data_owner_confirmed_true_hfs": f"{data_owner_ok}/{len(accepted_hfs)}",
            "training_eligible_pending_hfs": f"{training_ok}/{len(accepted_hfs)}",
            "source_historical_raceform_hfs": f"{source_ok}/{len(accepted_hfs)}",
            "bridge_version_complete_hfs": f"{bridge_ok}/{len(accepted_hfs)}",
            "discovery_version_complete_hfs": f"{discovery_ok}/{len(accepted_hfs)}",
            "event_identity_contract_complete_races": f"{race_event_contract_ok}/{len(accepted_races)}",
            "data_owner_confirmed_true_races": f"{race_data_owner_ok}/{len(accepted_races)}",
            "training_eligible_pending_races": f"{race_training_ok}/{len(accepted_races)}",
            "source_historical_raceform_races": f"{race_source_ok}/{len(accepted_races)}",
            "bridge_version_complete_races": f"{race_bridge_ok}/{len(accepted_races)}",
            "discovery_version_complete_races": f"{race_discovery_ok}/{len(accepted_races)}",
        },
    }


def apply_updates(sb: Client, analysis: Dict[str, Any]) -> Dict[str, Any]:
    race_updates = analysis["race_updates"]
    hfs_updates = analysis["hfs_updates"]

    for chunk in batched([item["updated_row"] for item in race_updates], 100):
        if chunk:
            sb.table("races").upsert(chunk).execute()

    for chunk in batched([item["updated_row"] for item in hfs_updates], 250):
        if chunk:
            sb.table("historical_feature_store").upsert(
                chunk,
                on_conflict="race_id,horse_id,reconstruction_version",
            ).execute()

    refreshed = analyze_scope(fetch_all_races(sb), fetch_hfs_rows(sb, [item["race_id"] for item in analysis["accepted_races"]]))
    refreshed_dry = refreshed["dry_run"]

    readback = doctrine_provenance_readback(refreshed["accepted_races"], refreshed["accepted_hfs"])
    provenance_complete = {
        "race_level_event_identity_contract_missing": refreshed_dry["race_level_rows_missing_event_identity_contract"],
        "race_level_data_owner_confirmed_missing": refreshed_dry["race_level_rows_missing_data_owner_confirmed"],
        "race_level_training_eligible_missing": refreshed_dry["race_level_rows_missing_training_eligible"],
        "hfs_event_identity_contract_missing": refreshed_dry["hfs_rows_missing_event_identity_contract"],
        "hfs_data_owner_confirmed_missing": refreshed_dry["hfs_rows_missing_data_owner_confirmed"],
        "hfs_training_eligible_missing": refreshed_dry["hfs_rows_missing_training_eligible"],
    }

    training_distribution = Counter()
    for item in refreshed["accepted_hfs"]:
        feature_json = item["row"].get("feature_json") or {}
        training_distribution[str(feature_json.get("training_eligible"))] += 1

    return {
        "race_level_rows_updated": len(race_updates),
        "hfs_rows_updated": len(hfs_updates),
        "rows_skipped": refreshed_dry["rows_excluded_due_to_2025_macro_gap"]
        + refreshed_dry["rows_excluded_due_to_missing_race_date_or_course"]
        + refreshed_dry["rows_excluded_due_to_macro_year_mismatch"],
        "duplicate_event_key_count_after": refreshed_dry["duplicate_event_key_count"],
        "provenance_completeness_after": provenance_complete,
        "doctrine_completeness_after": readback["doctrine"],
        "provenance_readback_after": readback["provenance"],
        "training_eligible_distribution_after": dict(training_distribution),
        "sample_updated_rows": (
            [
                {
                    "kind": "race",
                    "race_id": item["race_id"],
                    "event_key": item["event_key"],
                    "changes": item["changes"],
                }
                for item in race_updates[:10]
            ]
            + [
                {
                    "kind": "hfs",
                    "race_id": item["race_id"],
                    "horse_id": item["horse_id"],
                    "event_key": item["event_key"],
                    "changes": item["changes"],
                }
                for item in hfs_updates[:10]
            ]
        )[:20],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize provenance metadata on accepted historical OASIS rows.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    sb = get_sb_client()

    race_rows = fetch_all_races(sb)
    accepted_ids = [
        str(row.get("race_id"))
        for row in race_rows
        if isinstance(row.get("raw"), dict)
        and row["raw"].get("source") == EXPECTED_SOURCE
        and row["raw"].get("is_historical_backfill") is True
    ]
    hfs_rows = fetch_hfs_rows(sb, sorted(set(accepted_ids)))
    analysis = analyze_scope(race_rows, hfs_rows)
    dry = analysis["dry_run"]

    print("\nHISTORICAL PROVENANCE NORMALIZATION DRY-RUN")
    print(f"A. accepted historical races scanned: {dry['accepted_historical_races_scanned']}")
    print(f"B. accepted HFS rows scanned: {dry['accepted_hfs_rows_scanned']}")
    print(f"C. race-level rows missing event_identity_contract: {dry['race_level_rows_missing_event_identity_contract']}")
    print(f"D. race-level rows missing data_owner_confirmed: {dry['race_level_rows_missing_data_owner_confirmed']}")
    print(f"E. race-level rows missing training_eligible: {dry['race_level_rows_missing_training_eligible']}")
    print(f"F. HFS rows missing event_identity_contract: {dry['hfs_rows_missing_event_identity_contract']}")
    print(f"G. HFS rows missing data_owner_confirmed: {dry['hfs_rows_missing_data_owner_confirmed']}")
    print(f"H. HFS rows missing training_eligible: {dry['hfs_rows_missing_training_eligible']}")
    print(f"I. rows excluded due to 2025 macro gap: {dry['rows_excluded_due_to_2025_macro_gap']}")
    print(f"J. rows excluded due to missing race_date/course: {dry['rows_excluded_due_to_missing_race_date_or_course']}")
    print(f"K. duplicate event_key count: {dry['duplicate_event_key_count']}")
    print(f"L. proposed race-level updates: {dry['proposed_race_level_updates']}")
    print(f"M. proposed HFS feature_json updates: {dry['proposed_hfs_feature_json_updates']}")
    print("N. sample 20 proposed updates:")
    for sample in dry["sample_proposed_updates"]:
        print(f"   - {json.dumps(sample, ensure_ascii=True)}")

    if args.dry_run:
        return

    if dry["duplicate_event_key_count"] != 0:
        raise RuntimeError("Duplicate event keys present in accepted scope; refusing to apply normalization.")

    apply_summary = apply_updates(sb, analysis)
    print("\nHISTORICAL PROVENANCE NORMALIZATION APPLY")
    print(f"A. race-level rows updated: {apply_summary['race_level_rows_updated']}")
    print(f"B. HFS rows updated: {apply_summary['hfs_rows_updated']}")
    print(f"C. rows skipped: {apply_summary['rows_skipped']}")
    print(f"D. duplicate event_key count after: {apply_summary['duplicate_event_key_count_after']}")
    print(f"E. provenance completeness after: {json.dumps(apply_summary['provenance_completeness_after'], ensure_ascii=True)}")
    print(f"F. doctrine completeness after: {json.dumps(apply_summary['doctrine_completeness_after'], ensure_ascii=True)}")
    print(f"G. training_eligible distribution after: {json.dumps(apply_summary['training_eligible_distribution_after'], ensure_ascii=True)}")
    print("H. sample 20 updated rows:")
    for sample in apply_summary["sample_updated_rows"]:
        print(f"   - {json.dumps(sample, ensure_ascii=True)}")


if __name__ == "__main__":
    main()
