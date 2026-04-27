from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from supabase import Client, create_client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.runtime_env import load_optional_env_file, resolve_supabase_service_key, resolve_supabase_url

DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "velo_current_state.json"
RECONSTRUCTION_VERSION = "V17_B1"
HISTORICAL_SOURCE = "historical_raceform"
BRIDGE_VERSION = "RACEFORM_BRIDGE_V1"
DISCOVERY_VERSION = "CLEAN_INDEX_V1"
SIGNAL_CONTRACT_VERSION = "HISTORICAL_SIGNAL_PROXY_V1"
MPI_SOURCE = "archive_proxy_market_rank_v1"
CHAOS_SOURCE = "archive_proxy_market_entropy_going_v1"
EVENT_IDENTITY_CONTRACT = "race_id_course_race_date"
TRAINING_ELIGIBLE = "pending_global_training_gate"
MIN_ACCEPTED_YEAR = 2017
MAX_ACCEPTED_YEAR = 2025


def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_event_key(race_id: str, course: str | None, race_date: str | None) -> str:
    return f"{str(race_id)}|{course or ''}|{race_date or ''}"


def parse_date_str(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10:
        text = text[:10]
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def chunked(items: Sequence[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def count_extra_duplicates(keys: Iterable[Any]) -> int:
    counts = Counter(keys)
    return sum(count - 1 for count in counts.values() if count > 1)


def variance(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def get_sb_client() -> Client:
    load_optional_env_file(ROOT / ".env")
    url = resolve_supabase_url()
    key = resolve_supabase_service_key()
    if not url or not key:
        raise RuntimeError("Supabase credentials are required for global clean spine audit.")
    return create_client(url, key)


def exact_count(sb: Client, table: str) -> int:
    result = sb.table(table).select("*", count="exact", head=True).execute()
    return int(result.count or 0)


def paged_select(
    sb: Client,
    table: str,
    columns: str,
    *,
    page_size: int = 1000,
    filters: Sequence[tuple[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    filters = filters or []

    while True:
        query = sb.table(table).select(columns)
        for method, *args in filters:
            query = getattr(query, method)(*args)
        response = query.range(offset, offset + page_size - 1).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += len(batch)
    return rows


def load_accepted_historical_races(sb: Client) -> list[dict[str, Any]]:
    race_rows = paged_select(sb, "races", "race_id,date,course,raw")
    accepted: list[dict[str, Any]] = []
    for row in race_rows:
        raw = row.get("raw")
        if not isinstance(raw, dict):
            continue
        if raw.get("source") != HISTORICAL_SOURCE:
            continue
        if raw.get("is_historical_backfill") is not True:
            continue
        parsed = parse_date_str(row.get("date") or raw.get("race_date"))
        if parsed is None:
            continue
        if parsed.year < MIN_ACCEPTED_YEAR or parsed.year > MAX_ACCEPTED_YEAR:
            continue
        event_key = raw.get("event_key") or build_event_key(row["race_id"], row.get("course"), parsed.date().isoformat())
        accepted.append(
            {
                "race_id": str(row["race_id"]),
                "race_date": parsed.date().isoformat(),
                "course": row.get("course"),
                "event_key": event_key,
                "raw": raw,
            }
        )
    return accepted


def load_rows_by_race_ids(sb: Client, table: str, columns: str, race_ids: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in chunked(list(race_ids), 200):
        offset = 0
        while True:
            response = sb.table(table).select(columns).in_("race_id", chunk).range(offset, offset + 999).execute()
            batch = response.data or []
            rows.extend(batch)
            if len(batch) < 1000:
                break
            offset += len(batch)
    return rows


def load_blocked_block_025_summary(sb: Client) -> dict[str, Any]:
    manifest_path = DATA_DIR / "bridge_manifest_oasis_block_025.json"
    state = load_json_file(STATE_PATH) if STATE_PATH.exists() else {}
    manifest = load_json_file(manifest_path) if manifest_path.exists() else {}
    event_years = sorted({parse_date_str(event.get("race_date")).year for event in (manifest.get("race_events") or []) if parse_date_str(event.get("race_date"))})
    race_year = event_years[0] if len(event_years) == 1 else event_years
    race_ids = [str(race_id) for race_id in (manifest.get("race_ids") or [])]
    runner_count = int(manifest.get("runner_count", 0) or 0)
    archive_exhausted = bool(manifest.get("archive_exhausted", state.get("archive_exhausted", False)))
    if not race_ids:
        return {
            "bridge_block": manifest.get("bridge_block", "OASIS_BLOCK_025"),
            "status": "missing_manifest_scope",
            "race_events": len(manifest.get("race_events") or []),
            "runner_rows": runner_count,
            "race_year": race_year,
            "archive_exhausted": archive_exhausted,
        }

    race_rows = load_rows_by_race_ids(sb, "races", "race_id,date", race_ids)
    race_result_rows = load_rows_by_race_ids(sb, "race_results", "race_id", race_ids)
    runner_rows = load_rows_by_race_ids(sb, "runner_results", "race_id,horse_id,is_winner", race_ids)
    hfs_rows = [
        row
        for row in load_rows_by_race_ids(
            sb,
            "historical_feature_store",
            "race_id,horse_id,race_date,feature_json,reconstruction_version",
            race_ids,
        )
        if row.get("reconstruction_version") == RECONSTRUCTION_VERSION
    ]

    if not race_rows and not race_result_rows and not runner_rows and not hfs_rows:
        return {
            "bridge_block": manifest.get("bridge_block", "OASIS_BLOCK_025"),
            "status": "rolled_back",
            "race_events": len(manifest.get("race_events") or []),
            "runner_rows": runner_count,
            "reason": "macro_year_mismatch",
            "race_year": race_year,
            "macro_layer_support": "2012-2024",
            "scorer_fallback": "2025 -> 2024",
            "archive_exhausted": archive_exhausted,
        }

    macro_mismatch_count = 0
    macro_year_used_distribution: Counter[str] = Counter()
    macro_context_version_distribution: Counter[str] = Counter()
    for row in hfs_rows:
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        macro_year = feature_json.get("macro_year_used")
        macro_year_used_distribution[str(macro_year)] += 1
        macro_context_version_distribution[str(feature_json.get("macro_context_version"))] += 1
        race_date = parse_date_str(row.get("race_date"))
        if race_date is None or macro_year != race_date.year:
            macro_mismatch_count += 1

    return {
        "bridge_block": manifest.get("bridge_block", "OASIS_BLOCK_025"),
        "status": "accepted" if len(race_result_rows) == len(race_ids) and len(runner_rows) == runner_count and len(hfs_rows) == runner_count and macro_mismatch_count == 0 else "partially_present",
        "race_events": len(manifest.get("race_events") or []),
        "runner_rows": runner_count,
        "race_year": race_year,
        "archive_exhausted": archive_exhausted,
        "remaining_rows": {
            "races": len(race_rows),
            "race_results": len(race_result_rows),
            "runner_results": len(runner_rows),
            "historical_feature_store": len(hfs_rows),
        },
        "macro_year_mismatch_count": macro_mismatch_count,
        "macro_year_used_distribution": dict(macro_year_used_distribution),
        "macro_context_version_distribution": dict(macro_context_version_distribution),
    }


def build_audit_report(version: str) -> dict[str, Any]:
    sb = get_sb_client()
    accepted_races = load_accepted_historical_races(sb)
    accepted_race_ids = [row["race_id"] for row in accepted_races]
    accepted_race_id_set = set(accepted_race_ids)
    accepted_event_keys = [row["event_key"] for row in accepted_races]

    race_results_rows = load_rows_by_race_ids(sb, "race_results", "race_id,reconciled_at", accepted_race_ids)
    runner_results_rows = load_rows_by_race_ids(sb, "runner_results", "race_id,horse_id,is_winner", accepted_race_ids)
    hfs_rows_all = paged_select(
        sb,
        "historical_feature_store",
        "race_id,horse_id,reconstruction_version,race_date,course,jurisdiction,mpi,chaos_bloom,winner_flag,story_anchor,narrative_disruption,feature_json",
        filters=[("eq", "reconstruction_version", RECONSTRUCTION_VERSION)],
    )
    accepted_hfs_rows = [row for row in hfs_rows_all if str(row.get("race_id")) in accepted_race_id_set]

    runner_pairs = {(str(row["race_id"]), str(row["horse_id"])) for row in runner_results_rows}
    hfs_pairs = {(str(row["race_id"]), str(row["horse_id"])) for row in accepted_hfs_rows}

    winners_by_race: dict[str, int] = defaultdict(int)
    for row in runner_results_rows:
        if bool(row.get("is_winner")):
            winners_by_race[str(row["race_id"])] += 1

    bad_winner_races = {
        race_id: winners_by_race.get(race_id, 0)
        for race_id in accepted_race_ids
        if winners_by_race.get(race_id, 0) != 1
    }

    vector_lengths: Counter[str] = Counter()
    vector_null_count = 0
    mpi_values: list[float] = []
    chaos_values: list[float] = []
    mpi_null_count = 0
    chaos_null_count = 0
    macro_mismatch_count = 0
    macro_year_used_distribution: Counter[str] = Counter()
    macro_context_version_distribution: Counter[str] = Counter()
    expected_historical_nulls = 0

    signal_contract_hfs = 0
    mpi_source_hfs = 0
    chaos_source_hfs = 0
    event_identity_hfs = 0
    data_owner_hfs = 0
    training_eligible_hfs = 0
    source_hfs = 0
    bridge_version_hfs = 0
    discovery_version_hfs = 0
    source_table_hfs = 0
    training_distribution: Counter[str] = Counter()

    for row in accepted_hfs_rows:
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        vector = feature_json.get("strictly_ordered_vector")
        if isinstance(vector, list):
            vector_lengths[str(len(vector))] += 1
        else:
            vector_null_count += 1
            vector_lengths["null"] += 1

        mpi_value = safe_float(row.get("mpi"))
        if mpi_value is None:
            mpi_null_count += 1
        else:
            mpi_values.append(mpi_value)

        chaos_value = safe_float(row.get("chaos_bloom"))
        if chaos_value is None:
            chaos_null_count += 1
        else:
            chaos_values.append(chaos_value)

        race_date = parse_date_str(row.get("race_date"))
        macro_year_used = feature_json.get("macro_year_used")
        macro_year_used_distribution[str(macro_year_used)] += 1
        macro_context_version_distribution[str(feature_json.get("macro_context_version"))] += 1
        if race_date is None or macro_year_used != race_date.year:
            macro_mismatch_count += 1

        signal_contract_hfs += int(feature_json.get("signal_contract_version") == SIGNAL_CONTRACT_VERSION)
        mpi_source_hfs += int(feature_json.get("mpi_source") == MPI_SOURCE)
        chaos_source_hfs += int(feature_json.get("chaos_bloom_source") == CHAOS_SOURCE)
        event_identity_hfs += int(feature_json.get("event_identity_contract") == EVENT_IDENTITY_CONTRACT)
        data_owner_hfs += int(feature_json.get("data_owner_confirmed") is True)
        training_eligible_hfs += int(feature_json.get("training_eligible") == TRAINING_ELIGIBLE)
        source_hfs += int(feature_json.get("source") == HISTORICAL_SOURCE)
        bridge_version_hfs += int(feature_json.get("bridge_version") == BRIDGE_VERSION)
        discovery_version_hfs += int(feature_json.get("discovery_version") == DISCOVERY_VERSION)
        source_table_hfs += int(feature_json.get("source_table") == "raceform")
        training_distribution[str(feature_json.get("training_eligible"))] += 1

        if feature_json.get("story_anchor") is None and feature_json.get("narrative_disruption") is None:
            expected_historical_nulls += 1

    signal_contract_races = 0
    event_identity_races = 0
    data_owner_races = 0
    training_eligible_races = 0
    source_races = 0
    bridge_version_races = 0
    discovery_version_races = 0
    source_table_races = 0
    jurisdiction_breakdown: Counter[str] = Counter()
    year_breakdown: Counter[str] = Counter()
    course_breakdown: Counter[str] = Counter()
    race_dates = []
    for row in accepted_races:
        raw = row["raw"]
        signal_contract_races += int(raw.get("signal_contract_version") == SIGNAL_CONTRACT_VERSION)
        event_identity_races += int(raw.get("event_identity_contract") == EVENT_IDENTITY_CONTRACT)
        data_owner_races += int(raw.get("data_owner_confirmed") is True)
        training_eligible_races += int(raw.get("training_eligible") == TRAINING_ELIGIBLE)
        source_races += int(raw.get("source") == HISTORICAL_SOURCE)
        bridge_version_races += int(raw.get("bridge_version") == BRIDGE_VERSION)
        discovery_version_races += int(raw.get("discovery_version") == DISCOVERY_VERSION)
        source_table_races += int(raw.get("source_table") == "raceform")
        jurisdiction_breakdown[str(raw.get("jurisdiction"))] += 1
        parsed = parse_date_str(row["race_date"])
        if parsed:
            race_dates.append(parsed.date().isoformat())
            year_breakdown[str(parsed.year)] += 1
        course_breakdown[str(row.get("course"))] += 1

    missing_hfs_rows = len(runner_pairs - hfs_pairs)
    orphan_hfs_rows = len(hfs_pairs - runner_pairs)

    summary = {
        "A_accepted_clean_race_event_count": len(accepted_races),
        "B_accepted_historical_runner_count": len(runner_results_rows),
        "C_accepted_hfs_row_count": len(accepted_hfs_rows),
        "D_race_results_runner_results_hfs_parity": {
            "accepted_race_events": len(accepted_races),
            "accepted_race_results_rows": len(race_results_rows),
            "accepted_runner_rows": len(runner_results_rows),
            "accepted_hfs_rows": len(accepted_hfs_rows),
            "runner_hfs_match": len(runner_results_rows) == len(accepted_hfs_rows),
            "missing_hfs_rows": missing_hfs_rows,
            "orphan_hfs_rows": orphan_hfs_rows,
            "race_results_match": len(race_results_rows) == len(accepted_races),
        },
        "E_winner_parity": {
            "ok": not bad_winner_races,
            "bad_race_count": len(bad_winner_races),
            "bad_races_sample": dict(list(bad_winner_races.items())[:10]),
        },
        "F_duplicate_race_id_count": count_extra_duplicates(str(row["race_id"]) for row in race_results_rows),
        "G_duplicate_event_key_count": count_extra_duplicates(accepted_event_keys),
        "H_duplicate_race_id_horse_id_count": count_extra_duplicates((str(row["race_id"]), str(row["horse_id"])) for row in runner_results_rows),
        "I_missing_hfs_rows": missing_hfs_rows,
        "J_orphan_hfs_rows": orphan_hfs_rows,
        "K_vector_dimension_distribution": dict(vector_lengths),
        "L_MPI_stats": {
            "null_count": mpi_null_count,
            "min": min(mpi_values) if mpi_values else None,
            "max": max(mpi_values) if mpi_values else None,
            "variance": variance(mpi_values),
        },
        "M_chaos_bloom_stats": {
            "null_count": chaos_null_count,
            "min": min(chaos_values) if chaos_values else None,
            "max": max(chaos_values) if chaos_values else None,
            "variance": variance(chaos_values),
        },
        "N_macro_year_mismatch_count": macro_mismatch_count,
        "O_doctrine_tag_completeness": {
            "signal_contract_version_complete_hfs": f"{signal_contract_hfs}/{len(accepted_hfs_rows)}",
            "mpi_source_complete_hfs": f"{mpi_source_hfs}/{len(accepted_hfs_rows)}",
            "chaos_bloom_source_complete_hfs": f"{chaos_source_hfs}/{len(accepted_hfs_rows)}",
            "signal_contract_version_complete_races": f"{signal_contract_races}/{len(accepted_races)}",
        },
        "P_provenance_tag_completeness": {
            "event_identity_contract_complete_hfs": f"{event_identity_hfs}/{len(accepted_hfs_rows)}",
            "data_owner_confirmed_true_hfs": f"{data_owner_hfs}/{len(accepted_hfs_rows)}",
            "training_eligible_pending_hfs": f"{training_eligible_hfs}/{len(accepted_hfs_rows)}",
            "source_historical_raceform_hfs": f"{source_hfs}/{len(accepted_hfs_rows)}",
            "bridge_version_complete_hfs": f"{bridge_version_hfs}/{len(accepted_hfs_rows)}",
            "discovery_version_complete_hfs": f"{discovery_version_hfs}/{len(accepted_hfs_rows)}",
            "source_table_complete_hfs": f"{source_table_hfs}/{len(accepted_hfs_rows)}",
            "event_identity_contract_complete_races": f"{event_identity_races}/{len(accepted_races)}",
            "data_owner_confirmed_true_races": f"{data_owner_races}/{len(accepted_races)}",
            "training_eligible_pending_races": f"{training_eligible_races}/{len(accepted_races)}",
            "source_historical_raceform_races": f"{source_races}/{len(accepted_races)}",
            "bridge_version_complete_races": f"{bridge_version_races}/{len(accepted_races)}",
            "discovery_version_complete_races": f"{discovery_version_races}/{len(accepted_races)}",
            "source_table_complete_races": f"{source_table_races}/{len(accepted_races)}",
        },
        "Q_training_eligible_distribution": dict(training_distribution),
        "R_race_date_min_max": {
            "min": min(race_dates) if race_dates else None,
            "max": max(race_dates) if race_dates else None,
        },
        "S_jurisdiction_breakdown": dict(jurisdiction_breakdown),
        "T_year_breakdown": dict(year_breakdown),
        "U_blocked_block_025_summary": load_blocked_block_025_summary(sb),
        "macro_year_used_distribution": dict(macro_year_used_distribution),
        "macro_context_version_distribution": dict(macro_context_version_distribution),
        "course_breakdown_top_50": dict(course_breakdown.most_common(50)),
        "story_anchor_narrative_null_classification": {
            "expected_historical_nulls": expected_historical_nulls
        },
    }

    decision_gate = {
        "parity_holds": summary["D_race_results_runner_results_hfs_parity"]["runner_hfs_match"]
        and summary["D_race_results_runner_results_hfs_parity"]["race_results_match"]
        and summary["I_missing_hfs_rows"] == 0
        and summary["J_orphan_hfs_rows"] == 0,
        "winner_parity_100": summary["E_winner_parity"]["ok"],
        "duplicates_zero": summary["F_duplicate_race_id_count"] == 0
        and summary["G_duplicate_event_key_count"] == 0
        and summary["H_duplicate_race_id_horse_id_count"] == 0,
        "missing_vectors_zero": vector_null_count == 0,
        "vector_length_37_only": set(vector_lengths.keys()) <= {"37"} and vector_lengths.get("37", 0) == len(accepted_hfs_rows),
        "MPI_nulls_zero": mpi_null_count == 0,
        "chaos_bloom_nulls_zero": chaos_null_count == 0,
        "MPI_variance_gt_zero": summary["L_MPI_stats"]["variance"] > 0,
        "chaos_bloom_variance_gt_zero": summary["M_chaos_bloom_stats"]["variance"] > 0,
        "macro_year_mismatch_zero": macro_mismatch_count == 0,
        "doctrine_tags_complete": signal_contract_hfs == len(accepted_hfs_rows)
        and mpi_source_hfs == len(accepted_hfs_rows)
        and chaos_source_hfs == len(accepted_hfs_rows)
        and signal_contract_races == len(accepted_races),
        "provenance_tags_complete": event_identity_hfs == len(accepted_hfs_rows)
        and data_owner_hfs == len(accepted_hfs_rows)
        and training_eligible_hfs == len(accepted_hfs_rows)
        and source_hfs == len(accepted_hfs_rows)
        and bridge_version_hfs == len(accepted_hfs_rows)
        and discovery_version_hfs == len(accepted_hfs_rows)
        and event_identity_races == len(accepted_races)
        and data_owner_races == len(accepted_races)
        and training_eligible_races == len(accepted_races)
        and source_races == len(accepted_races)
        and bridge_version_races == len(accepted_races)
        and discovery_version_races == len(accepted_races),
        "training_eligible_pending_only": set(training_distribution.keys()) == {TRAINING_ELIGIBLE},
    }
    decision_gate["pass"] = all(decision_gate.values())

    return {
        "audit_version": version,
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": {
            "source": HISTORICAL_SOURCE,
            "is_historical_backfill": True,
            "reconstruction_version": RECONSTRUCTION_VERSION,
            "accepted_year_range": f"{MIN_ACCEPTED_YEAR}-{MAX_ACCEPTED_YEAR}",
        },
        "summary": summary,
        "decision_gate": decision_gate,
        "samples": {
            "clean_event_keys_sample": accepted_event_keys[:50],
        },
    }


def build_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    gate = report["decision_gate"]
    blocked = summary["U_blocked_block_025_summary"]
    return "\n".join(
        [
            f"**Global Clean Spine Audit {report['audit_version']}**",
            "",
            f"- generated_at: `{report['generated_at']}`",
            f"- source: `{report['scope']['source']}`",
            f"- accepted race events: `{summary['A_accepted_clean_race_event_count']}`",
            f"- accepted runner rows: `{summary['B_accepted_historical_runner_count']}`",
            f"- accepted HFS rows: `{summary['C_accepted_hfs_row_count']}`",
            f"- parity: `{'pass' if summary['D_race_results_runner_results_hfs_parity']['runner_hfs_match'] and summary['D_race_results_runner_results_hfs_parity']['race_results_match'] else 'fail'}`",
            f"- winner parity: `{'100%' if summary['E_winner_parity']['ok'] else 'fail'}`",
            f"- duplicate race_id count: `{summary['F_duplicate_race_id_count']}`",
            f"- duplicate event_key count: `{summary['G_duplicate_event_key_count']}`",
            f"- duplicate race_id + horse_id count: `{summary['H_duplicate_race_id_horse_id_count']}`",
            f"- missing HFS rows: `{summary['I_missing_hfs_rows']}`",
            f"- orphan HFS rows: `{summary['J_orphan_hfs_rows']}`",
            f"- vector distribution: `{json.dumps(summary['K_vector_dimension_distribution'], sort_keys=True)}`",
            f"- MPI stats: `{json.dumps(summary['L_MPI_stats'], sort_keys=True)}`",
            f"- chaos_bloom stats: `{json.dumps(summary['M_chaos_bloom_stats'], sort_keys=True)}`",
            f"- macro-year mismatch count: `{summary['N_macro_year_mismatch_count']}`",
            f"- doctrine completeness: `{json.dumps(summary['O_doctrine_tag_completeness'], sort_keys=True)}`",
            f"- provenance completeness: `{json.dumps(summary['P_provenance_tag_completeness'], sort_keys=True)}`",
            f"- training_eligible distribution: `{json.dumps(summary['Q_training_eligible_distribution'], sort_keys=True)}`",
            f"- race_date range: `{summary['R_race_date_min_max']['min']} -> {summary['R_race_date_min_max']['max']}`",
            f"- jurisdiction breakdown: `{json.dumps(summary['S_jurisdiction_breakdown'], sort_keys=True)}`",
            f"- year breakdown: `{json.dumps(summary['T_year_breakdown'], sort_keys=True)}`",
            f"- blocked Block 025: `{json.dumps(blocked, sort_keys=True)}`",
            f"- decision gate pass: `{gate['pass']}`",
            "",
            "**Sample Event Keys**",
            "",
            *[f"- `{event_key}`" for event_key in report["samples"]["clean_event_keys_sample"][:20]],
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Global clean spine audit for accepted historical OASIS rows.")
    parser.add_argument("--output-version", default="v3")
    parser.add_argument("--write-artifacts", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_audit_report(args.output_version)
    markdown = build_markdown(report)

    if args.write_artifacts and not args.dry_run:
        json_path = DATA_DIR / f"global_clean_spine_audit_{args.output_version}.json"
        md_path = DATA_DIR / f"global_clean_spine_audit_{args.output_version}.md"
        write_json_file(json_path, report)
        md_path.write_text(markdown, encoding="utf-8")
        print(f"Wrote {json_path}")
        print(f"Wrote {md_path}")

    print(json.dumps({"audit_version": args.output_version, "decision_gate": report["decision_gate"], "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
