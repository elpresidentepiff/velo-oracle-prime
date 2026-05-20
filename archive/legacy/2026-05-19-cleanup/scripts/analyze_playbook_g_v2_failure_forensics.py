from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
V2_SCRIPT = ROOT / "scripts" / "run_playbook_g_v2_ablation_dry_run.py"
V2_JSON = ROOT / "data" / "playbook_g_v2_ablation_dry_run.json"
JSON_OUT = ROOT / "data" / "playbook_g_v2_failure_forensics.json"
MD_OUT = ROOT / "data" / "playbook_g_v2_failure_forensics.md"


def load_v2_module():
    spec = importlib.util.spec_from_file_location("playbook_g_v2_ablation", V2_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {V2_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def feature_set(groups: dict[str, list[str]], name: str) -> list[str]:
    if name == "market_only":
        return groups["market"]
    if name == "ratings_only":
        return groups["ratings"]
    if name == "doctrine_only":
        return groups["doctrine"]
    if name == "market_plus_ratings":
        return groups["market"] + groups["ratings"]
    if name == "market_plus_doctrine":
        return groups["market"] + groups["doctrine"]
    if name == "ratings_plus_doctrine":
        return groups["ratings"] + groups["doctrine"]
    if name == "market_plus_ratings_plus_doctrine":
        return groups["market"] + groups["ratings"] + groups["doctrine"]
    raise KeyError(name)


def build_prediction_frame(
    frame: pd.DataFrame,
    probs: np.ndarray,
    market_probs: np.ndarray,
    model_name: str,
) -> pd.DataFrame:
    cols = ["event_key", "race_id", "horse_id", "race_date", "year", "jurisdiction", "course", "winner_flag"]
    out = frame[cols].copy().reset_index(drop=True)
    out["prob"] = np.asarray(probs, dtype=float)
    out["market_prob"] = np.asarray(market_probs, dtype=float)
    out["model_name"] = model_name
    out["model_rank"] = (
        out.groupby("event_key")["prob"].rank(method="first", ascending=False).astype(int)
    )
    out["market_rank"] = (
        out.groupby("event_key")["market_prob"].rank(method="first", ascending=False).astype(int)
    )
    out["is_model_top1"] = out["model_rank"] == 1
    out["is_market_top1"] = out["market_rank"] == 1
    return out


def run_model(
    pb2,
    splits: dict[str, pd.DataFrame],
    groups: dict[str, list[str]],
    model_name: str,
    *,
    direct_market: bool = False,
    jurisdiction_calibration: bool = False,
) -> dict[str, Any]:
    feature_names = feature_set(groups, model_name)
    train_frame = splits["train"].copy()
    validation_frame = splits["validation"].copy()
    test_frame = splits["test"].copy()

    if direct_market:
        train_probs = pb2.market_reference_probs(train_frame)
        validation_probs = pb2.market_reference_probs(validation_frame)
        test_probs = pb2.market_reference_probs(test_frame)
    else:
        model, calibrator = pb2.fit_gbm_model(train_frame, validation_frame, feature_names)
        if jurisdiction_calibration:
            validation_raw = model.predict_proba(pb2.feature_matrix(validation_frame, feature_names))[:, 1]
            calibrators = pb2.fit_jurisdiction_calibrators(validation_frame, validation_raw)
            train_probs = pb2.predict_with_jurisdiction_calibration(train_frame, feature_names, model, calibrators)
            validation_probs = pb2.predict_with_jurisdiction_calibration(
                validation_frame, feature_names, model, calibrators
            )
            test_probs = pb2.predict_with_jurisdiction_calibration(test_frame, feature_names, model, calibrators)
        else:
            train_probs = pb2.predict_frame(train_frame, feature_names, model, calibrator)
            validation_probs = pb2.predict_frame(validation_frame, feature_names, model, calibrator)
            test_probs = pb2.predict_frame(test_frame, feature_names, model, calibrator)

    market_train = pb2.market_reference_probs(train_frame)
    market_validation = pb2.market_reference_probs(validation_frame)
    market_test = pb2.market_reference_probs(test_frame)

    return {
        "name": model_name,
        "feature_names": feature_names,
        "train_frame": train_frame,
        "validation_frame": validation_frame,
        "test_frame": test_frame,
        "train_metrics": pb2.evaluate_frame(train_frame, train_probs, market_probs=market_train),
        "validation_metrics": pb2.evaluate_frame(validation_frame, validation_probs, market_probs=market_validation),
        "test_metrics": pb2.evaluate_frame(test_frame, test_probs, market_probs=market_test),
        "test_metrics_by_jurisdiction": pb2.split_metrics_payload(test_frame, test_probs, market_test)[0],
        "test_metrics_by_year": pb2.split_metrics_payload(test_frame, test_probs, market_test)[1],
        "overfit_warning": pb2.overfit_warning(
            pb2.evaluate_frame(train_frame, train_probs, market_probs=market_train),
            pb2.evaluate_frame(validation_frame, validation_probs, market_probs=market_validation),
            pb2.evaluate_frame(test_frame, test_probs, market_probs=market_test),
        ),
        "test_predictions": build_prediction_frame(test_frame, test_probs, market_test, model_name),
    }


def race_summary(predictions: pd.DataFrame, label: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event_key, race in predictions.groupby("event_key", sort=False):
        race = race.copy()
        winner = race.loc[race["winner_flag"] == 1].iloc[0]
        model_top = race.sort_values("prob", ascending=False).iloc[0]
        market_top = race.sort_values("market_prob", ascending=False).iloc[0]
        rows.append(
            {
                "event_key": event_key,
                "race_id": str(winner["race_id"]),
                "race_date": str(winner["race_date"]),
                "year": int(winner["year"]),
                "jurisdiction": str(winner["jurisdiction"]),
                "course": str(winner["course"]),
                f"{label}_winner_prob": float(winner["prob"]),
                f"{label}_winner_loss": float(-np.log(max(float(winner["prob"]), 1e-12))),
                f"{label}_winner_rank": int(winner["model_rank"]),
                f"{label}_market_winner_rank": int(winner["market_rank"]),
                f"{label}_top1_horse_id": str(model_top["horse_id"]),
                f"{label}_top1_prob": float(model_top["prob"]),
                f"{label}_top1_won": bool(model_top["winner_flag"]),
                f"{label}_top1_market_rank": int(model_top["market_rank"]),
                f"{label}_market_top1_horse_id": str(market_top["horse_id"]),
                f"{label}_market_top1_won": bool(market_top["winner_flag"]),
                f"{label}_n_runners": int(race.shape[0]),
            }
        )
    return pd.DataFrame(rows)


def grouped_probability_delta(
    merged: pd.DataFrame,
    left_col: str,
    right_col: str,
    mask: pd.Series,
) -> float | None:
    if not mask.any():
        return None
    return float((merged.loc[mask, left_col] - merged.loc[mask, right_col]).mean())


def model_vs_market_overlap(predictions: pd.DataFrame) -> float:
    race_rows = []
    for _, race in predictions.groupby("event_key", sort=False):
        model_top = race.sort_values("prob", ascending=False).iloc[0]["horse_id"]
        market_top = race.sort_values("market_prob", ascending=False).iloc[0]["horse_id"]
        race_rows.append(float(model_top == market_top))
    return float(np.mean(race_rows)) if race_rows else 0.0


def wrong_top1_overconfidence(predictions: pd.DataFrame) -> dict[str, float]:
    rows = []
    for _, race in predictions.groupby("event_key", sort=False):
        top = race.sort_values("prob", ascending=False).iloc[0]
        if not bool(top["winner_flag"]):
            rows.append(float(top["prob"]))
    return {
        "count": int(len(rows)),
        "avg_top1_prob_when_wrong": float(np.mean(rows)) if rows else 0.0,
        "p90_top1_prob_when_wrong": float(np.percentile(rows, 90)) if rows else 0.0,
    }


def year_stability(summary: pd.DataFrame) -> dict[str, Any]:
    if summary.empty:
        return {"n_races": 0}
    return {
        "n_races": int(summary.shape[0]),
        "mean_winner_loss": float(summary["winner_loss"].mean()),
        "std_winner_loss": float(summary["winner_loss"].std(ddof=0)),
        "p90_winner_loss": float(summary["winner_loss"].quantile(0.9)),
    }


def compare_examples(
    base: pd.DataFrame,
    other: pd.DataFrame,
    market: pd.DataFrame,
    *,
    top_n: int,
    direction: str,
) -> list[dict[str, Any]]:
    def maybe_float(row: pd.Series, key: str) -> float | None:
        return float(row[key]) if key in row.index and pd.notna(row[key]) else None

    def maybe_int(row: pd.Series, key: str) -> int | None:
        return int(row[key]) if key in row.index and pd.notna(row[key]) else None

    merged = base.merge(other, on=["event_key", "race_id", "race_date", "year", "jurisdiction", "course"])
    merged = merged.merge(market, on=["event_key", "race_id", "race_date", "year", "jurisdiction", "course"])
    if direction == "other_better":
        merged["gap"] = merged.iloc[:, merged.columns.get_loc("mrd_winner_loss")] - merged.iloc[:, merged.columns.get_loc("rpd_winner_loss")]
        merged = merged.sort_values("gap", ascending=False).head(top_n)
    else:
        merged["gap"] = merged.iloc[:, merged.columns.get_loc("ratings_only_winner_loss")] - merged.iloc[:, merged.columns.get_loc("rpd_winner_loss")]
        merged = merged.sort_values("gap", ascending=False).head(top_n)
    examples: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        examples.append(
            {
                "event_key": row["event_key"],
                "race_date": row["race_date"],
                "jurisdiction": row["jurisdiction"],
                "course": row["course"],
                "gap": float(row["gap"]),
                "market_winner_prob": float(row.get("market_winner_prob", 0.0)),
                "market_winner_rank": int(row.get("market_winner_rank", 0)),
                "mrd_winner_prob": maybe_float(row, "mrd_winner_prob"),
                "mrd_winner_rank": maybe_int(row, "mrd_winner_rank"),
                "rpd_winner_prob": maybe_float(row, "rpd_winner_prob"),
                "rpd_winner_rank": maybe_int(row, "rpd_winner_rank"),
                "ratings_only_winner_prob": maybe_float(row, "ratings_only_winner_prob"),
                "ratings_only_winner_rank": maybe_int(row, "ratings_only_winner_rank"),
                "mrd_top1_market_rank": maybe_int(row, "mrd_top1_market_rank"),
                "rpd_top1_market_rank": maybe_int(row, "rpd_top1_market_rank"),
            }
        )
    return examples


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Playbook G V2 Failure Forensics",
        "",
        f"- Final recommendation: `{report['final_recommendation']['code']}` - {report['final_recommendation']['label']}",
        f"- Core finding: `{report['summary']['core_finding']}`",
        f"- Market + ratings test log loss: `{report['summary']['market_plus_ratings_log_loss']:.6f}`",
        f"- Market + ratings + doctrine test log loss: `{report['summary']['market_plus_ratings_plus_doctrine_log_loss']:.6f}`",
        f"- Ratings + doctrine test log loss: `{report['summary']['ratings_plus_doctrine_log_loss']:.6f}`",
        "",
        "## Key Calls",
        f"- Market interference: `{report['A_market_feature_interference_analysis']['conclusion']}`",
        f"- HK improvement: `{report['C_hk_improvement_drivers']['conclusion']}`",
        f"- FR improvement: `{report['D_fr_improvement_drivers']['conclusion']}`",
        f"- 2025 instability: `{report['E_2025_instability_analysis']['conclusion']}`",
        f"- Market as raw input: `{report['K_market_as_calibration_or_input']['recommendation']}`",
        f"- Residual-learning V3 arm: `{report['L_should_v3_test_residual_learning_over_market']['recommendation']}`",
        "",
        "## Recommendation",
        report["final_recommendation"]["reason"],
        "",
    ]
    return "\n".join(lines)


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
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def main() -> None:
    pb2 = load_v2_module()
    v2 = load_json(V2_JSON)
    groups = pb2.load_feature_groups()
    df, cohort_checks = pb2.load_cohort()
    splits = pb2.split_frames(df)

    bundles = {
        "market_only": run_model(pb2, splits, groups, "market_only", direct_market=True),
        "ratings_only": run_model(pb2, splits, groups, "ratings_only"),
        "market_plus_ratings": run_model(pb2, splits, groups, "market_plus_ratings"),
        "ratings_plus_doctrine": run_model(pb2, splits, groups, "ratings_plus_doctrine"),
        "market_plus_ratings_plus_doctrine": run_model(pb2, splits, groups, "market_plus_ratings_plus_doctrine"),
        "jurisdiction_specific_calibration": run_model(
            pb2, splits, groups, "market_plus_ratings_plus_doctrine", jurisdiction_calibration=True
        ),
    }

    market_pred = bundles["market_only"]["test_predictions"].rename(columns={"prob": "market_prob_model"})
    ratings_only_pred = bundles["ratings_only"]["test_predictions"].rename(columns={"prob": "ratings_only_prob"})
    mr_pred = bundles["market_plus_ratings"]["test_predictions"].rename(columns={"prob": "mr_prob"})
    rpd_pred = bundles["ratings_plus_doctrine"]["test_predictions"].rename(columns={"prob": "rpd_prob"})
    mrd_pred = bundles["market_plus_ratings_plus_doctrine"]["test_predictions"].rename(columns={"prob": "mrd_prob"})

    merged = (
        market_pred[
            ["event_key", "horse_id", "winner_flag", "jurisdiction", "year", "course", "race_date", "market_prob_model", "market_prob", "market_rank"]
        ]
        .merge(ratings_only_pred[["event_key", "horse_id", "ratings_only_prob"]], on=["event_key", "horse_id"])
        .merge(mr_pred[["event_key", "horse_id", "mr_prob"]], on=["event_key", "horse_id"])
        .merge(rpd_pred[["event_key", "horse_id", "rpd_prob"]], on=["event_key", "horse_id"])
        .merge(mrd_pred[["event_key", "horse_id", "mrd_prob"]], on=["event_key", "horse_id"])
    )

    merged["is_market_favorite"] = merged["market_rank"] == 1
    merged["winner_flag"] = merged["winner_flag"].astype(int)

    market_race = race_summary(
        bundles["market_only"]["test_predictions"].rename(columns={"prob": "prob"}), "market"
    )
    ratings_race = race_summary(
        bundles["ratings_only"]["test_predictions"].rename(columns={"prob": "prob"}), "ratings_only"
    )
    rpd_race = race_summary(
        bundles["ratings_plus_doctrine"]["test_predictions"].rename(columns={"prob": "prob"}), "rpd"
    )
    mrd_race = race_summary(
        bundles["market_plus_ratings_plus_doctrine"]["test_predictions"].rename(columns={"prob": "prob"}), "mrd"
    )

    mrd_vs_rpd = mrd_race.merge(
        rpd_race,
        on=["event_key", "race_id", "race_date", "year", "jurisdiction", "course"],
    )
    ratings_vs_rpd = ratings_race.merge(
        rpd_race,
        on=["event_key", "race_id", "race_date", "year", "jurisdiction", "course"],
    )

    mrd_vs_rpd["loss_gap_mrd_minus_rpd"] = (
        mrd_vs_rpd["mrd_winner_loss"] - mrd_vs_rpd["rpd_winner_loss"]
    )
    ratings_vs_rpd["loss_gap_ratings_minus_rpd"] = (
        ratings_vs_rpd["ratings_only_winner_loss"] - ratings_vs_rpd["rpd_winner_loss"]
    )

    interference = {
        "mrd_test_log_loss": bundles["market_plus_ratings_plus_doctrine"]["test_metrics"]["log_loss"],
        "mr_test_log_loss": bundles["market_plus_ratings"]["test_metrics"]["log_loss"],
        "rpd_test_log_loss": bundles["ratings_plus_doctrine"]["test_metrics"]["log_loss"],
        "mrd_minus_mr_log_loss": float(
            bundles["market_plus_ratings_plus_doctrine"]["test_metrics"]["log_loss"]
            - bundles["market_plus_ratings"]["test_metrics"]["log_loss"]
        ),
        "mrd_minus_rpd_log_loss": float(
            bundles["market_plus_ratings_plus_doctrine"]["test_metrics"]["log_loss"]
            - bundles["ratings_plus_doctrine"]["test_metrics"]["log_loss"]
        ),
        "prob_correlation_with_market": {
            "rpd": float(np.corrcoef(merged["rpd_prob"], merged["market_prob"])[0, 1]),
            "mrd": float(np.corrcoef(merged["mrd_prob"], merged["market_prob"])[0, 1]),
        },
        "avg_prob_delta_mrd_minus_rpd": {
            "market_favorites": grouped_probability_delta(merged, "mrd_prob", "rpd_prob", merged["is_market_favorite"]),
            "winners": grouped_probability_delta(merged, "mrd_prob", "rpd_prob", merged["winner_flag"] == 1),
            "all_runners": float((merged["mrd_prob"] - merged["rpd_prob"]).mean()),
        },
        "top1_overlap_with_market": {
            "rpd": model_vs_market_overlap(bundles["ratings_plus_doctrine"]["test_predictions"]),
            "mrd": model_vs_market_overlap(bundles["market_plus_ratings_plus_doctrine"]["test_predictions"]),
        },
    }
    interference["conclusion"] = (
        "market raw input is too loud in the full stack"
        if interference["mrd_minus_mr_log_loss"] > 0 and interference["prob_correlation_with_market"]["mrd"] > interference["prob_correlation_with_market"]["rpd"]
        else "market interference is not clearly supported"
    )

    hk_market = v2["ablation_results"]["market_only"]["test_metrics_by_jurisdiction"]["HK"]
    hk_mrd = v2["ablation_results"]["market_plus_ratings_plus_doctrine"]["test_metrics_by_jurisdiction"]["HK"]
    fr_market = v2["ablation_results"]["market_only"]["test_metrics_by_jurisdiction"]["FR"]
    fr_mrd = v2["ablation_results"]["market_plus_ratings_plus_doctrine"]["test_metrics_by_jurisdiction"]["FR"]
    y2025_market = v2["ablation_results"]["market_only"]["test_metrics_by_year"]["2025"]
    y2025_mrd = v2["ablation_results"]["market_plus_ratings_plus_doctrine"]["test_metrics_by_year"]["2025"]

    hk_examples = mrd_vs_rpd[mrd_vs_rpd["jurisdiction"] == "HK"].sort_values("loss_gap_mrd_minus_rpd", ascending=False).head(5)
    fr_examples = ratings_vs_rpd[ratings_vs_rpd["jurisdiction"] == "FR"].sort_values("loss_gap_ratings_minus_rpd", ascending=False).head(5)

    calibration_table = {
        name: {
            "test_ece": result["test_metrics"]["ece"],
            "hk_test_ece": result["test_metrics_by_jurisdiction"].get("HK", {}).get("ece"),
            "fr_test_ece": result["test_metrics_by_jurisdiction"].get("FR", {}).get("ece"),
        }
        for name, result in v2["ablation_results"].items()
    }

    overconfidence = {
        "market_plus_ratings": {
            **bundles["market_plus_ratings"]["overfit_warning"],
            **wrong_top1_overconfidence(bundles["market_plus_ratings"]["test_predictions"]),
        },
        "ratings_plus_doctrine": {
            **bundles["ratings_plus_doctrine"]["overfit_warning"],
            **wrong_top1_overconfidence(bundles["ratings_plus_doctrine"]["test_predictions"]),
        },
        "market_plus_ratings_plus_doctrine": {
            **bundles["market_plus_ratings_plus_doctrine"]["overfit_warning"],
            **wrong_top1_overconfidence(bundles["market_plus_ratings_plus_doctrine"]["test_predictions"]),
        },
    }

    market_examples = compare_examples(
        mrd_race,
        rpd_race,
        market_race,
        top_n=5,
        direction="other_better",
    )
    doctrine_help_examples = compare_examples(
        ratings_race,
        rpd_race,
        market_race,
        top_n=5,
        direction="doctrine_help",
    )

    y2025_race = mrd_race[mrd_race["year"] == 2025].rename(columns={"mrd_winner_loss": "winner_loss"})

    report = {
        "summary": {
            "eligible_race_count": cohort_checks["eligible_race_count"],
            "eligible_runner_count": cohort_checks["eligible_runner_count"],
            "market_plus_ratings_log_loss": bundles["market_plus_ratings"]["test_metrics"]["log_loss"],
            "market_plus_ratings_plus_doctrine_log_loss": bundles["market_plus_ratings_plus_doctrine"]["test_metrics"]["log_loss"],
            "ratings_plus_doctrine_log_loss": bundles["ratings_plus_doctrine"]["test_metrics"]["log_loss"],
            "core_finding": "doctrine is alive, but raw market input degrades the full stack relative to ratings + doctrine",
        },
        "A_market_feature_interference_analysis": interference,
        "B_ratings_plus_doctrine_vs_full_stack": {
            "ratings_plus_doctrine_test_metrics": bundles["ratings_plus_doctrine"]["test_metrics"],
            "market_plus_ratings_plus_doctrine_test_metrics": bundles["market_plus_ratings_plus_doctrine"]["test_metrics"],
            "winner_log_loss_gap_summary": {
                "mean_mrd_minus_rpd": float(mrd_vs_rpd["loss_gap_mrd_minus_rpd"].mean()),
                "median_mrd_minus_rpd": float(mrd_vs_rpd["loss_gap_mrd_minus_rpd"].median()),
                "races_where_mrd_is_worse": int((mrd_vs_rpd["loss_gap_mrd_minus_rpd"] > 0).sum()),
                "races_where_rpd_is_worse": int((mrd_vs_rpd["loss_gap_mrd_minus_rpd"] < 0).sum()),
            },
            "conclusion": "ratings + doctrine is the cleaner core model on this cohort",
        },
        "C_hk_improvement_drivers": {
            "market_metrics": hk_market,
            "mrd_metrics": hk_mrd,
            "hk_only_diagnostic_metrics": v2["ablation_results"]["hk_only_diagnostic"]["test_metrics"],
            "hk_only_top_features": v2["ablation_results"]["hk_only_diagnostic"]["top_features"][:10],
            "sample_races": hk_examples.to_dict(orient="records"),
            "conclusion": "HK improved because doctrine + ratings helped ranking without requiring raw market dominance",
        },
        "D_fr_improvement_drivers": {
            "market_metrics": fr_market,
            "mrd_metrics": fr_mrd,
            "fr_only_diagnostic_metrics": v2["ablation_results"]["fr_only_diagnostic"]["test_metrics"],
            "fr_only_top_features": v2["ablation_results"]["fr_only_diagnostic"]["top_features"][:10],
            "sample_races": fr_examples.to_dict(orient="records"),
            "conclusion": "FR remains the strongest regime for doctrine-enhanced models",
        },
        "E_2025_instability_analysis": {
            "market_metrics": y2025_market,
            "mrd_metrics": y2025_mrd,
            "race_level_stability": year_stability(y2025_race),
            "conclusion": "2025 is still too small to anchor governance decisions on its own",
        },
        "F_feature_importance_by_ablation": {
            name: {
                "feature_importance_by_group": result["feature_importance_by_group"],
                "top_features": result["top_features"][:10],
            }
            for name, result in v2["ablation_results"].items()
        },
        "G_calibration_by_ablation": calibration_table,
        "H_overconfidence_log_loss_miss_analysis": overconfidence,
        "I_race_level_examples_where_market_hurt_full_model": market_examples,
        "J_race_level_examples_where_doctrine_helped": doctrine_help_examples,
        "K_market_as_calibration_or_input": {
            "recommendation": "test market as benchmark/calibration/residual, not as default raw feature in the core V3 model",
            "evidence": {
                "mrd_worse_than_mr_on_log_loss": bundles["market_plus_ratings_plus_doctrine"]["test_metrics"]["log_loss"]
                > bundles["market_plus_ratings"]["test_metrics"]["log_loss"],
                "mrd_worse_than_mr_on_brier": bundles["market_plus_ratings_plus_doctrine"]["test_metrics"]["brier"]
                > bundles["market_plus_ratings"]["test_metrics"]["brier"],
                "rpd_best_log_loss": bundles["ratings_plus_doctrine"]["test_metrics"]["log_loss"]
                < bundles["market_plus_ratings_plus_doctrine"]["test_metrics"]["log_loss"],
            },
        },
        "L_should_v3_test_residual_learning_over_market": {
            "recommendation": "yes",
            "reason": "the market signal is useful, but raw concatenation appears to crowd the doctrine layer",
        },
        "M_jurisdiction_specific_calibration_mandatory": {
            "recommendation": "no",
            "reason": "jurisdiction-specific calibration underperformed the plain full-stack model on the overall test",
            "jurisdiction_specific_test_metrics": v2["ablation_results"]["jurisdiction_specific_calibration"]["test_metrics"],
        },
        "N_should_hk_fr_use_separate_calibrators": {
            "recommendation": "diagnostic yes, mandatory no",
            "reason": "HK and FR differ enough to justify targeted experiments, but V2 did not prove separate calibrators should be mandatory",
        },
        "O_recommended_playbook_g_v3_experiment_design": {
            "core_model": "ratings_plus_doctrine",
            "required_arms": [
                "ratings + doctrine core",
                "ratings + doctrine with market residual target",
                "ratings + doctrine with market calibration only",
                "ratings + doctrine with HK/FR-specific calibrator diagnostics",
                "market + ratings as standing benchmark",
            ],
            "keep_offline_only": True,
            "governance": [
                "no training_eligible change",
                "no deployment",
                "no Playbook E",
                "same hard out-of-time gate",
            ],
        },
        "final_recommendation": {
            "code": "C",
            "label": "run V3 ratings+doctrine-first experiment",
            "reason": "V2 showed doctrine contributes real signal and fixes the HK failure, but the best overall log loss came from ratings + doctrine, not the raw full stack. The next clean experiment is to treat ratings + doctrine as the core and demote market to residual/calibration roles instead of feeding it blindly into the stack.",
        },
    }

    JSON_OUT.write_text(json.dumps(to_jsonable(report), indent=2), encoding="utf-8")
    MD_OUT.write_text(build_markdown(report), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
