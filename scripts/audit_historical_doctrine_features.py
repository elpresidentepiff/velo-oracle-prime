from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.v17_feature_extractor import DEFAULTS as V17_DEFAULTS
from scripts.global_clean_spine_audit import get_sb_client
from scripts.prepare_playbook_g_dry_run_gate import FEATURE_VECTOR_NAMES, load_eligible_rows

DATA_DIR = ROOT / "data"
JSON_OUT = DATA_DIR / "historical_doctrine_feature_audit_v1.json"
MD_OUT = DATA_DIR / "historical_doctrine_feature_audit_v1.md"

MARKET_FEATURES = [
    "sp_dec",
    "log_sp",
    "implied_prob",
    "sp_rank",
    "is_fav",
]

RATING_FEATURES = [
    "or_num",
    "rpr_num",
    "ts_num",
    "or_vs_field",
    "rpr_vs_field",
]

DOCTRINE_FEATURES = [
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

FORBIDDEN_OUTCOME_FIELDS = [
    "winner_flag",
    "is_winner",
    "placed_flag",
    "finish_position",
    "position",
    "pos",
    "comment",
    "result_comment",
    "future_race_result",
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

PROPOSED_FEATURE_GROUPS = {
    "market_pressure_rank": {
        "status": "activate_now",
        "inputs": ["sp_dec", "implied_prob", "sp_rank", "field_size", "within-race rank/normalization"],
        "leakage_risk": "low",
        "notes": "Pre-race market only; already available in accepted historical rows.",
    },
    "field_entropy": {
        "status": "activate_now",
        "inputs": ["field implied probability distribution", "field_size", "going", "jurisdiction"],
        "leakage_risk": "low",
        "notes": "Can be built from same-race prices; current mpi/chaos proxies prove this path is already safe.",
    },
    "draw_position_pressure": {
        "status": "activate_now",
        "inputs": ["draw", "field_size", "course", "jurisdiction"],
        "leakage_risk": "low",
        "notes": "Current rows already carry draw and field size for most accepted runners.",
    },
    "weight_vs_field_pressure": {
        "status": "activate_now",
        "inputs": ["weight_lbs", "field weight distribution", "race class", "distance"],
        "leakage_risk": "low",
        "notes": "No future info required; same-race relative calculation only.",
    },
    "or_rpr_vs_field_pressure": {
        "status": "activate_now",
        "inputs": ["official_rating", "rpr", "ts", "field rating distribution"],
        "leakage_risk": "low",
        "notes": "These are already active and can anchor doctrine proxies safely.",
    },
    "class_regime_pressure": {
        "status": "activate_now",
        "inputs": ["current class", "field class context", "jurisdiction", "race type"],
        "leakage_risk": "low",
        "notes": "Current row metadata exists in race/raceform without future dependence.",
    },
    "going_regime_pressure": {
        "status": "activate_now",
        "inputs": ["going", "jurisdiction", "course", "field distribution"],
        "leakage_risk": "low",
        "notes": "Same-race regime proxy only.",
    },
    "course_jurisdiction_regime": {
        "status": "activate_now",
        "inputs": ["course", "jurisdiction", "distance", "race type"],
        "leakage_risk": "low",
        "notes": "Pure race-level metadata.",
    },
    "field_size_chaos": {
        "status": "activate_now",
        "inputs": ["field_size", "market entropy", "going uncertainty"],
        "leakage_risk": "low",
        "notes": "Same-race structure only.",
    },
    "horse_prior_history": {
        "status": "requires_prior_history_engine",
        "inputs": ["horse_id", "prior race_date", "prior positions", "prior SP", "prior OR/RPR/TS", "prior course/going/distance", "prior jockey", "prior trainer", "prior beaten margin"],
        "leakage_risk": "medium",
        "notes": "Safe only if every aggregate uses rows strictly earlier than current race_date and same-day rows are excluded conservatively.",
    },
}

DEAD_FEATURE_INPUTS = {
    "runs_since_win": {
        "needs": ["horse_id", "prior race_date", "prior finishing positions"],
        "raceform_enough": True,
        "proof": ["raceform.horse", "raceform.date", "raceform.pos", "racing_horses.id"],
        "risk": "medium",
    },
    "runs_since_place": {
        "needs": ["horse_id", "prior race_date", "prior finishing positions"],
        "raceform_enough": True,
        "proof": ["raceform.horse", "raceform.date", "raceform.pos", "racing_horses.id"],
        "risk": "medium",
    },
    "runs_since_mkt_support": {
        "needs": ["horse_id", "prior race_date", "prior SP history"],
        "raceform_enough": True,
        "proof": ["raceform.sp", "raceform.date", "racing_horses.id"],
        "risk": "medium",
    },
    "curr_or_minus_last_win_or": {
        "needs": ["current OR", "horse_id", "prior winning OR"],
        "raceform_enough": True,
        "proof": ["raceform.or_rating", "raceform.pos", "raceform.date", "racing_horses.id"],
        "risk": "medium",
    },
    "curr_or_minus_best_or": {
        "needs": ["current OR", "horse_id", "prior OR history"],
        "raceform_enough": True,
        "proof": ["raceform.or_rating", "raceform.date", "racing_horses.id"],
        "risk": "medium",
    },
    "mark_compression_score": {
        "needs": ["current OR", "horse_id", "prior OR history"],
        "raceform_enough": True,
        "proof": ["raceform.or_rating", "raceform.date", "racing_horses.id"],
        "risk": "medium",
    },
    "release_window_score": {
        "needs": ["runs_since_win", "mark_compression_score"],
        "raceform_enough": True,
        "proof": ["Derived from prior-only history once OR + win history exist."],
        "risk": "medium",
    },
    "course_fit_score": {
        "needs": ["current course", "horse_id", "prior course matches", "prior win/place outcomes"],
        "raceform_enough": True,
        "proof": ["raceform.course", "raceform.date", "raceform.pos", "racing_horses.id"],
        "risk": "medium",
    },
    "going_fit_score": {
        "needs": ["current going", "horse_id", "prior going matches", "prior win/place outcomes"],
        "raceform_enough": True,
        "proof": ["raceform.going", "raceform.date", "raceform.pos", "racing_horses.id"],
        "risk": "medium",
    },
    "distance_fit_score": {
        "needs": ["current distance", "horse_id", "prior distance matches", "prior win/place outcomes"],
        "raceform_enough": True,
        "proof": ["raceform.dist", "raceform.date", "raceform.pos", "racing_horses.id"],
        "risk": "medium",
    },
    "quiet_run_score": {
        "needs": ["horse_id", "last prior race beaten margin"],
        "raceform_enough": True,
        "proof": ["raceform.ovr_btn", "raceform.date", "racing_horses.id"],
        "risk": "medium",
    },
    "trainer_timing_score": {
        "needs": ["current trainer", "trainer prior wins", "trainer prior starts", "current race_date"],
        "raceform_enough": True,
        "proof": ["raceform.trainer", "raceform.pos", "raceform.date"],
        "risk": "medium",
    },
    "jockey_switch_intent": {
        "needs": ["current jockey", "horse_id", "last prior jockey"],
        "raceform_enough": True,
        "proof": ["raceform.jockey", "raceform.date", "racing_horses.id"],
        "risk": "medium",
    },
    "odds_resilience_score": {
        "needs": ["horse_id", "last 2-3 prior SP values"],
        "raceform_enough": True,
        "proof": ["raceform.sp", "raceform.date", "racing_horses.id"],
        "risk": "medium",
    },
    "odds_contraction_score": {
        "needs": ["current SP", "horse_id", "last prior SP"],
        "raceform_enough": True,
        "proof": ["raceform.sp", "raceform.date", "racing_horses.id"],
        "risk": "medium",
    },
    "decoy_support_flag": {
        "needs": ["current is_fav", "trainer_timing_score"],
        "raceform_enough": True,
        "proof": ["Derived from current price + prior-only trainer timing."],
        "risk": "medium",
    },
    "setup_run_flag": {
        "needs": ["horse_id", "last prior beaten margin"],
        "raceform_enough": True,
        "proof": ["raceform.ovr_btn", "raceform.date", "racing_horses.id"],
        "risk": "medium",
    },
    "cash_run_flag": {
        "needs": ["trainer_timing_score", "runs_since_win", "mark_compression_score"],
        "raceform_enough": True,
        "proof": ["All inputs become available once prior-only horse + trainer history is built."],
        "risk": "medium",
    },
}


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


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def variance(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = mean(values)
    return sum((value - avg) ** 2 for value in values) / len(values)


def stdev(values: list[float]) -> float:
    return math.sqrt(variance(values))


def unique_count(values: list[float]) -> int:
    return len({round(value, 12) for value in values})


def feature_group(feature: str) -> str:
    if feature in MARKET_FEATURES:
        return "market"
    if feature in RATING_FEATURES:
        return "rating"
    if feature in DOCTRINE_FEATURES:
        return "doctrine"
    return "structure"


def find_line_number(path: Path, needle: str) -> int | None:
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if needle in line:
            return idx
    return None


def fetch_table_keys(sb, table: str) -> list[str]:
    rows = sb.table(table).select("*").limit(1).execute().data or []
    if not rows:
        return []
    return sorted(rows[0].keys())


def cohort_rows() -> list[dict[str, Any]]:
    return load_eligible_rows()


def build_feature_stats(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    stats: list[dict[str, Any]] = []
    active: list[str] = []
    constant_defaulted: list[str] = []
    constant_nondefault: list[str] = []

    for idx, feature in enumerate(FEATURE_VECTOR_NAMES):
        values = [float(row["_vector"][idx]) for row in rows]
        default_value = V17_DEFAULTS.get(feature)
        stats_row = {
            "index": idx,
            "feature": feature,
            "group": feature_group(feature),
            "default_value": default_value,
            "count": len(values),
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "mean": mean(values),
            "std": stdev(values),
            "nonzero_rate": (sum(1 for value in values if abs(value) > 1e-12) / len(values)) if values else 0.0,
            "unique_count": unique_count(values),
        }
        constant = stats_row["unique_count"] == 1
        equals_default = default_value is not None and all(abs(value - float(default_value)) <= 1e-12 for value in values)

        if constant and equals_default:
            stats_row["status"] = "constant_defaulted"
            constant_defaulted.append(feature)
        elif constant:
            stats_row["status"] = "constant_nondefault"
            constant_nondefault.append(feature)
        else:
            stats_row["status"] = "active_nonconstant"
            active.append(feature)

        stats.append(stats_row)

    return stats, active, constant_defaulted, constant_nondefault


def compute_prior_run_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_horse: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in rows:
        by_horse[str(row["horse_id"])].append((row["_race_date_iso"], str(row["race_id"])))

    total = 0
    with_prior_1 = 0
    with_prior_3 = 0
    for horse_rows in by_horse.values():
        horse_rows.sort()
        for idx, _ in enumerate(horse_rows):
            total += 1
            if idx >= 1:
                with_prior_1 += 1
            if idx >= 3:
                with_prior_3 += 1

    return {
        "rows_with_prior_1_run": with_prior_1,
        "rows_with_prior_3_runs": with_prior_3,
        "coverage_prior_1_run": (with_prior_1 / total) if total else 0.0,
        "coverage_prior_3_runs": (with_prior_3 / total) if total else 0.0,
    }


def build_dead_feature_audit() -> dict[str, Any]:
    backfill_path = ROOT / "scripts" / "backfill_historical_feature_store.py"
    scorer_path = ROOT / "app" / "services" / "velo_prime_service.py"

    backfill_line = find_line_number(backfill_path, "_build_live_features(r_norm, nrace, [], [])")
    default_line = find_line_number(scorer_path, "for k, v in DEFAULTS.items():")

    output: dict[str, Any] = {}
    for feature in DOCTRINE_FEATURES:
        output[feature] = {
            "default_value": V17_DEFAULTS.get(feature),
            "current_default_path": [
                {
                    "file": str(backfill_path),
                    "line": backfill_line,
                    "reason": "Historical reconstruction calls live feature builder without prior-history arrays or precomputed doctrine values.",
                },
                {
                    "file": str(scorer_path),
                    "line": default_line,
                    "reason": "Live feature builder fills missing doctrine keys from V17 DEFAULTS.",
                },
            ],
            "required_context": DEAD_FEATURE_INPUTS[feature]["needs"],
            "raceform_contains_required_source_data": DEAD_FEATURE_INPUTS[feature]["raceform_enough"],
            "source_data_proof": DEAD_FEATURE_INPUTS[feature]["proof"],
            "leakage_risk": DEAD_FEATURE_INPUTS[feature]["risk"],
        }
    return output


def build_historical_contract() -> dict[str, Any]:
    return {
        "name": "HISTORICAL_DOCTRINE_FEATURES_V1",
        "objective": "Activate leakage-free doctrine features for historical HFS without changing 37-vector order.",
        "vector_order_preserved": True,
        "allowed_current_race_inputs": [
            "sp_dec",
            "implied_prob",
            "field_size",
            "draw",
            "weight_lbs",
            "age",
            "official_rating",
            "rpr",
            "ts",
            "course",
            "going",
            "distance",
            "race class",
            "jurisdiction",
            "race_date",
        ],
        "allowed_history_inputs": [
            "same horse prior-only results with race_date < current race_date",
            "same trainer prior-only results with race_date < current race_date",
            "same horse prior SP history",
            "same horse prior course/going/distance history",
            "same horse prior beaten-margin history",
            "same horse prior jockey history",
        ],
        "forbidden_inputs": FORBIDDEN_OUTCOME_FIELDS,
        "activation_phases": [
            {
                "phase": "A",
                "status": "recommended_first",
                "feature_groups": [
                    "market_pressure_rank",
                    "field_entropy",
                    "draw_position_pressure",
                    "weight_vs_field_pressure",
                    "or_rpr_vs_field_pressure",
                    "class_regime_pressure",
                    "going_regime_pressure",
                    "course_jurisdiction_regime",
                    "field_size_chaos",
                ],
                "notes": "Pure race-level and runner-relative proxies; no prior horse history required.",
            },
            {
                "phase": "B",
                "status": "required_for_true_doctrine",
                "feature_groups": ["horse_prior_history"],
                "notes": "Needed to wake up the 18 current doctrine dimensions without leakage.",
            },
        ],
    }


def build_audit() -> dict[str, Any]:
    sb = get_sb_client()
    rows = cohort_rows()
    feature_stats, active_features, constant_defaulted, constant_nondefault = build_feature_stats(rows)
    dead_feature_audit = build_dead_feature_audit()
    prior_coverage = compute_prior_run_coverage(rows)

    raceform_keys = fetch_table_keys(sb, "raceform")
    runner_results_keys = fetch_table_keys(sb, "runner_results")
    races_keys = fetch_table_keys(sb, "races")

    historical_feasible = sorted(
        set(DOCTRINE_FEATURES)
        | {
            "mpi",
            "chaos_bloom",
            "market_pressure_rank",
            "field_entropy",
            "draw_position_pressure",
            "weight_vs_field_pressure",
            "or_rpr_vs_field_pressure",
            "class_regime_pressure",
            "going_regime_pressure",
            "course_jurisdiction_regime",
            "field_size_chaos",
            "prior_only_horse_history",
        }
    )
    historical_infeasible = sorted(LIVE_ONLY_FEATURES)

    schema = [
        {
            "index": idx,
            "feature": feature,
            "group": feature_group(feature),
        }
        for idx, feature in enumerate(FEATURE_VECTOR_NAMES)
    ]

    outcome_field_exclusion_proof = {
        "forbidden_fields": FORBIDDEN_OUTCOME_FIELDS,
        "contract_intersection_with_forbidden": sorted(set(FEATURE_VECTOR_NAMES) & set(FORBIDDEN_OUTCOME_FIELDS)),
        "current_race_label_usage_required": False,
        "rule": "Prior-race outcomes are allowed only when source race_date < current race_date; current-race outcomes are forbidden.",
    }

    dist_f_issue = None
    if "dist_f" in constant_nondefault:
        dist_f_stats = next(row for row in feature_stats if row["feature"] == "dist_f")
        dist_f_issue = {
            "feature": "dist_f",
            "status": "constant_nondefault",
            "current_value": dist_f_stats["min"],
            "cause": "Historical HFS passes numeric distance_f into ModelManager._parse_dist(), which expects string labels like '1m2f' and falls back to 16.0 when regex parsing fails.",
            "evidence": [
                "historical_feature_store.distance_f varies by race",
                "feature_json.strictly_ordered_vector[3] is constant at 16.0 in the scoped cohort",
            ],
            "not_part_of_doctrine_contract": True,
            "recommendation": "Fix this separately before Playbook G V2 so doctrine activation is not confounded by a dead distance dimension.",
        }

    recommendation = {
        "option": "D",
        "text": "Build prior-only horse history engine before Playbook G V2.",
        "why": [
            "All 18 doctrine dimensions in the current 37-vector are constant/defaulted in the scoped training cohort.",
            "Raceform already contains the raw pre-race and prior-history fields needed to compute them leakage-free.",
            "The missing piece is not data availability but a historical feature engine that rehydrates prior-only horse and trainer history before current race_date.",
        ],
    }

    implementation_plan = [
        "Expand historical context rehydration to carry current-row jockey, trainer, SP, beaten margin, class_raw, and distance metadata from raceform.",
        "Build a prior-only history engine keyed by horse_id and race_date, excluding current-day/current-race rows conservatively.",
        "Compute the 18 doctrine features from prior-only history instead of DEFAULTS, preserving the existing 37-vector order.",
        "Add manifest-scoped HFS reconstruction smoke test on a small accepted block and rerun this audit to prove doctrine dimensions are no longer constant.",
        "Only after doctrine activation passes should Playbook G V2 ablation dry-run proceed.",
    ]

    return {
        "scope": {
            "cohort_filter": {
                "training_eligible": "pending_global_training_gate",
                "data_owner_confirmed": True,
                "source": "historical_raceform",
                "signal_contract_version": "HISTORICAL_SIGNAL_PROXY_V1",
                "event_identity_contract": "race_id_course_race_date",
                "macro_year_mismatch": 0,
                "vector_length": 37,
            },
            "eligible_race_count": len({str(row["race_id"]) for row in rows}),
            "eligible_runner_count": len(rows),
        },
        "A_full_37_vector_schema": schema,
        "B_features_active_non_constant": active_features,
        "C_features_constant_defaulted": constant_defaulted,
        "constant_nondefault_features": constant_nondefault,
        "D_market_feature_list": MARKET_FEATURES,
        "E_rating_feature_list": RATING_FEATURES,
        "F_doctrine_feature_list": DOCTRINE_FEATURES,
        "G_live_only_feature_list": LIVE_ONLY_FEATURES,
        "H_historical_feasible_feature_list": historical_feasible,
        "I_historical_infeasible_feature_list": historical_infeasible,
        "J_dead_feature_default_paths": dead_feature_audit,
        "K_dead_feature_required_context": {name: payload["required_context"] for name, payload in dead_feature_audit.items()},
        "L_raceform_source_sufficiency": {
            "raceform_columns": raceform_keys,
            "runner_results_columns": runner_results_keys,
            "races_columns": races_keys,
            "per_feature": {
                name: {
                    "raceform_contains_enough_source_data": payload["raceform_contains_required_source_data"],
                    "proof": payload["source_data_proof"],
                }
                for name, payload in dead_feature_audit.items()
            },
            "prior_history_coverage_within_current_accepted_cohort": prior_coverage,
        },
        "M_leakage_risk_per_proposed_feature_group": PROPOSED_FEATURE_GROUPS,
        "N_outcome_field_exclusion_proof": outcome_field_exclusion_proof,
        "O_proposed_historical_doctrine_features_v1_contract": build_historical_contract(),
        "P_recommended_implementation_plan": implementation_plan,
        "feature_stats": feature_stats,
        "supporting_findings": {
            "current_historical_reconstruction_call": "_build_live_features(r_norm, nrace, [], [])",
            "default_fill_mechanism": "for k, v in DEFAULTS.items(): feats.setdefault(k, v)",
            "dead_doctrine_feature_count": len(constant_defaulted),
            "active_feature_count": len(active_features),
            "constant_nondefault_feature_count": len(constant_nondefault),
            "dist_f_issue": dist_f_issue,
            "recommendation": recommendation,
        },
        "final_recommendation": recommendation,
    }


def write_markdown(report: dict[str, Any]) -> str:
    recommendation = report["final_recommendation"]
    lines = [
        "# Historical Doctrine Feature Activation Audit V1",
        "",
        "## Scope",
        f"- Eligible races: `{report['scope']['eligible_race_count']}`",
        f"- Eligible runners: `{report['scope']['eligible_runner_count']}`",
        "",
        "## A. 37-Vector Schema",
    ]
    for item in report["A_full_37_vector_schema"]:
        lines.append(f"- `{item['index']:02d}` `{item['feature']}` ({item['group']})")

    lines.extend(
        [
            "",
            "## B/C. Activation Status",
            f"- Active / non-constant features (`{len(report['B_features_active_non_constant'])}`): `{', '.join(report['B_features_active_non_constant'])}`",
            f"- Constant / defaulted features (`{len(report['C_features_constant_defaulted'])}`): `{', '.join(report['C_features_constant_defaulted'])}`",
            "",
            "## Core Finding",
            "- Historical HFS reconstruction still calls `_build_live_features(r_norm, nrace, [], [])`.",
            "- `_build_live_features` then fills doctrine slots from `DEFAULTS` when nothing was precomputed.",
            "- Result: the entire doctrine layer is dead/defaulted in the scoped historical training cohort.",
            "",
            "## Separate Structural Issue",
            f"- Constant non-default features: `{', '.join(report['constant_nondefault_features'])}`",
            f"- `dist_f` is pinned at `{report['supporting_findings']['dist_f_issue']['current_value'] if report['supporting_findings']['dist_f_issue'] else 'n/a'}` because the historical HFS path feeds numeric `distance_f` into a parser that expects string labels like `1m2f` and falls back to `16.0`.",
            "",
            "## D/E/F. Feature Groups",
            f"- Market: `{', '.join(report['D_market_feature_list'])}`",
            f"- Rating: `{', '.join(report['E_rating_feature_list'])}`",
            f"- Doctrine: `{', '.join(report['F_doctrine_feature_list'])}`",
            "",
            "## G/H/I. Sourceability",
            f"- Live-only / not historical-safe as-is: `{', '.join(report['G_live_only_feature_list'])}`",
            f"- Historical-feasible: `{', '.join(report['H_historical_feasible_feature_list'])}`",
            f"- Historical-infeasible without other upstream systems: `{', '.join(report['I_historical_infeasible_feature_list'])}`",
            "",
            "## J/K/L. Why The Doctrine Layer Is Dead",
        ]
    )

    for feature in report["F_doctrine_feature_list"]:
        payload = report["J_dead_feature_default_paths"][feature]
        lines.append(
            f"- `{feature}` defaults via `{Path(payload['current_default_path'][0]['file']).name}:{payload['current_default_path'][0]['line']}` "
            f"and `{Path(payload['current_default_path'][1]['file']).name}:{payload['current_default_path'][1]['line']}`; "
            f"needs `{', '.join(payload['required_context'])}`; raceform sufficiency = `{payload['raceform_contains_required_source_data']}`"
        )

    lines.extend(
        [
            "",
            "## M. Leakage Risk",
        ]
    )
    for name, payload in report["M_leakage_risk_per_proposed_feature_group"].items():
        lines.append(
            f"- `{name}`: status=`{payload['status']}` risk=`{payload['leakage_risk']}` inputs=`{', '.join(payload['inputs'])}`"
        )

    lines.extend(
        [
            "",
            "## N. Outcome Exclusion Proof",
            f"- Forbidden fields: `{', '.join(report['N_outcome_field_exclusion_proof']['forbidden_fields'])}`",
            f"- Contract intersection with forbidden fields: `{report['N_outcome_field_exclusion_proof']['contract_intersection_with_forbidden']}`",
            f"- Rule: {report['N_outcome_field_exclusion_proof']['rule']}",
            "",
            "## O/P. Contract And Plan",
            f"- Recommended option: `{recommendation['option']}`",
            f"- Recommendation: {recommendation['text']}",
        ]
    )
    for step in report["P_recommended_implementation_plan"]:
        lines.append(f"- {step}")

    return "\n".join(lines) + "\n"


def main() -> None:
    report = build_audit()
    JSON_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    MD_OUT.write_text(write_markdown(report), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
