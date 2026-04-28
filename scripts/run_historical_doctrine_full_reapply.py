from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.historical_doctrine_support import HISTORICAL_DOCTRINE_CONTRACT
    from scripts.run_historical_doctrine_activation_smoke import (
        FEATURE_INDEX,
        FEATURE_VECTOR_NAMES,
        build_after_row,
        clean_name,
        doctrine_defaults_count,
        fetch_raceform_current_rows,
        fetch_runner_results,
        get_sb_client,
        leakage_audit,
        outcome_exclusion_audit,
        parse_date_key,
        safe_float,
        vector_length_distribution,
        vector_dist_stats,
    )
    from scripts.run_historical_doctrine_full_reapply_dry_run import (
        accepted_events,
        accepted_rows,
        build_accepted_prior_sources,
        doctrine_variance,
        recommended_batches,
    )
except ModuleNotFoundError:
    from historical_doctrine_support import HISTORICAL_DOCTRINE_CONTRACT
    from run_historical_doctrine_activation_smoke import (
        FEATURE_INDEX,
        FEATURE_VECTOR_NAMES,
        build_after_row,
        clean_name,
        doctrine_defaults_count,
        fetch_raceform_current_rows,
        fetch_runner_results,
        get_sb_client,
        leakage_audit,
        outcome_exclusion_audit,
        parse_date_key,
        safe_float,
        vector_length_distribution,
        vector_dist_stats,
    )
    from run_historical_doctrine_full_reapply_dry_run import (
        accepted_events,
        accepted_rows,
        build_accepted_prior_sources,
        doctrine_variance,
        recommended_batches,
    )

DATA_DIR = ROOT / "data"
JSON_OUT = DATA_DIR / "historical_doctrine_full_reapply_v1.json"
MD_OUT = DATA_DIR / "historical_doctrine_full_reapply_v1.md"


def total_hfs_row_count(sb) -> int:
    rows = (
        sb.table("historical_feature_store")
        .select("id", count="exact", head=True)
        .execute()
    )
    return int(rows.count or 0)


def event_batches(events: list[dict[str, Any]], target_event_batch_size: int = 100) -> list[list[dict[str, Any]]]:
    return [events[idx : idx + target_event_batch_size] for idx in range(0, len(events), target_event_batch_size)]


def build_after_rows(
    before_rows: list[dict[str, Any]],
    current_rows_by_race: dict[str, dict[str, dict[str, Any]]],
    horse_history_by_row: dict[tuple[str, str], list[dict[str, Any]]],
    trainer_history_by_name: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    after_rows: list[dict[str, Any]] = []
    for row in before_rows:
        current_source = current_rows_by_race.get(str(row["race_id"]), {}).get(clean_name(row.get("horse_name")))
        trainer_rows = trainer_history_by_name.get(str(current_source.get("trainer")), []) if current_source and current_source.get("trainer") else []
        after_rows.append(
            build_after_row(
                row,
                current_source=current_source,
                horse_history_rows=horse_history_by_row.get((str(row["race_id"]), str(row["horse_id"])), []),
                trainer_history_rows=trainer_rows,
            )
        )
    return after_rows


def build_event_key_dup_count(rows: list[dict[str, Any]]) -> int:
    event_map: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        event_key = str(feature_json.get("event_key") or "")
        if event_key:
            event_map[event_key].add(str(row.get("race_id")))
    return sum(1 for race_ids in event_map.values() if len(race_ids) > 1)


def build_post_write_metrics(
    after_rows: list[dict[str, Any]],
    runner_results: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    duplicate_pairs = len(after_rows) - len({(str(row["race_id"]), str(row["horse_id"])) for row in after_rows})
    mpi_null_count = 0
    chaos_null_count = 0
    macro_mismatch = 0
    winner_parity_unchanged = True
    doctrine_contract_missing = 0
    for row in after_rows:
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        race_year = parse_date_key(row.get("race_date"))[:4]
        if race_year.isdigit() and feature_json.get("macro_year_used") != int(race_year):
            macro_mismatch += 1
        mpi_null_count += int(safe_float(row.get("mpi")) is None)
        chaos_null_count += int(safe_float(row.get("chaos_bloom")) is None)
        doctrine_contract_missing += int(feature_json.get("historical_doctrine_contract") != HISTORICAL_DOCTRINE_CONTRACT)
        rr = runner_results.get((str(row["race_id"]), str(row["horse_id"])))
        if rr is not None and bool(rr.get("is_winner")) != bool(row.get("winner_flag")):
            winner_parity_unchanged = False
    return {
        "winner_parity_unchanged": winner_parity_unchanged,
        "duplicate_race_id_horse_id_count": duplicate_pairs,
        "duplicate_event_key_count": build_event_key_dup_count(after_rows),
        "mpi_null_count": mpi_null_count,
        "chaos_bloom_null_count": chaos_null_count,
        "macro_year_mismatch_count": macro_mismatch,
        "vector_dimension_distribution": vector_length_distribution(after_rows),
        "doctrine_contract_missing_count": doctrine_contract_missing,
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Historical Doctrine Full Reapply V1",
        "",
        f"- Rows evaluated: `{report['A_rows_evaluated']}`",
        f"- Rows updated: `{report['B_rows_updated']}`",
        f"- HFS before/after: `{report['C_hfs_before_after']}`",
        f"- Event count touched: `{report['D_event_count_touched']}`",
        f"- Runner count touched: `{report['E_runner_count_touched']}`",
        f"- Batch count: `{report['F_batch_count']}`",
        f"- Failures: `{report['G_failures']}`",
        f"- dist_f before/after: `{json.dumps(report['H_dist_f_before_after'])}`",
        f"- Leakage count: `{report['K_future_same_day_leakage_count']}`",
        f"- Outcome exclusion: `{report['L_outcome_field_exclusion_result']['status']}`",
        f"- Winner parity unchanged: `{report['M_winner_parity_unchanged']}`",
        f"- Duplicate event_key count: `{report['N_duplicate_event_key_count']}`",
        f"- Duplicate race_id+horse_id count: `{report['O_duplicate_race_id_horse_id_count']}`",
        f"- MPI / chaos nulls: `{report['P_mpi_null_count']} / {report['Q_chaos_bloom_null_count']}`",
        f"- Macro-year mismatch count: `{report['R_macro_year_mismatch_count']}`",
        f"- Vector dimensions: `{json.dumps(report['S_vector_dimension_distribution'])}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    sb = get_sb_client()
    hfs_before_total = total_hfs_row_count(sb)
    before_rows = accepted_rows(sb)
    eligible_row_count = len(before_rows)
    events = accepted_events(before_rows)
    current_rows_by_race = fetch_raceform_current_rows(sb, events)
    horse_history_by_row, trainer_history_by_name = build_accepted_prior_sources(before_rows, current_rows_by_race)
    after_rows = build_after_rows(before_rows, current_rows_by_race, horse_history_by_row, trainer_history_by_name)
    runner_results = fetch_runner_results(sb, [str(event["race_id"]) for event in events])

    preflight = {
        "A_hfs_row_count_before": hfs_before_total,
        "B_eligible_row_count": eligible_row_count,
        "C_expected_rows_to_update": eligible_row_count,
        "D_same_day_future_leakage_count": leakage_audit(after_rows)["same_day_or_future_history_rows_used"],
        "E_outcome_field_exclusion": outcome_exclusion_audit(),
        "F_vector_length_distribution": vector_length_distribution(after_rows),
    }

    failures: list[dict[str, Any]] = []
    batch_groups = event_batches(events, target_event_batch_size=100)
    rows_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in after_rows:
        rows_by_race[str(row["race_id"])].append(row)

    updated_rows = 0
    for batch_index, batch_events in enumerate(batch_groups, start=1):
        batch_rows: list[dict[str, Any]] = []
        for event in batch_events:
            batch_rows.extend(rows_by_race[str(event["race_id"])])
        payloads = []
        for row in batch_rows:
            payload = dict(row)
            payload.pop("id", None)
            payload.pop("created_at", None)
            payload.pop("updated_at", None)
            payloads.append(payload)
        try:
            for idx in range(0, len(payloads), 1000):
                sb.table("historical_feature_store").upsert(
                    payloads[idx : idx + 1000],
                    on_conflict="race_id,horse_id,reconstruction_version",
                ).execute()
            updated_rows += len(payloads)
        except Exception as exc:  # pragma: no cover - operational guard
            failures.append(
                {
                    "batch_index": batch_index,
                    "race_ids": [str(event["race_id"]) for event in batch_events],
                    "error": str(exc),
                }
            )

    after_rows_written = accepted_rows(sb)
    hfs_after_total = total_hfs_row_count(sb)
    metrics = build_post_write_metrics(after_rows_written, runner_results)
    report = {
        "preflight": preflight,
        "A_rows_evaluated": len(after_rows),
        "B_rows_updated": updated_rows,
        "C_hfs_before_after": {"before_total": hfs_before_total, "after_total": hfs_after_total},
        "D_event_count_touched": len(events),
        "E_runner_count_touched": len(after_rows),
        "F_batch_count": len(batch_groups),
        "G_failures": failures,
        "H_dist_f_before_after": {
            "before": vector_dist_stats(before_rows),
            "after": vector_dist_stats(after_rows_written),
        },
        "I_doctrine_default_counts_before_after": {
            "before": doctrine_defaults_count(before_rows, after=False),
            "after": doctrine_defaults_count(after_rows_written, after=True),
        },
        "J_variance_for_all_18_doctrine_dimensions": doctrine_variance(after_rows_written),
        "K_future_same_day_leakage_count": leakage_audit(after_rows)["same_day_or_future_history_rows_used"],
        "L_outcome_field_exclusion_result": outcome_exclusion_audit(),
        "M_winner_parity_unchanged": metrics["winner_parity_unchanged"],
        "N_duplicate_event_key_count": metrics["duplicate_event_key_count"],
        "O_duplicate_race_id_horse_id_count": metrics["duplicate_race_id_horse_id_count"],
        "P_mpi_null_count": metrics["mpi_null_count"],
        "Q_chaos_bloom_null_count": metrics["chaos_bloom_null_count"],
        "R_macro_year_mismatch_count": metrics["macro_year_mismatch_count"],
        "S_vector_dimension_distribution": metrics["vector_dimension_distribution"],
        "historical_doctrine_contract_missing_count": metrics["doctrine_contract_missing_count"],
        "recommended_batches": recommended_batches(len(events), len(after_rows)),
    }
    JSON_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    MD_OUT.write_text(build_markdown(report), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
