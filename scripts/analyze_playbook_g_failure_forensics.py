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

from scripts.prepare_playbook_g_dry_run_gate import FEATURE_VECTOR_NAMES, load_eligible_rows

DATA_DIR = ROOT / "data"
DRY_RUN_JSON = DATA_DIR / "playbook_g_offline_dry_run_v1.json"

MARKET_FEATURES = {"sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav"}
RATING_FEATURES = {
    "or_num",
    "rpr_num",
    "ts_num",
    "or_vs_field",
    "rpr_vs_field",
    "class_num",
    "wgt_lbs",
    "age_num",
    "draw_num",
    "draw_pct",
    "field_size",
    "dist_f",
    "going_code",
    "is_aw",
}
DOCTRINE_FEATURES = [feature for feature in FEATURE_VECTOR_NAMES if feature not in MARKET_FEATURES and feature not in RATING_FEATURES]
TOP_ANALYSIS_FEATURES = [
    "sp_dec",
    "log_sp",
    "implied_prob",
    "sp_rank",
    "is_fav",
    "or_num",
    "rpr_num",
    "ts_num",
    "or_vs_field",
    "rpr_vs_field",
    "draw_pct",
    "field_size",
    "runs_since_win",
    "runs_since_place",
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


def load_dry_run_report() -> dict[str, Any]:
    return json.loads(DRY_RUN_JSON.read_text(encoding="utf-8"))


def safe_float(value: Any) -> float:
    return float(value)


def build_records() -> list[dict[str, Any]]:
    rows = load_eligible_rows()
    records: list[dict[str, Any]] = []
    for row in rows:
        record = {name: float(value) for name, value in zip(FEATURE_VECTOR_NAMES, row["_vector"])}
        record["race_id"] = str(row["race_id"])
        record["horse_id"] = str(row["horse_id"])
        record["race_year"] = row["_race_year"]
        record["jurisdiction"] = row.get("jurisdiction") or "UNKNOWN"
        record["course"] = row.get("course") or "UNKNOWN"
        record["winner_flag"] = 1 if row.get("winner_flag") else 0
        records.append(record)
    return records


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def variance(values: list[float]) -> float:
    if not values:
        return 0.0
    m = mean(values)
    return sum((value - m) ** 2 for value in values) / len(values)


def stdev(values: list[float]) -> float:
    return math.sqrt(variance(values))


def doctrine_distribution(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for feature in DOCTRINE_FEATURES:
        values = [record[feature] for record in records]
        output[feature] = {
            "nonzero_rate": sum(1 for value in values if abs(value) > 1e-12) / len(values),
            "mean_abs": mean([abs(value) for value in values]),
            "std": stdev(values),
        }
    return output


def winner_gap_ranking(records: list[dict[str, Any]], features: list[str]) -> list[dict[str, float]]:
    winners = [record for record in records if record["winner_flag"] == 1]
    losers = [record for record in records if record["winner_flag"] == 0]
    output: list[dict[str, float]] = []
    for feature in features:
        values = [record[feature] for record in records]
        sigma = stdev(values)
        winner_mean = mean([record[feature] for record in winners])
        loser_mean = mean([record[feature] for record in losers])
        gap = winner_mean - loser_mean
        output.append(
            {
                "feature": feature,
                "winner_mean": winner_mean,
                "loser_mean": loser_mean,
                "gap": gap,
                "std_gap": (gap / sigma) if sigma > 1e-12 else 0.0,
            }
        )
    return sorted(output, key=lambda row: abs(row["std_gap"]), reverse=True)


def drift_summary(train_records: list[dict[str, Any]], compare_records: list[dict[str, Any]], features: list[str]) -> list[dict[str, float]]:
    output: list[dict[str, float]] = []
    for feature in features:
        train_values = [record[feature] for record in train_records]
        compare_values = [record[feature] for record in compare_records]
        pooled = stdev(train_values + compare_values)
        delta = mean(compare_values) - mean(train_values)
        output.append(
            {
                "feature": feature,
                "train_mean": mean(train_values),
                "compare_mean": mean(compare_values),
                "mean_shift": delta,
                "std_shift": (delta / pooled) if pooled > 1e-12 else 0.0,
            }
        )
    return sorted(output, key=lambda row: abs(row["std_shift"]), reverse=True)


def compute_group_counts(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(record[key]) for record in records))


def feature_importance_group_share(report: dict[str, Any]) -> dict[str, Any]:
    importance_map = report["S_feature_importance_summary"]["full_importance_map"]
    market_share = sum(importance_map.get(feature, 0.0) for feature in MARKET_FEATURES)
    rating_share = sum(importance_map.get(feature, 0.0) for feature in RATING_FEATURES)
    doctrine_share = sum(importance_map.get(feature, 0.0) for feature in DOCTRINE_FEATURES)
    return {
        "market_share": market_share,
        "rating_share": rating_share,
        "doctrine_share": doctrine_share,
        "combined_market_rating_share": market_share + rating_share,
    }


def top_jurisdiction_year_breakdown(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    by_pair: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        by_pair[record["jurisdiction"]][str(record["race_year"])] += 1
    return {key: dict(counter) for key, counter in by_pair.items()}


def build_forensics_report() -> dict[str, Any]:
    report = load_dry_run_report()
    records = build_records()

    train_records = [record for record in records if record["race_year"] <= 2020]
    validation_records = [record for record in records if 2021 <= record["race_year"] <= 2022]
    test_records = [record for record in records if record["race_year"] >= 2023]
    hk_test_records = [record for record in test_records if record["jurisdiction"] == "HK"]
    fr_test_records = [record for record in test_records if record["jurisdiction"] == "FR"]
    y2025_records = [record for record in records if record["race_year"] == 2025]

    doctrine_stats = doctrine_distribution(records)
    constant_doctrine = [feature for feature, stats in doctrine_stats.items() if stats["std"] == 0.0]
    zero_doctrine = [feature for feature, stats in doctrine_stats.items() if stats["nonzero_rate"] == 0.0]

    share = feature_importance_group_share(report)
    hk_metrics = report["P_jurisdiction_split_performance"]["HK"]
    fr_metrics = report["P_jurisdiction_split_performance"]["FR"]
    y2025_metrics = report["Q_year_split_performance"]["holdout_test_years"]["2025"]

    hk_lift = {
        "log_loss_delta_vs_market": hk_metrics["candidate"]["winner_multiclass_log_loss"] - hk_metrics["market"]["winner_multiclass_log_loss"],
        "brier_delta_vs_market": hk_metrics["candidate"]["brier_score"] - hk_metrics["market"]["brier_score"],
        "top1_delta_vs_market": hk_metrics["candidate"]["top_1_winner_hit_rate"] - hk_metrics["market"]["top_1_winner_hit_rate"],
        "top3_delta_vs_market": hk_metrics["candidate"]["top_3_containment"] - hk_metrics["market"]["top_3_containment"],
    }
    fr_lift = {
        "log_loss_delta_vs_market": fr_metrics["candidate"]["winner_multiclass_log_loss"] - fr_metrics["market"]["winner_multiclass_log_loss"],
        "brier_delta_vs_market": fr_metrics["candidate"]["brier_score"] - fr_metrics["market"]["brier_score"],
        "top1_delta_vs_market": fr_metrics["candidate"]["top_1_winner_hit_rate"] - fr_metrics["market"]["top_1_winner_hit_rate"],
        "top3_delta_vs_market": fr_metrics["candidate"]["top_3_containment"] - fr_metrics["market"]["top_3_containment"],
    }

    recommended_option = "D"
    recommendation_text = "Build stronger doctrine features first, then run the V2 ablation dry-run."

    return {
        "version": "v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "inputs": {
            "dry_run_report": str(DRY_RUN_JSON),
            "eligible_race_count": report["A_eligible_race_count"],
            "eligible_runner_count": report["B_eligible_runner_count"],
        },
        "A_HK_failure_drivers": {
            "sample_size": {
                "races": hk_metrics["market"]["race_count"],
                "runners": hk_metrics["market"]["runner_count"],
                "year_breakdown": top_jurisdiction_year_breakdown(hk_test_records)["HK"],
            },
            "metric_story": {
                "market_log_loss": hk_metrics["market"]["winner_multiclass_log_loss"],
                "candidate_log_loss": hk_metrics["candidate"]["winner_multiclass_log_loss"],
                "market_brier": hk_metrics["market"]["brier_score"],
                "candidate_brier": hk_metrics["candidate"]["brier_score"],
                "market_top1": hk_metrics["market"]["top_1_winner_hit_rate"],
                "candidate_top1": hk_metrics["candidate"]["top_1_winner_hit_rate"],
                "market_top3": hk_metrics["market"]["top_3_containment"],
                "candidate_top3": hk_metrics["candidate"]["top_3_containment"],
            },
            "interpretation": [
                "HK is the gating failure because candidate log loss is worse than market despite better top-1 and top-3 rates.",
                "That pattern means the candidate found more winners overall but made a small number of very overconfident mistakes, which multiclass log loss punishes heavily.",
                "HK doctrine features are effectively constant, so the model had no meaningful non-market doctrine structure to lean on when market/rating relationships shifted.",
            ],
            "winner_gap_ranking": winner_gap_ranking(hk_test_records, TOP_ANALYSIS_FEATURES)[:12],
            "candidate_vs_market_lift": hk_lift,
        },
        "B_FR_success_drivers": {
            "sample_size": {
                "races": fr_metrics["market"]["race_count"],
                "runners": fr_metrics["market"]["runner_count"],
                "year_breakdown": top_jurisdiction_year_breakdown(fr_test_records)["FR"],
            },
            "metric_story": {
                "market_log_loss": fr_metrics["market"]["winner_multiclass_log_loss"],
                "candidate_log_loss": fr_metrics["candidate"]["winner_multiclass_log_loss"],
                "market_brier": fr_metrics["market"]["brier_score"],
                "candidate_brier": fr_metrics["candidate"]["brier_score"],
                "market_top1": fr_metrics["market"]["top_1_winner_hit_rate"],
                "candidate_top1": fr_metrics["candidate"]["top_1_winner_hit_rate"],
                "market_top3": fr_metrics["market"]["top_3_containment"],
                "candidate_top3": fr_metrics["candidate"]["top_3_containment"],
            },
            "interpretation": [
                "FR drives the global success: candidate beats market on log loss, Brier, top-1, and top-3.",
                "FR winners separate strongly on market/rating features, especially implied probability and RPR-based signals.",
                "The candidate is effectively a sharper market/rating model here, not a doctrine-driven model.",
            ],
            "winner_gap_ranking": winner_gap_ranking(fr_test_records, TOP_ANALYSIS_FEATURES)[:12],
            "candidate_vs_market_lift": fr_lift,
        },
        "C_2025_instability_drivers": {
            "sample_size": {
                "races": y2025_metrics["market"]["race_count"],
                "runners": y2025_metrics["market"]["runner_count"],
                "jurisdiction_breakdown": compute_group_counts(y2025_records, "jurisdiction"),
            },
            "metric_story": {
                "market_log_loss": y2025_metrics["market"]["winner_multiclass_log_loss"],
                "candidate_log_loss": y2025_metrics["candidate"]["winner_multiclass_log_loss"],
                "market_brier": y2025_metrics["market"]["brier_score"],
                "candidate_brier": y2025_metrics["candidate"]["brier_score"],
                "market_top1": y2025_metrics["market"]["top_1_winner_hit_rate"],
                "candidate_top1": y2025_metrics["candidate"]["top_1_winner_hit_rate"],
            },
            "interpretation": [
                "2025 is tiny and unstable: only 26 races and 244 runners.",
                "Candidate beats market on Brier and top-1 in 2025 but loses badly on log loss, which points to overconfident misses rather than uniformly poor ranking.",
                "The explicit 2025 proxy macro is clean, but the sample is too small to stabilize a nonlinear model with no real doctrine variation.",
            ],
            "winner_gap_ranking": winner_gap_ranking(y2025_records, TOP_ANALYSIS_FEATURES)[:12],
        },
        "D_train_validation_test_drift": {
            "counts": {
                "train_races": report["C_train_validation_test_counts"]["train"]["race_count"],
                "validation_races": report["C_train_validation_test_counts"]["validation"]["race_count"],
                "test_races": report["C_train_validation_test_counts"]["test"]["race_count"],
            },
            "train_to_validation_top_drift": drift_summary(train_records, validation_records, TOP_ANALYSIS_FEATURES)[:12],
            "train_to_test_top_drift": drift_summary(train_records, test_records, TOP_ANALYSIS_FEATURES)[:12],
            "interpretation": [
                "The model was trained on a much larger 2017-2020 block and tested on a sparse 2023-2025 block.",
                "Train-to-test drift matters more because the test slice is smaller, FR-heavy, and structurally different from the early HK-heavy body.",
                "The overfit signal is consistent with a complex model fitting stable market/rating patterns in train while reacting too sharply out of time.",
            ],
        },
        "E_feature_importance_by_jurisdiction": {
            "method": "Diagnostic winner-separation ranking on the approved test slice; no retraining performed.",
            "HK_test_top_features": winner_gap_ranking(hk_test_records, TOP_ANALYSIS_FEATURES)[:12],
            "FR_test_top_features": winner_gap_ranking(fr_test_records, TOP_ANALYSIS_FEATURES)[:12],
        },
        "F_feature_importance_by_year": {
            "method": "Diagnostic winner-separation ranking on each holdout test year; no retraining performed.",
            "2023_top_features": winner_gap_ranking([record for record in records if record["race_year"] == 2023], TOP_ANALYSIS_FEATURES)[:12],
            "2024_top_features": winner_gap_ranking([record for record in records if record["race_year"] == 2024], TOP_ANALYSIS_FEATURES)[:12],
            "2025_top_features": winner_gap_ranking(y2025_records, TOP_ANALYSIS_FEATURES)[:12],
        },
        "G_is_model_mostly_learning_SP_RPR_OR": {
            "global_feature_importance_share": share,
            "interpretation": [
                f"Combined market + rating share is {share['combined_market_rating_share']:.4f}, which is effectively the entire learned signal.",
                f"Doctrine feature share is only {share['doctrine_share']:.4f}.",
                "So yes: this first dry-run is overwhelmingly learning market and rating structure rather than distinctive doctrine signal.",
            ],
        },
        "H_doctrine_features_dead_missing_or_drowned": {
            "distribution": doctrine_stats,
            "constant_features": constant_doctrine,
            "zero_features": zero_doctrine,
            "root_cause_evidence": [
                "Historical backfill calls _build_live_features(r_norm, nrace, [], []) in scripts/backfill_historical_feature_store.py.",
                "app/services/velo_prime_service.py then seeds v17 doctrine fields from DEFAULTS when not pre-computed.",
                "As a result, many doctrine features are constant defaults or always zero across the whole cohort.",
            ],
            "verdict": "dead_or_defaulted",
        },
        "I_calibration_by_jurisdiction": {
            "HK_market_ece": hk_metrics["market"]["calibration"]["ece"],
            "HK_candidate_ece": hk_metrics["candidate"]["calibration"]["ece"],
            "FR_market_ece": fr_metrics["market"]["calibration"]["ece"],
            "FR_candidate_ece": fr_metrics["candidate"]["calibration"]["ece"],
            "interpretation": [
                "Candidate calibration ECE is better than market in both HK and FR.",
                "That means HK failure is not simply poor average calibration; it is more likely a few high-confidence misses that hurt log loss disproportionately.",
            ],
        },
        "J_market_rank_lift_by_jurisdiction": {
            "HK": hk_lift,
            "FR": fr_lift,
            "interpretation": [
                "HK shows better hit-rate lift but worse log loss, which is the signature of brittle confidence.",
                "FR shows improvement on both ranking and probability metrics.",
            ],
        },
        "K_sample_size_warnings": {
            "overall_test": {
                "races": report["C_train_validation_test_counts"]["test"]["race_count"],
                "runners": report["C_train_validation_test_counts"]["test"]["runner_count"],
            },
            "HK_test": {"races": hk_metrics["market"]["race_count"], "runners": hk_metrics["market"]["runner_count"]},
            "FR_test": {"races": fr_metrics["market"]["race_count"], "runners": fr_metrics["market"]["runner_count"]},
            "JPN_test": {
                "races": report["P_jurisdiction_split_performance"]["JPN"]["market"]["race_count"],
                "runners": report["P_jurisdiction_split_performance"]["JPN"]["market"]["runner_count"],
            },
            "year_2025": {"races": y2025_metrics["market"]["race_count"], "runners": y2025_metrics["market"]["runner_count"]},
            "warning": "JPN and 2025 are too small for hard gating beyond directional diagnostics.",
        },
        "L_overfit_root_cause": {
            "reported_overfit": report["R_overfit_warning"],
            "root_causes": [
                "Nonlinear GBM + isotonic on a relatively small out-of-time test slice.",
                "Doctrine layer is effectively defaulted, so the model is fitting mostly market and rating structure with little extra robust signal.",
                "Temporal drift between 2017-2020 train and 2023-2025 test, plus a strong FR/HK composition shift.",
                "Small 2025 proxy-macro slice amplifies log-loss sensitivity to a few overconfident misses.",
            ],
        },
        "M_recommended_V2_experiment_design": {
            "mandatory_ablation_plan": [
                "1. Market-only baseline",
                "2. Ratings-only baseline",
                "3. Doctrine-only feature set",
                "4. Market + ratings",
                "5. Market + ratings + doctrine",
                "6. Jurisdiction-specific calibration",
                "7. HK-only diagnostic model",
                "8. FR-only diagnostic model",
            ],
            "must_change_before_v2": [
                "Rebuild the historical doctrine feature layer with real horse-history context instead of DEFAULTS-only backfill.",
                "Keep the same offline-only guardrails and the same grouped chronological split.",
                "Treat 2025 as sensitivity analysis, not the main source of lift claims.",
            ],
            "recommendation_option": recommended_option,
            "recommendation_text": recommendation_text,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Playbook G Failure Forensics v1",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "No retraining was performed. This is a forensics-only analysis of the checkpointed offline dry-run.",
        "",
        "## Core Diagnosis",
        f"- Recommendation: `{report['M_recommended_V2_experiment_design']['recommendation_option']}`",
        f"- {report['M_recommended_V2_experiment_design']['recommendation_text']}",
        "",
        "## HK Failure",
        f"- HK test sample: `{report['A_HK_failure_drivers']['sample_size']['races']} races / {report['A_HK_failure_drivers']['sample_size']['runners']} runners`",
        f"- HK market log loss: `{report['A_HK_failure_drivers']['metric_story']['market_log_loss']:.6f}`",
        f"- HK candidate log loss: `{report['A_HK_failure_drivers']['metric_story']['candidate_log_loss']:.6f}`",
        f"- HK candidate top-1 vs market: `{report['A_HK_failure_drivers']['metric_story']['candidate_top1']:.6f}` vs `{report['A_HK_failure_drivers']['metric_story']['market_top1']:.6f}`",
        "",
        "## FR Success",
        f"- FR test sample: `{report['B_FR_success_drivers']['sample_size']['races']} races / {report['B_FR_success_drivers']['sample_size']['runners']} runners`",
        f"- FR market log loss: `{report['B_FR_success_drivers']['metric_story']['market_log_loss']:.6f}`",
        f"- FR candidate log loss: `{report['B_FR_success_drivers']['metric_story']['candidate_log_loss']:.6f}`",
        "",
        "## Doctrine Layer",
        f"- Combined market + rating importance share: `{report['G_is_model_mostly_learning_SP_RPR_OR']['global_feature_importance_share']['combined_market_rating_share']:.6f}`",
        f"- Doctrine importance share: `{report['G_is_model_mostly_learning_SP_RPR_OR']['global_feature_importance_share']['doctrine_share']:.6f}`",
        f"- Constant doctrine features: `{json.dumps(report['H_doctrine_features_dead_missing_or_drowned']['constant_features'])}`",
        "",
        "## Overfit",
        f"- Overfit status: `{report['L_overfit_root_cause']['reported_overfit']['status']}`",
        f"- Validation log-loss increase vs train: `{report['L_overfit_root_cause']['reported_overfit']['relative_log_loss_increase_validation_vs_train']:.6f}`",
        f"- Test log-loss increase vs train: `{report['L_overfit_root_cause']['reported_overfit']['relative_log_loss_increase_test_vs_train']:.6f}`",
        "",
        "## Next Move",
        "- Do not promote the current candidate.",
        "- Rebuild the doctrine feature layer with real historical context.",
        "- Then run the required V2 ablation plan under the same offline controls.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze why Playbook G dry-run v1 failed its governance gate.")
    parser.parse_args()

    report = build_forensics_report()
    json_path = DATA_DIR / "playbook_g_failure_forensics_v1.json"
    md_path = DATA_DIR / "playbook_g_failure_forensics_v1.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
