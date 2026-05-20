from __future__ import annotations

import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.historical_doctrine_support import DOCTRINE_FEATURE_NAMES
    from scripts.run_historical_doctrine_activation_smoke import (
        DISTANCE_PARSER_VERSION,
        FEATURE_INDEX,
        FEATURE_VECTOR_NAMES,
        build_after_row,
        clean_name,
        doctrine_defaults_count,
        fetch_raceform_current_rows,
        get_sb_client,
        leakage_audit,
        outcome_exclusion_audit,
        parse_date_key,
        safe_float,
        variance,
        vector_dist_stats,
        vector_length_distribution,
    )
except ModuleNotFoundError:
    from historical_doctrine_support import DOCTRINE_FEATURE_NAMES
    from run_historical_doctrine_activation_smoke import (
        DISTANCE_PARSER_VERSION,
        FEATURE_INDEX,
        FEATURE_VECTOR_NAMES,
        build_after_row,
        clean_name,
        doctrine_defaults_count,
        fetch_raceform_current_rows,
        get_sb_client,
        leakage_audit,
        outcome_exclusion_audit,
        parse_date_key,
        safe_float,
        variance,
        vector_dist_stats,
        vector_length_distribution,
    )

DATA_DIR = ROOT / "data"
JSON_OUT = DATA_DIR / "historical_doctrine_full_reapply_dry_run_v1.json"
MD_OUT = DATA_DIR / "historical_doctrine_full_reapply_dry_run_v1.md"


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
        if not isinstance(vector, list) or len(vector) != len(FEATURE_VECTOR_NAMES):
            continue
        race_year = parse_date_key(row.get("race_date"))[:4]
        if not race_year.isdigit():
            continue
        if feature_json.get("macro_year_used") != int(race_year):
            continue
        accepted.append(row)
    accepted.sort(key=lambda item: (parse_date_key(item.get("race_date")), str(item.get("race_id")), str(item.get("horse_id"))))
    return accepted


def accepted_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    events: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("race_id")), str(row.get("course") or ""), parse_date_key(row.get("race_date")))
        if key in seen:
            continue
        seen.add(key)
        events.append(
            {
                "race_id": key[0],
                "course": key[1],
                "race_date": key[2],
                "jurisdiction": row.get("jurisdiction"),
            }
        )
    return events


def build_accepted_prior_sources(
    before_rows: list[dict[str, Any]],
    current_rows_by_race: dict[str, dict[str, dict[str, Any]]],
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    all_current_rows: list[dict[str, Any]] = []
    for race_rows in current_rows_by_race.values():
        all_current_rows.extend(race_rows.values())

    horse_rows_by_clean: dict[str, list[dict[str, Any]]] = defaultdict(list)
    trainer_rows_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_current_rows:
        horse_rows_by_clean[clean_name(row.get("horse"))].append(row)
        trainer = str(row.get("trainer") or "")
        if trainer:
            trainer_rows_by_name[trainer].append(row)

    for rows in horse_rows_by_clean.values():
        rows.sort(key=lambda item: str(item.get("date") or ""))
    for rows in trainer_rows_by_name.values():
        rows.sort(key=lambda item: str(item.get("date") or ""))

    horse_history_by_row: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in before_rows:
        current_source = current_rows_by_race.get(str(row["race_id"]), {}).get(clean_name(row.get("horse_name")))
        clean_keys = {clean_name(row.get("horse_name"))}
        if current_source:
            clean_keys.add(clean_name(current_source.get("horse")))
        merged: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for clean_key in clean_keys:
            for hist in horse_rows_by_clean.get(clean_key, []):
                key = (hist.get("race_id"), hist.get("date"), hist.get("horse"), hist.get("trainer"), hist.get("jockey"))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(hist)
        merged.sort(key=lambda item: str(item.get("date") or ""))
        horse_history_by_row[(str(row["race_id"]), str(row["horse_id"]))] = merged
    return horse_history_by_row, trainer_rows_by_name


def doctrine_variance(rows: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for feature in DOCTRINE_FEATURE_NAMES:
        idx = FEATURE_INDEX[feature]
        values = []
        for row in rows:
            vector = (row.get("feature_json") or {}).get("strictly_ordered_vector") or []
            if len(vector) != len(FEATURE_VECTOR_NAMES):
                continue
            value = safe_float(vector[idx])
            if value is not None:
                values.append(value)
        out[feature] = variance(values)
    return out


def runtime_estimate(elapsed_seconds: float, row_count: int) -> dict[str, Any]:
    upsert_batches = math.ceil(row_count / 100)
    estimated_write_seconds = round((elapsed_seconds * 1.1) + (upsert_batches * 0.5), 2)
    return {
        "dry_run_elapsed_seconds": round(elapsed_seconds, 2),
        "estimated_upsert_batches_at_100_rows": upsert_batches,
        "estimated_full_write_seconds": estimated_write_seconds,
    }


def recommended_batches(event_count: int, row_count: int) -> dict[str, Any]:
    event_batches = math.ceil(event_count / 100)
    row_batches = math.ceil(row_count / 1000)
    return {
        "recommended_strategy": "manifest_scoped_batches",
        "recommended_event_batch_size": 100,
        "recommended_runner_row_batch_size": 1000,
        "estimated_event_batches": event_batches,
        "estimated_runner_batches": row_batches,
        "note": "Preserve existing OASIS block boundaries where manifests already exist; otherwise synthesize write manifests at roughly 100 races / 1000 runner rows.",
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Historical Doctrine Full Reapply Dry Run V1",
        "",
        f"- Accepted events evaluated: `{report['A_accepted_events_evaluated']}`",
        f"- Runner rows evaluated: `{report['B_runner_rows_evaluated']}`",
        f"- Prior coverage: `0={report['C_prior_history_coverage']['rows_with_0_prior_runs']}, 1+={report['C_prior_history_coverage']['rows_with_1_plus_prior_runs']}, 3+={report['C_prior_history_coverage']['rows_with_3_plus_prior_runs']}`",
        f"- dist_f before: `{json.dumps(report['D_dist_f_before_after']['before'])}`",
        f"- dist_f after: `{json.dumps(report['D_dist_f_before_after']['after'])}`",
        f"- Leakage rows: `{report['G_rows_with_future_or_same_day_history_leakage']}`",
        f"- Outcome exclusion: `{report['H_outcome_field_exclusion_proof']['status']}`",
        f"- Runtime estimate: `{json.dumps(report['I_runtime_estimate_for_full_write'])}`",
        f"- Recommended batches: `{json.dumps(report['J_manifest_batches_recommended'])}`",
        f"- Go/No-Go: `{report['L_go_no_go_for_full_manifest_scoped_write']}`",
        "",
        "## Risks",
    ]
    lines.extend(f"- {risk}" for risk in report["K_risk_list"])
    return "\n".join(lines) + "\n"


def main() -> None:
    start = time.perf_counter()
    sb = get_sb_client()
    before_rows = accepted_rows(sb)
    events = accepted_events(before_rows)
    current_rows_by_race = fetch_raceform_current_rows(sb, events)
    horse_history_by_row, trainer_history_by_name = build_accepted_prior_sources(before_rows, current_rows_by_race)

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

    coverage = leakage_audit(after_rows)
    elapsed = time.perf_counter() - start
    before_defaults = doctrine_defaults_count(before_rows, after=False)
    after_defaults = doctrine_defaults_count(after_rows, after=True)

    risk_list = [
        "Accepted-spine-only prior history underestimates total horse and trainer context because rejected or non-OASIS races are intentionally excluded.",
        "Rows with zero prior runs remain on default doctrine values by design; this is coverage-limited, not leakage-driven.",
        "decoy_support_flag and cash_run_flag may remain constant if the accepted cohort rarely meets their conditions.",
        "Name-normalization collisions remain a theoretical risk when horse names collapse after country-suffix stripping, though none were observed in the Block 025 smoke.",
    ]

    active_non_constant = [
        feature for feature, feature_var in doctrine_variance(after_rows).items() if feature_var > 0.0
    ]
    go_no_go = (
        "GO"
        if coverage["same_day_or_future_history_rows_used"] == 0
        and outcome_exclusion_audit()["status"] == "pass"
        and vector_length_distribution(after_rows) == {"37": len(after_rows)}
        and len(active_non_constant) >= 8
        else "NO_GO"
    )

    report = {
        "A_accepted_events_evaluated": len(events),
        "B_runner_rows_evaluated": len(before_rows),
        "C_prior_history_coverage": coverage,
        "D_dist_f_before_after": {
            "before": vector_dist_stats(before_rows),
            "after": vector_dist_stats(after_rows),
        },
        "E_doctrine_default_count_before_after": {
            "before": before_defaults,
            "after": after_defaults,
        },
        "F_variance_for_all_18_doctrine_dimensions": doctrine_variance(after_rows),
        "G_rows_with_future_or_same_day_history_leakage": coverage["same_day_or_future_history_rows_used"],
        "H_outcome_field_exclusion_proof": outcome_exclusion_audit(),
        "I_runtime_estimate_for_full_write": runtime_estimate(elapsed, len(before_rows)),
        "J_manifest_batches_recommended": recommended_batches(len(events), len(before_rows)),
        "K_risk_list": risk_list,
        "L_go_no_go_for_full_manifest_scoped_write": go_no_go,
    }
    JSON_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    MD_OUT.write_text(build_markdown(report), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
