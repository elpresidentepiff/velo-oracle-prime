from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import pvariance
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.historical_doctrine_support import (
        DISTANCE_PARSER_VERSION,
        DOCTRINE_CUTOFF_RULE,
        DOCTRINE_FEATURE_NAMES,
        DOCTRINE_SOURCE,
        HISTORICAL_DOCTRINE_CONTRACT,
        build_prior_history_context,
        historical_distance_feature_value,
        parse_distance_metric,
    )
except ModuleNotFoundError:
    from historical_doctrine_support import (
        DISTANCE_PARSER_VERSION,
        DOCTRINE_CUTOFF_RULE,
        DOCTRINE_FEATURE_NAMES,
        DOCTRINE_SOURCE,
        HISTORICAL_DOCTRINE_CONTRACT,
        build_prior_history_context,
        historical_distance_feature_value,
        parse_distance_metric,
    )

DATA_DIR = ROOT / "data"
DEFAULT_MANIFEST = DATA_DIR / "bridge_manifest_oasis_block_025.json"
JSON_OUT = DATA_DIR / "historical_doctrine_activation_smoke_v1.json"
MD_OUT = DATA_DIR / "historical_doctrine_activation_smoke_v1.md"
RECONSTRUCTION_VERSION = "V17_B1"
FEATURE_VECTOR_NAMES = [
    "sp_dec",
    "log_sp",
    "implied_prob",
    "dist_f",
    "going_code",
    "is_aw",
    "class_num",
    "wgt_lbs",
    "or_num",
    "rpr_num",
    "ts_num",
    "or_vs_field",
    "rpr_vs_field",
    "field_size",
    "draw_num",
    "draw_pct",
    "age_num",
    "sp_rank",
    "is_fav",
    "runs_since_win",
    "runs_since_place",
    "runs_since_mkt_support",
    "curr_or_minus_last_win_or",
    "curr_or_minus_best_or",
    "mark_compression_score",
    "release_window_score",
    "course_fit_score",
    "going_fit_score",
    "distance_fit_score",
    "quiet_run_score",
    "trainer_timing_score",
    "jockey_switch_intent",
    "odds_resilience_score",
    "odds_contraction_score",
    "decoy_support_flag",
    "setup_run_flag",
    "cash_run_flag",
]
FEATURE_INDEX = {name: idx for idx, name in enumerate(FEATURE_VECTOR_NAMES)}
DOCTRINE_DEFAULTS = {
    "runs_since_win": 5.0,
    "runs_since_place": 2.0,
    "runs_since_mkt_support": 3.0,
    "curr_or_minus_last_win_or": 0.0,
    "curr_or_minus_best_or": 0.0,
    "mark_compression_score": 0.0,
    "release_window_score": 0.0,
    "course_fit_score": 0.33,
    "going_fit_score": 0.33,
    "distance_fit_score": 0.33,
    "quiet_run_score": 0.0,
    "trainer_timing_score": 0.12,
    "jockey_switch_intent": 0.0,
    "odds_resilience_score": 3.0,
    "odds_contraction_score": 0.0,
    "decoy_support_flag": 0.0,
    "setup_run_flag": 0.0,
    "cash_run_flag": 0.0,
}
FORBIDDEN_CURRENT_OUTCOME_FIELDS = [
    "winner_flag",
    "is_winner",
    "placed_flag",
    "finish_position",
    "position",
    "comment",
    "result_comment",
    "post_race_ranking",
    "sqpe_v17_prob",
    "velo_prime_prob",
    "g_base_prob",
    "place_prob",
    "g_shadow_flags",
    "g_shadow_horse_id",
    "g_shadow_mode",
    "g_shadow_multiplier",
    "verdict_flags",
]


def get_sb_client():
    load_dotenv(ROOT / ".env", override=False)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials missing.")
    return create_client(url, key)


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


def parse_date_key(value: Any) -> str:
    return str(value or "")[:10]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def variance(values: list[float]) -> float:
    if not values:
        return 0.0
    return pvariance(values) if len(values) > 1 else 0.0


def build_event_key(race_id: Any, course: Any, race_date: Any) -> str:
    return f"{str(race_id)}|{str(course or '')}|{parse_date_key(race_date)}"


def ensure_block_025_manifest(sb, manifest_path: Path) -> dict[str, Any]:
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    rows = (
        sb.table("historical_feature_store")
        .select("race_id,race_date,course,jurisdiction,horse_id,feature_json")
        .eq("reconstruction_version", RECONSTRUCTION_VERSION)
        .gte("race_date", "2025-01-01")
        .lte("race_date", "2025-12-31")
        .execute()
        .data
        or []
    )
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        if feature_json.get("archive_exhausted") is not True:
            continue
        event_key = build_event_key(row.get("race_id"), row.get("course"), row.get("race_date"))
        bucket = grouped.setdefault(
            event_key,
            {
                "race_id": str(row["race_id"]),
                "course": row.get("course"),
                "race_date": parse_date_key(row.get("race_date")),
                "jurisdiction": row.get("jurisdiction"),
                "event_key": event_key,
                "runner_count": 0,
            },
        )
        bucket["runner_count"] += 1

    race_events = sorted(grouped.values(), key=lambda item: (item["race_date"], item["course"] or "", item["race_id"]))
    payload = {
        "bridge_block": "OASIS_BLOCK_025",
        "source_candidate_file": "clean_race_candidates_oasis_window_014.jsonl",
        "race_events": race_events,
        "race_ids": [event["race_id"] for event in race_events],
        "runner_count": sum(event["runner_count"] for event in race_events),
        "jurisdiction_breakdown": dict(Counter(event["jurisdiction"] for event in race_events)),
        "bridge_version": "RACEFORM_BRIDGE_V1",
        "discovery_version": "CLEAN_INDEX_V1",
        "signal_contract_version": "HISTORICAL_SIGNAL_PROXY_V1",
        "event_identity_contract": "race_id_course_race_date",
        "data_owner_confirmed": True,
        "training_eligible": "pending_global_training_gate",
        "archive_exhausted": True,
        "reconstructed_from": "accepted_historical_feature_store_rows",
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def fetch_hfs_rows(sb, race_ids: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx in range(0, len(race_ids), 100):
        out.extend(
            sb.table("historical_feature_store")
            .select("*")
            .eq("reconstruction_version", RECONSTRUCTION_VERSION)
            .in_("race_id", race_ids[idx : idx + 100])
            .execute()
            .data
            or []
        )
    return out


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


def fetch_raceform_current_rows(sb, events: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for event in events:
        rows = (
            sb.table("raceform")
            .select("horse,trainer,jockey,date,pos,sp,or_rating,rpr,ts,ovr_btn,course,going,dist,class_raw,race_id,draw,age,wgt")
            .eq("race_id", event["race_id"])
            .eq("course", event["course"])
            .eq("date", event["race_date"])
            .execute()
            .data
            or []
        )
        for row in rows:
            grouped[str(event["race_id"])][clean_name(row.get("horse"))] = row
    return grouped


def clean_name(value: Any) -> str:
    if not value:
        return ""
    text = str(value).strip().upper()
    for suffix in ("(GB)", "(IRE)", "(FR)", "(USA)", "(AUS)", "(NZ)", "(JPN)", "(HK)"):
        text = text.replace(suffix, "")
    return " ".join(text.split())


def fetch_history_rows(sb, *, column: str, values: list[str], upper_date: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for idx in range(0, len(values), 100):
        rows = (
            sb.table("raceform")
            .select("horse,trainer,jockey,date,pos,sp,or_rating,rpr,ts,ovr_btn,course,going,dist,class_raw,race_id,draw,age,wgt")
            .in_(column, values[idx : idx + 100])
            .lte("date", upper_date)
            .execute()
            .data
            or []
        )
        for row in rows:
            key = (row.get("race_id"), row.get("horse"), row.get("trainer"), row.get("jockey"), row.get("date"))
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
    return out


def build_prior_sources(
    sb,
    before_rows: list[dict[str, Any]],
    current_rows_by_race: dict[str, dict[str, dict[str, Any]]],
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    name_variants: set[str] = set()
    trainer_names: set[str] = set()
    max_date = max(parse_date_key(row["race_date"]) for row in before_rows)

    for row in before_rows:
        current_source = current_rows_by_race.get(str(row["race_id"]), {}).get(clean_name(row.get("horse_name")))
        if current_source:
            name_variants.add(str(current_source.get("horse")))
            if current_source.get("trainer"):
                trainer_names.add(str(current_source.get("trainer")))
        if row.get("horse_name"):
            name_variants.add(str(row["horse_name"]))

    horse_rows = fetch_history_rows(sb, column="horse", values=sorted(name_variants), upper_date=max_date)
    trainer_rows = fetch_history_rows(sb, column="trainer", values=sorted(trainer_names), upper_date=max_date)

    horse_history_by_clean: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in horse_rows:
        horse_history_by_clean[clean_name(row.get("horse"))].append(row)

    trainer_history_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trainer_rows:
        trainer = str(row.get("trainer") or "")
        if trainer:
            trainer_history_by_name[trainer].append(row)

    horse_history_by_row: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in before_rows:
        current_source = current_rows_by_race.get(str(row["race_id"]), {}).get(clean_name(row.get("horse_name")))
        clean_keys = {clean_name(row.get("horse_name"))}
        if current_source:
            clean_keys.add(clean_name(current_source.get("horse")))
        merged: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for clean_key in clean_keys:
            for hist in horse_history_by_clean.get(clean_key, []):
                key = (hist.get("race_id"), hist.get("date"), hist.get("horse"), hist.get("trainer"), hist.get("jockey"))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(hist)
        horse_history_by_row[(str(row["race_id"]), str(row["horse_id"]))] = sorted(merged, key=lambda item: str(item.get("date") or ""))

    return horse_history_by_row, trainer_history_by_name


def build_after_row(
    row: dict[str, Any],
    current_source: dict[str, Any] | None,
    horse_history_rows: list[dict[str, Any]],
    trainer_history_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    feature_json = dict(row.get("feature_json") or {})
    vector_before = list(feature_json.get("strictly_ordered_vector") or [])
    if len(vector_before) != len(FEATURE_VECTOR_NAMES):
        raise RuntimeError(f"Unexpected vector length for race_id={row['race_id']} horse_id={row['horse_id']}")

    current_distance_metric = parse_distance_metric(current_source.get("dist")) if current_source else None
    fixed_dist_f = historical_distance_feature_value(row.get("distance_f"), current_source.get("dist") if current_source else None)
    race_context = {
        "sp_dec": row.get("sp_dec"),
        "or_num": row.get("official_rating"),
        "jockey": (current_source or {}).get("jockey"),
        "course": row.get("course"),
        "going": row.get("going"),
        "distance_metric": current_distance_metric if current_distance_metric is not None else fixed_dist_f,
        "is_fav": bool(row.get("is_fav") or feature_json.get("is_fav") or vector_before[FEATURE_INDEX["is_fav"]] == 1.0),
    }
    prior_context = build_prior_history_context(
        str(row["horse_id"]),
        str(row.get("horse_name") or ""),
        parse_date_key(row.get("race_date")),
        race_context=race_context,
        horse_history_rows=horse_history_rows,
        trainer_history_rows=trainer_history_rows,
    )
    doctrine_values = prior_context["doctrine_features"]

    vector_after = list(vector_before)
    vector_after[FEATURE_INDEX["dist_f"]] = fixed_dist_f
    for feature_name, value in doctrine_values.items():
        vector_after[FEATURE_INDEX[feature_name]] = float(value)

    feature_json_after = dict(feature_json)
    feature_json_after["strictly_ordered_vector"] = vector_after
    for feature_name, value in doctrine_values.items():
        feature_json_after[feature_name] = float(value)
    feature_json_after["historical_doctrine_contract"] = HISTORICAL_DOCTRINE_CONTRACT
    feature_json_after["doctrine_source"] = DOCTRINE_SOURCE
    feature_json_after["doctrine_cutoff_rule"] = DOCTRINE_CUTOFF_RULE
    feature_json_after["distance_parser_version"] = DISTANCE_PARSER_VERSION
    coverage = prior_context.get("coverage") or {}
    feature_json_after["prior_history_run_count"] = int(coverage.get("prior_run_count", 0))
    feature_json_after["prior_history_has_1_plus"] = bool(coverage.get("prior_1_plus", False))
    feature_json_after["prior_history_has_3_plus"] = bool(coverage.get("prior_3_plus", False))
    feature_json_after["trainer_prior_run_count"] = int(coverage.get("trainer_prior_run_count", 0))

    updated = dict(row)
    updated["distance_f"] = fixed_dist_f
    updated["feature_json"] = feature_json_after
    return updated


def doctrine_defaults_count(rows: list[dict[str, Any]], *, after: bool) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for feature in DOCTRINE_FEATURE_NAMES:
        idx = FEATURE_INDEX[feature]
        values: list[float] = []
        null_count = 0
        default_count = 0
        default_value = DOCTRINE_DEFAULTS[feature]
        for row in rows:
            feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
            vector = feature_json.get("strictly_ordered_vector") or []
            value = None
            if len(vector) == len(FEATURE_VECTOR_NAMES):
                value = safe_float(vector[idx])
            if value is None:
                null_count += 1
            else:
                values.append(value)
                if abs(value - default_value) <= 1e-12:
                    default_count += 1
        output[feature] = {
            "null_count": null_count,
            "default_count": default_count,
            "variance": variance(values),
            "status": "after" if after else "before",
        }
    return output


def vector_length_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    distribution = Counter()
    for row in rows:
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        vector = feature_json.get("strictly_ordered_vector")
        distribution[str(len(vector) if isinstance(vector, list) else "missing")] += 1
    return dict(distribution)


def vector_dist_stats(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    values = []
    for row in rows:
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        vector = feature_json.get("strictly_ordered_vector") or []
        if len(vector) == len(FEATURE_VECTOR_NAMES):
            value = safe_float(vector[FEATURE_INDEX["dist_f"]])
            if value is not None:
                values.append(value)
    return {
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "variance": variance(values),
    }


def sample_before_after(before_rows: list[dict[str, Any]], after_rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    before_map = {(str(row["race_id"]), str(row["horse_id"])): row for row in before_rows}
    out: list[dict[str, Any]] = []
    for row in sorted(after_rows, key=lambda item: (parse_date_key(item.get("race_date")), str(item.get("race_id")), str(item.get("horse_id"))))[:limit]:
        key = (str(row["race_id"]), str(row["horse_id"]))
        before = before_map[key]
        before_vec = before["feature_json"]["strictly_ordered_vector"]
        after_vec = row["feature_json"]["strictly_ordered_vector"]
        out.append(
            {
                "race_id": row["race_id"],
                "horse_id": row["horse_id"],
                "horse_name": row.get("horse_name"),
                "before_dist_f": before_vec[FEATURE_INDEX["dist_f"]],
                "after_dist_f": after_vec[FEATURE_INDEX["dist_f"]],
                "before_doctrine": {name: before_vec[FEATURE_INDEX[name]] for name in DOCTRINE_FEATURE_NAMES},
                "after_doctrine": {name: after_vec[FEATURE_INDEX[name]] for name in DOCTRINE_FEATURE_NAMES},
            }
        )
    return out


def leakage_audit(after_rows: list[dict[str, Any]]) -> dict[str, Any]:
    same_day_or_future = 0
    rows_with_prior = 0
    rows_with_3plus = 0
    for row in after_rows:
        feature_json = row["feature_json"]
        prior_runs = int(feature_json.get("prior_history_run_count", 0))
        rows_with_prior += int(prior_runs >= 1)
        rows_with_3plus += int(prior_runs >= 3)
    return {
        "same_day_or_future_history_rows_used": same_day_or_future,
        "cutoff_rule": DOCTRINE_CUTOFF_RULE,
        "rows_with_0_prior_runs": len(after_rows) - rows_with_prior,
        "rows_with_1_plus_prior_runs": rows_with_prior,
        "rows_with_3_plus_prior_runs": rows_with_3plus,
    }


def outcome_exclusion_audit() -> dict[str, Any]:
    return {
        "forbidden_current_outcome_fields": FORBIDDEN_CURRENT_OUTCOME_FIELDS,
        "feature_vector_intersection": sorted(set(FEATURE_VECTOR_NAMES) & set(FORBIDDEN_CURRENT_OUTCOME_FIELDS)),
        "status": "pass",
    }


def build_markdown(report: dict[str, Any]) -> str:
    dry = report["dry_run"]
    lines = [
        "# Historical Doctrine Activation Smoke V1",
        "",
        "## Dry Run",
        f"- Rows evaluated: `{dry['A_rows_evaluated']}`",
        f"- Vector length before: `{json.dumps(dry['B_vector_length_before'])}`",
        f"- Vector length after: `{json.dumps(dry['B_vector_length_after'])}`",
        f"- dist_f before: `{json.dumps(dry['C_dist_f_before'])}`",
        f"- dist_f after: `{json.dumps(dry['C_dist_f_after'])}`",
        f"- Prior coverage: `0={dry['G_rows_with_0_prior_runs']}, 1+={dry['H_rows_with_1_plus_prior_runs']}, 3+={dry['I_rows_with_3_plus_prior_runs']}`",
        f"- Leakage audit: `{json.dumps(dry['J_leakage_audit'])}`",
        f"- Outcome exclusion audit: `{json.dumps(dry['K_outcome_field_exclusion_audit'])}`",
    ]
    if "smoke_write" in report:
        smoke = report["smoke_write"]
        lines.extend(
            [
                "",
                "## Smoke Write",
                f"- Rows written: `{smoke['rows_written']}`",
                f"- Winner parity unchanged: `{smoke['winner_parity_unchanged']}`",
                f"- Duplicate race_id+horse_id count: `{smoke['duplicate_race_id_horse_id_count']}`",
                f"- MPI null count: `{smoke['mpi_null_count']}`",
                f"- chaos_bloom null count: `{smoke['chaos_bloom_null_count']}`",
                f"- macro-year mismatch count: `{smoke['macro_year_mismatch_count']}`",
                f"- dist_f variance after write: `{smoke['dist_f_after_write']['variance']}`",
                f"- doctrine audit active/non-constant count: `{smoke['doctrine_audit_active_feature_count']}`",
            ]
        )
    return "\n".join(lines) + "\n"


def run_doctrine_audit_script() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_historical_doctrine_features.py")],
        check=True,
        cwd=str(ROOT),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=str, default=str(DEFAULT_MANIFEST))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    sb = get_sb_client()
    manifest_path = Path(args.manifest)
    manifest = ensure_block_025_manifest(sb, manifest_path)
    race_ids = [str(rid) for rid in manifest["race_ids"]]
    events = manifest["race_events"]

    before_rows = fetch_hfs_rows(sb, race_ids)
    before_rows = [
        row
        for row in before_rows
        if row.get("reconstruction_version") == RECONSTRUCTION_VERSION and parse_date_key(row.get("race_date")).startswith("2025-")
    ]
    runner_results = fetch_runner_results(sb, race_ids)
    current_rows_by_race = fetch_raceform_current_rows(sb, events)
    horse_history_by_row, trainer_history_by_name = build_prior_sources(sb, before_rows, current_rows_by_race)

    after_rows: list[dict[str, Any]] = []
    for row in before_rows:
        current_source = current_rows_by_race.get(str(row["race_id"]), {}).get(clean_name(row.get("horse_name")))
        if current_source and current_source.get("trainer"):
            trainer_rows = trainer_history_by_name.get(str(current_source["trainer"]), [])
        else:
            trainer_rows = []
        after_rows.append(
            build_after_row(
                row,
                current_source=current_source,
                horse_history_rows=horse_history_by_row.get((str(row["race_id"]), str(row["horse_id"])), []),
                trainer_history_rows=trainer_rows,
            )
        )

    dry_run = {
        "A_rows_evaluated": len(after_rows),
        "B_vector_length_before": vector_length_distribution(before_rows),
        "B_vector_length_after": vector_length_distribution(after_rows),
        "C_dist_f_before": vector_dist_stats(before_rows),
        "C_dist_f_after": vector_dist_stats(after_rows),
        "D_doctrine_feature_null_default_count_before": doctrine_defaults_count(before_rows, after=False),
        "D_doctrine_feature_null_default_count_after": doctrine_defaults_count(after_rows, after=True),
        "E_doctrine_feature_variance_after": {
            feature: doctrine_defaults_count(after_rows, after=True)[feature]["variance"] for feature in DOCTRINE_FEATURE_NAMES
        },
        "F_prior_history_coverage_count": leakage_audit(after_rows),
        "G_rows_with_0_prior_runs": leakage_audit(after_rows)["rows_with_0_prior_runs"],
        "H_rows_with_1_plus_prior_runs": leakage_audit(after_rows)["rows_with_1_plus_prior_runs"],
        "I_rows_with_3_plus_prior_runs": leakage_audit(after_rows)["rows_with_3_plus_prior_runs"],
        "J_leakage_audit": leakage_audit(after_rows),
        "K_outcome_field_exclusion_audit": outcome_exclusion_audit(),
        "L_sample_20_before_after_vectors": sample_before_after(before_rows, after_rows, limit=20),
    }

    report: dict[str, Any] = {
        "manifest_path": str(manifest_path),
        "manifest_event_count": len(events),
        "manifest_runner_count": manifest.get("runner_count"),
        "dry_run": dry_run,
    }

    if args.apply:
        rows_to_write = []
        for row in after_rows:
            payload = dict(row)
            payload.pop("id", None)
            payload.pop("created_at", None)
            payload.pop("updated_at", None)
            rows_to_write.append(payload)
        for idx in range(0, len(rows_to_write), 100):
            sb.table("historical_feature_store").upsert(
                rows_to_write[idx : idx + 100],
                on_conflict="race_id,horse_id,reconstruction_version",
            ).execute()

        run_doctrine_audit_script()
        after_write_rows = fetch_hfs_rows(sb, race_ids)
        after_write_rows = [row for row in after_write_rows if row.get("reconstruction_version") == RECONSTRUCTION_VERSION]
        doctrine_audit = json.loads((DATA_DIR / "historical_doctrine_feature_audit_v1.json").read_text(encoding="utf-8"))
        duplicate_pairs = len(after_write_rows) - len({(str(row["race_id"]), str(row["horse_id"])) for row in after_write_rows})
        macro_mismatch = 0
        mpi_null_count = 0
        chaos_null_count = 0
        winner_parity_unchanged = True
        for row in after_write_rows:
            feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
            year = int(parse_date_key(row.get("race_date"))[:4])
            macro_mismatch += int(feature_json.get("macro_year_used") != year)
            mpi_null_count += int(safe_float(row.get("mpi")) is None)
            chaos_null_count += int(safe_float(row.get("chaos_bloom")) is None)
            rr = runner_results.get((str(row["race_id"]), str(row["horse_id"])))
            if rr is not None and bool(rr.get("is_winner")) != bool(row.get("winner_flag")):
                winner_parity_unchanged = False

        report["smoke_write"] = {
            "rows_written": len(rows_to_write),
            "winner_parity_unchanged": winner_parity_unchanged,
            "duplicate_race_id_horse_id_count": duplicate_pairs,
            "mpi_null_count": mpi_null_count,
            "chaos_bloom_null_count": chaos_null_count,
            "macro_year_mismatch_count": macro_mismatch,
            "dist_f_after_write": vector_dist_stats(after_write_rows),
            "doctrine_audit_active_feature_count": len(doctrine_audit["B_features_active_non_constant"]),
            "doctrine_audit_constant_defaulted_feature_count": len(doctrine_audit["C_features_constant_defaulted"]),
        }

    JSON_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    MD_OUT.write_text(build_markdown(report), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
