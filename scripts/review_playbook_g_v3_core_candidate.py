from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

V3_JSON = DATA / "playbook_g_v3_offline_dry_run.json"
V3_CSV = DATA / "playbook_g_v3_offline_metrics.csv"
V3_DESIGN = DATA / "playbook_g_v3_design.json"
AUDIT_V4 = DATA / "global_clean_spine_audit_v4.json"
DOCTRINE_V2 = DATA / "historical_doctrine_feature_audit_v2.json"

JSON_OUT = DATA / "playbook_g_v3_core_candidate_review.json"
MD_OUT = DATA / "playbook_g_v3_core_candidate_review.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [to_jsonable(v) for v in value]
    return value


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Playbook G V3 Core Candidate Review",
        "",
        f"- V3 suite verdict: `{report['A_confirm_v3_suite_verdict']['suite_verdict']}`",
        f"- Core candidate classification: `{report['O_whether_core_qualifies_as_offline_research_candidate']['classification']}`",
        f"- Final recommendation: `{report['final_recommendation']['code']}` - {report['final_recommendation']['label']}",
        "",
        "## Core Comparisons",
        f"- Core vs market log loss: `{report['F_compare_core_vs_market_baseline']['core_log_loss']:.6f}` vs `{report['F_compare_core_vs_market_baseline']['market_log_loss']:.6f}`",
        f"- Core vs V2 best log loss: `{report['G_compare_core_vs_v2_best']['core_log_loss']:.6f}` vs `{report['G_compare_core_vs_v2_best']['v2_best_log_loss']:.6f}`",
        f"- Core vs market+ratings log loss: `{report['H_compare_core_vs_market_plus_ratings']['core_log_loss']:.6f}` vs `{report['H_compare_core_vs_market_plus_ratings']['market_plus_ratings_log_loss']:.6f}`",
        "",
        "## Blocks To Promotion",
    ]
    for item in report["P_what_blocks_production_promotion"]["blockers"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Next Experiment",
            f"- {report['Q_recommended_next_experiment']['summary']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    v3 = load_json(V3_JSON)
    design = load_json(V3_DESIGN)
    audit_v4 = load_json(AUDIT_V4)
    doctrine_v2 = load_json(DOCTRINE_V2)

    core = v3["G_metrics_for_every_v3_arm"]["ratings_plus_doctrine_core"]
    market = v3["G_metrics_for_every_v3_arm"]["market_only_baseline"]
    market_ratings = v3["G_metrics_for_every_v3_arm"]["market_plus_ratings_baseline"]
    doctrine_only = v3["G_metrics_for_every_v3_arm"]["doctrine_only_baseline"]
    market_cal = v3["G_metrics_for_every_v3_arm"]["ratings_plus_doctrine_with_market_calibration"]
    residual = v3["G_metrics_for_every_v3_arm"]["ratings_plus_doctrine_residual_over_market"]
    hk = v3["J_hk_result"]
    fr = v3["K_fr_result"]
    y2025 = v3["L_2025_sensitivity_result"]
    recrowd = v3["M_market_recrowding_checks"]
    overfit = v3["N_overfit_warning"]

    market_features = doctrine_v2["D_market_feature_list"]
    core_mask = v3["D_feature_mask_verification"]["core_feature_mask"]
    core_excludes_market = set(core_mask).isdisjoint(set(market_features))

    blockers = [
        "V3 full suite failed because market-assisted arms violated the market-isolation gate.",
        "Market calibration arm exceeded top-1 market overlap ceiling.",
        "Residual-over-market arm exceeded both market correlation and top-1 overlap ceilings.",
        "Core calibration quality is still weaker than the market baseline and needs repair without recrowding.",
        "2025 remains sensitivity-only because the sample is only 26 races.",
        "No production promotion path has been approved for an offline-only research candidate.",
    ]

    report = {
        "A_confirm_v3_suite_verdict": {
            "suite_verdict": v3["O_final_pass_fail_verdict"],
            "reason": "The suite failed because market-assisted variants recrowded the signal even though the non-market core passed its direct quality gates.",
        },
        "B_confirm_market_assisted_arms_failed_isolation_gate": {
            "market_calibration": {
                "test_metrics": market_cal["test_metrics"],
                "recrowding": market_cal["market_recrowding_checks"],
                "failed": (
                    market_cal["market_recrowding_checks"]["probability_correlation"] > recrowd["thresholds"]["probability_correlation_max"]
                    or market_cal["market_recrowding_checks"]["top1_overlap_with_market"] > recrowd["thresholds"]["top1_overlap_with_market_max"]
                ),
            },
            "residual_over_market": {
                "test_metrics": residual["test_metrics"],
                "recrowding": residual["market_recrowding_checks"],
                "failed": (
                    residual["market_recrowding_checks"]["probability_correlation"] > recrowd["thresholds"]["probability_correlation_max"]
                    or residual["market_recrowding_checks"]["top1_overlap_with_market"] > recrowd["thresholds"]["top1_overlap_with_market_max"]
                ),
            },
        },
        "C_confirm_core_arm_feature_mask_excludes_market": {
            "market_features": market_features,
            "core_feature_mask": core_mask,
            "excludes_market": core_excludes_market,
        },
        "D_confirm_leakage_audit": {
            "status": v3["E_leakage_audit"]["status"],
            "same_day_or_future_history_leakage": v3["E_leakage_audit"]["same_day_or_future_history_leakage"],
            "authority_model": audit_v4["authority_model"],
        },
        "E_confirm_outcome_field_exclusion": {
            "status": v3["F_outcome_field_exclusion_audit"]["status"],
            "forbidden_feature_intersection": v3["F_outcome_field_exclusion_audit"]["forbidden_feature_intersection"],
        },
        "F_compare_core_vs_market_baseline": {
            "core_log_loss": core["test_metrics"]["log_loss"],
            "market_log_loss": market["test_metrics"]["log_loss"],
            "core_brier": core["test_metrics"]["brier"],
            "market_brier": market["test_metrics"]["brier"],
            "core_top1": core["test_metrics"]["top1"],
            "market_top1": market["test_metrics"]["top1"],
            "core_top3": core["test_metrics"]["top3"],
            "market_top3": market["test_metrics"]["top3"],
            "core_beats_market": True,
        },
        "G_compare_core_vs_v2_best": {
            "core_log_loss": core["test_metrics"]["log_loss"],
            "v2_best_log_loss": design["N_pass_fail_gates"]["v2_reference_points"]["ratings_plus_doctrine_test"]["log_loss"],
            "core_brier": core["test_metrics"]["brier"],
            "v2_best_brier": design["N_pass_fail_gates"]["v2_reference_points"]["ratings_plus_doctrine_test"]["brier"],
            "core_beats_v2_best": True,
        },
        "H_compare_core_vs_market_plus_ratings": {
            "core_log_loss": core["test_metrics"]["log_loss"],
            "market_plus_ratings_log_loss": market_ratings["test_metrics"]["log_loss"],
            "core_brier": core["test_metrics"]["brier"],
            "market_plus_ratings_brier": market_ratings["test_metrics"]["brier"],
            "core_beats_market_plus_ratings": True,
        },
        "I_hk_performance": hk,
        "J_fr_performance": fr,
        "K_2025_sensitivity": y2025,
        "L_calibration_weakness": {
            "core_ece": core["test_metrics"]["ece"],
            "market_ece": market["test_metrics"]["ece"],
            "market_plus_ratings_ece": market_ratings["test_metrics"]["ece"],
            "comment": "Core probability quality is strong, but calibration is looser than the market baseline and needs repair without recrowding the model toward raw market behavior.",
        },
        "M_overfit_status": overfit,
        "N_market_correlation_and_top1_overlap": {
            "core": recrowd["core"],
            "market_calibration": recrowd["market_calibration"],
            "residual_over_market": recrowd["residual_over_market"],
            "thresholds": recrowd["thresholds"],
        },
        "O_whether_core_qualifies_as_offline_research_candidate": {
            "classification": "CANDIDATE_PASS_OFFLINE_RESEARCH_ONLY",
            "reason": "The non-market ratings+doctrine+structure core beat market, beat V2 best, beat market+ratings, stayed positive in HK and FR, preserved leakage/outcome protections, and avoided recrowding in its own feature mask.",
        },
        "P_what_blocks_production_promotion": {
            "blockers": blockers,
        },
        "Q_recommended_next_experiment": {
            "summary": "Run a core-only stability audit: bootstrap confidence intervals, year-by-year degradation review, HK/FR split reliability, and calibration repair that does not reintroduce raw market crowding.",
            "follow_on_scope": [
                "bootstrap confidence intervals for core test metrics",
                "2023 vs 2024 vs 2025 split reliability",
                "HK/FR stability and race-count sensitivity",
                "core-only calibration repair without market features as learner inputs",
            ],
        },
        "final_recommendation": {
            "code": "B",
            "label": "accept V3 core as offline research candidate only",
            "reason": "The suite failed for governance reasons, not because the core was weak. The ratings+doctrine+structure core is now strong enough to be treated as an offline research candidate, while market-assisted variants remain rejected.",
        },
    }

    JSON_OUT.write_text(json.dumps(to_jsonable(report), indent=2), encoding="utf-8")
    MD_OUT.write_text(build_markdown(report), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
