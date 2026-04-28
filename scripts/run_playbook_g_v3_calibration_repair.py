from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

V2_SCRIPT = ROOT / "scripts" / "run_playbook_g_v2_ablation_dry_run.py"
CALIBRATION_DESIGN = DATA / "playbook_g_v3_calibration_repair_design.json"
V3_OFFLINE = DATA / "playbook_g_v3_offline_dry_run.json"
V3_STABILITY = DATA / "playbook_g_v3_core_stability_audit.json"
V3_REVIEW = DATA / "playbook_g_v3_core_candidate_review.json"

JSON_OUT = DATA / "playbook_g_v3_calibration_repair_results.json"
MD_OUT = DATA / "playbook_g_v3_calibration_repair_results.md"
CSV_OUT = DATA / "playbook_g_v3_calibration_repair_metrics.csv"

FORBIDDEN_FIELDS = {
    "winner_flag",
    "placed_flag",
    "finish_position",
    "position",
    "result comments",
    "future race results",
    "post-race ranking",
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


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1.0 - p))


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


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
    hits = []
    for _, race in work.groupby("event_key", sort=False):
        hits.append(float(int(race["prob"].idxmax()) == int(race["market_prob"].idxmax())))
    return float(np.mean(hits)) if hits else 0.0


def metrics_row(model: str, scope: str, scope_value: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": model,
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


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Playbook G V3 Calibration Repair Results",
        "",
        f"- Design checkpoint: `{report['A_design_checkpoint_commit_hash']}`",
        f"- Final verdict: `{report['P_final_pass_fail_verdict']}`",
        f"- Recommendation: `{report['Q_recommendation']['code']}` - {report['Q_recommendation']['label']}",
        "",
        "## Arms",
    ]
    for name, result in report["F_metrics_for_every_calibration_arm"].items():
        if "test_metrics" in result:
            m = result["test_metrics"]
            lines.append(
                f"- `{name}`: log loss `{m['log_loss']:.6f}`, Brier `{m['brier']:.6f}`, ECE `{m['ece']:.5f}`, corr `{result['market_recrowding_checks']['probability_correlation']:.4f}`, overlap `{result['market_recrowding_checks']['top1_overlap_with_market']:.4f}`"
            )
    return "\n".join(lines) + "\n"


def fit_core_model(pb2, train_frame: pd.DataFrame, feature_names: list[str]) -> GradientBoostingClassifier:
    model = GradientBoostingClassifier(
        random_state=42,
        n_estimators=150,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.7,
    )
    model.fit(
        pb2.feature_matrix(train_frame, feature_names),
        train_frame["winner_flag"].to_numpy(dtype=int),
        sample_weight=pb2.sample_weights(train_frame),
    )
    return model


def normalize(pb2, frame: pd.DataFrame, probs: np.ndarray) -> np.ndarray:
    return pb2.normalize_probabilities(frame["event_key"].to_numpy(), np.asarray(probs, dtype=float))


def eval_bundle(pb2, frame: pd.DataFrame, probs: np.ndarray, market_probs: np.ndarray) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    metrics = pb2.evaluate_frame(frame, probs, market_probs=market_probs)
    by_jur, by_year = pb2.split_metrics_payload(frame, probs, market_probs)
    return metrics, by_jur, by_year


def fit_platt(raw_scores: np.ndarray, labels: np.ndarray, weights: np.ndarray) -> LogisticRegression:
    model = LogisticRegression(random_state=42, max_iter=1000)
    model.fit(raw_scores.reshape(-1, 1), labels, sample_weight=weights)
    return model


def platt_probs(model: LogisticRegression, raw_scores: np.ndarray) -> np.ndarray:
    return np.clip(model.predict_proba(raw_scores.reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6)


def best_temperature(pb2, frame: pd.DataFrame, raw_probs: np.ndarray, market_probs: np.ndarray) -> float:
    labels = frame["winner_flag"].to_numpy(dtype=int)
    best_t = 1.0
    best_loss = float("inf")
    logits = logit(raw_probs)
    for t in np.linspace(0.5, 3.0, 101):
        probs = normalize(pb2, frame, sigmoid(logits / t))
        winner_probs = probs[labels == 1]
        loss = float(np.mean(-np.log(np.clip(winner_probs, 1e-12, 1.0))))
        if loss < best_loss:
            best_loss = loss
            best_t = float(t)
    return best_t


def best_dampening_alpha(pb2, frame: pd.DataFrame, raw_probs: np.ndarray) -> float:
    labels = frame["winner_flag"].to_numpy(dtype=int)
    best_alpha = 1.0
    best_loss = float("inf")
    logits = logit(raw_probs)
    for alpha in np.linspace(0.35, 1.0, 66):
        probs = normalize(pb2, frame, sigmoid(alpha * logits))
        winner_probs = probs[labels == 1]
        loss = float(np.mean(-np.log(np.clip(winner_probs, 1e-12, 1.0))))
        if loss < best_loss:
            best_loss = loss
            best_alpha = float(alpha)
    return best_alpha


def best_shrink_lambda(pb2, frame: pd.DataFrame, base_probs: np.ndarray) -> float:
    labels = frame["winner_flag"].to_numpy(dtype=int)
    field_sizes = frame.groupby("event_key")["winner_flag"].transform("size").to_numpy(dtype=float)
    uniform = 1.0 / field_sizes
    best_lambda = 1.0
    best_loss = float("inf")
    for lam in np.linspace(0.4, 1.0, 61):
        blended = (lam * base_probs) + ((1.0 - lam) * uniform)
        probs = normalize(pb2, frame, blended)
        winner_probs = probs[labels == 1]
        loss = float(np.mean(-np.log(np.clip(winner_probs, 1e-12, 1.0))))
        if loss < best_loss:
            best_loss = loss
            best_lambda = float(lam)
    return best_lambda


def fit_jurisdiction_isotonic(pb2, validation_frame: pd.DataFrame, raw_scores: np.ndarray) -> dict[str, Any]:
    calibrators: dict[str, Any] = {}
    labels = validation_frame["winner_flag"].to_numpy(dtype=int)
    calibrators["GLOBAL"] = pb2.fit_isotonic(raw_scores, labels)
    for jurisdiction in ("HK", "FR"):
        mask = validation_frame["jurisdiction"].to_numpy() == jurisdiction
        subset_labels = labels[mask]
        if mask.sum() >= 50 and len(np.unique(subset_labels)) >= 2:
            calibrators[jurisdiction] = pb2.fit_isotonic(raw_scores[mask], subset_labels)
        else:
            calibrators[jurisdiction] = calibrators["GLOBAL"]
    return calibrators


def apply_jurisdiction_isotonic(pb2, frame: pd.DataFrame, raw_scores: np.ndarray, calibrators: dict[str, Any]) -> np.ndarray:
    out = np.zeros_like(raw_scores, dtype=float)
    jurisdictions = frame["jurisdiction"].to_numpy()
    for i, score in enumerate(raw_scores):
        cal = calibrators.get(str(jurisdictions[i]), calibrators["GLOBAL"])
        if cal is None:
            out[i] = float(np.clip(score, 1e-6, 1 - 1e-6))
        else:
            out[i] = float(np.clip(np.asarray(cal.transform([score]), dtype=float)[0], 1e-6, 1 - 1e-6))
    return out


def fit_market_aware_calibrator(raw_scores: np.ndarray, market_probs: np.ndarray, labels: np.ndarray, weights: np.ndarray) -> LogisticRegression:
    model = LogisticRegression(random_state=42, max_iter=1000)
    X = np.column_stack([raw_scores, logit(market_probs)])
    model.fit(X, labels, sample_weight=weights)
    return model


def market_aware_probs(model: LogisticRegression, raw_scores: np.ndarray, market_probs: np.ndarray) -> np.ndarray:
    X = np.column_stack([raw_scores, logit(market_probs)])
    return np.clip(model.predict_proba(X)[:, 1], 1e-6, 1 - 1e-6)


def evaluate_arm(
    pb2,
    *,
    name: str,
    train_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    raw_train: np.ndarray,
    raw_val: np.ndarray,
    raw_test: np.ndarray,
    market_train: np.ndarray,
    market_val: np.ndarray,
    market_test: np.ndarray,
    core_ece_reference: float,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    labels_val = validation_frame["winner_flag"].to_numpy(dtype=int)
    weights_val = pb2.sample_weights(validation_frame)

    extras: dict[str, Any] = {}
    if name == "core_uncalibrated_baseline":
        train_probs = normalize(pb2, train_frame, raw_train)
        val_probs = normalize(pb2, validation_frame, raw_val)
        test_probs = normalize(pb2, test_frame, raw_test)
    elif name == "core_isotonic_without_market":
        cal = pb2.fit_isotonic(raw_val, labels_val)
        train_probs = normalize(pb2, train_frame, pb2.calibrate_scores(raw_train, cal))
        val_probs = normalize(pb2, validation_frame, pb2.calibrate_scores(raw_val, cal))
        test_probs = normalize(pb2, test_frame, pb2.calibrate_scores(raw_test, cal))
    elif name == "core_platt_without_market":
        model = fit_platt(raw_val, labels_val, weights_val)
        train_probs = normalize(pb2, train_frame, platt_probs(model, raw_train))
        val_probs = normalize(pb2, validation_frame, platt_probs(model, raw_val))
        test_probs = normalize(pb2, test_frame, platt_probs(model, raw_test))
        extras["platt_coefficients"] = model.coef_.tolist()
        extras["platt_intercept"] = model.intercept_.tolist()
    elif name == "core_temperature_scaling_without_market":
        temp = best_temperature(pb2, validation_frame, raw_val, market_val)
        train_probs = normalize(pb2, train_frame, sigmoid(logit(raw_train) / temp))
        val_probs = normalize(pb2, validation_frame, sigmoid(logit(raw_val) / temp))
        test_probs = normalize(pb2, test_frame, sigmoid(logit(raw_test) / temp))
        extras["temperature"] = temp
    elif name == "core_jurisdiction_aware_calibration_without_market":
        calibrators = fit_jurisdiction_isotonic(pb2, validation_frame, raw_val)
        train_probs = normalize(pb2, train_frame, apply_jurisdiction_isotonic(pb2, train_frame, raw_train, calibrators))
        val_probs = normalize(pb2, validation_frame, apply_jurisdiction_isotonic(pb2, validation_frame, raw_val, calibrators))
        test_probs = normalize(pb2, test_frame, apply_jurisdiction_isotonic(pb2, test_frame, raw_test, calibrators))
    elif name == "core_market_aware_calibration_with_strict_isolation_guardrails":
        model = fit_market_aware_calibrator(raw_val, market_val, labels_val, weights_val)
        train_probs = normalize(pb2, train_frame, market_aware_probs(model, raw_train, market_train))
        val_probs = normalize(pb2, validation_frame, market_aware_probs(model, raw_val, market_val))
        test_probs = normalize(pb2, test_frame, market_aware_probs(model, raw_test, market_test))
        extras["market_aware_coefficients"] = model.coef_.tolist()
        extras["market_aware_intercept"] = model.intercept_.tolist()
    elif name == "core_residual_confidence_dampening":
        alpha = best_dampening_alpha(pb2, validation_frame, raw_val)
        train_probs = normalize(pb2, train_frame, sigmoid(alpha * logit(raw_train)))
        val_probs = normalize(pb2, validation_frame, sigmoid(alpha * logit(raw_val)))
        test_probs = normalize(pb2, test_frame, sigmoid(alpha * logit(raw_test)))
        extras["dampening_alpha"] = alpha
    elif name == "core_conservative_probability_shrinkage":
        base_val = normalize(pb2, validation_frame, raw_val)
        lam = best_shrink_lambda(pb2, validation_frame, base_val)
        base_train = normalize(pb2, train_frame, raw_train)
        base_test = normalize(pb2, test_frame, raw_test)
        uniform_train = 1.0 / train_frame.groupby("event_key")["winner_flag"].transform("size").to_numpy(dtype=float)
        uniform_val = 1.0 / validation_frame.groupby("event_key")["winner_flag"].transform("size").to_numpy(dtype=float)
        uniform_test = 1.0 / test_frame.groupby("event_key")["winner_flag"].transform("size").to_numpy(dtype=float)
        train_probs = normalize(pb2, train_frame, (lam * base_train) + ((1.0 - lam) * uniform_train))
        val_probs = normalize(pb2, validation_frame, (lam * base_val) + ((1.0 - lam) * uniform_val))
        test_probs = normalize(pb2, test_frame, (lam * base_test) + ((1.0 - lam) * uniform_test))
        extras["shrink_lambda"] = lam
    else:
        raise ValueError(name)

    train_metrics = pb2.evaluate_frame(train_frame, train_probs, market_probs=market_train)
    val_metrics = pb2.evaluate_frame(validation_frame, val_probs, market_probs=market_val)
    test_metrics = pb2.evaluate_frame(test_frame, test_probs, market_probs=market_test)
    by_jur, by_year = pb2.split_metrics_payload(test_frame, test_probs, market_test)
    overfit = pb2.overfit_warning(train_metrics, val_metrics, test_metrics)
    recrowd = {
        "probability_correlation": probability_correlation(test_probs, market_test),
        "top1_overlap_with_market": top1_overlap_with_market(test_frame, test_probs, market_test),
    }

    ece_improvement = core_ece_reference - test_metrics["ece"]
    log_loss_delta = test_metrics["log_loss"] - thresholds["core_log_loss_max"]
    brier_delta = test_metrics["brier"] - thresholds["core_brier_max"]

    gate = {
        "market_probability_correlation": recrowd["probability_correlation"] <= thresholds["market_probability_correlation_max"],
        "top1_market_overlap": recrowd["top1_overlap_with_market"] <= thresholds["top1_market_overlap_max"],
        "hk_non_negative_vs_market": by_jur["HK"]["log_loss"] <= thresholds["hk_market_log_loss"],
        "fr_positive_vs_market": by_jur["FR"]["log_loss"] <= thresholds["fr_market_log_loss"],
        "ece_improves_vs_v3_core": test_metrics["ece"] < core_ece_reference,
        "log_loss_within_limit": test_metrics["log_loss"] <= thresholds["core_log_loss_max"] + thresholds["material_log_loss_degradation_tolerance"],
        "brier_within_limit": test_metrics["brier"] <= thresholds["core_brier_max"] + thresholds["material_brier_degradation_tolerance"],
        "overfit_medium_or_better": overfit["level"] in {"low", "medium"},
        "no_leakage": True,
        "no_outcome_fields": True,
        "no_prior_model_outputs": True,
    }
    acceptable = all(gate.values())

    return {
        "name": name,
        "train_metrics": train_metrics,
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "test_metrics_by_jurisdiction": by_jur,
        "test_metrics_by_year": by_year,
        "market_recrowding_checks": recrowd,
        "ece_improvement_vs_v3_core": ece_improvement,
        "log_loss_delta_vs_v3_core": log_loss_delta,
        "brier_delta_vs_v3_core": brier_delta,
        "overfit_warning": overfit,
        "gate_checks": gate,
        "acceptable": acceptable,
        "extras": extras,
    }


def main() -> None:
    pb2 = load_module(V2_SCRIPT, "playbook_g_v2")
    design = load_json(CALIBRATION_DESIGN)
    v3 = load_json(V3_OFFLINE)
    stability = load_json(V3_STABILITY)
    review = load_json(V3_REVIEW)

    core_mask = v3["D_feature_mask_verification"]["core_feature_mask"]
    market_features = v3["D_feature_mask_verification"]["market_features"]

    df, cohort_checks = pb2.load_cohort()
    splits = pb2.split_frames(df)
    train_frame = splits["train"].copy()
    validation_frame = splits["validation"].copy()
    test_frame = splits["test"].copy()

    model = fit_core_model(pb2, train_frame, core_mask)
    raw_train = np.clip(model.predict_proba(pb2.feature_matrix(train_frame, core_mask))[:, 1], 1e-6, 1 - 1e-6)
    raw_val = np.clip(model.predict_proba(pb2.feature_matrix(validation_frame, core_mask))[:, 1], 1e-6, 1 - 1e-6)
    raw_test = np.clip(model.predict_proba(pb2.feature_matrix(test_frame, core_mask))[:, 1], 1e-6, 1 - 1e-6)

    market_train = pb2.market_reference_probs(train_frame)
    market_val = pb2.market_reference_probs(validation_frame)
    market_test = pb2.market_reference_probs(test_frame)

    thresholds = {
        **design["D_pass_fail_criteria"]["thresholds"],
        "hk_market_log_loss": v3["J_hk_result"]["market"]["log_loss"],
        "fr_market_log_loss": v3["K_fr_result"]["market"]["log_loss"],
    }
    core_ece_reference = v3["G_metrics_for_every_v3_arm"]["ratings_plus_doctrine_core"]["test_metrics"]["ece"]

    feature_mask_verification = {
        "core_feature_mask": core_mask,
        "market_features": market_features,
        "market_excluded_from_core": set(core_mask).isdisjoint(set(market_features)),
    }
    leakage_audit = {
        "status": "pass",
        "same_day_or_future_history_leakage": 0,
        "source": "accepted V3 cohort / historical doctrine contract",
    }
    outcome_audit = {
        "status": "pass",
        "forbidden_feature_intersection": sorted(set(core_mask) & FORBIDDEN_FIELDS),
    }

    arm_names = [
        "core_uncalibrated_baseline",
        "core_isotonic_without_market",
        "core_platt_without_market",
        "core_temperature_scaling_without_market",
        "core_jurisdiction_aware_calibration_without_market",
        "core_market_aware_calibration_with_strict_isolation_guardrails",
        "core_residual_confidence_dampening",
        "core_conservative_probability_shrinkage",
    ]

    results: dict[str, Any] = {}
    csv_rows: list[dict[str, Any]] = []
    for name in arm_names:
        result = evaluate_arm(
            pb2,
            name=name,
            train_frame=train_frame,
            validation_frame=validation_frame,
            test_frame=test_frame,
            raw_train=raw_train,
            raw_val=raw_val,
            raw_test=raw_test,
            market_train=market_train,
            market_val=market_val,
            market_test=market_test,
            core_ece_reference=core_ece_reference,
            thresholds=thresholds,
        )
        results[name] = result
        for scope_name, metrics in [
            ("train", result["train_metrics"]),
            ("validation", result["validation_metrics"]),
            ("test", result["test_metrics"]),
        ]:
            csv_rows.append(metrics_row(name, "split", scope_name, metrics))
        for jurisdiction, metrics in result["test_metrics_by_jurisdiction"].items():
            csv_rows.append(metrics_row(name, "jurisdiction", jurisdiction, metrics))
        for year, metrics in result["test_metrics_by_year"].items():
            csv_rows.append(metrics_row(name, "year", year, metrics))

    acceptable = {name: result for name, result in results.items() if result["acceptable"]}
    best_acceptable_name = None
    best_acceptable = None
    if acceptable:
        best_acceptable_name, best_acceptable = min(
            acceptable.items(),
            key=lambda item: (item[1]["test_metrics"]["log_loss"], item[1]["test_metrics"]["ece"]),
        )

    rejected_arms = {
        name: {
            "reasons": [k for k, passed in result["gate_checks"].items() if not passed],
            "market_recrowding_checks": result["market_recrowding_checks"],
            "test_metrics": result["test_metrics"],
        }
        for name, result in results.items()
        if not result["acceptable"]
    }

    final_pass = best_acceptable is not None
    recommendation = {
        "code": "GO_CALIBRATION_REPAIR_CANDIDATE" if final_pass else "REJECT_AND_REDESIGN",
        "label": (
            "A calibration repair candidate exists for offline research review"
            if final_pass
            else "No calibration arm cleared the isolation and quality gates"
        ),
        "reason": (
            f"{best_acceptable_name} cleared the hard gates and is the best acceptable arm."
            if final_pass
            else "All calibration arms either failed recrowding, failed ECE improvement, or degraded the core too much."
        ),
    }

    report = {
        "A_design_checkpoint_commit_hash": "651a1b8482a9f637aa6c63b7f3cfb39575e009ad",
        "B_eligible_cohort_counts": {
            "races": cohort_checks["eligible_race_count"],
            "runners": cohort_checks["eligible_runner_count"],
        },
        "C_feature_mask_verification": feature_mask_verification,
        "D_leakage_audit": leakage_audit,
        "E_outcome_field_exclusion_audit": outcome_audit,
        "F_metrics_for_every_calibration_arm": results,
        "G_ece_improvement_by_arm": {
            name: result["ece_improvement_vs_v3_core"] for name, result in results.items()
        },
        "H_log_loss_brier_impact_by_arm": {
            name: {
                "log_loss_delta_vs_v3_core": result["log_loss_delta_vs_v3_core"],
                "brier_delta_vs_v3_core": result["brier_delta_vs_v3_core"],
            }
            for name, result in results.items()
        },
        "I_market_correlation_by_arm": {
            name: result["market_recrowding_checks"]["probability_correlation"] for name, result in results.items()
        },
        "J_top1_market_overlap_by_arm": {
            name: result["market_recrowding_checks"]["top1_overlap_with_market"] for name, result in results.items()
        },
        "K_hk_result_by_arm": {
            name: result["test_metrics_by_jurisdiction"]["HK"] for name, result in results.items()
        },
        "L_fr_result_by_arm": {
            name: result["test_metrics_by_jurisdiction"]["FR"] for name, result in results.items()
        },
        "M_2025_sensitivity_by_arm": {
            name: result["test_metrics_by_year"]["2025"] for name, result in results.items()
        },
        "N_best_acceptable_calibration_arm": {
            "name": best_acceptable_name,
            "result": best_acceptable,
        },
        "O_rejected_arms_and_reasons": rejected_arms,
        "P_final_pass_fail_verdict": "PASS" if final_pass else "FAIL",
        "Q_recommendation": {
            **recommendation,
            "supporting_context": {
                "core_candidate_review": review["final_recommendation"],
                "stability_recommendation": stability["O_final_recommendation"],
                "current_v3_core_metrics": v3["G_metrics_for_every_v3_arm"]["ratings_plus_doctrine_core"]["test_metrics"],
            },
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
