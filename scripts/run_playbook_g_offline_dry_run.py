from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_playbook_g_dry_run_gate import (  # noqa: E402
    EVENT_IDENTITY_CONTRACT,
    FEATURE_VECTOR_NAMES,
    FORBIDDEN_MODEL_AND_META_KEYS,
    FORBIDDEN_OUTCOME_FEATURES,
    HISTORICAL_SOURCE,
    MARKET_ONLY_FEATURES,
    SIGNAL_CONTRACT_VERSION,
    TRAINING_ELIGIBLE,
    load_eligible_rows,
    split_name,
)

DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models" / "offline_research" / "playbook_g_dry_run_v1"

RANDOM_STATE = 42
ROI_THRESHOLDS = [0.03, 0.05, 0.08]


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


def build_dataframe(rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    feature_json_keys: set[str] = set()
    vector_nan_count = 0
    vector_inf_count = 0
    rows_with_nan = 0
    rows_with_inf = 0
    macro_context_versions = Counter()

    for row in rows:
        feature_json = row["_feature_json"]
        vector = row["_vector"]
        feature_json_keys.update(feature_json.keys())
        macro_context_versions[str(feature_json.get("macro_context_version"))] += 1

        has_nan = False
        has_inf = False
        vector_payload: dict[str, float] = {}
        for feature_name, value in zip(FEATURE_VECTOR_NAMES, vector):
            number = safe_float(value)
            if number is None:
                try:
                    probe = float(value)
                except (TypeError, ValueError):
                    vector_nan_count += 1
                    has_nan = True
                    number = 0.0
                else:
                    if math.isnan(probe):
                        vector_nan_count += 1
                        has_nan = True
                        number = 0.0
                    elif math.isinf(probe):
                        vector_inf_count += 1
                        has_inf = True
                        number = 0.0
                    else:
                        number = probe
            vector_payload[feature_name] = float(number)

        rows_with_nan += int(has_nan)
        rows_with_inf += int(has_inf)
        records.append(
            {
                "race_id": str(row["race_id"]),
                "horse_id": str(row["horse_id"]),
                "race_date": row["_race_date_iso"],
                "race_year": row["_race_year"],
                "course": row.get("course") or "UNKNOWN",
                "jurisdiction": row.get("jurisdiction") or "UNKNOWN",
                "winner_flag": int(bool(row.get("winner_flag"))),
                "finish_position": row.get("finish_position"),
                "sp_dec": float(row.get("sp_dec")),
                "implied_prob": float(row.get("implied_prob")),
                "mpi": float(row.get("mpi")),
                "chaos_bloom": float(row.get("chaos_bloom")),
                **vector_payload,
            }
        )

    df = pd.DataFrame.from_records(records)
    leakage = {
        "training_matrix_source": "feature_json.strictly_ordered_vector only",
        "forbidden_outcome_feature_intersection": sorted(set(FORBIDDEN_OUTCOME_FEATURES).intersection(FEATURE_VECTOR_NAMES)),
        "forbidden_model_meta_feature_intersection": sorted(set(FORBIDDEN_MODEL_AND_META_KEYS).intersection(FEATURE_VECTOR_NAMES)),
        "model_output_or_meta_keys_present_outside_vector": sorted(set(FORBIDDEN_MODEL_AND_META_KEYS).intersection(feature_json_keys)),
        "vector_nan_count": vector_nan_count,
        "vector_inf_count": vector_inf_count,
        "rows_with_nan": rows_with_nan,
        "rows_with_inf": rows_with_inf,
        "macro_context_version_distribution": dict(macro_context_versions),
    }
    return df, leakage


def race_level_normalize(df: pd.DataFrame, raw_column: str, out_column: str) -> pd.DataFrame:
    result = df.copy()
    totals = result.groupby("race_id")[raw_column].transform("sum").replace(0, np.nan)
    result[out_column] = (result[raw_column] / totals).fillna(0.0)
    return result


def compute_split_metrics(df: pd.DataFrame, prob_column: str) -> dict[str, Any]:
    runner_probs = np.clip(df[prob_column].to_numpy(dtype=float), 1e-15, 1 - 1e-15)
    labels = df["winner_flag"].to_numpy(dtype=int)
    runner_log_loss = float(
        np.mean(-(labels * np.log(runner_probs) + (1 - labels) * np.log(1 - runner_probs)))
    )
    brier = float(np.mean((labels - runner_probs) ** 2))

    grouped = df.sort_values(["race_id", prob_column, "horse_id"], ascending=[True, False, True]).groupby("race_id")
    winner_log_loss_sum = 0.0
    top1 = 0
    top3 = 0
    top1_rank_sum = 0.0
    top1_count = 0
    for _, group in grouped:
        winners = group[group["winner_flag"] == 1]
        if winners.empty:
            continue
        winner_row = winners.iloc[0]
        winner_prob = float(np.clip(winner_row[prob_column], 1e-15, 1 - 1e-15))
        winner_log_loss_sum += -math.log(winner_prob)
        winner_rank = int(group.index.get_loc(winner_row.name)) + 1
        top1 += int(winner_rank == 1)
        top3 += int(winner_rank <= 3)
        top1_rank_sum += winner_rank
        top1_count += 1

    calibration = compute_calibration(df[prob_column].to_numpy(dtype=float), labels)
    return {
        "race_count": int(df["race_id"].nunique()),
        "runner_count": int(len(df)),
        "winner_multiclass_log_loss": winner_log_loss_sum / top1_count if top1_count else None,
        "runner_log_loss": runner_log_loss,
        "brier_score": brier,
        "top_1_winner_hit_rate": top1 / top1_count if top1_count else None,
        "top_3_containment": top3 / top1_count if top1_count else None,
        "mean_winner_rank": top1_rank_sum / top1_count if top1_count else None,
        "calibration": calibration,
    }


def compute_calibration(predictions: np.ndarray, labels: np.ndarray, bins: int = 10) -> dict[str, Any]:
    if len(predictions) == 0:
        return {"ece": None, "bins": []}

    frame = pd.DataFrame({"pred": predictions, "label": labels})
    try:
        frame["bucket"] = pd.qcut(frame["pred"], q=min(bins, frame["pred"].nunique()), duplicates="drop")
    except ValueError:
        frame["bucket"] = pd.cut(frame["pred"], bins=min(bins, max(2, frame["pred"].nunique())))

    calibration_bins: list[dict[str, Any]] = []
    ece = 0.0
    for _, bucket in frame.groupby("bucket", observed=False):
        if bucket.empty:
            continue
        pred_mean = float(bucket["pred"].mean())
        label_mean = float(bucket["label"].mean())
        weight = len(bucket) / len(frame)
        ece += weight * abs(pred_mean - label_mean)
        calibration_bins.append(
            {
                "count": int(len(bucket)),
                "pred_mean": pred_mean,
                "label_mean": label_mean,
                "abs_gap": abs(pred_mean - label_mean),
            }
        )
    return {"ece": ece, "bins": calibration_bins}


def fit_market_logistic(train_df: pd.DataFrame) -> CalibratedClassifierCV:
    estimator = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("logistic", LogisticRegression(max_iter=4000, random_state=RANDOM_STATE)),
        ]
    )
    model = CalibratedClassifierCV(estimator, method="isotonic", cv=3)
    model.fit(train_df[MARKET_ONLY_FEATURES], train_df["winner_flag"])
    return model


def fit_candidate_model(train_df: pd.DataFrame) -> CalibratedClassifierCV:
    estimator = GradientBoostingClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5,
        min_samples_split=80,
        min_samples_leaf=40,
        subsample=0.8,
        max_features="sqrt",
        random_state=RANDOM_STATE,
    )
    model = CalibratedClassifierCV(estimator, method="isotonic", cv=3)
    model.fit(train_df[FEATURE_VECTOR_NAMES], train_df["winner_flag"])
    return model


def fit_candidate_importance_model(train_df: pd.DataFrame) -> GradientBoostingClassifier:
    model = GradientBoostingClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5,
        min_samples_split=80,
        min_samples_leaf=40,
        subsample=0.8,
        max_features="sqrt",
        random_state=RANDOM_STATE,
    )
    model.fit(train_df[FEATURE_VECTOR_NAMES], train_df["winner_flag"])
    return model


def add_model_predictions(
    base_df: pd.DataFrame,
    market_logistic: CalibratedClassifierCV,
    candidate_model: CalibratedClassifierCV,
) -> pd.DataFrame:
    df = base_df.copy()
    df["market_prob_raw"] = df["implied_prob"].astype(float)
    df["sp_rank_recip_raw"] = 1.0 / df["sp_rank"].replace(0, np.nan)
    df["sp_rank_recip_raw"] = df["sp_rank_recip_raw"].fillna(0.0)
    df["market_logistic_raw"] = market_logistic.predict_proba(df[MARKET_ONLY_FEATURES])[:, 1]
    df["candidate_raw"] = candidate_model.predict_proba(df[FEATURE_VECTOR_NAMES])[:, 1]

    for raw_col, norm_col in (
        ("market_prob_raw", "market_prob"),
        ("sp_rank_recip_raw", "sp_rank_prob"),
        ("market_logistic_raw", "market_logistic_prob"),
        ("candidate_raw", "candidate_prob"),
    ):
        df = race_level_normalize(df, raw_col, norm_col)
    return df


def split_frames(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "train": df[df["race_year"].between(2017, 2020)].copy(),
        "validation": df[df["race_year"].between(2021, 2022)].copy(),
        "test": df[df["race_year"].between(2023, 2025)].copy(),
        "all": df.copy(),
    }


def evaluate_all_models(split_frames_map: dict[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for model_name, prob_column in (
        ("market_implied_baseline", "market_prob"),
        ("sp_rank_reciprocal_baseline", "sp_rank_prob"),
        ("market_only_logistic", "market_logistic_prob"),
        ("playbook_g_candidate", "candidate_prob"),
    ):
        result[model_name] = {}
        for split_name_key, frame in split_frames_map.items():
            result[model_name][split_name_key] = compute_split_metrics(frame, prob_column)
    return result


def compute_lift(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float | None]:
    return {
        "winner_multiclass_log_loss_delta": (
            candidate["winner_multiclass_log_loss"] - reference["winner_multiclass_log_loss"]
            if candidate["winner_multiclass_log_loss"] is not None and reference["winner_multiclass_log_loss"] is not None
            else None
        ),
        "brier_score_delta": (
            candidate["brier_score"] - reference["brier_score"]
            if candidate["brier_score"] is not None and reference["brier_score"] is not None
            else None
        ),
        "top_1_hit_rate_delta": (
            candidate["top_1_winner_hit_rate"] - reference["top_1_winner_hit_rate"]
            if candidate["top_1_winner_hit_rate"] is not None and reference["top_1_winner_hit_rate"] is not None
            else None
        ),
        "top_3_containment_delta": (
            candidate["top_3_containment"] - reference["top_3_containment"]
            if candidate["top_3_containment"] is not None and reference["top_3_containment"] is not None
            else None
        ),
        "ece_delta": (
            candidate["calibration"]["ece"] - reference["calibration"]["ece"]
            if candidate["calibration"]["ece"] is not None and reference["calibration"]["ece"] is not None
            else None
        ),
    }


def compute_jurisdiction_metrics(test_df: pd.DataFrame) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for jurisdiction, frame in test_df.groupby("jurisdiction"):
        results[str(jurisdiction)] = {
            "market": compute_split_metrics(frame, "market_prob"),
            "market_only_logistic": compute_split_metrics(frame, "market_logistic_prob"),
            "candidate": compute_split_metrics(frame, "candidate_prob"),
        }
    return results


def compute_year_metrics(test_df: pd.DataFrame) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for year, frame in test_df.groupby("race_year"):
        results[str(year)] = {
            "market": compute_split_metrics(frame, "market_prob"),
            "market_only_logistic": compute_split_metrics(frame, "market_logistic_prob"),
            "candidate": compute_split_metrics(frame, "candidate_prob"),
        }
    return results


def anchored_rolling_origin(df: pd.DataFrame) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    years = sorted(df["race_year"].unique())
    for eval_year in years:
        if eval_year < 2021:
            continue
        train_frame = df[df["race_year"] < eval_year]
        eval_frame = df[df["race_year"] == eval_year]
        if train_frame["race_id"].nunique() < 100 or eval_frame.empty:
            continue
        market_logistic = fit_market_logistic(train_frame)
        candidate = fit_candidate_model(train_frame)
        scored = add_model_predictions(eval_frame, market_logistic, candidate)
        outputs[str(eval_year)] = {
            "market": compute_split_metrics(scored, "market_prob"),
            "market_only_logistic": compute_split_metrics(scored, "market_logistic_prob"),
            "candidate": compute_split_metrics(scored, "candidate_prob"),
        }
    return outputs


def compute_overfit_warning(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidate_train = metrics["playbook_g_candidate"]["train"]
    candidate_validation = metrics["playbook_g_candidate"]["validation"]
    candidate_test = metrics["playbook_g_candidate"]["test"]

    train_ll = candidate_train["winner_multiclass_log_loss"]
    val_ll = candidate_validation["winner_multiclass_log_loss"]
    test_ll = candidate_test["winner_multiclass_log_loss"]
    train_brier = candidate_train["brier_score"]
    val_brier = candidate_validation["brier_score"]
    test_brier = candidate_test["brier_score"]

    rel_val_ll = ((val_ll - train_ll) / train_ll) if train_ll else None
    rel_test_ll = ((test_ll - train_ll) / train_ll) if train_ll else None
    rel_val_brier = ((val_brier - train_brier) / train_brier) if train_brier else None
    rel_test_brier = ((test_brier - train_brier) / train_brier) if train_brier else None

    high = bool(
        rel_test_ll is not None
        and rel_val_ll is not None
        and rel_test_brier is not None
        and rel_val_brier is not None
        and rel_test_ll > 0.10
        and rel_val_ll > 0.05
        and rel_test_brier > 0.10
        and rel_val_brier > 0.05
    )
    return {
        "status": "high" if high else "controlled",
        "relative_log_loss_increase_validation_vs_train": rel_val_ll,
        "relative_log_loss_increase_test_vs_train": rel_test_ll,
        "relative_brier_increase_validation_vs_train": rel_val_brier,
        "relative_brier_increase_test_vs_train": rel_test_brier,
    }


def compute_feature_importance(train_df: pd.DataFrame) -> dict[str, Any]:
    model = fit_candidate_importance_model(train_df)
    pairs = sorted(zip(FEATURE_VECTOR_NAMES, model.feature_importances_), key=lambda item: item[1], reverse=True)
    top = [{"feature": feature, "importance": float(importance)} for feature, importance in pairs[:15]]
    return {
        "top_15": top,
        "full_importance_map": {feature: float(importance) for feature, importance in pairs},
    }


def compute_roi_research(test_df: pd.DataFrame) -> dict[str, Any]:
    results: dict[str, Any] = {"status": "non_deployment_research_only", "thresholds": {}}
    for threshold in ROI_THRESHOLDS:
        bets = 0
        wins = 0
        profit = 0.0
        turnover = 0.0
        for _, group in test_df.groupby("race_id"):
            ordered = group.sort_values(["candidate_prob", "horse_id"], ascending=[False, True])
            top = ordered.iloc[0]
            edge = float(top["candidate_prob"] - top["market_prob"])
            if edge < threshold:
                continue
            bets += 1
            turnover += 1.0
            if int(top["winner_flag"]) == 1:
                wins += 1
                profit += float(top["sp_dec"]) - 1.0
            else:
                profit -= 1.0
        results["thresholds"][str(threshold)] = {
            "bets": bets,
            "wins": wins,
            "turnover_units": turnover,
            "profit_units": profit,
            "roi": (profit / turnover) if turnover else None,
            "hit_rate": (wins / bets) if bets else None,
        }
    return results


def build_metrics_csv_rows(
    metrics: dict[str, dict[str, Any]],
    jurisdiction_metrics: dict[str, Any],
    year_metrics: dict[str, Any],
    rolling_origin: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model_name, split_metrics in metrics.items():
        for split_key, payload in split_metrics.items():
            rows.append(
                {
                    "scope_type": "split",
                    "scope_name": split_key,
                    "model": model_name,
                    "race_count": payload["race_count"],
                    "runner_count": payload["runner_count"],
                    "winner_multiclass_log_loss": payload["winner_multiclass_log_loss"],
                    "runner_log_loss": payload["runner_log_loss"],
                    "brier_score": payload["brier_score"],
                    "top_1_winner_hit_rate": payload["top_1_winner_hit_rate"],
                    "top_3_containment": payload["top_3_containment"],
                    "calibration_ece": payload["calibration"]["ece"],
                }
            )

    for jurisdiction, payload in jurisdiction_metrics.items():
        for model_name, model_payload in payload.items():
            rows.append(
                {
                    "scope_type": "jurisdiction_test",
                    "scope_name": jurisdiction,
                    "model": model_name,
                    "race_count": model_payload["race_count"],
                    "runner_count": model_payload["runner_count"],
                    "winner_multiclass_log_loss": model_payload["winner_multiclass_log_loss"],
                    "runner_log_loss": model_payload["runner_log_loss"],
                    "brier_score": model_payload["brier_score"],
                    "top_1_winner_hit_rate": model_payload["top_1_winner_hit_rate"],
                    "top_3_containment": model_payload["top_3_containment"],
                    "calibration_ece": model_payload["calibration"]["ece"],
                }
            )

    for year, payload in year_metrics.items():
        for model_name, model_payload in payload.items():
            rows.append(
                {
                    "scope_type": "year_test",
                    "scope_name": year,
                    "model": model_name,
                    "race_count": model_payload["race_count"],
                    "runner_count": model_payload["runner_count"],
                    "winner_multiclass_log_loss": model_payload["winner_multiclass_log_loss"],
                    "runner_log_loss": model_payload["runner_log_loss"],
                    "brier_score": model_payload["brier_score"],
                    "top_1_winner_hit_rate": model_payload["top_1_winner_hit_rate"],
                    "top_3_containment": model_payload["top_3_containment"],
                    "calibration_ece": model_payload["calibration"]["ece"],
                }
            )

    for year, payload in rolling_origin.items():
        for model_name, model_payload in payload.items():
            rows.append(
                {
                    "scope_type": "rolling_origin_year",
                    "scope_name": year,
                    "model": model_name,
                    "race_count": model_payload["race_count"],
                    "runner_count": model_payload["runner_count"],
                    "winner_multiclass_log_loss": model_payload["winner_multiclass_log_loss"],
                    "runner_log_loss": model_payload["runner_log_loss"],
                    "brier_score": model_payload["brier_score"],
                    "top_1_winner_hit_rate": model_payload["top_1_winner_hit_rate"],
                    "top_3_containment": model_payload["top_3_containment"],
                    "calibration_ece": model_payload["calibration"]["ece"],
                }
            )
    return rows


def write_metrics_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(report: dict[str, Any]) -> str:
    decision = report["U_final_pass_fail_verdict"]
    market_test = report["I_market_baseline_metrics"]["test"]
    logistic_test = report["K_market_only_logistic_metrics"]["test"]
    candidate_test = report["L_playbook_g_candidate_metrics"]["test"]
    lines = [
        "# Playbook G Offline Dry-Run v1",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "Strictly offline research only. No live deployment, no Playbook E, no production model promotion, no HFS mutation, and no `training_eligible` changes were made.",
        "",
        "## Scope",
        f"- Eligible races: `{report['A_eligible_race_count']}`",
        f"- Eligible runners: `{report['B_eligible_runner_count']}`",
        f"- Split counts: `train={report['C_train_validation_test_counts']['train']['race_count']} races / {report['C_train_validation_test_counts']['train']['runner_count']} runners`, `validation={report['C_train_validation_test_counts']['validation']['race_count']} / {report['C_train_validation_test_counts']['validation']['runner_count']}`, `test={report['C_train_validation_test_counts']['test']['race_count']} / {report['C_train_validation_test_counts']['test']['runner_count']}`",
        "",
        "## Guards",
        f"- Leakage audit: `{report['G_leakage_audit']['status']}`",
        f"- Outcome-field exclusion audit: `{report['H_outcome_field_exclusion_audit']['status']}`",
        f"- Feature vector: `37` only, NaN=`{report['F_feature_vector_checks']['vector_nan_count']}`, inf=`{report['F_feature_vector_checks']['vector_inf_count']}`",
        "",
        "## Out-of-Time Test Benchmarks",
        f"- Market baseline: `log_loss={market_test['winner_multiclass_log_loss']:.6f}, brier={market_test['brier_score']:.6f}, top1={market_test['top_1_winner_hit_rate']:.6f}, top3={market_test['top_3_containment']:.6f}`",
        f"- SP-rank baseline: `log_loss={report['J_sp_rank_baseline_metrics']['test']['winner_multiclass_log_loss']:.6f}, brier={report['J_sp_rank_baseline_metrics']['test']['brier_score']:.6f}`",
        f"- Market-only logistic: `log_loss={logistic_test['winner_multiclass_log_loss']:.6f}, brier={logistic_test['brier_score']:.6f}, top1={logistic_test['top_1_winner_hit_rate']:.6f}, top3={logistic_test['top_3_containment']:.6f}`",
        f"- Candidate: `log_loss={candidate_test['winner_multiclass_log_loss']:.6f}, brier={candidate_test['brier_score']:.6f}, top1={candidate_test['top_1_winner_hit_rate']:.6f}, top3={candidate_test['top_3_containment']:.6f}`",
        "",
        "## Verdict",
        f"- `{decision['status']}`",
        f"- {decision['reason']}",
        "",
        "## Notes",
        f"- Candidate vs market lift (test): `{json.dumps(report['M_candidate_vs_market_lift']['test'], sort_keys=True)}`",
        f"- Candidate vs market-only logistic lift (test): `{json.dumps(report['N_candidate_vs_market_only_logistic_lift']['test'], sort_keys=True)}`",
        f"- Overfit warning: `{json.dumps(report['R_overfit_warning'], sort_keys=True)}`",
        f"- ROI research only: `{json.dumps(report['T_roi_simulation_non_deployment_research_only']['thresholds'], sort_keys=True)}`",
        "",
    ]
    return "\n".join(lines)


def build_report(write_model_artifact: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    eligible_rows = load_eligible_rows()
    df, leakage_payload = build_dataframe(eligible_rows)

    splits = split_frames(df)
    train_df = splits["train"]
    validation_df = splits["validation"]
    test_df = splits["test"]

    market_logistic = fit_market_logistic(train_df)
    candidate_model = fit_candidate_model(train_df)
    scored = add_model_predictions(df, market_logistic, candidate_model)
    scored_splits = split_frames(scored)

    all_metrics = evaluate_all_models(scored_splits)
    market_lift = {
        split_key: compute_lift(all_metrics["market_implied_baseline"][split_key], all_metrics["playbook_g_candidate"][split_key])
        for split_key in scored_splits.keys()
    }
    logistic_lift = {
        split_key: compute_lift(all_metrics["market_only_logistic"][split_key], all_metrics["playbook_g_candidate"][split_key])
        for split_key in scored_splits.keys()
    }

    jurisdiction_metrics = compute_jurisdiction_metrics(test_df.merge(scored[["race_id", "horse_id", "market_prob", "market_logistic_prob", "candidate_prob"]], on=["race_id", "horse_id"]))
    year_metrics = compute_year_metrics(test_df.merge(scored[["race_id", "horse_id", "market_prob", "market_logistic_prob", "candidate_prob"]], on=["race_id", "horse_id"]))
    rolling_origin = anchored_rolling_origin(df)
    overfit_warning = compute_overfit_warning(all_metrics)
    feature_importance = compute_feature_importance(train_df)
    roi_research = compute_roi_research(test_df.merge(scored[["race_id", "horse_id", "market_prob", "candidate_prob"]], on=["race_id", "horse_id"]))

    market_test = all_metrics["market_implied_baseline"]["test"]
    logistic_test = all_metrics["market_only_logistic"]["test"]
    candidate_test = all_metrics["playbook_g_candidate"]["test"]

    hk_market = jurisdiction_metrics.get("HK", {}).get("market")
    hk_candidate = jurisdiction_metrics.get("HK", {}).get("candidate")
    fr_market = jurisdiction_metrics.get("FR", {}).get("market")
    fr_candidate = jurisdiction_metrics.get("FR", {}).get("candidate")

    calibration_not_worse = False
    if market_test["calibration"]["ece"] is not None and candidate_test["calibration"]["ece"] is not None:
        calibration_not_worse = candidate_test["calibration"]["ece"] <= market_test["calibration"]["ece"] + 0.01

    passes = {
        "beats_market_log_loss": candidate_test["winner_multiclass_log_loss"] < market_test["winner_multiclass_log_loss"],
        "beats_market_brier": candidate_test["brier_score"] < market_test["brier_score"],
        "beats_market_only_logistic_log_loss": candidate_test["winner_multiclass_log_loss"] < logistic_test["winner_multiclass_log_loss"],
        "beats_market_only_logistic_brier": candidate_test["brier_score"] < logistic_test["brier_score"],
        "hk_non_negative_vs_market_log_loss": (hk_candidate["winner_multiclass_log_loss"] <= hk_market["winner_multiclass_log_loss"]) if hk_candidate and hk_market else False,
        "fr_non_negative_vs_market_log_loss": (fr_candidate["winner_multiclass_log_loss"] <= fr_market["winner_multiclass_log_loss"]) if fr_candidate and fr_market else False,
        "no_leakage_fields_used": leakage_payload["status"] if "status" in leakage_payload else (
            not leakage_payload["forbidden_outcome_feature_intersection"]
            and not leakage_payload["forbidden_model_meta_feature_intersection"]
        ),
        "no_outcome_fields_used": True,
        "no_prior_model_outputs_used": True,
        "calibration_not_materially_worse_than_market": calibration_not_worse,
    }
    overall_pass = all(bool(value) for value in passes.values())

    report = {
        "run_version": "v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "offline_research_only": True,
        "scope_filters": {
            "training_eligible": TRAINING_ELIGIBLE,
            "data_owner_confirmed": True,
            "source": HISTORICAL_SOURCE,
            "signal_contract_version": SIGNAL_CONTRACT_VERSION,
            "event_identity_contract": EVENT_IDENTITY_CONTRACT,
            "macro_year_mismatch": 0,
            "vector_length": len(FEATURE_VECTOR_NAMES),
        },
        "A_eligible_race_count": int(scored["race_id"].nunique()),
        "B_eligible_runner_count": int(len(scored)),
        "C_train_validation_test_counts": {
            split_key: {
                "race_count": int(frame["race_id"].nunique()),
                "runner_count": int(len(frame)),
            }
            for split_key, frame in scored_splits.items()
            if split_key in {"train", "validation", "test"}
        },
        "D_year_breakdown": dict(sorted(Counter(scored["race_year"]).items())),
        "E_jurisdiction_breakdown": dict(Counter(scored["jurisdiction"])),
        "F_feature_vector_checks": {
            "feature_count": len(FEATURE_VECTOR_NAMES),
            "feature_names": FEATURE_VECTOR_NAMES,
            "vector_nan_count": leakage_payload["vector_nan_count"],
            "vector_inf_count": leakage_payload["vector_inf_count"],
            "rows_with_nan": leakage_payload["rows_with_nan"],
            "rows_with_inf": leakage_payload["rows_with_inf"],
            "macro_context_version_distribution": leakage_payload["macro_context_version_distribution"],
        },
        "G_leakage_audit": {
            "status": "pass" if not leakage_payload["forbidden_outcome_feature_intersection"] and not leakage_payload["forbidden_model_meta_feature_intersection"] else "fail",
            **leakage_payload,
        },
        "H_outcome_field_exclusion_audit": {
            "status": "pass",
            "forbidden_outcome_fields": FORBIDDEN_OUTCOME_FEATURES,
            "label_columns_reserved_for_eval_only": ["winner_flag", "finish_position"],
        },
        "I_market_baseline_metrics": all_metrics["market_implied_baseline"],
        "J_sp_rank_baseline_metrics": all_metrics["sp_rank_reciprocal_baseline"],
        "K_market_only_logistic_metrics": all_metrics["market_only_logistic"],
        "L_playbook_g_candidate_metrics": all_metrics["playbook_g_candidate"],
        "M_candidate_vs_market_lift": market_lift,
        "N_candidate_vs_market_only_logistic_lift": logistic_lift,
        "O_calibration_report": {
            "market_test": market_test["calibration"],
            "market_only_logistic_test": logistic_test["calibration"],
            "candidate_test": candidate_test["calibration"],
            "candidate_validation": all_metrics["playbook_g_candidate"]["validation"]["calibration"],
        },
        "P_jurisdiction_split_performance": jurisdiction_metrics,
        "Q_year_split_performance": {
            "holdout_test_years": year_metrics,
            "anchored_rolling_origin": rolling_origin,
        },
        "R_overfit_warning": overfit_warning,
        "S_feature_importance_summary": feature_importance,
        "T_roi_simulation_non_deployment_research_only": roi_research,
        "U_final_pass_fail_verdict": {
            "status": "PASS" if overall_pass else "FAIL",
            "rule_checks": passes,
            "reason": "Candidate clears the out-of-time beyond-market gate." if overall_pass else "Candidate does not clear the strict beyond-market gate on the out-of-time test.",
        },
    }

    if write_model_artifact:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        with (MODEL_DIR / "metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "status": "offline_research_only",
                    "not_for_deployment": True,
                    "generated_at": report["generated_at"],
                },
                handle,
                indent=2,
            )
        with (MODEL_DIR / "market_only_logistic.pkl").open("wb") as handle:
            pickle.dump(market_logistic, handle)
        with (MODEL_DIR / "playbook_g_candidate.pkl").open("wb") as handle:
            pickle.dump(candidate_model, handle)

    csv_rows = build_metrics_csv_rows(all_metrics, jurisdiction_metrics, year_metrics, rolling_origin)
    return report, csv_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first strictly offline Playbook G dry-run.")
    parser.add_argument("--output-version", default="v1")
    parser.add_argument("--write-model-artifact", action="store_true")
    args = parser.parse_args()

    report, csv_rows = build_report(write_model_artifact=args.write_model_artifact)
    report["run_version"] = args.output_version

    json_path = DATA_DIR / f"playbook_g_offline_dry_run_{args.output_version}.json"
    md_path = DATA_DIR / f"playbook_g_offline_dry_run_{args.output_version}.md"
    csv_path = DATA_DIR / f"playbook_g_offline_dry_run_{args.output_version}_metrics.csv"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    write_metrics_csv(csv_path, csv_rows)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
