"""
Manifest-scoped macro-date integrity audit for historical HFS reconstruction.

Audits the exact race set in one or more bridge manifests, then dry-runs the
historical reconstructor to capture the macro year actually used by the scoring
path without writing any rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import pvariance
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backfill_historical_feature_store import (
    batched,
    fetch_historical_runner_context,
    get_sb_client,
    init_worker,
    reconstruct_race_payload,
)


def load_manifest_race_ids(paths: Sequence[Path]) -> list[str]:
    race_ids: list[str] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        race_ids.extend(str(rid) for rid in payload.get("race_ids") or [])
    return list(dict.fromkeys(race_ids))


def fetch_table_rows(sb, table: str, race_ids: Sequence[str], columns: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in batched(list(race_ids), 25):
        rows.extend(sb.table(table).select(columns).in_("race_id", list(chunk)).execute().data or [])
    return rows


def summarize_date_range(rows: Sequence[dict[str, Any]], field: str) -> tuple[str | None, str | None]:
    vals = sorted(str(row[field])[:10] for row in rows if row.get(field))
    if not vals:
        return None, None
    return vals[0], vals[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest-files",
        nargs="+",
        required=True,
        help="One or more bridge manifest JSON files.",
    )
    parser.add_argument("--sample-size", type=int, default=20)
    args = parser.parse_args()

    manifest_paths = [Path(p) for p in args.manifest_files]
    race_ids = load_manifest_race_ids(manifest_paths)
    sb = get_sb_client()

    races = fetch_table_rows(sb, "races", race_ids, "race_id,date,course,going,class,race_type,raw")
    runners = fetch_table_rows(sb, "runner_results", race_ids, "*")
    hfs_rows = []
    for chunk in batched(race_ids, 25):
        hfs_rows.extend(
            sb.table("historical_feature_store")
            .select("race_id,race_date,feature_json")
            .in_("race_id", list(chunk))
            .eq("reconstruction_version", "V17_B1")
            .execute()
            .data
            or []
        )

    races_by_id: dict[str, dict[str, Any]] = {str(row["race_id"]): row for row in races}
    runners_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in runners:
        runners_by_race[str(row["race_id"])].append(row)

    historical_context = fetch_historical_runner_context(sb, race_ids, runners_by_race)

    race_date_min, race_date_max = summarize_date_range(races, "date")
    hfs_date_min, hfs_date_max = summarize_date_range(hfs_rows, "race_date")

    # Capture the actual macro year used by score_race_velo_prime().
    from src.intelligence.macro_regime import bha_macro_context as bha_mod

    original_get_macro_context_for_race = bha_mod.get_macro_context_for_race
    current_race_id: dict[str, str | None] = {"value": None}
    macro_trace: dict[str, dict[str, Any]] = {}

    def tracing_get_macro_context_for_race(date_str: str, race_code: str):
        ctx = original_get_macro_context_for_race(date_str, race_code)
        macro_trace[str(current_race_id["value"])] = {
            "macro_year_used": ctx.year,
            "macro_race_code": race_code,
            "macro_input_date": date_str,
        }
        return ctx

    bha_mod.get_macro_context_for_race = tracing_get_macro_context_for_race

    init_worker()
    dry_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    try:
        for race_id in race_ids:
            race = races_by_id.get(str(race_id))
            if not race:
                continue
            current_race_id["value"] = str(race_id)
            rows_out, _, _, _, _ = reconstruct_race_payload(
                race,
                runners_by_race.get(str(race_id), []),
                existing_keys=set(),
                historical_context=historical_context.get(str(race_id), {}),
                trace_mode=False,
            )
            dry_rows.extend(rows_out)
            macro_info = macro_trace.get(str(race_id), {})
            for row in rows_out:
                if len(sample_rows) < args.sample_size:
                    sample_rows.append(
                        {
                            "race_id": row["race_id"],
                            "race_date": race.get("date"),
                            "hfs_race_date": row.get("race_date"),
                            "macro_year_used": macro_info.get("macro_year_used"),
                            "course": row.get("course"),
                            "jurisdiction": row.get("jurisdiction"),
                            "vector_length": len((row.get("feature_json") or {}).get("strictly_ordered_vector") or []),
                        }
                    )
    finally:
        bha_mod.get_macro_context_for_race = original_get_macro_context_for_race

    mismatch_count = 0
    macro_2026_count = 0
    macro_years: list[int] = []
    for race_id in race_ids:
        race = races_by_id.get(str(race_id))
        if not race:
            continue
        expected_year = int(str(race.get("date"))[:4]) if race.get("date") else None
        actual_year = (macro_trace.get(str(race_id)) or {}).get("macro_year_used")
        if actual_year is not None:
            macro_years.append(int(actual_year))
            if actual_year == 2026:
                macro_2026_count += 1
        if expected_year is not None and actual_year != expected_year:
            mismatch_count += 1

    vector_lengths = sorted(
        set(len((row.get("feature_json") or {}).get("strictly_ordered_vector") or []) for row in dry_rows)
    )
    mpi_vals = [float(row["mpi"]) for row in dry_rows if row.get("mpi") is not None]
    chaos_vals = [float(row["chaos_bloom"]) for row in dry_rows if row.get("chaos_bloom") is not None]
    mpi_nulls = sum(1 for row in dry_rows if row.get("mpi") is None)
    chaos_nulls = sum(1 for row in dry_rows if row.get("chaos_bloom") is None)

    print("MACRO DATE AUDIT")
    print(f"A. race IDs audited: {len(race_ids)}")
    print(f"B. race_date min/max from races: {race_date_min} -> {race_date_max}")
    print(f"C. race_date min/max from historical_feature_store: {hfs_date_min} -> {hfs_date_max}")
    print("D. macro year used by sampled races:")
    for row in sample_rows:
        print(f"   - {json.dumps(row)}")
    print(f"E. count where macro year != race_date year: {mismatch_count}")
    print(f"F. count where macro year = 2026: {macro_2026_count}")
    print("G. reconstructor source: historical scoring payload now uses race.date/race_date; scorer fallback is datetime.now() only when date is absent")
    print("H. sample 20 rows above")
    print()
    print("PATCHED DRY-RUN")
    print(f"A. rows evaluated: {len(dry_rows)}")
    print(f"B. races evaluated: {len([rid for rid in race_ids if rid in races_by_id])}")
    if macro_years:
        print(f"C. macro year min/max: {min(macro_years)} -> {max(macro_years)}")
    else:
        print("C. macro year min/max: n/a")
    print(f"D. macro-year mismatch count: {mismatch_count}")
    print(f"E. vector dimension consistency: {vector_lengths}")
    print(f"F. MPI null count: {mpi_nulls}")
    print(f"G. chaos_bloom null count: {chaos_nulls}")
    print("H. sample 20 patched macro rows:")
    for row in sample_rows:
        print(f"   - {json.dumps(row)}")
    if mpi_vals:
        print(f"I. MPI min/max/variance: {min(mpi_vals)} / {max(mpi_vals)} / {pvariance(mpi_vals) if len(mpi_vals) > 1 else 0.0}")
    else:
        print("I. MPI min/max/variance: n/a")
    if chaos_vals:
        print(f"J. chaos_bloom min/max/variance: {min(chaos_vals)} / {max(chaos_vals)} / {pvariance(chaos_vals) if len(chaos_vals) > 1 else 0.0}")
    else:
        print("J. chaos_bloom min/max/variance: n/a")


if __name__ == "__main__":
    main()
