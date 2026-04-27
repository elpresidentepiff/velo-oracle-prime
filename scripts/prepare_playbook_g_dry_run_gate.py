from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.global_clean_spine_audit import get_sb_client, paged_select, parse_date_str

DATA_DIR = ROOT / "data"

RECONSTRUCTION_VERSION = "V17_B1"
TRAINING_ELIGIBLE = "pending_global_training_gate"
HISTORICAL_SOURCE = "historical_raceform"
SIGNAL_CONTRACT_VERSION = "HISTORICAL_SIGNAL_PROXY_V1"
EVENT_IDENTITY_CONTRACT = "race_id_course_race_date"

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

MARKET_ONLY_FEATURES = ["sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav"]
FORBIDDEN_OUTCOME_FEATURES = [
    "winner_flag",
    "placed_flag",
    "finish_position",
    "position",
    "pos",
    "result",
    "outcome",
]
FORBIDDEN_MODEL_AND_META_KEYS = [
    "sqpe_v17_prob",
    "velo_prime_prob",
    "g_base_prob",
    "place_prob",
    "release_day_prob",
    "longshot_prob",
    "comment_intel_score",
    "improvement_score",
    "market_deception_score",
    "story_anchor",
    "narrative_disruption",
    "g_shadow_flags",
    "g_shadow_horse_id",
    "g_shadow_mode",
    "g_shadow_multiplier",
    "sentient_aggression_level",
    "sentient_modifier_applied",
    "sentient_modifier_mode",
    "sentient_races_observed",
    "sentient_state_loaded",
    "sentient_state_source",
    "tie_gate_signal_count",
    "tie_gate_signals",
    "verdict_flags",
]


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


def quantile_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {
            "min": None,
            "p10": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p90": None,
            "max": None,
            "mean": None,
        }
    ordered = sorted(values)

    def q(p: float) -> float:
        idx = (len(ordered) - 1) * p
        lo = math.floor(idx)
        hi = math.ceil(idx)
        if lo == hi:
            return ordered[lo]
        frac = idx - lo
        return ordered[lo] * (1 - frac) + ordered[hi] * frac

    return {
        "min": ordered[0],
        "p10": q(0.10),
        "p25": q(0.25),
        "median": q(0.50),
        "p75": q(0.75),
        "p90": q(0.90),
        "max": ordered[-1],
        "mean": sum(ordered) / len(ordered),
    }


def split_name(year: int) -> str:
    if 2017 <= year <= 2020:
        return "train"
    if 2021 <= year <= 2022:
        return "validation"
    return "test"


def load_eligible_rows() -> list[dict[str, Any]]:
    sb = get_sb_client()
    rows = paged_select(
        sb,
        "historical_feature_store",
        "race_id,horse_id,race_date,course,jurisdiction,winner_flag,finish_position,sp_dec,implied_prob,mpi,chaos_bloom,feature_json,reconstruction_version",
        page_size=1000,
    )

    accepted: list[dict[str, Any]] = []
    for row in rows:
        if row.get("reconstruction_version") != RECONSTRUCTION_VERSION:
            continue
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        race_date = parse_date_str(row.get("race_date"))
        vector = feature_json.get("strictly_ordered_vector")

        if not isinstance(vector, list) or len(vector) != len(FEATURE_VECTOR_NAMES):
            continue
        if feature_json.get("training_eligible") != TRAINING_ELIGIBLE:
            continue
        if feature_json.get("data_owner_confirmed") is not True:
            continue
        if feature_json.get("source") != HISTORICAL_SOURCE:
            continue
        if feature_json.get("signal_contract_version") != SIGNAL_CONTRACT_VERSION:
            continue
        if feature_json.get("event_identity_contract") != EVENT_IDENTITY_CONTRACT:
            continue
        if race_date is None:
            continue
        if feature_json.get("macro_year_used") != race_date.year:
            continue

        accepted.append(
            {
                **row,
                "_feature_json": feature_json,
                "_vector": vector,
                "_race_year": race_date.year,
                "_race_date_iso": race_date.date().isoformat(),
            }
        )
    return accepted


def build_race_groups(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["race_id"])].append(row)
    return grouped


def compute_grouped_baseline_metrics(
    race_groups: dict[str, list[dict[str, Any]]],
    baseline_name: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for scope in ("train", "validation", "test", "all"):
        runner_labels: list[int] = []
        runner_probs: list[float] = []
        brier_terms: list[float] = []
        winner_log_loss_sum = 0.0
        top1_hits = 0
        top3_hits = 0
        race_count = 0

        for race_rows in race_groups.values():
            year = race_rows[0]["_race_year"]
            if scope != "all" and split_name(year) != scope:
                continue

            race_count += 1
            ordered = sorted(race_rows, key=lambda row: (float(row.get("sp_dec") or 999999.0), str(row.get("horse_id"))))
            if baseline_name == "market_implied_normalized":
                raw_scores = [safe_float(row.get("implied_prob")) or 0.0 for row in ordered]
            elif baseline_name == "sp_rank_reciprocal":
                raw_scores = [1.0 / (idx + 1) for idx, _ in enumerate(ordered)]
            else:
                raise ValueError(f"Unsupported baseline {baseline_name}")

            total = sum(raw_scores) or 1.0
            probs = [score / total for score in raw_scores]
            winner_index: int | None = None
            for idx, row in enumerate(ordered):
                label = 1 if row.get("winner_flag") else 0
                prob = probs[idx]
                runner_labels.append(label)
                runner_probs.append(prob)
                brier_terms.append((label - prob) ** 2)
                if label == 1:
                    winner_index = idx
                    winner_log_loss_sum += -math.log(min(max(prob, 1e-15), 1 - 1e-15))
            if winner_index == 0:
                top1_hits += 1
            if winner_index is not None and winner_index < 3:
                top3_hits += 1

        runner_log_loss = None
        if runner_labels:
            total = 0.0
            for label, prob in zip(runner_labels, runner_probs):
                p = min(max(prob, 1e-15), 1 - 1e-15)
                total += -(label * math.log(p) + (1 - label) * math.log(1 - p))
            runner_log_loss = total / len(runner_labels)

        result[scope] = {
            "race_count": race_count,
            "runner_log_loss": runner_log_loss,
            "winner_multiclass_log_loss": (winner_log_loss_sum / race_count) if race_count else None,
            "brier_score": (sum(brier_terms) / len(brier_terms)) if brier_terms else None,
            "top_1_winner_hit_rate": (top1_hits / race_count) if race_count else None,
            "top_3_containment": (top3_hits / race_count) if race_count else None,
        }

    return result


def compute_gate_report() -> dict[str, Any]:
    rows = load_eligible_rows()
    race_groups = build_race_groups(rows)
    race_meta = {
        race_id: {
            "race_year": group[0]["_race_year"],
            "jurisdiction": group[0].get("jurisdiction") or "UNKNOWN",
            "course": group[0].get("course") or "UNKNOWN",
            "runner_count": len(group),
            "winner_count": sum(1 for row in group if row.get("winner_flag")),
        }
        for race_id, group in race_groups.items()
    }

    year_race_counts = Counter(meta["race_year"] for meta in race_meta.values())
    year_runner_counts = Counter(row["_race_year"] for row in rows)
    jurisdiction_race_counts = Counter(meta["jurisdiction"] for meta in race_meta.values())
    jurisdiction_runner_counts = Counter(row.get("jurisdiction") or "UNKNOWN" for row in rows)
    course_race_counts = Counter(meta["course"] for meta in race_meta.values())
    course_runner_counts = Counter(row.get("course") or "UNKNOWN" for row in rows)
    runner_counts = [meta["runner_count"] for meta in race_meta.values()]

    winners = sum(1 for row in rows if row.get("winner_flag"))
    winner_rate = winners / len(rows) if rows else 0.0

    sp_values = [value for value in (safe_float(row.get("sp_dec")) for row in rows) if value is not None]
    implied_prob_values = [value for value in (safe_float(row.get("implied_prob")) for row in rows) if value is not None]
    mpi_values = [value for value in (safe_float(row.get("mpi")) for row in rows) if value is not None]
    chaos_values = [value for value in (safe_float(row.get("chaos_bloom")) for row in rows) if value is not None]

    vector_nan_count = 0
    vector_inf_count = 0
    rows_with_nan = 0
    rows_with_inf = 0
    feature_json_keys: set[str] = set()
    macro_context_versions = Counter()
    for row in rows:
        feature_json = row["_feature_json"]
        feature_json_keys.update(feature_json.keys())
        macro_context_versions[str(feature_json.get("macro_context_version"))] += 1
        has_nan = False
        has_inf = False
        for value in row["_vector"]:
            number = safe_float(value)
            if number is None:
                if value is None or (isinstance(value, float) and math.isnan(value)):
                    vector_nan_count += 1
                    has_nan = True
                else:
                    try:
                        probe = float(value)
                    except (TypeError, ValueError):
                        vector_nan_count += 1
                        has_nan = True
                    else:
                        if math.isnan(probe):
                            vector_nan_count += 1
                            has_nan = True
                        elif math.isinf(probe):
                            vector_inf_count += 1
                            has_inf = True
            elif math.isinf(number):
                vector_inf_count += 1
                has_inf = True
        rows_with_nan += int(has_nan)
        rows_with_inf += int(has_inf)

    bad_winner_races = [race_id for race_id, meta in race_meta.items() if meta["winner_count"] != 1]
    market_baseline = compute_grouped_baseline_metrics(race_groups, "market_implied_normalized")
    sp_rank_baseline = compute_grouped_baseline_metrics(race_groups, "sp_rank_reciprocal")

    split_summary: dict[str, dict[str, Any]] = {}
    split_years = {
        "train": [2017, 2018, 2019, 2020],
        "validation": [2021, 2022],
        "test": [2023, 2024, 2025],
    }
    for name, years in split_years.items():
        split_race_ids = [race_id for race_id, meta in race_meta.items() if meta["race_year"] in years]
        split_runners = sum(race_meta[race_id]["runner_count"] for race_id in split_race_ids)
        split_summary[name] = {
            "years": years,
            "race_count": len(split_race_ids),
            "runner_count": split_runners,
            "jurisdiction_breakdown": dict(
                Counter(race_meta[race_id]["jurisdiction"] for race_id in split_race_ids)
            ),
        }

    report = {
        "gate_version": "v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "no_training_executed": True,
        "scope_filters": {
            "training_eligible": TRAINING_ELIGIBLE,
            "data_owner_confirmed": True,
            "source": HISTORICAL_SOURCE,
            "signal_contract_version": SIGNAL_CONTRACT_VERSION,
            "event_identity_contract": EVENT_IDENTITY_CONTRACT,
            "macro_year_used_equals_race_year": True,
            "vector_length": len(FEATURE_VECTOR_NAMES),
        },
        "A_eligible_race_count": len(race_groups),
        "B_eligible_runner_count": len(rows),
        "C_year_breakdown": {
            "race_counts": dict(sorted(year_race_counts.items())),
            "runner_counts": dict(sorted(year_runner_counts.items())),
        },
        "D_jurisdiction_breakdown": {
            "race_counts": dict(jurisdiction_race_counts),
            "runner_counts": dict(jurisdiction_runner_counts),
        },
        "E_course_breakdown": {
            "race_counts_top_50": dict(course_race_counts.most_common(50)),
            "runner_counts_top_50": dict(course_runner_counts.most_common(50)),
        },
        "F_runners_per_race": {
            "average": sum(runner_counts) / len(runner_counts) if runner_counts else None,
            "min": min(runner_counts) if runner_counts else None,
            "max": max(runner_counts) if runner_counts else None,
        },
        "G_winner_label_distribution": {
            "positive_winners": winners,
            "negative_non_winners": len(rows) - winners,
            "positive_rate": winner_rate,
            "per_race_one_hot_ok": len(bad_winner_races) == 0,
        },
        "H_sp_implied_probability_distribution": {
            "sp_dec": quantile_summary(sp_values),
            "implied_prob": quantile_summary(implied_prob_values),
        },
        "I_MPI_distribution": quantile_summary(mpi_values),
        "J_chaos_bloom_distribution": quantile_summary(chaos_values),
        "K_feature_vector_dimension_check": {
            "feature_count": len(FEATURE_VECTOR_NAMES),
            "feature_names": FEATURE_VECTOR_NAMES,
            "vector_length_distribution": {str(len(FEATURE_VECTOR_NAMES)): len(rows)},
            "vector_nan_count": vector_nan_count,
            "vector_inf_count": vector_inf_count,
            "rows_with_nan": rows_with_nan,
            "rows_with_inf": rows_with_inf,
            "macro_context_version_distribution": dict(macro_context_versions),
        },
        "L_leakage_exclusion_check": {
            "training_matrix_source": "feature_json.strictly_ordered_vector only",
            "forbidden_outcome_feature_intersection": sorted(set(FORBIDDEN_OUTCOME_FEATURES).intersection(FEATURE_VECTOR_NAMES)),
            "forbidden_model_meta_feature_intersection": sorted(set(FORBIDDEN_MODEL_AND_META_KEYS).intersection(FEATURE_VECTOR_NAMES)),
            "model_output_or_meta_keys_present_outside_vector": sorted(set(FORBIDDEN_MODEL_AND_META_KEYS).intersection(feature_json_keys)),
            "status": "pass" if not set(FORBIDDEN_OUTCOME_FEATURES).intersection(FEATURE_VECTOR_NAMES) and not set(FORBIDDEN_MODEL_AND_META_KEYS).intersection(FEATURE_VECTOR_NAMES) else "fail",
            "note": "The first offline dry-run must train only on the 37-vector and must exclude existing model outputs, shadow state, verdict metadata, and narrative fields.",
        },
        "M_outcome_field_exclusion_check": {
            "label_columns_reserved_for_targets_or_eval_only": ["winner_flag", "placed_flag", "finish_position"],
            "top_level_outcome_fields_excluded_from_training_matrix": True,
            "per_race_winner_parity_ok": len(bad_winner_races) == 0,
            "bad_race_sample": bad_winner_races[:10],
            "status": "pass" if len(bad_winner_races) == 0 else "fail",
        },
        "N_proposed_train_validation_test_split": {
            "strategy": "grouped chronological split by race_id with no cross-race leakage",
            "rationale": "Train on the dense 2017-2020 spine, tune on 2021-2022, and hold out 2023-2025 so the final test remains genuinely out of time and includes the explicit 2025 proxy-macro slice.",
            "splits": split_summary,
            "secondary_recommendation": "Run an anchored rolling-origin backtest by year in addition to the primary holdout because the late years are sparse and FR-heavy.",
        },
        "O_proposed_baseline_models": {
            "mandatory": [
                {
                    "name": "market_implied_probability_baseline",
                    "inputs": ["implied_prob"],
                    "prediction_rule": "Normalize implied_prob within each race to produce a proper winner distribution.",
                    "reference_metrics": market_baseline,
                },
                {
                    "name": "sp_rank_baseline",
                    "inputs": ["sp_rank"],
                    "prediction_rule": "Convert SP rank to reciprocal-rank weights within each race.",
                    "reference_metrics": sp_rank_baseline,
                },
                {
                    "name": "simple_logistic_baseline",
                    "inputs": MARKET_ONLY_FEATURES,
                    "prediction_rule": "L2-regularized logistic regression on market-only controls, grouped by race and calibrated on validation.",
                    "purpose": "Direct beyond-market control: if the candidate cannot beat a learned market-only model, it has not proven non-market signal.",
                },
                {
                    "name": "playbook_g_candidate_model",
                    "inputs": FEATURE_VECTOR_NAMES,
                    "prediction_rule": "Calibrated GradientBoostingClassifier plus isotonic calibration on the 37-feature vector only, normalized within race at inference.",
                    "purpose": "Match the established SQPE stack while keeping the first dry-run offline and governance-safe.",
                },
            ],
            "recommended_additional_control": {
                "name": "full37_logistic_ablation",
                "inputs": FEATURE_VECTOR_NAMES,
                "prediction_rule": "Simple logistic regression on the same 37 features to separate feature signal from model-family nonlinearity.",
            },
        },
        "P_proposed_target_metrics": {
            "primary": [
                "winner_multiclass_log_loss",
                "runner_level_brier_score",
                "top_1_winner_hit_rate",
                "top_3_containment",
                "calibration_curve",
                "market_rank_lift",
            ],
            "secondary": [
                "jurisdiction_split_performance",
                "year_split_performance",
                "overfit_warning",
                "roi_simulation_non_deployment_research_only",
            ],
            "definitions": {
                "calibration_curve": "Reliability curve on validation and test using grouped, race-normalized win probabilities; report at least 10 bins or quantile bins if sparse.",
                "market_rank_lift": "Improvement in top-1 and top-3 winner capture versus the normalized market-implied baseline on the same split.",
                "roi_simulation_non_deployment_research_only": "Optional paper study on thresholded overlays only; no staking logic, promotion, or deployment decisions may depend on it alone.",
            },
        },
        "Q_pass_fail_criteria": {
            "question": "Does VELO learn signal beyond market odds?",
            "go_if": [
                "The candidate beats the normalized market baseline on out-of-time test winner_multiclass_log_loss and runner_level_brier_score.",
                "The candidate beats the market-only logistic control on out-of-time test log loss or Brier score.",
                "Top-1 hit rate is at least the market favorite baseline minus 1 percentage point, and top-3 containment is non-negative versus market or offset by materially better log loss and Brier.",
                "Calibration on validation and test is stable: no obvious probability collapse, and expected calibration error is not worse than the market baseline.",
                "HK and FR each show non-negative log-loss lift versus market; JPN is informational only because the sample is too small for gating.",
            ],
            "stop_if": [
                "The candidate only improves on training or validation but fails to beat market on the out-of-time test.",
                "Validation-to-test degradation exceeds 10 percent relative on both log loss and Brier score.",
                "Any training matrix includes forbidden outcome fields, prior model outputs, Playbook shadow state, or verdict metadata.",
                "The model wins only on ROI simulation while losing on probability scoring metrics.",
            ],
            "market_reference_test_split": market_baseline["test"],
        },
        "R_risks": [
            "The eligible training cohort is 1,697 race events and 18,575 runners, not the full ~1,939 clean historical races. The excluded remainder is outside the strict pending_global_training_gate OASIS scope and should stay excluded from the first dry-run.",
            "The 2025 slice is clean but small (26 races / 244 runners) and uses explicit proxy macro context 2025_PROXY_V1. It should be included in the out-of-time test, but any 2025-specific conclusions must be treated as low-sample sensitivity checks.",
            "The late test period is FR-heavy and JPN-light. Jurisdiction gating should focus on HK and FR; JPN should be monitored but not used as a blocker.",
            "historical_feature_store rows contain prior model outputs and sentient metadata outside the 37-vector. Those keys are safe only if they remain excluded from the first training matrix.",
            "No training should touch training_eligible, historical_feature_store, or live verdict systems during the dry-run.",
        ],
        "S_final_go_no_go_recommendation": {
            "recommendation": "GO_OFFLINE_DRY_RUN_ONLY",
            "reason": "The accepted OASIS cohort is large enough, fully audited, macro-year-correct, provenance-complete, and leakage-safe when restricted to the 37-vector. The next step should be a strictly offline Playbook G dry-run whose only purpose is to measure whether the candidate beats market probability on out-of-time data.",
            "not_approved": [
                "live deployment",
                "Playbook E activation",
                "production model promotion",
                "mutation of historical_feature_store",
                "training_eligible state changes",
            ],
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    market_test = report["Q_pass_fail_criteria"]["market_reference_test_split"]
    lines = [
        "# Playbook G Dry-Run Gate v1",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "No training was executed. This is a training-readiness gate only.",
        "",
        "## Scope",
        f"- Eligible race events: `{report['A_eligible_race_count']}`",
        f"- Eligible runner rows: `{report['B_eligible_runner_count']}`",
        f"- Training scope: `training_eligible = {TRAINING_ELIGIBLE}`, `source = {HISTORICAL_SOURCE}`, `signal_contract_version = {SIGNAL_CONTRACT_VERSION}`, `event_identity_contract = {EVENT_IDENTITY_CONTRACT}`, `macro_year_used = race year`, `vector length = 37`",
        "",
        "## Data Shape",
        f"- Year breakdown (races): `{json.dumps(report['C_year_breakdown']['race_counts'], sort_keys=True)}`",
        f"- Jurisdiction breakdown (races): `{json.dumps(report['D_jurisdiction_breakdown']['race_counts'], sort_keys=True)}`",
        f"- Course breakdown (top): `{json.dumps(report['E_course_breakdown']['race_counts_top_50'], sort_keys=True)}`",
        f"- Runners per race: `avg={report['F_runners_per_race']['average']:.3f}, min={report['F_runners_per_race']['min']}, max={report['F_runners_per_race']['max']}`",
        f"- Winner label distribution: `positives={report['G_winner_label_distribution']['positive_winners']}, negatives={report['G_winner_label_distribution']['negative_non_winners']}, positive_rate={report['G_winner_label_distribution']['positive_rate']:.6f}`",
        "",
        "## Feature Readiness",
        f"- Vector dimension check: `{json.dumps(report['K_feature_vector_dimension_check']['vector_length_distribution'], sort_keys=True)}`",
        f"- Vector NaN / inf: `nan={report['K_feature_vector_dimension_check']['vector_nan_count']}, inf={report['K_feature_vector_dimension_check']['vector_inf_count']}`",
        f"- Leakage exclusion: `{report['L_leakage_exclusion_check']['status']}`",
        f"- Outcome exclusion: `{report['M_outcome_field_exclusion_check']['status']}`",
        "",
        "## Market Benchmarks",
        "- The candidate must beat these out-of-time market references on the first dry-run.",
        f"- Test market baseline: `log_loss={market_test['winner_multiclass_log_loss']:.6f}, brier={market_test['brier_score']:.6f}, top1={market_test['top_1_winner_hit_rate']:.6f}, top3={market_test['top_3_containment']:.6f}`",
        "",
        "## Proposed Split",
        f"- Train: `{json.dumps(report['N_proposed_train_validation_test_split']['splits']['train'], sort_keys=True)}`",
        f"- Validation: `{json.dumps(report['N_proposed_train_validation_test_split']['splits']['validation'], sort_keys=True)}`",
        f"- Test: `{json.dumps(report['N_proposed_train_validation_test_split']['splits']['test'], sort_keys=True)}`",
        f"- Secondary recommendation: {report['N_proposed_train_validation_test_split']['secondary_recommendation']}",
        "",
        "## Baselines",
        "- `market_implied_probability_baseline`: normalize implied probability within race.",
        "- `sp_rank_baseline`: reciprocal SP-rank weights within race.",
        "- `simple_logistic_baseline`: market-only logistic control on `[sp_dec, log_sp, implied_prob, sp_rank, is_fav]`.",
        "- `playbook_g_candidate_model`: calibrated GBM plus isotonic calibration on the 37-vector only.",
        "",
        "## Pass / Fail",
        "- Pass only if the candidate beats the market-implied baseline and the market-only logistic control on out-of-time probability metrics.",
        "- HK and FR must each be non-negative versus market on log loss; JPN is informational only.",
        "- Any use of prior model outputs, Playbook shadow state, verdict metadata, or outcome labels in the training matrix is an automatic stop.",
        "",
        "## Risks",
    ]
    for risk in report["R_risks"]:
        lines.append(f"- {risk}")

    lines.extend(
        [
            "",
            "## Recommendation",
            f"- `{report['S_final_go_no_go_recommendation']['recommendation']}`",
            f"- {report['S_final_go_no_go_recommendation']['reason']}",
            "- Not approved in this step: "
            + ", ".join(f"`{item}`" for item in report["S_final_go_no_go_recommendation"]["not_approved"]),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the Playbook G offline dry-run gate without executing training.")
    parser.add_argument("--output-version", default="v1")
    parser.add_argument("--write-artifacts", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report = compute_gate_report()
    report["gate_version"] = args.output_version

    markdown = render_markdown(report)

    if args.write_artifacts:
        json_path = DATA_DIR / f"playbook_g_dry_run_gate_{args.output_version}.json"
        md_path = DATA_DIR / f"playbook_g_dry_run_gate_{args.output_version}.md"
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")

    print(json.dumps(report, indent=2))
    if args.dry_run:
        print("\n[playbook-g-dry-run-gate] dry-run only; no artifacts written." if not args.write_artifacts else "\n[playbook-g-dry-run-gate] dry-run summary complete; artifacts written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
