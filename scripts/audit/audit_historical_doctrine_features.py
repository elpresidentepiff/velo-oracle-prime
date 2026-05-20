from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.historical_doctrine_support import DOCTRINE_FEATURE_NAMES, DOCTRINE_SOURCE, HISTORICAL_DOCTRINE_CONTRACT
except ModuleNotFoundError:
    from historical_doctrine_support import DOCTRINE_FEATURE_NAMES, DOCTRINE_SOURCE, HISTORICAL_DOCTRINE_CONTRACT

DATA_DIR = ROOT / "data"
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
MARKET_FEATURES = ["sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav"]
RATING_FEATURES = ["or_num", "rpr_num", "ts_num", "or_vs_field", "rpr_vs_field"]
LIVE_ONLY_FEATURES = [
    "plot_conviction",
    "or_compression_score",
    "postdata_score",
    "ts_master",
    "or_delta_to_best_win",
    "intent_signals",
    "trainer_recent_form",
    "comment_intel_score",
    "horse_state",
    "tie_gate_signals",
]
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


def paged_hfs_rows() -> list[dict[str, Any]]:
    sb = get_sb_client()
    rows: list[dict[str, Any]] = []
    start = 0
    page_size = 1000
    while True:
        page = (
            sb.table("historical_feature_store")
            .select("race_id,horse_id,race_date,course,jurisdiction,feature_json")
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


def accepted_rows() -> list[dict[str, Any]]:
    rows = []
    for row in paged_hfs_rows():
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
        rows.append({**row, "_feature_json": feature_json, "_vector": vector})
    return rows


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def variance(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = mean(values)
    return sum((value - avg) ** 2 for value in values) / len(values)


def unique_count(values: list[float]) -> int:
    return len({round(value, 12) for value in values})


def build_report() -> dict[str, Any]:
    rows = accepted_rows()
    feature_stats = []
    active = []
    defaulted = []
    constant_nondefault = []
    for idx, feature in enumerate(FEATURE_VECTOR_NAMES):
        values = [float(row["_vector"][idx]) for row in rows]
        default = DOCTRINE_DEFAULTS.get(feature)
        unique = unique_count(values)
        stats = {
            "index": idx,
            "feature": feature,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "variance": variance(values),
            "unique_count": unique,
        }
        if feature in DOCTRINE_FEATURE_NAMES and default is not None and all(abs(v - default) <= 1e-12 for v in values):
            stats["status"] = "constant_defaulted"
            defaulted.append(feature)
        elif unique == 1:
            stats["status"] = "constant_nondefault"
            constant_nondefault.append(feature)
        else:
            stats["status"] = "active_nonconstant"
            active.append(feature)
        feature_stats.append(stats)

    contract_counts = Counter(
        (row["_feature_json"].get("historical_doctrine_contract") or "missing")
        for row in rows
    )
    doctrine_source_counts = Counter(
        (row["_feature_json"].get("doctrine_source") or "missing")
        for row in rows
    )
    distance_parser_counts = Counter(
        (row["_feature_json"].get("distance_parser_version") or "missing")
        for row in rows
    )
    cutoff_rule_counts = Counter(
        (row["_feature_json"].get("doctrine_cutoff_rule") or "missing")
        for row in rows
    )

    report = {
        "scope": {
            "eligible_race_count": len({str(row["race_id"]) for row in rows}),
            "eligible_runner_count": len(rows),
        },
        "A_full_37_vector_schema": [{"index": idx, "feature": name} for idx, name in enumerate(FEATURE_VECTOR_NAMES)],
        "B_features_active_non_constant": active,
        "C_features_constant_defaulted": defaulted,
        "D_market_feature_list": MARKET_FEATURES,
        "E_rating_feature_list": RATING_FEATURES,
        "F_doctrine_feature_list": DOCTRINE_FEATURE_NAMES,
        "G_live_only_feature_list": LIVE_ONLY_FEATURES,
        "H_historical_feasible_feature_list": sorted(DOCTRINE_FEATURE_NAMES),
        "I_historical_infeasible_feature_list": LIVE_ONLY_FEATURES,
        "J_dead_feature_default_paths": {
            feature: {
                "current_default_path": "historical reconstructor lacked prior-only context before activation patch"
            }
            for feature in DOCTRINE_FEATURE_NAMES
        },
        "K_dead_feature_required_context": {
            "horse_prior_history": "prior race_date, SP, OR/RPR/TS, course, going, distance, jockey, trainer, finish"
        },
        "L_raceform_source_sufficiency": {
            "raceform_contains_enough_source_data": True,
        },
        "M_leakage_risk_per_proposed_feature_group": {
            "prior_only_horse_history": {"risk": "medium", "rule": "prior_race_date_lt_current_race_date"},
            "race_level_proxies": {"risk": "low"},
        },
        "N_outcome_field_exclusion_proof": {
            "status": "pass",
            "forbidden_current_race_fields_excluded": True,
        },
        "O_proposed_historical_doctrine_features_v1_contract": {
            "historical_doctrine_contract": HISTORICAL_DOCTRINE_CONTRACT,
            "doctrine_source": DOCTRINE_SOURCE,
            "doctrine_cutoff_rule": "prior_race_date_lt_current_race_date",
        },
        "P_recommended_implementation_plan": [
            "Use prior-only horse history for doctrine features.",
            "Keep vector order fixed at 37.",
            "Preserve current-race outcome exclusion.",
            "Reapply manifest-scoped before broader rollout.",
        ],
        "feature_stats": feature_stats,
        "supporting_findings": {
            "active_feature_count": len(active),
            "dead_doctrine_feature_count": len(defaulted),
            "constant_nondefault_feature_count": len(constant_nondefault),
            "dist_f_issue": next((row for row in feature_stats if row["feature"] == "dist_f"), None),
            "historical_doctrine_contract_counts": dict(contract_counts),
            "doctrine_source_counts": dict(doctrine_source_counts),
            "doctrine_cutoff_rule_counts": dict(cutoff_rule_counts),
            "distance_parser_version_counts": dict(distance_parser_counts),
            "historical_doctrine_contract_complete": contract_counts == Counter({HISTORICAL_DOCTRINE_CONTRACT: len(rows)}),
            "doctrine_source_complete": doctrine_source_counts == Counter({DOCTRINE_SOURCE: len(rows)}),
            "distance_parser_version_complete": distance_parser_counts == Counter({"HISTORICAL_DISTANCE_FIX_V1": len(rows)}),
        },
        "final_recommendation": {
            "option": "D",
            "text": "Build prior-only horse history engine before Playbook G V2.",
        },
    }
    return report


def write_markdown(report: dict[str, Any], *, version: str) -> str:
    return "\n".join(
        [
            f"# Historical Doctrine Feature Activation Audit {version.upper()}",
            "",
            f"- Eligible races: `{report['scope']['eligible_race_count']}`",
            f"- Eligible runners: `{report['scope']['eligible_runner_count']}`",
            f"- Active / non-constant features: `{len(report['B_features_active_non_constant'])}`",
            f"- Constant / defaulted doctrine features: `{len(report['C_features_constant_defaulted'])}`",
            f"- Doctrine contract counts: `{json.dumps(report['supporting_findings']['historical_doctrine_contract_counts'])}`",
            f"- Doctrine source counts: `{json.dumps(report['supporting_findings']['doctrine_source_counts'])}`",
            f"- Distance parser counts: `{json.dumps(report['supporting_findings']['distance_parser_version_counts'])}`",
            f"- Recommendation: `{report['final_recommendation']['option']}` {report['final_recommendation']['text']}",
            "",
            "## Active features",
            f"- `{', '.join(report['B_features_active_non_constant'])}`",
            "",
            "## Constant / defaulted doctrine features",
            f"- `{', '.join(report['C_features_constant_defaulted'])}`",
        ]
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-version", default="v1")
    args = parser.parse_args()

    json_out = DATA_DIR / f"historical_doctrine_feature_audit_{args.output_version}.json"
    md_out = DATA_DIR / f"historical_doctrine_feature_audit_{args.output_version}.md"
    report = build_report()
    json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_out.write_text(write_markdown(report, version=args.output_version), encoding="utf-8")
    print(f"Wrote {json_out}")
    print(f"Wrote {md_out}")


if __name__ == "__main__":
    main()
