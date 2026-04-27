"""
Hardened clean-race discovery for historical archive oasis courses.

This script is discovery-only. It does not bridge, run HFS, or train models.
It keyset-scans raceform using raceform.id, persists cursor state, and writes
auditable clean-candidate / rejection JSONL files before any downstream bridge
approval is allowed.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from supabase import Client, create_client


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CURSOR_PATH = DATA_DIR / "clean_race_index_cursor.json"
CANDIDATES_PATH = DATA_DIR / "clean_race_candidates_oasis.jsonl"
REJECTIONS_PATH = DATA_DIR / "clean_race_rejections_oasis.jsonl"

DISCOVERY_VERSION = "CLEAN_INDEX_V1"
TARGET_COURSES = [
    "Compiegne",
    "Chantilly",
    "Kokura",
    "Sapporo",
    "Happy Valley",
    "Sha Tin",
]
ALLOWED_JURISDICTIONS = {"UK", "IRE", "FR", "JPN", "HK", "USA", "UAE", "AUS", "SAF"}
REJECTION_PRIORITY = [
    "duplicate_existing_race",
    "incomplete_field",
    "unmatched_horse_identity",
    "ambiguous_horse_identity",
    "duplicate_race_horse_pair",
    "malformed_sp",
    "malformed_position",
    "missing_winner",
    "multiple_winners",
    "one_horse_race",
]
EVENT_IDENTITY_CONTRACT = "race_id_course_race_date"

def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # Keep our audit logs visible without flooding the terminal with per-request HTTP traces.
    for noisy_logger in ("httpx", "httpcore", "postgrest", "supabase"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


configure_logging()
LOG = logging.getLogger("clean_course_mining")


def get_sb_client() -> Client:
    load_dotenv(ROOT / ".env", override=False)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials missing.")
    return create_client(url, key)


def clean_horse_name(name: Any) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"\([A-Z]+\)$", "", str(name)).strip().upper()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def normalize_sp(sp_str: Any) -> Optional[float]:
    if sp_str in (None, "", "-", "â€“"):
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
    try:
        pos = int(cleaned)
    except ValueError:
        return None, False
    return pos, pos == 1


def detect_jurisdiction(course: str) -> Optional[str]:
    suffix_map = {
        "(FR)": "FR",
        "(JPN)": "JPN",
        "(HK)": "HK",
        "(IRE)": "IRE",
        "(GB)": "UK",
        "(UK)": "UK",
        "(USA)": "USA",
        "(UAE)": "UAE",
        "(AUS)": "AUS",
        "(SAF)": "SAF",
    }
    upper = (course or "").upper()
    for suffix, juris in suffix_map.items():
        if suffix in upper:
            return juris
    if "HAPPY VALLEY" in upper or "SHA TIN" in upper:
        return "HK"
    return None


def build_event_key(race_id: Any, course: Any, race_date: Any) -> str:
    return f"{str(race_id)}|{str(course or '').strip()}|{str(race_date or '').strip()}"


def canonical_target(course: str) -> Tuple[Optional[str], Optional[str], bool]:
    if not course:
        return None, None, False
    normalized = course.strip().upper()
    for target in TARGET_COURSES:
        if normalized == target.upper():
            return target, course, True
        for juris in ("FR", "JPN", "HK"):
            if normalized == f"{target} ({juris})".upper():
                return target, course, True
    for target in TARGET_COURSES:
        if target.upper() in normalized:
            return target, course, False
    return None, None, False


def load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def load_jsonl_keys(path: Path, key_name: str, fallback_race_id: bool = False) -> set[str]:
    seen: set[str] = set()
    if not path.exists():
        return seen
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            key_val = payload.get(key_name)
            if key_val is not None:
                seen.add(str(key_val))
                continue
            if fallback_race_id:
                race_id = payload.get("race_id")
                course = payload.get("course")
                race_date = payload.get("race_date")
                if race_id is not None and course is not None and race_date is not None:
                    seen.add(build_event_key(race_id, course, race_date))
    return seen


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def truncate_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def load_horse_registry(sb: Client, page_size: int = 1000) -> Dict[str, set]:
    LOG.info("Loading horse identity registry with keyset pagination...")
    registry: Dict[str, set] = defaultdict(set)
    last_id = ""
    loaded = 0
    while True:
        query = sb.table("racing_horses").select("id,name").order("id").limit(page_size)
        if last_id:
            query = query.gt("id", last_id)
        rows = query.execute().data or []
        if not rows:
            break
        for row in rows:
            registry[clean_horse_name(row.get("name"))].add(row["id"])
        loaded += len(rows)
        last_id = rows[-1]["id"]
        if loaded % 50000 == 0:
            LOG.info("  loaded %s horses...", f"{loaded:,}")
    LOG.info("Horse registry loaded: %s canonical names", f"{len(registry):,}")
    return registry


def load_existing_event_keys(sb: Client) -> set[str]:
    LOG.info("Loading existing bridged race event keys...")
    existing: set[str] = set()
    last_race_id = ""
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
    LOG.info("Existing bridged race events loaded: %s", f"{len(existing):,}")
    return existing


def choose_reason(candidates: List[str]) -> str:
    for reason in REJECTION_PRIORITY:
        if reason in candidates:
            return reason
    return "incomplete_field"


def validate_race(
    race_id: str,
    event_key: str,
    race_rows: List[Dict[str, Any]],
    horse_registry: Dict[str, set],
    existing_event_keys: set[str],
) -> Tuple[str, Optional[str], Dict[str, Any], Counter]:
    sample = race_rows[0] if race_rows else {}
    course = sample.get("course") or ""
    race_date = str(sample.get("date") or "")
    jurisdiction = detect_jurisdiction(course)
    runner_count = len(race_rows)

    diagnostics = Counter()
    details = {
        "race_id": race_id,
        "event_key": event_key,
        "course": course,
        "jurisdiction": jurisdiction,
        "race_date": race_date,
        "runner_count": runner_count,
        "sample_horse": sample.get("horse"),
        "sample_sp": sample.get("sp"),
        "sample_pos": sample.get("pos"),
        "winner_count": 0,
    }

    if event_key in existing_event_keys:
        return "skipped_existing", None, details, diagnostics
    if not jurisdiction or jurisdiction not in ALLOWED_JURISDICTIONS:
        return "rejected", "incomplete_field", details, diagnostics
    if not race_rows:
        return "rejected", "incomplete_field", details, diagnostics
    if runner_count == 1:
        return "rejected", "one_horse_race", details, diagnostics

    resolved_horse_ids: List[Any] = []
    rejection_candidates: List[str] = []
    winner_count = 0

    for row in race_rows:
        horse_name = clean_horse_name(row.get("horse"))
        matches = horse_registry.get(horse_name, set())
        if not matches:
            diagnostics["unmatched_runner_rows"] += 1
            rejection_candidates.append("unmatched_horse_identity")
        elif len(matches) > 1:
            diagnostics["ambiguous_runner_rows"] += 1
            rejection_candidates.append("ambiguous_horse_identity")
        else:
            resolved_horse_ids.append(next(iter(matches)))

        if normalize_sp(row.get("sp")) is None:
            diagnostics["malformed_sp_runner_rows"] += 1
            rejection_candidates.append("malformed_sp")

        pos_val, is_winner = normalize_pos(row.get("pos"))
        if pos_val is None:
            diagnostics["malformed_position_runner_rows"] += 1
            rejection_candidates.append("malformed_position")
        elif is_winner:
            winner_count += 1

    details["winner_count"] = winner_count

    if resolved_horse_ids:
        duplicate_pairs = len(resolved_horse_ids) - len(set(resolved_horse_ids))
        if duplicate_pairs > 0:
            diagnostics["duplicate_race_horse_pair_rows"] += duplicate_pairs
            rejection_candidates.append("duplicate_race_horse_pair")

    if winner_count == 0:
        rejection_candidates.append("missing_winner")
    elif winner_count > 1:
        rejection_candidates.append("multiple_winners")

    if rejection_candidates:
        return "rejected", choose_reason(rejection_candidates), details, diagnostics
    return "clean", None, details, diagnostics


def fetch_full_race_rows(
    sb: Client, race_meta: Dict[str, Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for event_key, meta in race_meta.items():
        rows = (
            sb.table("raceform")
            .select("race_id,course,date,horse,sp,pos")
            .eq("race_id", meta["race_id"])
            .eq("course", meta["course"])
            .eq("date", meta["race_date"])
            .execute()
            .data
            or []
        )
        grouped[event_key] = rows
    return grouped


def run_targeted_discovery(args: argparse.Namespace) -> None:
    start_ts = time.time()
    sb = get_sb_client()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.reset_window:
        truncate_file(CANDIDATES_PATH)
        truncate_file(REJECTIONS_PATH)
        start_id = args.start_id
        write_json(
            CURSOR_PATH,
            {
                "last_id": start_id,
                "rows_scanned_total": 0,
                "courses_confirmed": [],
                "last_runtime_seconds": 0.0,
                "discovery_version": DISCOVERY_VERSION,
            },
        )
    else:
        cursor = load_json(
            CURSOR_PATH,
            {
                "last_id": 0,
                "rows_scanned_total": 0,
                "courses_confirmed": [],
                "last_runtime_seconds": 0.0,
            },
        )
        start_id = args.start_id if args.start_id is not None else int(cursor.get("last_id", 0) or 0)

    base_clean_lines = count_lines(CANDIDATES_PATH)
    base_rejection_lines = count_lines(REJECTIONS_PATH)
    persisted_candidate_keys = load_jsonl_keys(CANDIDATES_PATH, "event_key", fallback_race_id=True)
    persisted_rejection_keys = load_jsonl_keys(REJECTIONS_PATH, "event_key", fallback_race_id=True)

    horse_registry = load_horse_registry(sb)
    existing_event_keys = load_existing_event_keys(sb)

    audit: Dict[str, Any] = {
        "rows_scanned": 0,
        "matched_courses": set(),
        "exact_courses": set(),
        "closest_course_strings": defaultdict(set),
        "runner_diagnostics": Counter(),
    }

    target_race_meta: Dict[str, Dict[str, Any]] = {}
    last_id = start_id
    LOG.info("Starting discovery dry-run from raceform.id > %s", start_id)

    while audit["rows_scanned"] < args.max_rows:
        remaining = args.max_rows - audit["rows_scanned"]
        limit = min(args.batch_size, remaining)
        rows = (
            sb.table("raceform")
            .select("id,race_id,course,date,horse,sp,pos")
            .gt("id", last_id)
            .order("id")
            .limit(limit)
            .execute()
            .data
            or []
        )
        if not rows:
            break

        last_id = rows[-1]["id"]
        audit["rows_scanned"] += len(rows)

        for row in rows:
            target, actual_course, is_exact = canonical_target(str(row.get("course") or ""))
            if not target or not actual_course or not is_exact:
                continue
            audit["matched_courses"].add(actual_course)
            audit["exact_courses"].add(actual_course)

            race_id = str(row["race_id"])
            race_date = str(row.get("date") or "")
            event_key = build_event_key(race_id, actual_course, race_date)
            meta = target_race_meta.setdefault(
                event_key,
                {
                    "event_key": event_key,
                    "race_id": race_id,
                    "course": actual_course,
                    "race_date": race_date,
                    "jurisdiction": detect_jurisdiction(actual_course),
                    "scan_runner_rows": 0,
                },
            )
            meta["scan_runner_rows"] += 1

        if audit["rows_scanned"] % (args.batch_size * 25) == 0:
            LOG.info(
                "Scanned %s rows | unique target races %s",
                f"{audit['rows_scanned']:,}",
                f"{len(target_race_meta):,}",
            )

    event_keys = sorted(
        target_race_meta.keys(),
        key=lambda key: (
            target_race_meta[key]["race_date"],
            target_race_meta[key]["course"],
            int(target_race_meta[key]["race_id"]),
        ),
    )
    full_race_rows = fetch_full_race_rows(sb, target_race_meta)

    block_stats: Dict[Tuple[str, str, str], Dict[str, Any]] = defaultdict(
        lambda: {
            "course": "",
            "jurisdiction": "UNKNOWN",
            "year_month": "UNKNOWN",
            "candidate_races": 0,
            "clean_races": 0,
            "runner_rows": 0,
            "rejections": Counter(),
        }
    )
    clean_output_rows: List[Dict[str, Any]] = []
    rejection_output_rows: List[Dict[str, Any]] = []
    status_counts = Counter()
    rejection_counts = Counter()
    sample_clean_ids: List[str] = []
    sample_rejected_rows: List[Dict[str, Any]] = []

    for event_key in event_keys:
        meta = target_race_meta[event_key]
        race_id = meta["race_id"]
        rows = full_race_rows.get(event_key, [])
        status, reason, details, diagnostics = validate_race(
            race_id,
            event_key,
            rows,
            horse_registry,
            existing_event_keys,
        )
        audit["runner_diagnostics"].update(diagnostics)

        course = details["course"] or meta["course"]
        jurisdiction = details["jurisdiction"] or meta["jurisdiction"] or "UNKNOWN"
        year_month = (details["race_date"] or meta["race_date"] or "UNKNOWN")[:7] or "UNKNOWN"
        block = block_stats[(course, jurisdiction, year_month)]
        block["course"] = course
        block["jurisdiction"] = jurisdiction
        block["year_month"] = year_month
        block["candidate_races"] += 1
        block["runner_rows"] += len(rows)

        if status == "clean":
            status_counts["clean"] += 1
            block["clean_races"] += 1
            if event_key not in persisted_candidate_keys:
                clean_output_rows.append(
                    {
                        "race_id": race_id,
                        "event_key": event_key,
                        "event_identity_contract": EVENT_IDENTITY_CONTRACT,
                        "course": course,
                        "jurisdiction": jurisdiction,
                        "race_date": details["race_date"],
                        "runner_count": details["runner_count"],
                        "winner_count": details["winner_count"],
                        "clean_status": True,
                        "rejection_reason": None,
                        "source_table": "raceform",
                        "discovery_version": DISCOVERY_VERSION,
                    }
                )
                persisted_candidate_keys.add(event_key)
            if len(sample_clean_ids) < 50:
                sample_clean_ids.append(event_key)
        elif status == "skipped_existing":
            status_counts["skipped_existing"] += 1
        else:
            status_counts["rejected"] += 1
            rejection_counts[reason] += 1
            block["rejections"][reason] += 1
            row = {
                "race_id": race_id,
                "event_key": event_key,
                "event_identity_contract": EVENT_IDENTITY_CONTRACT,
                "course": course,
                "jurisdiction": jurisdiction,
                "race_date": details["race_date"],
                "runner_count": details["runner_count"],
                "rejection_reason": reason,
                "sample_horse": details["sample_horse"],
                "sample_sp": details["sample_sp"],
                "sample_pos": details["sample_pos"],
                "discovery_version": DISCOVERY_VERSION,
            }
            if event_key not in persisted_rejection_keys:
                rejection_output_rows.append(row)
                persisted_rejection_keys.add(event_key)
            if len(sample_rejected_rows) < 20:
                sample_rejected_rows.append(row)

    candidate_races = len(event_keys)
    clean_races = status_counts["clean"]
    rejected_races = status_counts["rejected"]
    skipped_existing_races = status_counts["skipped_existing"]
    expected_candidate_total = clean_races + rejected_races + skipped_existing_races

    appended_candidates = append_jsonl(CANDIDATES_PATH, clean_output_rows)
    appended_rejections = append_jsonl(REJECTIONS_PATH, rejection_output_rows)

    clean_file_lines = count_lines(CANDIDATES_PATH)
    rejection_file_lines = count_lines(REJECTIONS_PATH)
    persisted_clean_keys = load_jsonl_keys(CANDIDATES_PATH, "event_key", fallback_race_id=True)
    duplicate_clean_ids = clean_file_lines - len(persisted_clean_keys)

    runtime = round(time.time() - start_ts, 3)
    cursor_payload = {
        "last_id": last_id,
        "rows_scanned_total": args.max_rows if args.reset_window else load_json(CURSOR_PATH, {}).get("rows_scanned_total", 0) + audit["rows_scanned"],
        "courses_confirmed": sorted(audit["exact_courses"]),
        "closest_course_strings": {
            key: sorted(values) for key, values in audit["closest_course_strings"].items()
        },
        "last_runtime_seconds": runtime,
        "discovery_version": DISCOVERY_VERSION,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(CURSOR_PATH, cursor_payload)

    report_rows: List[Dict[str, Any]] = []
    for block in block_stats.values():
        clean_rate = (block["clean_races"] / block["candidate_races"] * 100.0) if block["candidate_races"] else 0.0
        report_rows.append(
            {
                "course": block["course"],
                "jurisdiction": block["jurisdiction"],
                "year_month": block["year_month"],
                "candidate_races": block["candidate_races"],
                "clean_races": block["clean_races"],
                "clean_rate": round(clean_rate, 2),
                "runner_rows": block["runner_rows"],
            }
        )
    report_rows.sort(key=lambda row: (row["clean_races"], row["clean_rate"], row["runner_rows"]), reverse=True)

    print("\n" + "=" * 112)
    print("HARDENED CLEAN RACE INDEX DISCOVERY".center(112))
    print("=" * 112)
    print(f"A. rows scanned: {audit['rows_scanned']:,}")
    print(f"B. unique race event keys seen in target courses: {candidate_races:,}")
    print(f"C. clean race events: {clean_races:,}")
    print(f"D. rejected race events: {rejected_races:,}")
    print(f"E. skipped existing race events: {skipped_existing_races:,}")
    print(
        "F. accounting invariant: "
        f"{candidate_races} = {clean_races} + {rejected_races} + {skipped_existing_races}"
    )
    print("G. rejection reasons by race count:")
    for reason, count in rejection_counts.most_common():
        print(f"   - {reason:<28} {count}")
    print("H. runner-level diagnostic counts:")
    for reason, count in audit["runner_diagnostics"].most_common():
        print(f"   - {reason:<28} {count}")

    print("\nI. top 20 clean-dense blocks:")
    print(
        f"{'COURSE':<28} {'JURIS':<6} {'YM':<8} {'CAND':>6} {'CLEAN':>6} {'RATE%':>8} {'RUNNERS':>8}"
    )
    print("-" * 112)
    for row in report_rows[:20]:
        print(
            f"{row['course']:<28} {row['jurisdiction']:<6} {row['year_month']:<8} "
            f"{row['candidate_races']:>6} {row['clean_races']:>6} {row['clean_rate']:>8.2f} {row['runner_rows']:>8}"
        )
    print(f"\nJ. clean candidate file line count: {clean_file_lines}")
    print(f"K. rejection file line count: {rejection_file_lines}")
    print(f"L. duplicate clean event keys: {duplicate_clean_ids}")
    print(f"M. cursor start/end: {start_id} -> {last_id}")
    print(f"N. sample clean event keys: {sample_clean_ids}")
    print("O. sample rejected event keys with reasons:")
    for row in sample_rejected_rows:
        print(
            f"   - event_key={row['event_key']} race_id={row['race_id']} course={row['course']} reason={row['rejection_reason']} "
            f"horse={row['sample_horse']} sp={row['sample_sp']} pos={row['sample_pos']}"
        )
    print(f"\nPersisted candidate file: {CANDIDATES_PATH}")
    print(f"Persisted rejection file: {REJECTIONS_PATH}")
    print(f"Persisted cursor file: {CURSOR_PATH}")
    print(f"New candidate rows appended: {appended_candidates}")
    print(f"New rejection rows appended: {appended_rejections}")
    print("=" * 112)

    invariant_ok = candidate_races == expected_candidate_total
    clean_lines_ok = clean_file_lines == base_clean_lines + appended_candidates
    rejection_lines_ok = rejection_file_lines == base_rejection_lines + appended_rejections
    no_duplicate_clean_ids = duplicate_clean_ids == 0

    if not (invariant_ok and clean_lines_ok and rejection_lines_ok and no_duplicate_clean_ids):
        print("ACCOUNTING_INVARIANT_FAIL")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discovery-only clean race index mining for oasis courses.")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--max-rows", type=int, default=100000)
    parser.add_argument("--start-id", type=int, default=0)
    parser.add_argument("--reset-window", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run_targeted_discovery(parse_args())
