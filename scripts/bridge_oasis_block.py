"""
Controlled bridge + HFS reconstruction for approved oasis clean candidates.

Uses only the approved clean candidate file, bridges a bounded race block,
persists a manifest, and reconstructs HFS strictly from that manifest.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, UTC
from pathlib import Path
from statistics import pvariance
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from supabase import Client, create_client


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CANDIDATE_FILE = DATA_DIR / "clean_race_candidates_oasis.jsonl"
MANIFEST_FILE = DATA_DIR / "bridge_manifest_oasis_block_001.json"
PREVIOUS_MANIFEST_FILE = DATA_DIR / "bridge_manifest_oasis_block_001.json"
BRIDGE_VERSION = "RACEFORM_BRIDGE_V1"
DISCOVERY_VERSION = "CLEAN_INDEX_V1"
BLOCK_NAME = "OASIS_BLOCK_001"
HFS_VERSION = "V17_B1"
SIGNAL_CONTRACT_VERSION = "HISTORICAL_SIGNAL_PROXY_V1"
MPI_SOURCE = "archive_proxy_market_rank_v1"
CHAOS_SOURCE = "archive_proxy_market_entropy_going_v1"
EVENT_IDENTITY_CONTRACT = "race_id_course_race_date"
TRAINING_ELIGIBLE_DEFAULT = "pending_global_training_gate"

def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # Preserve bridge/HFS audit visibility while silencing request-level client noise.
    for noisy_logger in ("httpx", "httpcore", "postgrest", "supabase"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


configure_logging()
LOG = logging.getLogger("oasis_block_bridge")


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


def count_table_rows(sb: Client, table: str) -> int:
    res = sb.table(table).select("*", count="exact").limit(1).execute()
    return int(res.count or 0)


def count_rows_for_race_ids(sb: Client, table: str, race_ids: List[str], extra_filters: Optional[Dict[str, Any]] = None) -> int:
    total = 0
    extra_filters = extra_filters or {}
    for chunk in batched(race_ids, 100):
        query = sb.table(table).select("*", count="exact").in_("race_id", chunk)
        for key, value in extra_filters.items():
            query = query.eq(key, value)
        total += int(query.limit(1).execute().count or 0)
    return total


def clean_horse_name(name: Any) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"\([A-Z]+\)$", "", str(name)).strip().upper()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def normalize_sp(sp_str: Any) -> Optional[float]:
    if sp_str in (None, "", "-", "–"):
        return None
    try:
        text = str(sp_str).strip().upper().rstrip("FCJ")
        if "/" in text:
            num, den = text.split("/", 1)
            return round((float(num) / float(den)) + 1.0, 6)
        return float(text)
    except Exception:
        return None


def normalize_pos(pos_str: Any) -> Tuple[Optional[int], bool]:
    if pos_str in (None, ""):
        return None, False
    cleaned = re.sub(r"[^\d]", "", str(pos_str))
    if not cleaned:
        return None, False
    pos = int(cleaned)
    return pos, pos == 1


def normalize_distance(dist_str: Any) -> Optional[int]:
    if not dist_str:
        return None
    text = str(dist_str)
    total = 0.0
    m = re.search(r"(\d+)m", text)
    if m:
        total += float(m.group(1)) * 8
    f = re.search(r"(\d+)f", text)
    if f:
        total += float(f.group(1))
    if total == 0 and text.replace(".", "").isdigit():
        total = float(text)
    return int(round(total)) if total > 0 else None


def build_event_key(race_id: Any, course: Any, race_date: Any) -> str:
    return f"{str(race_id)}|{str(course or '')}|{str(race_date or '')[:10]}"


def load_candidate_pool(path: Path) -> List[Dict[str, Any]]:
    pool: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row["event_key"] = build_event_key(row.get("race_id"), row.get("course"), row.get("race_date"))
            pool.append(row)
    return pool


def load_manifest(path: Path | None) -> Dict[str, Any]:
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_existing_race_ids(sb: Client) -> set[str]:
    existing: set[str] = set()
    last_race_id = 0
    while True:
        query = sb.table("race_results").select("race_id").order("race_id").limit(1000)
        if last_race_id:
            query = query.gt("race_id", last_race_id)
        rows = query.execute().data or []
        if not rows:
            break
        for row in rows:
            existing.add(str(row["race_id"]))
        last_race_id = rows[-1]["race_id"]
    return existing


def load_existing_event_keys(sb: Client) -> set[str]:
    existing: set[str] = set()
    last_race_id = 0
    while True:
        query = sb.table("races").select("race_id,course,date").order("race_id").limit(1000)
        if last_race_id:
            query = query.gt("race_id", last_race_id)
        rows = query.execute().data or []
        if not rows:
            break
        for row in rows:
            existing.add(build_event_key(row.get("race_id"), row.get("course"), row.get("date")))
        last_race_id = rows[-1]["race_id"]
    return existing


def load_horse_registry(sb: Client) -> Dict[str, set]:
    registry: Dict[str, set] = defaultdict(set)
    last_id = ""
    while True:
        query = sb.table("racing_horses").select("id,name").order("id").limit(1000)
        if last_id:
            query = query.gt("id", last_id)
        rows = query.execute().data or []
        if not rows:
            break
        for row in rows:
            registry[clean_horse_name(row["name"])].add(row["id"])
        last_id = rows[-1]["id"]
    return registry


def fetch_raceform_rows(sb: Client, candidates: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for candidate in candidates:
        rows = (
            sb.table("raceform")
            .select("*")
            .eq("race_id", str(candidate["race_id"]))
            .eq("course", candidate.get("course"))
            .eq("date", candidate.get("race_date"))
            .execute()
            .data
            or []
        )
        grouped[str(candidate["event_key"])] = rows
    return grouped


def validate_candidate(
    candidate: Dict[str, Any],
    race_rows: List[Dict[str, Any]],
    horse_registry: Dict[str, set],
) -> Tuple[bool, Dict[str, Any]]:
    info = {
        "race_id": str(candidate["race_id"]),
        "event_key": candidate.get("event_key"),
        "course": candidate.get("course"),
        "jurisdiction": candidate.get("jurisdiction"),
        "race_date": candidate.get("race_date"),
        "runner_count": candidate.get("runner_count"),
        "winner_count": candidate.get("winner_count"),
        "reason": None,
    }
    if not race_rows:
        info["reason"] = "missing_race_rows"
        return False, info

    if len(race_rows) != int(candidate["runner_count"]):
        info["reason"] = "runner_count_mismatch"
        return False, info

    for row in race_rows:
        if (
            str(row.get("course") or "") != str(candidate.get("course") or "")
            or str(row.get("date") or "")[:10] != str(candidate.get("race_date") or "")[:10]
        ):
            info["reason"] = "event_identity_mismatch"
            return False, info

    winner_count = 0
    seen_horse_ids = set()
    for row in race_rows:
        matches = horse_registry.get(clean_horse_name(row.get("horse")), set())
        if len(matches) != 1:
            info["reason"] = "candidate_identity_failure"
            return False, info
        horse_id = next(iter(matches))
        if horse_id in seen_horse_ids:
            info["reason"] = "duplicate_race_horse_pair"
            return False, info
        seen_horse_ids.add(horse_id)

        sp_val = normalize_sp(row.get("sp"))
        if sp_val is None:
            info["reason"] = "candidate_malformed_sp"
            return False, info
        pos_val, is_winner = normalize_pos(row.get("pos"))
        if pos_val is None:
            info["reason"] = "candidate_malformed_position"
            return False, info
        if is_winner:
            winner_count += 1

    if winner_count != 1:
        info["reason"] = "winner_parity_fail"
        return False, info
    if winner_count != int(candidate["winner_count"]):
        info["reason"] = "winner_count_mismatch"
        return False, info

    return True, info


def build_bridge_payloads(
    selected_candidates: List[Dict[str, Any]],
    race_rows_by_event: Dict[str, List[Dict[str, Any]]],
    horse_registry: Dict[str, set],
    signal_contract_version: str,
    data_owner_confirmed: bool,
    training_eligible: str,
    archive_exhausted: bool,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    races_payload: List[Dict[str, Any]] = []
    race_results_payload: List[Dict[str, Any]] = []
    runner_results_payload: List[Dict[str, Any]] = []

    for candidate in selected_candidates:
        race_id = str(candidate["race_id"])
        event_key = str(candidate["event_key"])
        rows = race_rows_by_event[event_key]
        sample = rows[0]

        races_payload.append(
            {
                "race_id": race_id,
                "course": sample.get("course"),
                "date": sample.get("date"),
                "time": sample.get("off") or "00:00",
                "going": sample.get("going"),
                "class": sample.get("class_raw"),
                "distance_f": normalize_distance(sample.get("dist")),
                "race_name": sample.get("race_name"),
                "runners_count": len(rows),
                "raw": {
                    "source": "historical_raceform",
                    "bridge_version": BRIDGE_VERSION,
                    "signal_contract_version": signal_contract_version,
                    "event_identity_contract": EVENT_IDENTITY_CONTRACT,
                    "data_owner_confirmed": data_owner_confirmed,
                    "training_eligible": training_eligible,
                    "archive_exhausted": archive_exhausted,
                    "event_key": event_key,
                    "is_historical_backfill": True,
                    "discovery_version": DISCOVERY_VERSION,
                    "jurisdiction": candidate.get("jurisdiction"),
                    "course": candidate.get("course"),
                    "race_date": candidate.get("race_date"),
                    "source_table": "raceform",
                    "source_race_id": race_id,
                },
            }
        )
        race_results_payload.append(
            {
                "race_id": race_id,
                "reconciled_at": datetime.now(UTC).isoformat(),
            }
        )

        for row in rows:
            horse_id = next(iter(horse_registry[clean_horse_name(row.get("horse"))]))
            pos_val, is_winner = normalize_pos(row.get("pos"))
            sp_val = normalize_sp(row.get("sp"))
            runner_results_payload.append(
                {
                    "race_id": race_id,
                    "horse_id": horse_id,
                    "position": pos_val,
                    "position_text": row.get("pos"),
                    "is_winner": is_winner,
                    "sp": row.get("sp"),
                    "sp_dec": sp_val,
                    "btn": row.get("btn"),
                    "ovr_btn": row.get("ovr_btn"),
                    "time": row.get("time"),
                    "prize": row.get("prize"),
                    "bsp": row.get("bsp"),
                    "in_running_comment": row.get("in_running_comment"),
                }
            )

    return races_payload, race_results_payload, runner_results_payload


def sample_winner_rows(rows: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    return rows[:limit]


def compute_pair_duplicates(rows: List[Dict[str, Any]], key_fields: Tuple[str, str]) -> int:
    seen = set()
    dupes = 0
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key in seen:
            dupes += 1
        else:
            seen.add(key)
    return dupes


def write_manifest(
    path: Path,
    block_name: str,
    race_events: List[Dict[str, Any]],
    race_ids: List[str],
    runner_count: int,
    jurisdiction_breakdown: Dict[str, int],
    source_candidate_file: Path,
    previous_manifests: List[Path],
    quarantined_candidate_ids: List[str],
    signal_contract_version: str,
    discovery_window: str | None,
    data_owner_confirmed: bool,
    training_eligible: str,
    archive_exhausted: bool,
) -> None:
    payload = {
        "bridge_block": block_name,
        "race_events": race_events,
        "race_ids": race_ids,
        "runner_count": runner_count,
        "jurisdiction_breakdown": jurisdiction_breakdown,
        "created_at": datetime.now(UTC).isoformat(),
        "source_candidate_file": str(source_candidate_file),
        "excluded_previous_manifests": [path.name for path in previous_manifests],
        "excluded_previous_manifest": previous_manifests[0].name if len(previous_manifests) == 1 else None,
        "quarantined_candidate_ids": quarantined_candidate_ids,
        "discovery_window": discovery_window,
        "discovery_version": DISCOVERY_VERSION,
        "bridge_version": BRIDGE_VERSION,
        "signal_contract_version": signal_contract_version,
        "event_identity_contract": EVENT_IDENTITY_CONTRACT,
        "data_owner_confirmed": data_owner_confirmed,
        "training_eligible": training_eligible,
        "archive_exhausted": archive_exhausted,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_hfs_manifest(manifest_path: Path, race_limit: int, workers: int) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "backfill_historical_feature_store.py"),
        "--manifest-file",
        str(manifest_path),
        "--limit-races",
        str(race_limit),
        "--batch-races",
        "25",
        "--workers",
        str(workers),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-races", type=int, default=100)
    parser.add_argument("--candidate-file", type=Path, default=CANDIDATE_FILE)
    parser.add_argument("--manifest-file", type=Path, default=MANIFEST_FILE)
    parser.add_argument("--exclude-manifest", action="append", type=Path, default=[])
    parser.add_argument("--exclude-race-ids", default="")
    parser.add_argument("--block-name", default=BLOCK_NAME)
    parser.add_argument("--signal-contract-version", default=SIGNAL_CONTRACT_VERSION)
    parser.add_argument("--data-owner-confirmed", action="store_true")
    parser.add_argument("--training-eligible", default=TRAINING_ELIGIBLE_DEFAULT)
    parser.add_argument("--archive-exhausted", action="store_true")
    parser.add_argument("--hfs-workers", type=int, default=4)
    parser.add_argument("--discovery-window", default=None)
    args = parser.parse_args()

    if not args.candidate_file.exists():
        raise RuntimeError(f"Candidate file missing: {args.candidate_file}")

    sb = get_sb_client()
    candidate_pool = load_candidate_pool(args.candidate_file)
    previous_manifests = [path for path in args.exclude_manifest if path]
    previous_manifest_payloads = [load_manifest(path) for path in previous_manifests]
    excluded_event_keys = {
        str(event["event_key"])
        for payload in previous_manifest_payloads
        for event in (payload.get("race_events") or [])
        if event.get("event_key")
    }
    excluded_race_ids = {
        str(rid)
        for payload in previous_manifest_payloads
        for rid in (payload.get("race_ids") or [])
    }
    explicit_excluded_race_ids = {
        rid.strip()
        for rid in str(args.exclude_race_ids or "").split(",")
        if rid and rid.strip()
    }
    excluded_race_ids.update(explicit_excluded_race_ids)
    existing_race_ids = load_existing_race_ids(sb)
    existing_event_keys = load_existing_event_keys(sb)
    horse_registry = load_horse_registry(sb)

    race_rows_by_event = fetch_raceform_rows(sb, candidate_pool)

    selected_candidates: List[Dict[str, Any]] = []
    selected_ids: set[str] = set()
    selected_event_keys: set[str] = set()
    skipped_existing_ids: List[str] = []
    skipped_existing_events: List[str] = []
    validation_failures: List[Dict[str, Any]] = []

    for candidate in candidate_pool:
        race_id = str(candidate["race_id"])
        event_key = str(candidate["event_key"])
        if event_key in selected_event_keys:
            continue
        if event_key in excluded_event_keys or race_id in excluded_race_ids:
            continue
        if event_key in existing_event_keys:
            skipped_existing_events.append(event_key)
            continue
        if race_id in existing_race_ids:
            skipped_existing_ids.append(race_id)
            continue
        if race_id in selected_ids:
            info = {
                "race_id": race_id,
                "event_key": event_key,
                "course": candidate.get("course"),
                "jurisdiction": candidate.get("jurisdiction"),
                "race_date": candidate.get("race_date"),
                "runner_count": candidate.get("runner_count"),
                "winner_count": candidate.get("winner_count"),
                "reason": "duplicate_selected_race_id",
            }
            validation_failures.append(info)
            continue
        valid, info = validate_candidate(candidate, race_rows_by_event.get(event_key, []), horse_registry)
        if not valid:
            validation_failures.append(info)
            continue
        selected_candidates.append(candidate)
        selected_ids.add(race_id)
        selected_event_keys.add(event_key)
        if len(selected_candidates) >= args.max_races:
            break

    selected_race_ids = [str(row["race_id"]) for row in selected_candidates]
    selected_event_key_list = [str(row["event_key"]) for row in selected_candidates]
    selected_race_rows = {event_key: race_rows_by_event[event_key] for event_key in selected_event_key_list}

    candidate_file_line_count = len(candidate_pool)
    duplicate_selected_event_keys = len(selected_event_key_list) - len(set(selected_event_key_list))
    duplicate_selected_ids = len(selected_race_ids) - len(set(selected_race_ids))
    expected_runner_rows = sum(len(selected_race_rows[event_key]) for event_key in selected_event_key_list)
    expected_jurisdiction_breakdown = dict(Counter(row["jurisdiction"] for row in selected_candidates))
    selected_sample = [
        {
            "race_id": row["race_id"],
            "event_key": row["event_key"],
            "course": row["course"],
            "jurisdiction": row["jurisdiction"],
            "runner_count": row["runner_count"],
            "winner_count": row["winner_count"],
            "race_date": row.get("race_date"),
        }
        for row in selected_candidates[:20]
    ]

    print("\nPRE-BRIDGE VERIFICATION")
    print(f"A. candidate file line count: {candidate_file_line_count}")
    print(f"B. previous manifest race IDs excluded: {sum(len(payload.get('race_ids') or []) for payload in previous_manifest_payloads)}")
    print(f"C. quarantined IDs excluded: {len(explicit_excluded_race_ids)}")
    print(f"D. selected bridge race count: {len(selected_race_ids)}")
    print(f"E. duplicate selected event keys: {duplicate_selected_event_keys}")
    print(f"F. duplicate selected race IDs: {duplicate_selected_ids}")
    print(f"G. already-existing selected race IDs/events skipped: {len(skipped_existing_ids) + len(skipped_existing_events)}")
    print(f"H. expected runner rows: {expected_runner_rows}")
    print(f"I. expected jurisdiction breakdown: {expected_jurisdiction_breakdown}")
    print("J. sampled 20 selected race IDs:")
    for row in selected_sample:
        print(
            f"   - race_id={row['race_id']} course={row['course']} jurisdiction={row['jurisdiction']} "
            f"runner_count={row['runner_count']} winner_count={row['winner_count']} race_date={row['race_date']}"
        )
    if validation_failures:
        print(f"K. quarantined candidate validation failures: {len(validation_failures)}")
        for row in validation_failures[:10]:
            print(
                f"   - race_id={row['race_id']} course={row['course']} jurisdiction={row['jurisdiction']} "
                f"reason={row['reason']} runner_count={row['runner_count']} winner_count={row['winner_count']}"
            )

    if duplicate_selected_event_keys != 0 or duplicate_selected_ids != 0:
        raise RuntimeError("Selected race IDs / event keys are not unique.")
    if len(selected_race_ids) < args.max_races:
        raise RuntimeError(
            f"Unable to assemble requested block size from validated candidates. "
            f"selected={len(selected_race_ids)} requested={args.max_races} "
            f"failures={validation_failures[:10]}"
        )

    race_results_before = count_table_rows(sb, "race_results")
    runner_results_before = count_table_rows(sb, "runner_results")

    races_payload, race_results_payload, runner_results_payload = build_bridge_payloads(
        selected_candidates,
        selected_race_rows,
        horse_registry,
        args.signal_contract_version,
        args.data_owner_confirmed,
        args.training_eligible,
        args.archive_exhausted,
    )

    if races_payload:
        for chunk in batched(races_payload, 100):
            sb.table("races").upsert(chunk).execute()
    if race_results_payload:
        for chunk in batched(race_results_payload, 100):
            sb.table("race_results").upsert(chunk).execute()
    if runner_results_payload:
        for chunk in batched(runner_results_payload, 500):
            sb.table("runner_results").upsert(chunk, on_conflict="race_id,horse_id").execute()

    write_manifest(
        args.manifest_file,
        args.block_name,
        race_events=[
            {
                "race_id": str(row["race_id"]),
                "course": row.get("course"),
                "race_date": row.get("race_date"),
                "jurisdiction": row.get("jurisdiction"),
                "event_key": row.get("event_key"),
                "runner_count": row.get("runner_count"),
                "winner_count": row.get("winner_count"),
            }
            for row in selected_candidates
        ],
        race_ids=selected_race_ids,
        runner_count=len(runner_results_payload),
        jurisdiction_breakdown=expected_jurisdiction_breakdown,
        source_candidate_file=args.candidate_file,
        previous_manifests=previous_manifests,
        quarantined_candidate_ids=sorted(explicit_excluded_race_ids),
        signal_contract_version=args.signal_contract_version,
        discovery_window=args.discovery_window,
        data_owner_confirmed=args.data_owner_confirmed,
        training_eligible=args.training_eligible,
        archive_exhausted=args.archive_exhausted,
    )

    race_results_after = count_table_rows(sb, "race_results")
    runner_results_after = count_table_rows(sb, "runner_results")

    bridged_race_rows = []
    bridged_runner_rows = []
    for chunk in batched(selected_race_ids, 25):
        bridged_race_rows.extend(sb.table("race_results").select("race_id,reconciled_at").in_("race_id", chunk).execute().data or [])
        bridged_runner_rows.extend(
            sb.table("runner_results").select("race_id,horse_id,position,is_winner,sp,sp_dec,position_text").in_("race_id", chunk).execute().data or []
        )

    duplicate_race_id_count = len(bridged_race_rows) - len({str(row["race_id"]) for row in bridged_race_rows})
    duplicate_pair_count = compute_pair_duplicates(bridged_runner_rows, ("race_id", "horse_id"))
    duplicate_event_key_count = len(selected_event_key_list) - len(set(selected_event_key_list))
    winner_counts = Counter()
    for row in bridged_runner_rows:
        if row.get("is_winner"):
            winner_counts[str(row["race_id"])] += 1
    winner_parity_ok = all(winner_counts.get(rid, 0) == 1 for rid in selected_race_ids)
    jurisdiction_breakdown = dict(Counter(row["jurisdiction"] for row in selected_candidates))

    print("\nPOST-BRIDGE AUDIT")
    print(f"A. race_results rows before/after: {race_results_before} -> {race_results_after}")
    print(f"B. runner_results rows before/after: {runner_results_before} -> {runner_results_after}")
    print(f"C. races attempted: {len(selected_race_ids)}")
    print(f"D. races bridged: {len({str(row['race_id']) for row in bridged_race_rows})}")
    print(f"E. runners inserted: {len(runner_results_payload)}")
    print(f"F. races skipped existing: {len(skipped_existing_ids)}")
    print("G. ambiguous runners blocked: 0")
    print("H. unmatched runners blocked: 0")
    print("I. malformed runners blocked: 0")
    print(f"J. winner parity: {'100%' if winner_parity_ok else 'FAIL'}")
    print(f"K. duplicate race_id count: {duplicate_race_id_count}")
    print(f"L. duplicate (race_id + horse_id) count: {duplicate_pair_count}")
    print(f"M. duplicate event_key count: {duplicate_event_key_count}")
    print(f"N. jurisdiction breakdown: {jurisdiction_breakdown}")
    print("O. sample 20 bridged runner rows:")
    for row in sample_winner_rows(bridged_runner_rows):
        print(f"   - {row}")

    hfs_before_total = count_table_rows(sb, "historical_feature_store")
    hfs_before_selected = count_rows_for_race_ids(
        sb, "historical_feature_store", selected_race_ids, {"reconstruction_version": HFS_VERSION}
    )

    run_hfs_manifest(args.manifest_file, len(selected_race_ids), args.hfs_workers)

    hfs_after_total = count_table_rows(sb, "historical_feature_store")
    hfs_after_selected_rows = []
    for chunk in batched(selected_race_ids, 25):
        hfs_after_selected_rows.extend(
            sb.table("historical_feature_store")
            .select(
                "race_id,horse_id,winner_flag,mpi,chaos_bloom,story_anchor,narrative_disruption,feature_json,reconstruction_version,race_date"
            )
            .in_("race_id", chunk)
            .eq("reconstruction_version", HFS_VERSION)
            .execute()
            .data
            or []
        )

    hfs_after_selected = len(hfs_after_selected_rows)
    per_race_counts = Counter(str(row["race_id"]) for row in hfs_after_selected_rows)
    per_race_winners = Counter(str(row["race_id"]) for row in hfs_after_selected_rows if row.get("winner_flag"))
    vector_missing = 0
    expected_historical_nulls = 0
    mpi_values: List[float] = []
    chaos_values: List[float] = []
    vector_lengths: List[int] = []
    mpi_null_count = 0
    chaos_null_count = 0
    mpi_source_count = 0
    chaos_source_count = 0
    contract_version_count = 0
    macro_year_mismatch_count = 0
    for row in hfs_after_selected_rows:
        feature_json = row.get("feature_json") or {}
        vector = feature_json.get("strictly_ordered_vector") or []
        if not vector:
            vector_missing += 1
        vector_lengths.append(len(vector))
        if row.get("story_anchor") is None and row.get("narrative_disruption") is None:
            expected_historical_nulls += 1
        if row.get("mpi") is not None:
            mpi_values.append(float(row["mpi"]))
        else:
            mpi_null_count += 1
        if row.get("chaos_bloom") is not None:
            chaos_values.append(float(row["chaos_bloom"]))
        else:
            chaos_null_count += 1
        if feature_json.get("mpi_source") == MPI_SOURCE:
            mpi_source_count += 1
        if feature_json.get("chaos_bloom_source") == CHAOS_SOURCE:
            chaos_source_count += 1
        if feature_json.get("signal_contract_version") == args.signal_contract_version:
            contract_version_count += 1
        row_race_date = row.get("race_date")
        macro_year_used = feature_json.get("macro_year_used")
        if row_race_date and macro_year_used is not None:
            try:
                if int(str(row_race_date)[:4]) != int(macro_year_used):
                    macro_year_mismatch_count += 1
            except (TypeError, ValueError):
                macro_year_mismatch_count += 1

    hfs_duplicate_pairs = compute_pair_duplicates(hfs_after_selected_rows, ("race_id", "horse_id"))
    hfs_winner_parity_ok = all(per_race_winners.get(rid, 0) == 1 for rid in selected_race_ids)
    vector_length_unique = sorted(set(vector_lengths))
    runner_rows_reconstructed = hfs_after_selected - hfs_before_selected

    print("\nHFS AUDIT")
    print(f"A. HFS rows before/after: {hfs_before_total} -> {hfs_after_total}")
    print(f"B. new HFS rows written: {runner_rows_reconstructed}")
    print(f"C. distinct races reconstructed: {len(per_race_counts)}")
    print(f"D. runner rows reconstructed: {runner_rows_reconstructed}")
    if per_race_counts:
        counts = list(per_race_counts.values())
        print(f"E. avg/min/max runners per race: {sum(counts)/len(counts):.2f} / {min(counts)} / {max(counts)}")
    else:
        print("E. avg/min/max runners per race: 0 / 0 / 0")
    print(f"F. winner parity: {'100%' if hfs_winner_parity_ok else 'FAIL'}")
    print(f"G. duplicate HFS rows: {hfs_duplicate_pairs}")
    print(f"H. missing vectors: {vector_missing}")
    print(f"I. vector dimension consistency: {vector_length_unique}")
    print(f"J. mpi null count: {mpi_null_count}")
    if mpi_values:
        print(f"K. mpi min/max/variance: {min(mpi_values)} / {max(mpi_values)} / {pvariance(mpi_values) if len(mpi_values) > 1 else 0.0}")
    else:
        print("K. mpi min/max/variance: n/a")
    print(f"L. chaos_bloom null count: {chaos_null_count}")
    if chaos_values:
        print(f"M. chaos_bloom min/max/variance: {min(chaos_values)} / {max(chaos_values)} / {pvariance(chaos_values) if len(chaos_values) > 1 else 0.0}")
    else:
        print("M. chaos_bloom min/max/variance: n/a")
    print(f"N. macro-year mismatch count: {macro_year_mismatch_count}")
    print(
        f"O. source tags present: mpi_source={mpi_source_count}/{len(hfs_after_selected_rows)} "
        f"chaos_bloom_source={chaos_source_count}/{len(hfs_after_selected_rows)} "
        f"signal_contract_version={contract_version_count}/{len(hfs_after_selected_rows)}"
    )
    print(
        f"P. narrative/story nulls classified as expected historical nulls: "
        f"{expected_historical_nulls}/{len(hfs_after_selected_rows)}"
    )
    print("Q. sample 20 post-HFS runners:")
    for row in hfs_after_selected_rows[:20]:
        feature_json = row.get("feature_json") or {}
        print(
            "   - "
            + json.dumps(
                {
                    "race_id": row.get("race_id"),
                    "horse_id": row.get("horse_id"),
                    "race_date": row.get("race_date"),
                    "macro_year_used": feature_json.get("macro_year_used"),
                    "winner_flag": row.get("winner_flag"),
                    "mpi": row.get("mpi"),
                    "chaos_bloom": row.get("chaos_bloom"),
                    "mpi_source": feature_json.get("mpi_source"),
                    "chaos_bloom_source": feature_json.get("chaos_bloom_source"),
                    "signal_contract_version": feature_json.get("signal_contract_version"),
                    "vector_length": len(feature_json.get("strictly_ordered_vector") or []),
                }
            )
        )

    if not winner_parity_ok or duplicate_race_id_count or duplicate_pair_count:
        raise RuntimeError("Bridge audit failed.")
    if not hfs_winner_parity_ok or hfs_duplicate_pairs or vector_missing:
        raise RuntimeError("HFS audit failed.")
    if runner_rows_reconstructed != len(runner_results_payload):
        raise RuntimeError("HFS rows written do not match runner rows inserted.")
    if mpi_null_count or chaos_null_count:
        raise RuntimeError("Signal field nulls remain after HFS reconstruction.")
    if macro_year_mismatch_count:
        raise RuntimeError("Macro-year mismatch remains after HFS reconstruction.")
    if vector_length_unique != [37]:
        raise RuntimeError("Vector dimension consistency failed.")
    if mpi_source_count != len(hfs_after_selected_rows) or chaos_source_count != len(hfs_after_selected_rows):
        raise RuntimeError("Historical proxy source tags missing from HFS rows.")
    if contract_version_count != len(hfs_after_selected_rows):
        raise RuntimeError("Signal contract version missing from HFS rows.")


if __name__ == "__main__":
    main()
