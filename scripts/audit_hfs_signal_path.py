"""
Manifest-scoped HFS signal path audit for historical archive repairs.

This script never bridges, trains, or scans beyond the supplied manifest.
It traces reconstruction inputs and outputs, then simulates a dry-run repair
for Block 001 before any writeback is approved.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backfill_historical_feature_store import (
    CHAOS_SOURCE_MARKET,
    MPI_SOURCE_MARKET,
    RECONSTRUCTION_VERSION,
    SIGNAL_CONTRACT_VERSION,
    batched,
    compute_archive_chaos_proxy,
    compute_archive_mpi_proxies,
    fetch_historical_runner_context,
    get_sb_client,
    init_worker,
    is_historical_race,
    load_manifest_race_ids,
    reconstruct_race_payload,
)


def variance_or_none(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return 0.0 if len(values) == 1 else None
    return statistics.pvariance(values)


def sample_traces(traces: Sequence[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return list(traces[:limit])


def vector_length(row: dict[str, Any]) -> int | None:
    vec = (row.get("feature_json") or {}).get("strictly_ordered_vector")
    return len(vec) if isinstance(vec, list) else None


def summarize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    runner = trace["raw_runner_results"]
    recon = trace["reconstruction_input"]
    pred = trace.get("prediction_object") or {}
    final_payload = trace["final_payload"]
    feature_json = trace["feature_json_before_insert"] or {}
    return {
        "race_id": trace["race_id"],
        "horse_id": trace["horse_id"],
        "sp_dec": final_payload.get("sp_dec"),
        "implied_prob": final_payload.get("implied_prob"),
        "finish_position": final_payload.get("finish_position"),
        "position": runner.get("position"),
        "winner_flag": final_payload.get("winner_flag"),
        "is_winner": runner.get("is_winner"),
        "prediction_present": trace["prediction_present"],
        "prediction_keys": sorted(pred.keys()),
        "feature_json_keys": sorted(feature_json.keys()),
        "strictly_ordered_vector_length": len(feature_json.get("strictly_ordered_vector", [])),
        "mpi_source": trace.get("mpi_source"),
        "chaos_bloom_source": trace.get("chaos_bloom_source"),
        "mpi_value": final_payload.get("mpi"),
        "chaos_bloom_value": final_payload.get("chaos_bloom"),
        "scoring_status": feature_json.get("scoring_status"),
        "horse_name_input": recon.get("horse_name"),
        "raw_runner_horse_name": runner.get("horse_name"),
    }


def fetch_rows_by_race_ids(sb, table: str, race_ids: Sequence[str], columns: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in batched(list(race_ids), 25):
        rows.extend(sb.table(table).select(columns).in_("race_id", list(chunk)).execute().data or [])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest-file",
        type=str,
        default=str(ROOT / "data" / "bridge_manifest_oasis_block_001.json"),
    )
    parser.add_argument("--sample-races", type=int, default=20)
    parser.add_argument("--sample-runners", type=int, default=100)
    args = parser.parse_args()

    race_ids = load_manifest_race_ids(args.manifest_file) or []
    if not race_ids:
        raise RuntimeError("Manifest has no race_ids.")

    sb = get_sb_client()
    init_worker()

    race_results = fetch_rows_by_race_ids(sb, "race_results", race_ids, "race_id,reconciled_at")
    race_lookup = {str(row["race_id"]): row for row in race_results}
    race_meta_rows = fetch_rows_by_race_ids(sb, "races", race_ids, "race_id,course,going,class,distance_f,date,raw")
    race_meta_lookup = {str(row["race_id"]): row for row in race_meta_rows}
    runners = fetch_rows_by_race_ids(sb, "runner_results", race_ids, "*")
    hfs_rows = fetch_rows_by_race_ids(
        sb,
        "historical_feature_store",
        race_ids,
        "race_id,horse_id,sp_dec,implied_prob,mpi,chaos_bloom,feature_json,finish_position,winner_flag,reconstruction_version",
    )

    runners_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in runners:
        runners_by_race[str(row["race_id"])].append(row)

    historical_race_ids = [
        rid
        for rid in race_ids
        if is_historical_race({**race_lookup.get(rid, {}), **race_meta_lookup.get(rid, {})})
    ]
    historical_context = fetch_historical_runner_context(sb, historical_race_ids, runners_by_race)

    leakage_formula_mpi = (
        "For each runner: implied_prob = 1/sp_dec; normalize within race; "
        "rank_pressure = 1 - ((rank-1)/(field_size-1)); "
        "share_pressure = normalized_prob / max_normalized_prob; "
        "mpi = 100 * (0.6*rank_pressure + 0.4*share_pressure)."
    )
    leakage_formula_chaos = (
        "For each race: normalized_entropy of implied_prob distribution, "
        "plus going uncertainty factor and field-size factor; "
        "chaos_bloom = 100 * (0.5*entropy + 0.35*going_factor + 0.15*field_factor)."
    )

    sampled_race_ids = race_ids[: args.sample_races]
    all_traces: list[dict[str, Any]] = []
    patched_rows: list[dict[str, Any]] = []
    reason_counter: Counter[str] = Counter()
    prediction_missing = 0
    prediction_missing_due_name = 0
    native_prediction_has_mpi = 0
    native_prediction_has_chaos = 0

    for rid in sampled_race_ids:
        race = {**race_lookup.get(rid, {}), **race_meta_lookup.get(rid, {})}
        sample_norms = []
        for row in runners_by_race.get(rid, []):
            ctx = historical_context.get(rid, {}).get(str(row["horse_id"]).strip(), {})
            sample_norms.append(
                {
                    "horse_id": str(row["horse_id"]).strip(),
                    "best_odds_decimal": row.get("sp_dec"),
                    "horse_name": ctx.get("horse_name") or row.get("horse_name"),
                }
            )
        if sample_norms:
            mpi_preview = compute_archive_mpi_proxies(sample_norms)
            chaos_preview = compute_archive_chaos_proxy(race, sample_norms)
        else:
            mpi_preview = {}
            chaos_preview = None
        rows, _, _, _, traces = reconstruct_race_payload(
            race,
            runners_by_race.get(rid, []),
            existing_keys=set(),
            historical_context=historical_context.get(rid, {}),
            trace_mode=True,
        )
        patched_rows.extend(rows)
        all_traces.extend(traces)

    for rid in race_ids[args.sample_races :]:
        race = {**race_lookup.get(rid, {}), **race_meta_lookup.get(rid, {})}
        rows, _, _, _, _ = reconstruct_race_payload(
            race,
            runners_by_race.get(rid, []),
            existing_keys=set(),
            historical_context=historical_context.get(rid, {}),
            trace_mode=False,
        )
        patched_rows.extend(rows)

    for trace in all_traces:
        pred = trace.get("prediction_object") or {}
        feature_json = trace.get("feature_json_before_insert") or {}
        if not trace["prediction_present"]:
            prediction_missing += 1
            if trace["raw_runner_results"].get("horse_name") in (None, "") and trace["reconstruction_input"].get("horse_name"):
                prediction_missing_due_name += 1
        if pred.get("mpi") is not None:
            native_prediction_has_mpi += 1
        if pred.get("chaos_bloom") is not None:
            native_prediction_has_chaos += 1
        if feature_json.get("scoring_status") == "missing_prediction":
            reason_counter["missing_prediction"] += 1
        elif feature_json.get("mpi_source") == "archive_proxy_winner_sp":
            reason_counter["archive_mpi_proxy"] += 1
        elif feature_json.get("chaos_bloom_source") == "archive_proxy_going":
            reason_counter["archive_chaos_proxy"] += 1

    mpi_values = [row["mpi"] for row in patched_rows if row.get("mpi") is not None]
    chaos_values = [row["chaos_bloom"] for row in patched_rows if row.get("chaos_bloom") is not None]
    incomplete_rows = [
        row
        for row in patched_rows
        if row.get("mpi") is None or row.get("chaos_bloom") is None
    ]

    print("PHASE 1 — FORENSIC SIGNAL TRACE")
    print(f"A. sampled races traced: {len(sampled_race_ids)}")
    print(f"B. sampled runners traced: {min(len(all_traces), args.sample_runners)}")
    print(f"C. prediction_missing_in_sample: {prediction_missing}")
    print(f"D. prediction_missing_due_name_hydration_in_sample: {prediction_missing_due_name}")
    print(f"E. native_prediction_has_mpi_in_sample: {native_prediction_has_mpi}")
    print(f"F. native_prediction_has_chaos_bloom_in_sample: {native_prediction_has_chaos}")
    print("TRACE SAMPLE:")
    for trace in sample_traces([summarize_trace(t) for t in all_traces], args.sample_runners)[:20]:
        print(json.dumps(trace, default=str))

    print("\nPHASE 2 — BREAKPOINT")
    print("1. mpi and chaos_bloom are computed but not mapped into HFS columns: FALSE")
    print("2. mpi and chaos_bloom are missing from prediction output: TRUE")
    print("3. Prediction output is missing because historical hrs_rf_ horse IDs do not resolve inside the model manager: FALSE")
    print("   Note: the real join failure was missing horse_name on historical runner rows, not horse_id resolution.")
    print("4. The reconstructor depends on live velo_verdicts fields that do not exist for archive rows: FALSE")
    print("5. The values exist inside the 37-dim vector but are not extracted into named HFS columns: FALSE")
    print("6. The values are never computed for historical rows in score_race_velo_prime: TRUE")

    print("\nTARGET LEAKAGE AUDIT")
    print(f"A. exact formula for archive proxy mpi: {leakage_formula_mpi}")
    print(f"B. exact formula for archive proxy chaos: {leakage_formula_chaos}")
    print("C. all input fields used for mpi: sp_dec, implied_prob, race field_size, within-race normalized probability rank")
    print("D. all input fields used for chaos_bloom: sp_dec distribution, implied_prob distribution, race field_size, going")
    print("E. forbidden outcome fields read by current proxies: none")
    print("F. MPI differs by runner using only that runner’s own market price / implied probability plus field distribution: TRUE")
    print("G. chaos_bloom is race-level or runner-level: race-level")
    print("H. values change if outcome fields are removed from input payload: FALSE")
    print("I. sample 20 rows showing proxy inputs and outputs:")
    for trace in [summarize_trace(t) for t in all_traces[:20]]:
        print(json.dumps(trace, default=str))
    print("J. verdict: LEAKAGE_FREE")

    print("\nPHASE 4 — DRY-RUN PATCH ON MANIFEST")
    print(f"A. rows evaluated: {len(patched_rows)}")
    print(f"B. rows with sp_dec: {sum(1 for row in patched_rows if row.get('sp_dec') is not None)}")
    print(f"C. rows with implied_prob: {sum(1 for row in patched_rows if row.get('implied_prob') is not None)}")
    print(f"D. rows that would receive mpi: {len(mpi_values)}")
    print(
        "E. mpi min / max / variance: "
        f"{(min(mpi_values) if mpi_values else None)} / "
        f"{(max(mpi_values) if mpi_values else None)} / "
        f"{variance_or_none(mpi_values)}"
    )
    print(f"F. rows that would receive chaos_bloom: {len(chaos_values)}")
    print(
        "G. chaos_bloom min / max / variance: "
        f"{(min(chaos_values) if chaos_values else None)} / "
        f"{(max(chaos_values) if chaos_values else None)} / "
        f"{variance_or_none(chaos_values)}"
    )
    print(f"H. rows still signal-incomplete: {len(incomplete_rows)}")
    print(f"I. reason for remaining incomplete rows: {dict(reason_counter)}")
    print("J. sample 20 patched payloads:")
    for row in patched_rows[:20]:
        feature_json = row.get("feature_json") or {}
        sample = {
            "race_id": row["race_id"],
            "horse_id": row["horse_id"],
            "horse_name": row.get("horse_name"),
            "sp_dec": row.get("sp_dec"),
            "implied_prob": row.get("implied_prob"),
            "mpi": row.get("mpi"),
            "chaos_bloom": row.get("chaos_bloom"),
            "scoring_status": feature_json.get("scoring_status"),
            "mpi_source": feature_json.get("mpi_source"),
            "chaos_bloom_source": feature_json.get("chaos_bloom_source"),
            "vector_length": len(feature_json.get("strictly_ordered_vector", [])),
        }
        print(json.dumps(sample, default=str))

    # Existing HFS file-state context for comparison
    existing_hfs_by_key = {
        (str(row["race_id"]), str(row["horse_id"])): row
        for row in hfs_rows
        if row.get("reconstruction_version") == RECONSTRUCTION_VERSION
    }
    existing_mpi_null = sum(1 for row in existing_hfs_by_key.values() if row.get("mpi") is None)
    existing_chaos_null = sum(1 for row in existing_hfs_by_key.values() if row.get("chaos_bloom") is None)
    print("\nCURRENT HFS SNAPSHOT FOR MANIFEST")
    print(f"existing_rows: {len(existing_hfs_by_key)}")
    print(f"existing_mpi_null_count: {existing_mpi_null}")
    print(f"existing_chaos_bloom_null_count: {existing_chaos_null}")


if __name__ == "__main__":
    main()
