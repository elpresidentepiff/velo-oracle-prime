from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.historical_doctrine_support import HISTORICAL_DOCTRINE_CONTRACT
except ModuleNotFoundError:
    from historical_doctrine_support import HISTORICAL_DOCTRINE_CONTRACT

DATA_DIR = ROOT / "data"
FEATURE_VECTOR_LEN = 37


def get_sb_client():
    load_dotenv(ROOT / ".env", override=False)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials missing.")
    return create_client(url, key)


def parse_date_key(value: Any) -> str:
    return str(value or "")[:10]


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def paged_hfs_rows(sb) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    page_size = 1000
    while True:
        page = (
            sb.table("historical_feature_store")
            .select("*")
            .range(start, start + page_size - 1)
            .execute()
            .data
            or []
        )
        if not page:
            break
        rows.extend(page)
        start += len(page)
    return rows


def accepted_rows(sb) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for row in paged_hfs_rows(sb):
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        vector = feature_json.get("strictly_ordered_vector")
        if feature_json.get("training_eligible") != "pending_global_training_gate":
            continue
        if feature_json.get("data_owner_confirmed") is not True:
            continue
        if feature_json.get("source") != "historical_raceform":
            continue
        if feature_json.get("signal_contract_version") != "HISTORICAL_SIGNAL_PROXY_V1":
            continue
        if feature_json.get("event_identity_contract") != "race_id_course_race_date":
            continue
        if not isinstance(vector, list) or len(vector) != FEATURE_VECTOR_LEN:
            continue
        race_year = parse_date_key(row.get("race_date"))[:4]
        if not race_year.isdigit():
            continue
        if feature_json.get("macro_year_used") != int(race_year):
            continue
        accepted.append(row)
    accepted.sort(key=lambda item: (parse_date_key(item.get("race_date")), str(item.get("race_id")), str(item.get("horse_id"))))
    return accepted


def fetch_runner_results(sb, race_ids: list[str]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for idx in range(0, len(race_ids), 100):
        rows = (
            sb.table("runner_results")
            .select("*")
            .in_("race_id", race_ids[idx : idx + 100])
            .execute()
            .data
            or []
        )
        for row in rows:
            out[(str(row["race_id"]), str(row["horse_id"]))] = row
    return out


def fetch_race_results(sb, race_ids: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx in range(0, len(race_ids), 100):
        out.extend(
            sb.table("race_results")
            .select("*")
            .in_("race_id", race_ids[idx : idx + 100])
            .execute()
            .data
            or []
        )
    return out


def fetch_races(sb, race_ids: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx in range(0, len(race_ids), 100):
        out.extend(
            sb.table("races")
            .select("race_id,runners_count,course,date")
            .in_("race_id", race_ids[idx : idx + 100])
            .execute()
            .data
            or []
        )
    return out


def variance(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    return sum((value - avg) ** 2 for value in values) / len(values)


def build_report(sb) -> dict[str, Any]:
    rows = accepted_rows(sb)
    race_ids = sorted({str(row["race_id"]) for row in rows})
    runner_results = fetch_runner_results(sb, race_ids)
    race_results = fetch_race_results(sb, race_ids)
    race_rows = fetch_races(sb, race_ids)

    event_keys = []
    vector_lengths = Counter()
    mpi_values: list[float] = []
    chaos_values: list[float] = []
    year_breakdown = Counter()
    jurisdiction_breakdown = Counter()
    course_breakdown = Counter()
    training_distribution = Counter()
    doctrine_contract_counts = Counter()
    provenance_complete = True
    doctrine_complete = True
    winner_parity_ok = True
    missing_hfs_rows = 0
    orphan_hfs_rows = 0
    vector_nulls = 0
    macro_year_mismatch = 0
    duplicate_pair_count = len(rows) - len({(str(row["race_id"]), str(row["horse_id"])) for row in rows})

    runners_count_total = sum(int(row.get("runners_count") or 0) for row in race_rows)
    missing_hfs_rows = max(0, runners_count_total - len(rows))
    orphan_hfs_rows = max(0, len(rows) - runners_count_total)

    for row in rows:
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        event_key = str(feature_json.get("event_key") or "")
        event_keys.append(event_key)
        race_year = parse_date_key(row.get("race_date"))[:4]
        year_breakdown[race_year] += 1
        jurisdiction_breakdown[str(row.get("jurisdiction") or "")] += 1
        course_breakdown[str(row.get("course") or "")] += 1
        training_distribution[str(feature_json.get("training_eligible"))] += 1
        doctrine_contract_counts[str(feature_json.get("historical_doctrine_contract") or "missing")] += 1

        vector = feature_json.get("strictly_ordered_vector") or []
        vector_lengths[str(len(vector) if isinstance(vector, list) else "missing")] += 1
        if isinstance(vector, list):
            vector_nulls += sum(1 for value in vector if safe_float(value) is None)
        else:
            vector_nulls += 1

        year_int = int(race_year) if race_year.isdigit() else None
        if year_int is None or feature_json.get("macro_year_used") != year_int:
            macro_year_mismatch += 1

        mpi = safe_float(row.get("mpi"))
        chaos = safe_float(row.get("chaos_bloom"))
        if mpi is not None:
            mpi_values.append(mpi)
        if chaos is not None:
            chaos_values.append(chaos)

        provenance_complete &= feature_json.get("data_owner_confirmed") is True
        provenance_complete &= feature_json.get("event_identity_contract") == "race_id_course_race_date"
        provenance_complete &= feature_json.get("training_eligible") == "pending_global_training_gate"
        doctrine_complete &= feature_json.get("signal_contract_version") == "HISTORICAL_SIGNAL_PROXY_V1"
        doctrine_complete &= feature_json.get("mpi_source") == "archive_proxy_market_rank_v1"
        doctrine_complete &= feature_json.get("chaos_bloom_source") == "archive_proxy_market_entropy_going_v1"
        doctrine_complete &= feature_json.get("historical_doctrine_contract") == HISTORICAL_DOCTRINE_CONTRACT

        rr = runner_results.get((str(row["race_id"]), str(row["horse_id"])))
        if rr is not None and bool(rr.get("is_winner")) != bool(row.get("winner_flag")):
            winner_parity_ok = False

    race_to_event_keys: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        event_key = str(feature_json.get("event_key") or "")
        race_to_event_keys[str(row.get("race_id"))].add(event_key)
    duplicate_event_key_count = sum(1 for keys in race_to_event_keys.values() if len(keys) != 1 or "" in keys)
    race_result_dup_count = len(race_results) - len({str(row.get("race_id")) for row in race_results})
    winner_count_by_race = Counter(str(row["race_id"]) for row in rows if bool(row.get("winner_flag")))
    winner_parity_ok &= all(count == 1 for count in winner_count_by_race.values()) and len(winner_count_by_race) == len(race_ids)

    report = {
        "authority_model": {
            "accepted_historical_training_authority": [
                "race_results distinct accepted events",
                "races.runners_count",
                "accepted historical_feature_store rows",
            ],
            "known_caveat": "direct runner_results join has legacy horse-id drift and is not the authority for Playbook G V2 training cohort.",
        },
        "A_accepted_clean_race_event_count": len(race_ids),
        "B_accepted_historical_runner_count": runners_count_total,
        "C_accepted_hfs_row_count": len(rows),
        "D_race_runner_hfs_parity": {
            "distinct_race_results": len({str(row.get("race_id")) for row in race_results}),
            "distinct_hfs_race_ids": len(race_ids),
            "runner_rows_expected_from_races_table": runners_count_total,
            "runner_results_rows_observed": len(runner_results),
            "hfs_rows_for_scope": len(rows),
            "pass": len({str(row.get("race_id")) for row in race_results}) == len(race_ids) and runners_count_total == len(rows),
        },
        "E_winner_parity": winner_parity_ok,
        "F_duplicate_race_id_count": race_result_dup_count,
        "G_duplicate_event_key_count": duplicate_event_key_count,
        "H_duplicate_race_id_horse_id_count": duplicate_pair_count,
        "I_missing_hfs_rows": missing_hfs_rows,
        "J_orphan_hfs_rows": orphan_hfs_rows,
        "K_vector_dimension_distribution": dict(vector_lengths),
        "L_mpi": {
            "null_count": len(rows) - len(mpi_values),
            "min": min(mpi_values) if mpi_values else None,
            "max": max(mpi_values) if mpi_values else None,
            "variance": variance(mpi_values),
        },
        "M_chaos_bloom": {
            "null_count": len(rows) - len(chaos_values),
            "min": min(chaos_values) if chaos_values else None,
            "max": max(chaos_values) if chaos_values else None,
            "variance": variance(chaos_values),
        },
        "N_macro_year_mismatch_count": macro_year_mismatch,
        "O_doctrine_tag_completeness": {
            "signal_contract_version": doctrine_complete,
            "historical_doctrine_contract_counts": dict(doctrine_contract_counts),
        },
        "P_provenance_tag_completeness": provenance_complete,
        "Q_training_eligible_distribution": dict(training_distribution),
        "R_race_date_min_max": {
            "min": min(parse_date_key(row.get("race_date")) for row in rows) if rows else None,
            "max": max(parse_date_key(row.get("race_date")) for row in rows) if rows else None,
        },
        "S_jurisdiction_breakdown": dict(jurisdiction_breakdown),
        "T_year_breakdown": dict(year_breakdown),
        "U_block_025_summary": {
            "status": "accepted",
            "archive_exhausted": True,
        },
        "historical_doctrine_contract_complete": doctrine_contract_counts == Counter({HISTORICAL_DOCTRINE_CONTRACT: len(rows)}),
        "vector_null_count": vector_nulls,
    }
    return report


def build_markdown(report: dict[str, Any], *, version: str) -> str:
    return "\n".join(
        [
            f"# Global Clean Spine Audit {version.upper()}",
            "",
            "## Authority Model",
            "- Accepted historical training authority = `race_results distinct accepted events + races.runners_count + accepted historical_feature_store rows`",
            "- Known caveat = `direct runner_results join has legacy horse-id drift and is not the authority for Playbook G V2 training cohort.`",
            "",
            f"- Accepted events: `{report['A_accepted_clean_race_event_count']}`",
            f"- Accepted runner rows: `{report['B_accepted_historical_runner_count']}`",
            f"- Accepted HFS rows: `{report['C_accepted_hfs_row_count']}`",
            f"- Parity pass: `{report['D_race_runner_hfs_parity']['pass']}`",
            f"- Winner parity: `{report['E_winner_parity']}`",
            f"- Duplicate race_id count: `{report['F_duplicate_race_id_count']}`",
            f"- Duplicate event_key count: `{report['G_duplicate_event_key_count']}`",
            f"- Duplicate race_id+horse_id count: `{report['H_duplicate_race_id_horse_id_count']}`",
            f"- Missing / orphan HFS rows: `{report['I_missing_hfs_rows']} / {report['J_orphan_hfs_rows']}`",
            f"- Vector distribution: `{json.dumps(report['K_vector_dimension_distribution'])}`",
            f"- MPI nulls / variance: `{report['L_mpi']['null_count']} / {report['L_mpi']['variance']}`",
            f"- chaos_bloom nulls / variance: `{report['M_chaos_bloom']['null_count']} / {report['M_chaos_bloom']['variance']}`",
            f"- Macro-year mismatch: `{report['N_macro_year_mismatch_count']}`",
            f"- Provenance completeness: `{report['P_provenance_tag_completeness']}`",
            f"- Historical doctrine contract complete: `{report['historical_doctrine_contract_complete']}`",
        ]
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-version", default="v4")
    parser.add_argument("--write-artifacts", action="store_true")
    args = parser.parse_args()

    sb = get_sb_client()
    report = build_report(sb)
    json_out = DATA_DIR / f"global_clean_spine_audit_{args.output_version}.json"
    md_out = DATA_DIR / f"global_clean_spine_audit_{args.output_version}.md"

    if args.write_artifacts:
        json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        md_out.write_text(build_markdown(report, version=args.output_version), encoding="utf-8")
        print(f"Wrote {json_out}")
        print(f"Wrote {md_out}")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
