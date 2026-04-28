from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

V2_ABLATION = DATA / "playbook_g_v2_ablation_dry_run.json"
V2_FORENSICS = DATA / "playbook_g_v2_failure_forensics.json"
DOCTRINE_AUDIT_V2 = DATA / "historical_doctrine_feature_audit_v2.json"
GLOBAL_AUDIT_V4 = DATA / "global_clean_spine_audit_v4.json"

SCRIPT_OUT = ROOT / "scripts" / "design_playbook_g_v3_experiment.py"
JSON_OUT = DATA / "playbook_g_v3_design.json"
MD_OUT = DATA / "playbook_g_v3_design.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


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
        "# Playbook G V3 Design",
        "",
        f"- Objective: {report['A_objective']}",
        f"- Core hypothesis: {report['B_hypothesis']}",
        f"- Eligible cohort: `{report['C_eligible_cohort_definition']['eligible_races']} races / {report['C_eligible_cohort_definition']['eligible_runners']} runners`",
        f"- Recommendation for V3 execution: `{report['Q_final_go_no_go_recommendation']['status']}`",
        "",
        "## V3 Arms",
    ]
    for arm in report["H_model_arms"]:
        lines.append(
            f"- `{arm['code']}` `{arm['name']}`: {arm['purpose']}"
        )

    lines.extend(
        [
            "",
            "## Exact Feature Masks",
            f"- Core `ratings + doctrine + structure`: `{', '.join(report['E_feature_groups']['core_feature_mask'])}`",
            f"- Market features excluded from core: `{', '.join(report['E_feature_groups']['market_features'])}`",
            f"- Ratings features: `{', '.join(report['E_feature_groups']['ratings_features'])}`",
            f"- Doctrine features: `{', '.join(report['E_feature_groups']['doctrine_features'])}`",
            f"- Structure/context features: `{', '.join(report['E_feature_groups']['structure_context_features'])}`",
            "",
            "## Hard Gate",
            f"- Core log loss target: `<= {report['N_pass_fail_gates']['thresholds']['ratings_doctrine_core_log_loss_max']}`",
            f"- Core Brier target: `<= {report['N_pass_fail_gates']['thresholds']['ratings_doctrine_core_brier_max']}`",
            f"- Market-crowding correlation ceiling: `<= {report['N_pass_fail_gates']['thresholds']['market_correlation_ceiling']}`",
            f"- Market top-1 overlap ceiling: `<= {report['N_pass_fail_gates']['thresholds']['market_top1_overlap_ceiling']}`",
            "",
            "## Risks",
        ]
    )
    for risk in report["Q_final_go_no_go_recommendation"]["risks"]:
        lines.append(f"- {risk}")

    lines.extend(
        [
            "",
            "## Next Mission",
            f"- {report['Q_final_go_no_go_recommendation']['next_approved_mission']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    v2 = load_json(V2_ABLATION)
    forensics = load_json(V2_FORENSICS)
    doctrine = load_json(DOCTRINE_AUDIT_V2)
    audit_v4 = load_json(GLOBAL_AUDIT_V4)

    full_schema = [item["feature"] for item in doctrine["A_full_37_vector_schema"]]
    market = doctrine["D_market_feature_list"]
    ratings = doctrine["E_rating_feature_list"]
    doctrine_features = doctrine["F_doctrine_feature_list"]
    structure_context = [f for f in full_schema if f not in set(market + ratings + doctrine_features)]
    core_mask = unique_preserve(ratings + doctrine_features + structure_context)

    ratings_doctrine_test = v2["ablation_results"]["ratings_plus_doctrine"]["test_metrics"]
    market_ratings_test = v2["ablation_results"]["market_plus_ratings"]["test_metrics"]
    full_stack_test = v2["ablation_results"]["market_plus_ratings_plus_doctrine"]["test_metrics"]
    market_only_test = v2["ablation_results"]["market_only"]["test_metrics"]
    doctrine_only_test = v2["ablation_results"]["doctrine_only"]["test_metrics"]
    hk_status = v2["P_hk_failure_fixed_or_reduced"]
    fr_status = v2["Q_fr_remains_positive"]
    y2025_status = v2["R_2025_remains_unstable"]
    interference = forensics["A_market_feature_interference_analysis"]

    report: dict[str, Any] = {
        "A_objective": "Design the first Playbook G V3 offline experiment around a ratings + doctrine core while isolating market information to benchmark, calibration, and residual-learning roles.",
        "B_hypothesis": "Ratings + doctrine is the primary signal engine; raw market features crowd doctrine when injected into the core stack, but market can still add value as benchmark, calibration input, or residual target if it is isolated from core feature learning.",
        "C_eligible_cohort_definition": {
            "authority_model": audit_v4["authority_model"],
            "filters": {
                "training_eligible": "pending_global_training_gate",
                "data_owner_confirmed": True,
                "source": "historical_raceform",
                "event_identity_contract": "race_id_course_race_date",
                "signal_contract_version": "HISTORICAL_SIGNAL_PROXY_V1",
                "historical_doctrine_contract": "HISTORICAL_DOCTRINE_FEATURES_V1",
                "doctrine_source": "prior_only_raceform_history",
                "macro_year_mismatch": 0,
                "vector_length": 37,
            },
            "eligible_races": v2["A_eligible_race_count"],
            "eligible_runners": v2["B_eligible_runner_count"],
            "jurisdiction_breakdown_races": v2["E_jurisdiction_breakdown"],
            "year_breakdown_races": v2["D_year_breakdown"],
        },
        "D_train_validation_test_split": {
            "train_years": [2017, 2018, 2019, 2020],
            "validation_years": [2021, 2022],
            "test_years": [2023, 2024, 2025],
            "counts": v2["C_train_validation_test_counts"],
            "rule": "strict out-of-time split; no random shuffle across years",
            "secondary_review": "also report 2023-2024-only test metrics so 2025 cannot dominate governance",
        },
        "E_feature_groups": {
            "full_37_vector": full_schema,
            "market_features": market,
            "ratings_features": ratings,
            "doctrine_features": doctrine_features,
            "structure_context_features": structure_context,
            "core_feature_mask": core_mask,
            "core_feature_policy": "core arms may use ratings + doctrine + leakage-free structure/context features only; raw market features excluded from core learning",
        },
        "F_forbidden_fields": {
            "outcome_fields": [
                "winner_flag",
                "placed_flag",
                "finish_position",
                "position",
                "result_comments",
                "future_race_results",
                "post_race_ranking",
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
            "market_core_exclusions": market,
        },
        "G_leakage_protections": {
            "history_cutoff_rule": "prior_race_date_lt_current_race_date",
            "current_v4_status": {
                "global_audit_v4": "pass",
                "doctrine_audit_v2": "pass",
                "same_day_or_future_leakage": 0,
                "outcome_field_exclusion": "pass",
            },
            "execution_requirements": [
                "training matrix derived only from approved masks",
                "no raw market features in core arms",
                "no outcome fields in any arm",
                "no prior model outputs in any arm",
                "no database writes",
                "no production writes",
            ],
        },
        "H_model_arms": [
            {
                "code": "V3-1",
                "name": "market_only_baseline",
                "feature_mask": market,
                "market_role": "baseline only",
                "purpose": "unchanged benchmark to beat on out-of-time log loss and Brier",
            },
            {
                "code": "V3-2",
                "name": "market_plus_ratings_baseline",
                "feature_mask": unique_preserve(market + ratings),
                "market_role": "baseline only",
                "purpose": "carry forward the strongest market-led baseline from V2 for comparison",
            },
            {
                "code": "V3-3",
                "name": "doctrine_only_baseline",
                "feature_mask": doctrine_features,
                "market_role": "none",
                "purpose": "prove doctrine retains standalone non-zero signal after full activation",
            },
            {
                "code": "V3-4",
                "name": "ratings_plus_doctrine_core",
                "feature_mask": core_mask,
                "market_role": "none",
                "purpose": "primary V3 core model candidate",
            },
            {
                "code": "V3-5",
                "name": "ratings_plus_doctrine_with_market_calibration",
                "feature_mask": core_mask,
                "market_role": "calibration input only",
                "purpose": "test whether market helps only in post-model calibration without crowding core learning",
            },
            {
                "code": "V3-6",
                "name": "ratings_plus_doctrine_residual_over_market",
                "feature_mask": core_mask,
                "market_role": "offset / residual target only",
                "purpose": "test additive residual learning over market without feeding raw market into the core feature stack",
            },
            {
                "code": "V3-7",
                "name": "hk_diagnostic",
                "feature_mask": core_mask,
                "market_role": "benchmark/calibration only",
                "purpose": "confirm HK retains the V2 improvement and quantify crowding sensitivity",
            },
            {
                "code": "V3-8",
                "name": "fr_diagnostic",
                "feature_mask": core_mask,
                "market_role": "benchmark/calibration only",
                "purpose": "confirm FR remains positive and stable under the core design",
            },
            {
                "code": "V3-9",
                "name": "year_2025_sensitivity_report",
                "feature_mask": core_mask,
                "market_role": "benchmark comparison only",
                "purpose": "report 2025 separately as sensitivity-only; do not let it dominate governance because sample is small",
            },
        ],
        "I_calibration_plan": {
            "core_arm": "global isotonic or Platt-style calibration using validation years only",
            "market_calibration_arm": "combine core raw score with market benchmark only in calibrator stage; market cannot enter core learner features",
            "jurisdiction_review": "report HK and FR calibration separately; jurisdiction-specific calibrators are diagnostic, not default",
            "v2_evidence": {
                "mrd_test_ece": full_stack_test["ece"],
                "ratings_doctrine_test_ece": ratings_doctrine_test["ece"],
                "market_test_ece": market_only_test["ece"],
                "jurisdiction_specific_calibration_underperformed": True,
            },
        },
        "J_residual_learning_plan": {
            "objective": "treat market as an offset or target to explain residual edge, not as a raw dominant feature",
            "design": [
                "compute race-normalized market probability baseline from implied probability",
                "convert market probability to clipped logit or log-score baseline",
                "train a residual model on core features only to predict additive adjustment over the market baseline",
                "tune residual strength on validation only",
                "renormalize within race before evaluation",
            ],
            "guardrails": [
                "market value cannot appear as a direct core feature",
                "residual arm must report market-correlation and market top-1 overlap",
                "residual arm fails if it collapses back toward V2-style market crowding",
            ],
        },
        "K_jurisdiction_diagnostics": {
            "required_reviews": ["HK", "FR", "JPN informational only"],
            "hk_baseline": hk_status,
            "fr_baseline": fr_status,
            "requirements": [
                "HK log loss must remain improved vs market or at least non-negative vs market",
                "FR must remain positive vs market on log loss",
                "report top-1/top-3 and calibration by jurisdiction",
            ],
        },
        "L_2025_sensitivity_handling": {
            "status_from_v2": y2025_status,
            "policy": [
                "2025 remains sensitivity-only because 26 races is too small for primary governance",
                "primary pass/fail should be reported on full 2023-2025 and separately on 2023-2024",
                "if 2025 disagrees sharply with 2023-2024, flag it as instability rather than as a gating failure by itself",
            ],
        },
        "M_metrics": {
            "required_for_all_arms": [
                "log_loss",
                "brier_score",
                "top1_winner_hit_rate",
                "top3_containment",
                "calibration_ece",
                "market_rank_lift",
                "jurisdiction_split_performance",
                "year_split_performance",
                "overfit_warning",
                "feature_importance_by_group",
            ],
            "additional_core_metrics": [
                "market_probability_correlation",
                "top1_overlap_with_market",
                "2023_2024_subtest",
                "2025_sensitivity_only_report",
            ],
        },
        "N_pass_fail_gates": {
            "thresholds": {
                "ratings_doctrine_core_log_loss_max": round(ratings_doctrine_test["log_loss"], 6),
                "ratings_doctrine_core_brier_max": round(ratings_doctrine_test["brier"], 6),
                "market_correlation_ceiling": 0.58,
                "market_top1_overlap_ceiling": 0.45,
                "calibration_ece_degradation_tolerance": 0.01,
            },
            "hard_rules": [
                "ratings + doctrine core must hold or beat V2 best test log loss",
                "ratings + doctrine core should hold or beat V2 ratings+doctrine Brier where feasible",
                "market-calibrated or residual arms must not push market correlation above 0.58 or market top-1 overlap above 0.45 without compensating out-of-time gain",
                "HK must stay improved or at least non-negative vs market on log loss",
                "FR must remain positive vs market on log loss",
                "2025 must be reported separately and cannot dominate the governance call",
                "overfit warning must remain medium or better",
                "no leakage fields used",
                "no outcome fields used",
                "no prior model outputs used",
                "no production writes",
            ],
            "v2_reference_points": {
                "market_only_test": market_only_test,
                "market_plus_ratings_test": market_ratings_test,
                "ratings_plus_doctrine_test": ratings_doctrine_test,
                "market_plus_ratings_plus_doctrine_test": full_stack_test,
                "interference_evidence": {
                    "mrd_market_correlation": round(interference["prob_correlation_with_market"]["mrd"], 4),
                    "rpd_market_correlation": round(interference["prob_correlation_with_market"]["rpd"], 4),
                    "mrd_market_top1_overlap": round(interference["top1_overlap_with_market"]["mrd"], 4),
                    "rpd_market_top1_overlap": round(interference["top1_overlap_with_market"]["rpd"], 4),
                },
            },
        },
        "O_artifact_outputs": {
            "design_artifacts_written_now": [
                str(JSON_OUT),
                str(MD_OUT),
                str(SCRIPT_OUT),
            ],
            "future_v3_execution_outputs": [
                str(DATA / "playbook_g_v3_dry_run.json"),
                str(DATA / "playbook_g_v3_dry_run.md"),
                str(DATA / "playbook_g_v3_dry_run_metrics.csv"),
            ],
            "optional_model_dir": str(ROOT / "models" / "offline_research" / "playbook_g_v3"),
        },
        "P_rollback_safety_rules": {
            "because_design_only": "no database writes, no HFS mutation, no training_eligible mutation, no verdict writes",
            "future_v3_execution_rules": [
                "offline research only",
                "no deployment",
                "no Playbook E",
                "no production model promotion",
                "checkpoint artifacts before and after execution",
            ],
        },
        "Q_final_go_no_go_recommendation": {
            "status": "GO_DESIGN_APPROVED_PENDING_REVIEW",
            "reason": "The accepted spine and doctrine layer are clean, and V2 forensics gave a clear directional answer: ratings + doctrine should be the core while market is isolated to benchmark/calibration/residual roles.",
            "risks": [
                "2025 remains a tiny sensitivity slice",
                "JPN is too small for strong conclusions",
                "market can still recrowd the model if calibration/residual layers are implemented sloppily",
                "V3 should preserve the accepted historical authority model and not fall back to raw runner_results joins",
            ],
            "next_approved_mission": "Review this V3 design, then approve or reject Playbook G V3 offline execution.",
        },
    }

    JSON_OUT.write_text(json.dumps(to_jsonable(report), indent=2), encoding="utf-8")
    MD_OUT.write_text(build_markdown(report), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
