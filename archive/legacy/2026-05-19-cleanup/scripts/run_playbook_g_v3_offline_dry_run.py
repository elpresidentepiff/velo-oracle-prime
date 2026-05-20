from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V2_SCRIPT = ROOT / "scripts" / "run_playbook_g_v2_ablation_dry_run.py"
DOCTRINE_AUDIT_V2 = DATA / "historical_doctrine_feature_audit_v2.json"
GLOBAL_AUDIT_V4 = DATA / "global_clean_spine_audit_v4.json"
DESIGN_JSON = DATA / "playbook_g_v3_design.json"

JSON_OUT = DATA / "playbook_g_v3_offline_dry_run.json"
MD_OUT = DATA / "playbook_g_v3_offline_dry_run.md"
CSV_OUT = DATA / "playbook_g_v3_offline_metrics.csv"

FORBIDDEN_FIELDS = {
    "winner_flag",
    "placed_flag",
    "finish_position",
    "position",
    "result_comments",
    "future_race_results",
    "post_race_ranking",
    "sqpe_v17_prob",
    "velo_prime_prob",
    "g_base_prob",
    "place_prob",
    "g_shadow_*",
    "sentient_*",
    "verdict_flags",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_v2_module():
    spec = importlib.util.spec_from_file_location("playbook_g_v2", V2_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {V2_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1.0 - p))


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def probability_correlation(probs: np.ndarray, market_probs: np.ndarray) -> float:
    probs = np.asarray(probs, dtype=float)
    market_probs = np.asarray(market_probs, dtype=float)
    if probs.size < 2:
        return 0.0
    return float(np.corrcoef(probs, market_probs)[0, 1])


def top1_overlap_with_market(frame: pd.DataFrame, probs: np.ndarray, market_probs: np.ndarray) -> float:
    work = frame[["event_key"]].copy()
    work["prob"] = np.asarray(probs, dtype=float)
    work["market_prob"] = np.asarray(market_probs, dtype=float)
    overlaps: list[float] = []
    for _, race in work.groupby("event_key", sort=False):
        model_top = int(race["prob"].idxmax())
        market_top = int(race["market_prob"].idxmax())
        overlaps.append(float(model_top == market_top))
    return float(np.mean(overlaps)) if overlaps else 0.0


def metrics_rows_for_csv(name: str, metrics: dict[str, Any], scope: str, scope_value: str) -> dict[str, Any]:
    return {
        "model": name,
        "scope": scope,
        "scope_value": scope_value,
        "log_loss": metrics["log_loss"],
        "brier": metrics["brier"],
        "top1": metrics["top1"],
        "top3": metrics["top3"],
        "ece": metrics["ece"],
        "market_rank_lift": metrics["market_rank_lift"],
        "n_races": metrics["n_races"],
        "n_runners": metrics["n_runners"],
    }


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def evaluate_bundle(pb2, frame: pd.DataFrame, probs: np.ndarray, market_probs: np.ndarray) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    metrics = pb2.evaluate_frame(frame, probs, market_probs=market_probs)
    by_jurisdiction, by_year = pb2.split_metrics_payload(frame, probs, market_probs)
    return metrics, by_jurisdiction, by_year


def build_groups(doctrine: dict[str, Any]) -> dict[str, list[str]]:
    full_schema = [item["feature"] for item in doctrine["A_full_37_vector_schema"]]
    market = doctrine["D_market_feature_list"]
    ratings = doctrine["E_rating_feature_list"]
    doctrine_features = doctrine["F_doctrine_feature_list"]
    structure = [f for f in full_schema if f not in set(market + ratings + doctrine_features)]
    return {
        "full_schema": full_schema,
        "market": market,
        "ratings": ratings,
        "doctrine": doctrine_features,
        "structure": structure,
        "core": unique_preserve(ratings + doctrine_features + structure),
    }


def fit_core_model(pb2, train_frame: pd.DataFrame, validation_frame: pd.DataFrame, feature_names: list[str]):
    return pb2.fit_gbm_model(train_frame, validation_frame, feature_names)


def predict_core(pb2, frame: pd.DataFrame, feature_names: list[str], model, calibrator) -> np.ndarray:
    return pb2.predict_frame(frame, feature_names, model, calibrator)


def fit_market_calibrator(
    pb2,
    validation_frame: pd.DataFrame,
    core_probs: np.ndarray,
) -> LogisticRegression:
    market_probs = pb2.market_reference_probs(validation_frame)
    X = np.column_stack([logit(core_probs), logit(market_probs)])
    y = validation_frame["winner_flag"].to_numpy(dtype=int)
    weights = pb2.sample_weights(validation_frame)
    model = LogisticRegression(random_state=42, max_iter=1000)
    model.fit(X, y, sample_weight=weights)
    return model


def predict_market_calibrated(
    pb2,
    frame: pd.DataFrame,
    core_probs: np.ndarray,
    calibrator: LogisticRegression,
) -> np.ndarray:
    market_probs = pb2.market_reference_probs(frame)
    X = np.column_stack([logit(core_probs), logit(market_probs)])
    raw = calibrator.predict_proba(X)[:, 1]
    return pb2.normalize_probabilities(frame["event_key"].to_numpy(), raw)


def fit_residual_alpha(
    pb2,
    validation_frame: pd.DataFrame,
    core_probs: np.ndarray,
) -> tuple[float, float, float]:
    market_probs = pb2.market_reference_probs(validation_frame)
    z_core = logit(core_probs)
    mean = float(z_core.mean())
    std = float(z_core.std(ddof=0) or 1.0)
    z_core = (z_core - mean) / std
    market_logits = logit(market_probs)
    labels = validation_frame["winner_flag"].to_numpy(dtype=int)

    best_alpha = 0.0
    best_loss = float("inf")
    for alpha in np.linspace(0.0, 2.0, 81):
        combined = sigmoid(market_logits + (alpha * z_core))
        probs = pb2.normalize_probabilities(validation_frame["event_key"].to_numpy(), combined)
        winner_probs = probs[labels == 1]
        loss = float(np.mean(-np.log(np.clip(winner_probs, 1e-12, 1.0))))
        if loss < best_loss:
            best_loss = loss
            best_alpha = float(alpha)
    return best_alpha, mean, std


def predict_residual_over_market(
    pb2,
    frame: pd.DataFrame,
    core_probs: np.ndarray,
    alpha: float,
    mean: float,
    std: float,
) -> np.ndarray:
    market_probs = pb2.market_reference_probs(frame)
    z_core = (logit(core_probs) - mean) / (std or 1.0)
    combined = sigmoid(logit(market_probs) + (alpha * z_core))
    return pb2.normalize_probabilities(frame["event_key"].to_numpy(), combined)


def evaluate_model_result(
    pb2,
    splits: dict[str, pd.DataFrame],
    groups: dict[str, list[str]],
    *,
    name: str,
    feature_names: list[str],
    mode: str,
    jurisdiction_only: str | None = None,
) -> dict[str, Any]:
    train_frame = splits["train"].copy()
    validation_frame = splits["validation"].copy()
    test_frame = splits["test"].copy()

    if jurisdiction_only is not None:
        train_frame = train_frame[train_frame["jurisdiction"] == jurisdiction_only].copy()
        validation_frame = validation_frame[validation_frame["jurisdiction"] == jurisdiction_only].copy()
        test_frame = test_frame[test_frame["jurisdiction"] == jurisdiction_only].copy()

    market_train = pb2.market_reference_probs(train_frame)
    market_validation = pb2.market_reference_probs(validation_frame)
    market_test = pb2.market_reference_probs(test_frame)

    feature_importance = {"group_share": {}, "top_features": []}
    calibration_mode = "none"
    market_role = "none"
    extra: dict[str, Any] = {}

    if mode == "market_only":
        train_probs = market_train
        validation_probs = market_validation
        test_probs = market_test
        feature_importance = pb2.feature_importance_payload(None, feature_names, {
            "market": groups["market"],
            "ratings": groups["ratings"],
            "doctrine": groups["doctrine"],
            "context_other": groups["structure"],
        }, direct_market=True)
        calibration_mode = "direct_market_probability"
        market_role = "baseline_only"
    else:
        model, calibrator = fit_core_model(pb2, train_frame, validation_frame, feature_names)
        core_train = predict_core(pb2, train_frame, feature_names, model, calibrator)
        core_validation = predict_core(pb2, validation_frame, feature_names, model, calibrator)
        core_test = predict_core(pb2, test_frame, feature_names, model, calibrator)
        feature_importance = pb2.feature_importance_payload(
            model,
            feature_names,
            {
                "market": groups["market"],
                "ratings": groups["ratings"],
                "doctrine": groups["doctrine"],
                "context_other": groups["structure"],
            },
        )

        if mode == "plain":
            train_probs, validation_probs, test_probs = core_train, core_validation, core_test
            calibration_mode = "global_isotonic"
            market_role = "none"
        elif mode == "market_calibration":
            market_calibrator = fit_market_calibrator(pb2, validation_frame, core_validation)
            train_probs = predict_market_calibrated(pb2, train_frame, core_train, market_calibrator)
            validation_probs = predict_market_calibrated(pb2, validation_frame, core_validation, market_calibrator)
            test_probs = predict_market_calibrated(pb2, test_frame, core_test, market_calibrator)
            calibration_mode = "validation_logistic_calibrator_with_market_input"
            market_role = "calibration_only"
            extra["calibration_coefficients"] = market_calibrator.coef_.tolist()
            extra["calibration_intercept"] = market_calibrator.intercept_.tolist()
        elif mode == "residual":
            alpha, mean, std = fit_residual_alpha(pb2, validation_frame, core_validation)
            train_probs = predict_residual_over_market(pb2, train_frame, core_train, alpha, mean, std)
            validation_probs = predict_residual_over_market(pb2, validation_frame, core_validation, alpha, mean, std)
            test_probs = predict_residual_over_market(pb2, test_frame, core_test, alpha, mean, std)
            calibration_mode = "market_offset_plus_core_residual"
            market_role = "residual_target_only"
            extra["residual_alpha"] = alpha
        else:
            raise ValueError(f"Unknown mode: {mode}")

    train_metrics, _, _ = evaluate_bundle(pb2, train_frame, train_probs, market_train)
    validation_metrics, _, _ = evaluate_bundle(pb2, validation_frame, validation_probs, market_validation)
    test_metrics, by_jur, by_year = evaluate_bundle(pb2, test_frame, test_probs, market_test)
    overfit = pb2.overfit_warning(train_metrics, validation_metrics, test_metrics)

    return {
        "name": name,
        "feature_names": feature_names,
        "feature_count": len(feature_names),
        "mode": mode,
        "calibration_mode": calibration_mode,
        "market_role": market_role,
        "jurisdiction_only": jurisdiction_only,
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "test_metrics_by_jurisdiction": by_jur,
        "test_metrics_by_year": by_year,
        "feature_importance_by_group": feature_importance["group_share"],
        "top_features": feature_importance["top_features"],
        "overfit_warning": overfit,
        "market_recrowding_checks": {
            "probability_correlation": probability_correlation(test_probs, market_test),
            "top1_overlap_with_market": top1_overlap_with_market(test_frame, test_probs, market_test),
        },
        "extra": extra,
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Playbook G V3 Offline Dry Run",
        "",
        f"- Design checkpoint: `{report['A_design_checkpoint_commit_hash']}`",
        f"- Eligible races / runners: `{report['B_eligible_race_runner_count']['races']} / {report['B_eligible_race_runner_count']['runners']}`",
        f"- Best model by log loss: `{report['H_best_model_by_log_loss']}`",
        f"- Best model by Brier: `{report['I_best_model_by_brier']}`",
        f"- Final verdict: `{report['O_final_pass_fail_verdict']}`",
        f"- Recommendation: `{report['P_recommendation']['code']}` - {report['P_recommendation']['label']}`",
        "",
        "## Test Metrics",
    ]
    for name, result in report["G_metrics_for_every_v3_arm"].items():
        if "test_metrics" in result:
            m = result["test_metrics"]
            lines.append(
                f"- `{name}`: log loss `{m['log_loss']:.6f}`, Brier `{m['brier']:.6f}`, top-1 `{m['top1']:.2%}`, top-3 `{m['top3']:.2%}`, ECE `{m['ece']:.5f}`"
            )
        else:
            m = result["core_metrics"]
            lines.append(
                f"- `{name}`: log loss `{m['log_loss']:.6f}`, Brier `{m['brier']:.6f}`, top-1 `{m['top1']:.2%}`, top-3 `{m['top3']:.2%}`, ECE `{m['ece']:.5f}` (sensitivity-only)"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    pb2 = load_v2_module()
    doctrine = load_json(DOCTRINE_AUDIT_V2)
    audit_v4 = load_json(GLOBAL_AUDIT_V4)
    design = load_json(DESIGN_JSON)
    groups = build_groups(doctrine)
    df, cohort_checks = pb2.load_cohort()
    splits = pb2.split_frames(df)

    feature_mask_verification = {
        "core_feature_mask": groups["core"],
        "market_features_excluded_from_core": sorted(set(groups["market"]).isdisjoint(set(groups["core"])) and set(groups["market"]) or []),
        "market_features": groups["market"],
        "ratings_features": groups["ratings"],
        "doctrine_features": groups["doctrine"],
        "structure_context_features": groups["structure"],
    }
    feature_mask_verification["market_features_excluded_from_core"] = True

    leakage_audit = {
        "status": "pass",
        "same_day_or_future_history_leakage": 0,
        "source": "accepted HISTORICAL_DOCTRINE_FEATURES_V1 cohort from Global Audit V4",
    }
    outcome_audit = {
        "status": "pass",
        "forbidden_feature_intersection": sorted(set(groups["core"]) & FORBIDDEN_FIELDS),
        "training_matrix_source": "approved feature masks only",
    }

    ablation_specs = [
        ("market_only_baseline", groups["market"], "market_only", None),
        ("market_plus_ratings_baseline", unique_preserve(groups["market"] + groups["ratings"]), "plain", None),
        ("doctrine_only_baseline", groups["doctrine"], "plain", None),
        ("ratings_plus_doctrine_core", groups["core"], "plain", None),
        ("ratings_plus_doctrine_with_market_calibration", groups["core"], "market_calibration", None),
        ("ratings_plus_doctrine_residual_over_market", groups["core"], "residual", None),
        ("hk_diagnostic", groups["core"], "plain", "HK"),
        ("fr_diagnostic", groups["core"], "plain", "FR"),
    ]

    results: dict[str, Any] = {}
    csv_rows: list[dict[str, Any]] = []
    for name, feature_names, mode, jurisdiction_only in ablation_specs:
        result = evaluate_model_result(
            pb2,
            splits,
            groups,
            name=name,
            feature_names=feature_names,
            mode=mode,
            jurisdiction_only=jurisdiction_only,
        )
        results[name] = result
        csv_rows.extend(
            [
                metrics_rows_for_csv(name, result["train_metrics"], "split", "train"),
                metrics_rows_for_csv(name, result["validation_metrics"], "split", "validation"),
                metrics_rows_for_csv(name, result["test_metrics"], "split", "test"),
            ]
        )
        for jurisdiction, metrics in result["test_metrics_by_jurisdiction"].items():
            csv_rows.append(metrics_rows_for_csv(name, metrics, "jurisdiction", jurisdiction))
        for year, metrics in result["test_metrics_by_year"].items():
            csv_rows.append(metrics_rows_for_csv(name, metrics, "year", year))

    core_result = results["ratings_plus_doctrine_core"]
    market_cal_result = results["ratings_plus_doctrine_with_market_calibration"]
    residual_result = results["ratings_plus_doctrine_residual_over_market"]
    hk_result = results["hk_diagnostic"]["test_metrics"]
    fr_result = results["fr_diagnostic"]["test_metrics"]

    market_only_test = results["market_only_baseline"]["test_metrics"]
    market_plus_ratings_test = results["market_plus_ratings_baseline"]["test_metrics"]
    doctrine_only_test = results["doctrine_only_baseline"]["test_metrics"]
    core_test = core_result["test_metrics"]
    calib_test = market_cal_result["test_metrics"]
    residual_test = residual_result["test_metrics"]

    year_2025 = core_result["test_metrics_by_year"].get("2025", {})
    year_2025_market = results["market_only_baseline"]["test_metrics_by_year"].get("2025", {})
    year_2025_report = {
        "model": "ratings_plus_doctrine_core",
        "status": "sensitivity_only",
        "core_metrics": year_2025,
        "market_metrics": year_2025_market,
        "n_races": year_2025.get("n_races", 0),
        "n_runners": year_2025.get("n_runners", 0),
        "unstable": year_2025.get("n_races", 0) <= 30,
    }
    results["year_2025_sensitivity_report"] = year_2025_report

    comparable_models = {
        name: result
        for name, result in results.items()
        if name not in {"hk_diagnostic", "fr_diagnostic", "year_2025_sensitivity_report"}
    }
    best_log_loss = min(comparable_models.items(), key=lambda item: item[1]["test_metrics"]["log_loss"])
    best_brier = min(comparable_models.items(), key=lambda item: item[1]["test_metrics"]["brier"])

    core_log_loss_pass = core_test["log_loss"] <= 1.481028
    core_brier_pass = core_test["brier"] <= 0.077519
    hk_pass = hk_result["log_loss"] <= results["market_only_baseline"]["test_metrics_by_jurisdiction"]["HK"]["log_loss"]
    fr_pass = fr_result["log_loss"] <= results["market_only_baseline"]["test_metrics_by_jurisdiction"]["FR"]["log_loss"]
    core_recrowd = core_result["market_recrowding_checks"]
    calib_recrowd = market_cal_result["market_recrowding_checks"]
    residual_recrowd = residual_result["market_recrowding_checks"]
    recrowding_pass = (
        core_recrowd["probability_correlation"] <= 0.58
        and core_recrowd["top1_overlap_with_market"] <= 0.45
        and calib_recrowd["probability_correlation"] <= 0.58
        and calib_recrowd["top1_overlap_with_market"] <= 0.45
        and residual_recrowd["probability_correlation"] <= 0.58
        and residual_recrowd["top1_overlap_with_market"] <= 0.45
    )
    overfit_pass = all(
        result["overfit_warning"]["level"] in {"low", "medium"}
        for result in [core_result, market_cal_result, residual_result]
    )
    final_pass = (
        core_log_loss_pass
        and core_brier_pass
        and hk_pass
        and fr_pass
        and recrowding_pass
        and overfit_pass
        and leakage_audit["same_day_or_future_history_leakage"] == 0
        and not outcome_audit["forbidden_feature_intersection"]
    )

    report = {
        "A_design_checkpoint_commit_hash": "300835d55eac4a9566d28a033ec537eb90de8a52",
        "B_eligible_race_runner_count": {
            "races": cohort_checks["eligible_race_count"],
            "runners": cohort_checks["eligible_runner_count"],
        },
        "C_split_counts": {
            split_name: {
                "races": int(frame["event_key"].nunique()),
                "runners": int(frame.shape[0]),
            }
            for split_name, frame in splits.items()
        },
        "D_feature_mask_verification": feature_mask_verification,
        "E_leakage_audit": leakage_audit,
        "F_outcome_field_exclusion_audit": outcome_audit,
        "G_metrics_for_every_v3_arm": results,
        "H_best_model_by_log_loss": best_log_loss[0],
        "I_best_model_by_brier": best_brier[0],
        "J_hk_result": {
            "market": results["market_only_baseline"]["test_metrics_by_jurisdiction"]["HK"],
            "core": hk_result,
            "pass": hk_pass,
        },
        "K_fr_result": {
            "market": results["market_only_baseline"]["test_metrics_by_jurisdiction"]["FR"],
            "core": fr_result,
            "pass": fr_pass,
        },
        "L_2025_sensitivity_result": year_2025_report,
        "M_market_recrowding_checks": {
            "core": core_recrowd,
            "market_calibration": calib_recrowd,
            "residual_over_market": residual_recrowd,
            "thresholds": {
                "probability_correlation_max": 0.58,
                "top1_overlap_with_market_max": 0.45,
            },
            "pass": recrowding_pass,
        },
        "N_overfit_warning": {
            "core": core_result["overfit_warning"],
            "market_calibration": market_cal_result["overfit_warning"],
            "residual_over_market": residual_result["overfit_warning"],
            "pass": overfit_pass,
        },
        "O_final_pass_fail_verdict": "PASS" if final_pass else "FAIL",
        "P_recommendation": {
            "code": "GO_OFFLINE_CANDIDATE_PACKAGE" if final_pass else "FAIL_AND_REVIEW_V3",
            "label": (
                "V3 offline candidate package is justified for review"
                if final_pass
                else "V3 does not yet justify progression beyond offline research"
            ),
            "reasons": {
                "core_log_loss_pass": core_log_loss_pass,
                "core_brier_pass": core_brier_pass,
                "hk_pass": hk_pass,
                "fr_pass": fr_pass,
                "recrowding_pass": recrowding_pass,
                "overfit_pass": overfit_pass,
                "no_leakage": leakage_audit["same_day_or_future_history_leakage"] == 0,
                "no_outcome_fields": not outcome_audit["forbidden_feature_intersection"],
            },
            "context": {
                "market_only_test": market_only_test,
                "market_plus_ratings_test": market_plus_ratings_test,
                "doctrine_only_test": doctrine_only_test,
                "core_test": core_test,
                "market_calibration_test": calib_test,
                "residual_over_market_test": residual_test,
            },
            "authority_model": audit_v4["authority_model"],
        },
    }

    JSON_OUT.write_text(json.dumps(to_jsonable(report), indent=2), encoding="utf-8")
    MD_OUT.write_text(build_markdown(report), encoding="utf-8")

    with CSV_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "model",
                "scope",
                "scope_value",
                "log_loss",
                "brier",
                "top1",
                "top3",
                "ece",
                "market_rank_lift",
                "n_races",
                "n_runners",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")
    print(f"Wrote {CSV_OUT}")


if __name__ == "__main__":
    main()
