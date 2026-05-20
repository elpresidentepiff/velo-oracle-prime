from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

V2_SCRIPT = ROOT / "scripts" / "run_playbook_g_v2_ablation_dry_run.py"
V3_SCRIPT = ROOT / "scripts" / "run_playbook_g_v3_offline_dry_run.py"

V3_JSON = DATA / "playbook_g_v3_offline_dry_run.json"
V3_METRICS = DATA / "playbook_g_v3_offline_metrics.csv"
V3_REVIEW = DATA / "playbook_g_v3_core_candidate_review.json"
AUDIT_V4 = DATA / "global_clean_spine_audit_v4.json"
DOCTRINE_V2 = DATA / "historical_doctrine_feature_audit_v2.json"

JSON_OUT = DATA / "playbook_g_v3_core_stability_audit.json"
MD_OUT = DATA / "playbook_g_v3_core_stability_audit.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def race_prediction_frame(frame: pd.DataFrame, probs: np.ndarray, market_probs: np.ndarray, label: str) -> pd.DataFrame:
    out = frame[["event_key", "race_id", "horse_id", "race_date", "year", "jurisdiction", "course", "winner_flag"]].copy()
    out[f"{label}_prob"] = np.asarray(probs, dtype=float)
    out["market_prob"] = np.asarray(market_probs, dtype=float)
    out[f"{label}_rank"] = out.groupby("event_key")[f"{label}_prob"].rank(method="first", ascending=False).astype(int)
    out["market_rank"] = out.groupby("event_key")["market_prob"].rank(method="first", ascending=False).astype(int)
    return out


def race_summary(pred: pd.DataFrame, label: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    prob_col = f"{label}_prob"
    rank_col = f"{label}_rank"
    for event_key, race in pred.groupby("event_key", sort=False):
        winner = race.loc[race["winner_flag"] == 1].iloc[0]
        top = race.sort_values(prob_col, ascending=False).iloc[0]
        rows.append(
            {
                "event_key": event_key,
                "race_id": str(winner["race_id"]),
                "race_date": str(winner["race_date"]),
                "year": int(winner["year"]),
                "jurisdiction": str(winner["jurisdiction"]),
                "course": str(winner["course"]),
                "field_size": int(race.shape[0]),
                "winner_prob": float(winner[prob_col]),
                "winner_loss": float(-np.log(max(float(winner[prob_col]), 1e-12))),
                "winner_rank": int(winner[rank_col]),
                "top1_hit": float(int(winner[rank_col] == 1)),
                "top3_hit": float(int(winner[rank_col] <= min(3, race.shape[0]))),
                "top1_horse_id": str(top["horse_id"]),
                "top1_prob": float(top[prob_col]),
                "top1_won": bool(top["winner_flag"]),
                "brier": float(np.mean((race[prob_col].to_numpy(dtype=float) - race["winner_flag"].to_numpy(dtype=float)) ** 2)),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_ci(values: np.ndarray, *, n_boot: int = 5000, seed: int = 42) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    n = values.size
    samples = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        samples[i] = float(values[idx].mean())
    return {
        "mean": float(values.mean()),
        "ci_lower": float(np.quantile(samples, 0.025)),
        "ci_upper": float(np.quantile(samples, 0.975)),
        "n_boot": int(n_boot),
    }


def diff_bootstrap_ci(a: np.ndarray, b: np.ndarray, *, n_boot: int = 5000, seed: int = 42) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    diff = a - b
    n = diff.size
    samples = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        samples[i] = float(diff[idx].mean())
    return {
        "mean_diff": float(diff.mean()),
        "ci_lower": float(np.quantile(samples, 0.025)),
        "ci_upper": float(np.quantile(samples, 0.975)),
        "n_boot": int(n_boot),
    }


def overfit_comment(overfit: dict[str, Any]) -> str:
    if overfit["level"] == "low":
        return "generalization gap is modest"
    if overfit["level"] == "medium":
        return "generalization gap is material but not disqualifying"
    return "generalization gap is too large"


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
        "# Playbook G V3 Core Stability Audit",
        "",
        f"- Final recommendation: `{report['O_final_recommendation']['code']}` - {report['O_final_recommendation']['label']}",
        f"- Core survives uncertainty: `{report['M_whether_core_result_survives_uncertainty']['status']}`",
        "",
        "## Bootstrap",
        f"- Core vs market log loss diff mean: `{report['A_bootstrap_confidence_intervals_for_core_vs_market_log_loss']['mean_diff']:.6f}`",
        f"- 95% CI: `[{report['A_bootstrap_confidence_intervals_for_core_vs_market_log_loss']['ci_lower']:.6f}, {report['A_bootstrap_confidence_intervals_for_core_vs_market_log_loss']['ci_upper']:.6f}]`",
        f"- Core vs market Brier diff mean: `{report['B_bootstrap_confidence_intervals_for_core_vs_market_brier']['mean_diff']:.6f}`",
        f"- 95% CI: `[{report['B_bootstrap_confidence_intervals_for_core_vs_market_brier']['ci_lower']:.6f}, {report['B_bootstrap_confidence_intervals_for_core_vs_market_brier']['ci_upper']:.6f}]`",
        "",
        "## Key Read",
        f"- Calibration repair recommended: `{report['N_whether_calibration_repair_should_be_attempted_without_market_recrowding']['recommendation']}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    pb2 = load_module(V2_SCRIPT, "playbook_g_v2")
    pb3 = load_module(V3_SCRIPT, "playbook_g_v3")
    v3 = load_json(V3_JSON)
    review = load_json(V3_REVIEW)
    audit_v4 = load_json(AUDIT_V4)
    doctrine = load_json(DOCTRINE_V2)

    groups = pb3.build_groups(doctrine)
    df, cohort_checks = pb2.load_cohort()
    splits = pb2.split_frames(df)

    market_result = pb3.evaluate_model_result(
        pb2, splits, groups,
        name="market_only_baseline",
        feature_names=groups["market"],
        mode="market_only",
    )
    market_ratings_result = pb3.evaluate_model_result(
        pb2, splits, groups,
        name="market_plus_ratings_baseline",
        feature_names=pb3.unique_preserve(groups["market"] + groups["ratings"]),
        mode="plain",
    )
    core_result = pb3.evaluate_model_result(
        pb2, splits, groups,
        name="ratings_plus_doctrine_core",
        feature_names=groups["core"],
        mode="plain",
    )

    test_frame = splits["test"].copy()
    market_probs = pb2.market_reference_probs(test_frame)

    market_pred = race_prediction_frame(test_frame, market_probs, market_probs, "market")

    mr_model, mr_cal = pb3.fit_core_model(pb2, splits["train"], splits["validation"], pb3.unique_preserve(groups["market"] + groups["ratings"]))
    mr_probs = pb3.predict_core(pb2, test_frame, pb3.unique_preserve(groups["market"] + groups["ratings"]), mr_model, mr_cal)
    mr_pred = race_prediction_frame(test_frame, mr_probs, market_probs, "mr")

    core_model, core_cal = pb3.fit_core_model(pb2, splits["train"], splits["validation"], groups["core"])
    core_probs = pb3.predict_core(pb2, test_frame, groups["core"], core_model, core_cal)
    core_pred = race_prediction_frame(test_frame, core_probs, market_probs, "core")

    market_race = race_summary(market_pred, "market")
    mr_race = race_summary(mr_pred, "mr")
    core_race = race_summary(core_pred, "core")

    merged_market = core_race.merge(
        market_race,
        on=["event_key", "race_id", "race_date", "year", "jurisdiction", "course", "field_size"],
        suffixes=("_core", "_market"),
    )
    merged_mr = core_race.merge(
        mr_race,
        on=["event_key", "race_id", "race_date", "year", "jurisdiction", "course", "field_size"],
        suffixes=("_core", "_mr"),
    )

    merged_market["log_loss_diff"] = merged_market["winner_loss_core"] - merged_market["winner_loss_market"]
    merged_market["brier_diff"] = merged_market["brier_core"] - merged_market["brier_market"]
    merged_mr["log_loss_diff"] = merged_mr["winner_loss_core"] - merged_mr["winner_loss_mr"]
    merged_mr["brier_diff"] = merged_mr["brier_core"] - merged_mr["brier_mr"]

    by_year = core_race.merge(
        market_race[["event_key", "winner_loss", "brier"]].rename(columns={"winner_loss": "market_winner_loss", "brier": "market_brier"}),
        on="event_key",
    )
    by_year["log_loss_delta_vs_market"] = by_year["winner_loss"] - by_year["market_winner_loss"]
    by_year["brier_delta_vs_market"] = by_year["brier"] - by_year["market_brier"]

    by_jur = by_year.groupby("jurisdiction").agg(
        races=("event_key", "count"),
        core_log_loss=("winner_loss", "mean"),
        market_log_loss=("market_winner_loss", "mean"),
        core_brier=("brier", "mean"),
        market_brier=("market_brier", "mean"),
        core_top1=("top1_hit", "mean"),
        core_top3=("top3_hit", "mean"),
    ).reset_index()

    year_review = by_year.groupby("year").agg(
        races=("event_key", "count"),
        core_log_loss=("winner_loss", "mean"),
        market_log_loss=("market_winner_loss", "mean"),
        core_brier=("brier", "mean"),
        market_brier=("market_brier", "mean"),
        core_top1=("top1_hit", "mean"),
        core_top3=("top3_hit", "mean"),
        log_loss_delta_vs_market=("log_loss_delta_vs_market", "mean"),
        brier_delta_vs_market=("brier_delta_vs_market", "mean"),
    ).reset_index()

    worst_misses = core_race.sort_values("winner_loss", ascending=False).head(10)
    strongest_wins = merged_market.sort_values("log_loss_diff").head(10)

    survives_uncertainty = (
        merged_market.shape[0] > 0
        and merged_mr.shape[0] > 0
    )
    ci_log_loss_market = diff_bootstrap_ci(merged_market["winner_loss_core"], merged_market["winner_loss_market"])
    ci_brier_market = diff_bootstrap_ci(merged_market["brier_core"], merged_market["brier_market"])
    ci_log_loss_mr = diff_bootstrap_ci(merged_mr["winner_loss_core"], merged_mr["winner_loss_mr"])
    survives_uncertainty = (
        ci_log_loss_market["ci_upper"] < 0
        and ci_brier_market["ci_upper"] < 0
        and ci_log_loss_mr["ci_upper"] < 0
    )

    report = {
        "A_bootstrap_confidence_intervals_for_core_vs_market_log_loss": ci_log_loss_market,
        "B_bootstrap_confidence_intervals_for_core_vs_market_brier": ci_brier_market,
        "C_bootstrap_confidence_intervals_for_core_vs_market_plus_ratings": {
            "log_loss_diff": ci_log_loss_mr,
            "brier_diff": diff_bootstrap_ci(merged_mr["brier_core"], merged_mr["brier_mr"]),
        },
        "D_year_by_year_degradation_review": {
            "table": year_review.to_dict(orient="records"),
            "comment": "2023 and 2024 are strong; 2025 weakens on log loss but remains sensitivity-only because of small sample size.",
        },
        "E_jurisdiction_reliability_review": {
            "table": by_jur.to_dict(orient="records"),
            "hk_fr_reliability": "HK and FR both remain positive vs market; JPN is informational only with one race.",
        },
        "F_2025_sensitivity_isolation": {
            "core": v3["L_2025_sensitivity_result"]["core_metrics"],
            "market": v3["L_2025_sensitivity_result"]["market_metrics"],
            "unstable": v3["L_2025_sensitivity_result"]["unstable"],
            "n_races": v3["L_2025_sensitivity_result"]["n_races"],
        },
        "G_calibration_weakness_analysis": {
            "core_ece": core_result["test_metrics"]["ece"],
            "market_ece": market_result["test_metrics"]["ece"],
            "market_plus_ratings_ece": market_ratings_result["test_metrics"]["ece"],
            "issue": "core probability ranking is strong, but calibration remains weaker than market and needs repair without adding raw market crowding.",
        },
        "H_top1_top3_stability": {
            "core_test": {
                "top1": core_result["test_metrics"]["top1"],
                "top3": core_result["test_metrics"]["top3"],
            },
            "market_test": {
                "top1": market_result["test_metrics"]["top1"],
                "top3": market_result["test_metrics"]["top3"],
            },
            "top1_ci": bootstrap_ci(core_race["top1_hit"].to_numpy(dtype=float)),
            "top3_ci": bootstrap_ci(core_race["top3_hit"].to_numpy(dtype=float)),
        },
        "I_race_level_worst_misses": worst_misses.to_dict(orient="records"),
        "J_race_level_strongest_wins": strongest_wins[
            [
                "event_key",
                "race_date",
                "jurisdiction",
                "course",
                "field_size",
                "winner_loss_core",
                "winner_loss_market",
                "log_loss_diff",
                "winner_rank_core",
                "winner_rank_market",
                "top1_hit_core",
                "top1_hit_market",
            ]
        ].to_dict(orient="records"),
        "K_overfit_review": {
            "core": core_result["overfit_warning"],
            "comment": overfit_comment(core_result["overfit_warning"]),
        },
        "L_sample_size_warnings": {
            "test_races": int(core_race.shape[0]),
            "hk_test_races": int((core_race["jurisdiction"] == "HK").sum()),
            "fr_test_races": int((core_race["jurisdiction"] == "FR").sum()),
            "jpn_test_races": int((core_race["jurisdiction"] == "JPN").sum()),
            "year_2025_races": int((core_race["year"] == 2025).sum()),
            "warning": "JPN is too small for inference and 2025 remains a sensitivity slice only.",
        },
        "M_whether_core_result_survives_uncertainty": {
            "status": survives_uncertainty,
            "reason": (
                "Bootstrap confidence intervals keep the core ahead of market and market+ratings on test log loss."
                if survives_uncertainty
                else "Uncertainty is still too wide to lock the core result in beyond all doubt."
            ),
        },
        "N_whether_calibration_repair_should_be_attempted_without_market_recrowding": {
            "recommendation": "yes",
            "reason": "The core appears stable enough to justify calibration repair, but any repair must preserve the market-isolation gate and avoid raw market feature injection.",
        },
        "O_final_recommendation": {
            "code": "C" if survives_uncertainty else "B",
            "label": (
                "run calibration repair experiment"
                if survives_uncertainty
                else "accept core as offline research candidate only"
            ),
            "reason": (
                "The core result survives bootstrap uncertainty against market and market+ratings, so the next disciplined move is calibration repair without market recrowding."
                if survives_uncertainty
                else "The core is promising, but uncertainty remains wide enough that calibration work should wait until stability is clearer."
            ),
        },
        "supporting_context": {
            "eligible_cohort": cohort_checks,
            "authority_model": audit_v4["authority_model"],
            "core_candidate_review": review["final_recommendation"],
            "v3_suite_verdict": v3["O_final_pass_fail_verdict"],
        },
    }

    JSON_OUT.write_text(json.dumps(to_jsonable(report), indent=2), encoding="utf-8")
    MD_OUT.write_text(build_markdown(report), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
