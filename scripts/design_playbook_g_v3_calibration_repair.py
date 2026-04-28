from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

STABILITY = DATA / "playbook_g_v3_core_stability_audit.json"
CORE_REVIEW = DATA / "playbook_g_v3_core_candidate_review.json"
V3_OFFLINE = DATA / "playbook_g_v3_offline_dry_run.json"
V3_METRICS = DATA / "playbook_g_v3_offline_metrics.csv"
V3_DESIGN = DATA / "playbook_g_v3_design.json"

JSON_OUT = DATA / "playbook_g_v3_calibration_repair_design.json"
MD_OUT = DATA / "playbook_g_v3_calibration_repair_design.md"


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
        "# Playbook G V3 Calibration Repair Design",
        "",
        f"- Recommendation: `{report['J_whether_calibration_repair_execution_is_recommended']['status']}`",
        f"- Objective: {report['A_proposed_calibration_arms']['objective']}",
        "",
        "## Arms",
    ]
    for arm in report["A_proposed_calibration_arms"]["arms"]:
        lines.append(f"- `{arm['code']}` `{arm['name']}`: {arm['purpose']}")
    lines.extend(
        [
            "",
            "## Hard Gates",
            f"- Market correlation ceiling: `<= {report['D_pass_fail_criteria']['thresholds']['market_probability_correlation_max']}`",
            f"- Top-1 market overlap ceiling: `<= {report['D_pass_fail_criteria']['thresholds']['top1_market_overlap_max']}`",
            f"- Core log-loss floor: `<= {report['D_pass_fail_criteria']['thresholds']['core_log_loss_max']}`",
            f"- Core Brier floor: `<= {report['D_pass_fail_criteria']['thresholds']['core_brier_max']}`",
            "",
            "## Next Step",
            f"- {report['I_recommended_execution_plan']['next_approved_mission']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    stability = load_json(STABILITY)
    core_review = load_json(CORE_REVIEW)
    v3 = load_json(V3_OFFLINE)
    design = load_json(V3_DESIGN)

    feature_groups = v3["D_feature_mask_verification"]
    core_metrics = v3["G_metrics_for_every_v3_arm"]["ratings_plus_doctrine_core"]["test_metrics"]
    market_metrics = v3["G_metrics_for_every_v3_arm"]["market_only_baseline"]["test_metrics"]
    market_ratings_metrics = v3["G_metrics_for_every_v3_arm"]["market_plus_ratings_baseline"]["test_metrics"]
    recrowd = v3["M_market_recrowding_checks"]
    overfit = v3["N_overfit_warning"]["core"]
    hk = v3["J_hk_result"]
    fr = v3["K_fr_result"]
    year_2025 = v3["L_2025_sensitivity_result"]

    allowed_core_inputs = {
        "ratings_features": feature_groups["ratings_features"],
        "doctrine_features": feature_groups["doctrine_features"],
        "structure_context_features": feature_groups["structure_context_features"],
        "core_feature_mask": feature_groups["core_feature_mask"],
    }
    forbidden_inputs = {
        "market_raw_core_features": feature_groups["market_features"],
        "outcome_fields": [
            "winner_flag",
            "placed_flag",
            "finish_position",
            "position",
            "result comments",
            "future race results",
            "post-race ranking",
        ],
        "prior_model_outputs": [
            "sqpe_v17_prob",
            "velo_prime_prob",
            "g_base_prob",
            "place_prob",
            "g_shadow_*",
            "sentient_*",
            "verdict_flags",
            "any prior model output",
        ],
    }

    arms = [
        {
            "code": "CR-1",
            "name": "core_uncalibrated_baseline",
            "purpose": "Reference point for pure ratings + doctrine + structure behavior.",
            "allowed_inputs": ["core feature mask only"],
            "market_usage": "benchmark only",
        },
        {
            "code": "CR-2",
            "name": "core_isotonic_no_market",
            "purpose": "Repair calibration using validation-only isotonic on core scores without any market inputs.",
            "allowed_inputs": ["core raw score", "validation labels", "race-normalization"],
            "market_usage": "diagnostic only",
        },
        {
            "code": "CR-3",
            "name": "core_platt_no_market",
            "purpose": "Test logistic/Platt calibration on core scores only.",
            "allowed_inputs": ["core raw score", "validation labels"],
            "market_usage": "diagnostic only",
        },
        {
            "code": "CR-4",
            "name": "core_temperature_scaling_no_market",
            "purpose": "Apply one-parameter confidence scaling to reduce overconfidence without changing ranking.",
            "allowed_inputs": ["core raw score", "validation labels"],
            "market_usage": "diagnostic only",
        },
        {
            "code": "CR-5",
            "name": "core_jurisdiction_aware_calibration_no_market",
            "purpose": "Allow HK/FR-specific calibration on core scores only if validation support is adequate.",
            "allowed_inputs": ["core raw score", "jurisdiction tag", "validation labels"],
            "market_usage": "diagnostic only",
        },
        {
            "code": "CR-6",
            "name": "core_market_aware_calibration_guardrailed",
            "purpose": "Optional market-aware calibration-side metadata experiment with strict recrowding gates and no raw market feature learning in the core.",
            "allowed_inputs": ["core raw score", "validation labels", "bounded market metadata for post-core calibrator only"],
            "market_usage": "calibration-side metadata only under isolation limits",
        },
        {
            "code": "CR-7",
            "name": "core_residual_confidence_dampening",
            "purpose": "Shrink extreme core probabilities toward race-level neutrality without using raw market features.",
            "allowed_inputs": ["core probability", "validation-set shrink parameter"],
            "market_usage": "benchmark only",
        },
        {
            "code": "CR-8",
            "name": "core_conservative_probability_shrinkage",
            "purpose": "Apply conservative post-hoc shrinkage to improve calibration while preserving the core ranking signal.",
            "allowed_inputs": ["core probability", "race-normalized shrinkage rule"],
            "market_usage": "benchmark only",
        },
    ]

    report = {
        "A_proposed_calibration_arms": {
            "objective": "Repair probability calibration for the ratings + doctrine + structure core without letting market information recrowd or dominate the model.",
            "arms": arms,
        },
        "B_exact_allowed_inputs_per_arm": {
            arm["name"]: {
                "allowed_inputs": arm["allowed_inputs"],
                "market_usage": arm["market_usage"],
            }
            for arm in arms
        },
        "C_exact_forbidden_inputs": forbidden_inputs,
        "D_pass_fail_criteria": {
            "thresholds": {
                "core_log_loss_max": round(core_metrics["log_loss"], 6),
                "core_brier_max": round(core_metrics["brier"], 6),
                "market_probability_correlation_max": recrowd["thresholds"]["probability_correlation_max"],
                "top1_market_overlap_max": recrowd["thresholds"]["top1_overlap_with_market_max"],
                "ece_target_max": round(core_metrics["ece"], 6),
                "material_log_loss_degradation_tolerance": 0.01,
                "material_brier_degradation_tolerance": 0.0025,
            },
            "rules": [
                "Calibration arm must not degrade core log loss by more than 0.01.",
                "Calibration arm must not degrade core Brier by more than 0.0025.",
                "Calibration ECE must improve relative to the current core.",
                "HK must remain non-negative vs market on log loss.",
                "FR must remain positive vs market on log loss.",
                "Market probability correlation must stay at or below 0.58.",
                "Top-1 market overlap must stay at or below 0.45.",
                "No leakage, no outcome fields, no prior model outputs, no production writes.",
            ],
        },
        "E_leakage_protections": {
            "current_status": {
                "core_review_leakage": core_review["D_confirm_leakage_audit"],
                "core_review_outcome_exclusion": core_review["E_confirm_outcome_field_exclusion"],
            },
            "repair_requirements": [
                "Calibrators train on validation years only.",
                "No same-day or future history.",
                "No label leakage through market-derived outcome surrogates.",
                "No use of prior model outputs.",
            ],
        },
        "F_market_recrowding_protections": {
            "observed_v3_failures": {
                "market_calibration": core_review["B_confirm_market_assisted_arms_failed_isolation_gate"]["market_calibration"],
                "residual_over_market": core_review["B_confirm_market_assisted_arms_failed_isolation_gate"]["residual_over_market"],
            },
            "guardrails": [
                "Market cannot appear in the core feature mask.",
                "Any market-aware arm must report market correlation and top-1 overlap explicitly.",
                "Any arm that crosses either isolation threshold is rejected regardless of headline log loss.",
                "Residual-learning over market must be treated as an optional diagnostic, not a default path.",
            ],
        },
        "G_hk_fr_evaluation_plan": {
            "hk_baseline": hk,
            "fr_baseline": fr,
            "requirements": [
                "Evaluate HK and FR separately for every calibration arm.",
                "HK must stay improved or at least non-negative vs market.",
                "FR must stay positive vs market.",
                "JPN remains informational only until sample size improves.",
            ],
        },
        "H_2025_sensitivity_handling": {
            "status": year_2025,
            "policy": [
                "2025 remains sensitivity-only.",
                "Primary go/no-go should be based on full out-of-time test and separately reviewed 2023-2024.",
                "2025 may veto a calibration arm only if it also harms 2023-2024 or materially breaks calibration.",
            ],
        },
        "I_recommended_execution_plan": {
            "sequence": [
                "Run core uncalibrated baseline as immutable reference.",
                "Test non-market calibrators first: isotonic, Platt, temperature, conservative shrinkage.",
                "Run jurisdiction-aware non-market calibration only if validation support is adequate.",
                "Only after non-market arms are evaluated, optionally test strict market-aware calibration metadata arm.",
                "Reject any arm that trips the recrowding gates even if headline metrics improve.",
            ],
            "best_starting_point": "temperature scaling or conservative shrinkage on the core, because both can improve calibration with lower risk of reintroducing market dependence.",
            "next_approved_mission": "Review this calibration-repair design, then approve or reject offline calibration-repair execution.",
        },
        "J_whether_calibration_repair_execution_is_recommended": {
            "status": "GO_DESIGN_APPROVED_PENDING_REVIEW",
            "reason": "The core has enough signal and stability to justify calibration repair research, but only under strict market-isolation gates and without any production writes.",
            "supporting_context": {
                "core_candidate_review": core_review["final_recommendation"],
                "stability_recommendation": stability["O_final_recommendation"],
                "current_core_metrics": core_metrics,
                "market_baseline": market_metrics,
                "market_plus_ratings_baseline": market_ratings_metrics,
                "core_overfit": overfit,
            },
        },
    }

    JSON_OUT.write_text(json.dumps(to_jsonable(report), indent=2), encoding="utf-8")
    MD_OUT.write_text(build_markdown(report), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
