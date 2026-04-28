from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
JSON_OUT = DATA_DIR / "playbook_g_v2_ablation_dry_run.json"
MD_OUT = DATA_DIR / "playbook_g_v2_ablation_dry_run.md"
CSV_OUT = DATA_DIR / "playbook_g_v2_ablation_metrics.csv"
DOCTRINE_AUDIT_PATH = DATA_DIR / "historical_doctrine_feature_audit_v2.json"

V1_MARKET_TEST = {
    "log_loss": 1.725229,
    "brier": 0.085483,
    "top1": 0.3596,
    "top3": 0.6930,
}
V1_HK_MARKET_LOG_LOSS = 2.004304
V1_HK_CANDIDATE_LOG_LOSS = 2.413058
V1_HK_LOG_LOSS_GAP = V1_HK_CANDIDATE_LOG_LOSS - V1_HK_MARKET_LOG_LOSS
V1_OVERFIT_TEST_TRAIN_GAP_PCT = 63.5

FORBIDDEN_FIELDS = {
    "winner_flag",
    "placed_flag",
    "finish_position",
    "position",
    "result_comment",
    "post_race_ranking",
    "sqpe_v17_prob",
    "velo_prime_prob",
    "g_base_prob",
    "place_prob",
    "verdict_flags",
}
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


def get_sb_client():
    load_dotenv(ROOT / ".env", override=False)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials missing.")
    return create_client(url, key)


def parse_date_key(value: Any) -> str:
    return str(value or "")[:10]


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


def paged_hfs_rows(sb) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    page_size = 1000
    while True:
        page = (
            sb.table("historical_feature_store")
            .select("race_id,horse_id,race_date,course,jurisdiction,winner_flag,feature_json")
            .range(start, start + page_size - 1)
            .execute()
            .data
            or []
        )
        if not page:
            break
        rows.extend(page)
        start += len(page)
    return rows


def load_feature_groups() -> dict[str, list[str]]:
    audit = json.loads(DOCTRINE_AUDIT_PATH.read_text(encoding="utf-8"))
    market = list(audit["D_market_feature_list"])
    ratings = list(audit["E_rating_feature_list"])
    doctrine = list(audit["F_doctrine_feature_list"])
    context_other = [name for name in FEATURE_VECTOR_NAMES if name not in set(market + ratings + doctrine)]
    return {
        "market": market,
        "ratings": ratings,
        "doctrine": doctrine,
        "context_other": context_other,
    }


def load_cohort() -> tuple[pd.DataFrame, dict[str, Any]]:
    sb = get_sb_client()
    rows = []
    for row in paged_hfs_rows(sb):
        feature_json = row.get("feature_json") if isinstance(row.get("feature_json"), dict) else {}
        vector = feature_json.get("strictly_ordered_vector")
        race_year = parse_date_key(row.get("race_date"))[:4]
        if feature_json.get("training_eligible") != "pending_global_training_gate":
            continue
        if feature_json.get("data_owner_confirmed") is not True:
            continue
        if feature_json.get("source") != "historical_raceform":
            continue
        if feature_json.get("event_identity_contract") != "race_id_course_race_date":
            continue
        if feature_json.get("signal_contract_version") != "HISTORICAL_SIGNAL_PROXY_V1":
            continue
        if feature_json.get("historical_doctrine_contract") != "HISTORICAL_DOCTRINE_FEATURES_V1":
            continue
        if feature_json.get("doctrine_source") != "prior_only_raceform_history":
            continue
        if not isinstance(vector, list) or len(vector) != len(FEATURE_VECTOR_NAMES):
            continue
        if not race_year.isdigit():
            continue
        if feature_json.get("macro_year_used") != int(race_year):
            continue
        record: dict[str, Any] = {
            "race_id": str(row["race_id"]),
            "horse_id": str(row["horse_id"]),
            "event_key": str(feature_json.get("event_key") or f"{row['race_id']}|{row.get('course') or ''}|{parse_date_key(row.get('race_date'))}"),
            "race_date": parse_date_key(row.get("race_date")),
            "year": int(race_year),
            "course": str(row.get("course") or ""),
            "jurisdiction": str(row.get("jurisdiction") or ""),
            "winner_flag": int(bool(row.get("winner_flag"))),
        }
        for idx, feature_name in enumerate(FEATURE_VECTOR_NAMES):
            record[feature_name] = float(vector[idx])
        rows.append(record)

    df = pd.DataFrame(rows).sort_values(["race_date", "race_id", "horse_id"]).reset_index(drop=True)
    race_level = (
        df.groupby("event_key")
        .agg(
            race_id=("race_id", "first"),
            race_date=("race_date", "first"),
            year=("year", "first"),
            course=("course", "first"),
            jurisdiction=("jurisdiction", "first"),
            field_size=("winner_flag", "size"),
            winner_count=("winner_flag", "sum"),
        )
        .reset_index()
    )
    checks = {
        "eligible_race_count": int(race_level.shape[0]),
        "eligible_runner_count": int(df.shape[0]),
        "year_breakdown_races": {str(k): int(v) for k, v in race_level["year"].value_counts().sort_index().items()},
        "jurisdiction_breakdown_races": {str(k): int(v) for k, v in race_level["jurisdiction"].value_counts().items()},
        "course_breakdown_races": {str(k): int(v) for k, v in race_level["course"].value_counts().items()},
        "feature_vector_length_ok": True,
    }
    return df, checks


def split_frames(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "train": df[df["year"].between(2017, 2020)].copy(),
        "validation": df[df["year"].between(2021, 2022)].copy(),
        "test": df[df["year"].between(2023, 2025)].copy(),
    }


def fit_isotonic(scores: np.ndarray, labels: np.ndarray) -> IsotonicRegression | None:
    if len(np.unique(labels)) < 2:
        return None
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(scores, labels)
    return iso


def normalize_probabilities(event_keys: np.ndarray, raw_probs: np.ndarray) -> np.ndarray:
    probs = np.clip(np.asarray(raw_probs, dtype=float), 1e-12, 1 - 1e-12)
    out = np.zeros_like(probs)
    key_to_indices: dict[str, list[int]] = {}
    for idx, key in enumerate(event_keys):
        key_to_indices.setdefault(str(key), []).append(idx)
    for indices in key_to_indices.values():
        race_probs = probs[indices]
        total = float(race_probs.sum())
        if total <= 0 or not np.isfinite(total):
            out[indices] = 1.0 / len(indices)
        else:
            out[indices] = race_probs / total
    return out


def runner_level_ece(probs: np.ndarray, labels: np.ndarray, bins: int = 15) -> float:
    probs = np.asarray(probs, dtype=float)
    labels = np.asarray(labels, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    total = len(probs)
    for start, end in zip(edges[:-1], edges[1:]):
        if end == 1.0:
            mask = (probs >= start) & (probs <= end)
        else:
            mask = (probs >= start) & (probs < end)
        if not mask.any():
            continue
        conf = float(probs[mask].mean())
        acc = float(labels[mask].mean())
        ece += abs(conf - acc) * (mask.sum() / total)
    return ece


def random_baseline_metrics(race_level: pd.DataFrame) -> dict[str, float]:
    field_sizes = race_level["field_size"].astype(float).to_numpy()
    uniform_log_loss = float(np.mean(np.log(field_sizes)))
    uniform_top1 = float(np.mean(1.0 / field_sizes))
    uniform_top3 = float(np.mean(np.minimum(3.0 / field_sizes, 1.0)))
    return {
        "uniform_log_loss": uniform_log_loss,
        "uniform_top1": uniform_top1,
        "uniform_top3": uniform_top3,
    }


def market_reference_probs(frame: pd.DataFrame) -> np.ndarray:
    return normalize_probabilities(frame["event_key"].to_numpy(), frame["implied_prob"].to_numpy(dtype=float))


def evaluate_frame(
    frame: pd.DataFrame,
    probs: np.ndarray,
    *,
    market_probs: np.ndarray,
) -> dict[str, Any]:
    if frame.empty:
        return {
            "log_loss": None,
            "brier": None,
            "top1": None,
            "top3": None,
            "ece": None,
            "market_rank_lift": None,
            "n_races": 0,
            "n_runners": 0,
        }

    work = frame[["event_key", "winner_flag", "jurisdiction", "year"]].copy()
    work["prob"] = np.asarray(probs, dtype=float)
    work["market_prob"] = np.asarray(market_probs, dtype=float)

    winner_probs = work.loc[work["winner_flag"] == 1, "prob"].to_numpy()
    log_loss = float(np.mean(-np.log(np.clip(winner_probs, 1e-12, 1.0))))
    brier = float(np.mean((work["prob"].to_numpy() - work["winner_flag"].to_numpy(dtype=float)) ** 2))
    ece = runner_level_ece(work["prob"].to_numpy(), work["winner_flag"].to_numpy(dtype=float))

    top1_hits = []
    top3_hits = []
    market_rank_lifts = []
    for _, race in work.groupby("event_key", sort=False):
        race = race.sort_values("prob", ascending=False).reset_index(drop=True)
        winner_index = int(race.index[race["winner_flag"] == 1][0])
        top1_hits.append(float(winner_index == 0))
        top3_hits.append(float(winner_index < min(3, race.shape[0])))

        race_market = race.sort_values("market_prob", ascending=False).reset_index(drop=True)
        market_winner_index = int(race_market.index[race_market["winner_flag"] == 1][0])
        market_rank_lifts.append(float(market_winner_index - winner_index))

    return {
        "log_loss": log_loss,
        "brier": brier,
        "top1": float(np.mean(top1_hits)),
        "top3": float(np.mean(top3_hits)),
        "ece": ece,
        "market_rank_lift": float(np.mean(market_rank_lifts)),
        "n_races": int(work["event_key"].nunique()),
        "n_runners": int(work.shape[0]),
    }


def feature_matrix(frame: pd.DataFrame, feature_names: list[str]) -> np.ndarray:
    return frame[feature_names].to_numpy(dtype=float)


def sample_weights(frame: pd.DataFrame) -> np.ndarray:
    field_sizes = frame.groupby("event_key")["winner_flag"].transform("size").to_numpy(dtype=float)
    return 1.0 / field_sizes


def fit_gbm_model(
    train_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    feature_names: list[str],
) -> tuple[GradientBoostingClassifier, IsotonicRegression | None]:
    model = GradientBoostingClassifier(
        random_state=42,
        n_estimators=150,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.7,
    )
    model.fit(
        feature_matrix(train_frame, feature_names),
        train_frame["winner_flag"].to_numpy(dtype=int),
        sample_weight=sample_weights(train_frame),
    )
    val_scores = model.predict_proba(feature_matrix(validation_frame, feature_names))[:, 1]
    calibrator = fit_isotonic(val_scores, validation_frame["winner_flag"].to_numpy(dtype=int))
    return model, calibrator


def calibrate_scores(
    scores: np.ndarray,
    calibrator: IsotonicRegression | None,
) -> np.ndarray:
    if calibrator is None:
        return np.clip(scores, 1e-6, 1 - 1e-6)
    calibrated = calibrator.transform(scores)
    return np.clip(np.asarray(calibrated, dtype=float), 1e-6, 1 - 1e-6)


def predict_frame(
    frame: pd.DataFrame,
    feature_names: list[str],
    model: GradientBoostingClassifier,
    calibrator: IsotonicRegression | None,
) -> np.ndarray:
    raw_scores = model.predict_proba(feature_matrix(frame, feature_names))[:, 1]
    calibrated = calibrate_scores(raw_scores, calibrator)
    return normalize_probabilities(frame["event_key"].to_numpy(), calibrated)


def fit_jurisdiction_calibrators(
    validation_frame: pd.DataFrame,
    raw_scores: np.ndarray,
) -> dict[str, IsotonicRegression | None]:
    calibrators: dict[str, IsotonicRegression | None] = {
        "GLOBAL": fit_isotonic(raw_scores, validation_frame["winner_flag"].to_numpy(dtype=int))
    }
    for jurisdiction in ("HK", "FR"):
        mask = validation_frame["jurisdiction"].to_numpy() == jurisdiction
        labels = validation_frame.loc[mask, "winner_flag"].to_numpy(dtype=int)
        if mask.sum() >= 50 and len(np.unique(labels)) >= 2:
            calibrators[jurisdiction] = fit_isotonic(raw_scores[mask], labels)
        else:
            calibrators[jurisdiction] = calibrators["GLOBAL"]
    return calibrators


def predict_with_jurisdiction_calibration(
    frame: pd.DataFrame,
    feature_names: list[str],
    model: GradientBoostingClassifier,
    calibrators: dict[str, IsotonicRegression | None],
) -> np.ndarray:
    raw_scores = model.predict_proba(feature_matrix(frame, feature_names))[:, 1]
    calibrated = np.zeros_like(raw_scores, dtype=float)
    jurisdictions = frame["jurisdiction"].to_numpy()
    for idx, score in enumerate(raw_scores):
        calibrator = calibrators.get(str(jurisdictions[idx]), calibrators.get("GLOBAL"))
        calibrated[idx] = calibrate_scores(np.asarray([score], dtype=float), calibrator)[0]
    return normalize_probabilities(frame["event_key"].to_numpy(), calibrated)


def feature_importance_payload(
    model: GradientBoostingClassifier | None,
    feature_names: list[str],
    groups: dict[str, list[str]],
    *,
    direct_market: bool = False,
) -> dict[str, Any]:
    if direct_market:
        return {
            "group_share": {"market": 1.0, "ratings": 0.0, "doctrine": 0.0, "context_other": 0.0},
            "top_features": [{"feature": "implied_prob", "importance": 1.0}],
        }
    if model is None:
        return {"group_share": {}, "top_features": []}
    importances = dict(zip(feature_names, model.feature_importances_.tolist()))
    total = sum(importances.values()) or 1.0
    group_share = {}
    for group_name, group_features in groups.items():
        group_share[group_name] = float(sum(importances.get(name, 0.0) for name in group_features) / total)
    top_features = [
        {"feature": name, "importance": value}
        for name, value in sorted(importances.items(), key=lambda item: item[1], reverse=True)[:10]
    ]
    return {"group_share": group_share, "top_features": top_features}


def split_metrics_payload(
    frame: pd.DataFrame,
    probs: np.ndarray,
    market_probs: np.ndarray,
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_jurisdiction: dict[str, Any] = {}
    for jurisdiction in sorted(frame["jurisdiction"].unique()):
        mask = frame["jurisdiction"].to_numpy() == jurisdiction
        by_jurisdiction[str(jurisdiction)] = evaluate_frame(frame.loc[mask], probs[mask], market_probs=market_probs[mask])

    by_year: dict[str, Any] = {}
    for year in sorted(frame["year"].unique()):
        mask = frame["year"].to_numpy() == year
        by_year[str(int(year))] = evaluate_frame(frame.loc[mask], probs[mask], market_probs=market_probs[mask])
    return by_jurisdiction, by_year


def overfit_warning(train_metrics: dict[str, Any], validation_metrics: dict[str, Any], test_metrics: dict[str, Any]) -> dict[str, Any]:
    train_ll = train_metrics["log_loss"]
    val_ll = validation_metrics["log_loss"]
    test_ll = test_metrics["log_loss"]
    train_br = train_metrics["brier"]
    val_br = validation_metrics["brier"]
    test_br = test_metrics["brier"]

    ll_gap_pct = float(((test_ll - train_ll) / train_ll) * 100.0) if train_ll else None
    brier_gap_pct = float(((test_br - train_br) / train_br) * 100.0) if train_br else None
    if ll_gap_pct is None or brier_gap_pct is None:
        level = "unknown"
    elif ll_gap_pct > 50 or brier_gap_pct > 50:
        level = "high"
    elif ll_gap_pct > 20 or brier_gap_pct > 20:
        level = "medium"
    else:
        level = "low"
    return {
        "level": level,
        "test_vs_train_log_loss_gap_pct": ll_gap_pct,
        "validation_vs_train_log_loss_gap_pct": float(((val_ll - train_ll) / train_ll) * 100.0) if train_ll else None,
        "test_vs_train_brier_gap_pct": brier_gap_pct,
        "validation_vs_train_brier_gap_pct": float(((val_br - train_br) / train_br) * 100.0) if train_br else None,
    }


def evaluate_model_result(
    name: str,
    feature_names: list[str],
    splits: dict[str, pd.DataFrame],
    groups: dict[str, list[str]],
    *,
    direct_market: bool = False,
    jurisdiction_calibration: bool = False,
    jurisdiction_only: str | None = None,
) -> dict[str, Any]:
    train_frame = splits["train"]
    validation_frame = splits["validation"]
    test_frame = splits["test"]

    if jurisdiction_only is not None:
        train_frame = train_frame[train_frame["jurisdiction"] == jurisdiction_only].copy()
        validation_frame = validation_frame[validation_frame["jurisdiction"] == jurisdiction_only].copy()
        test_frame = test_frame[test_frame["jurisdiction"] == jurisdiction_only].copy()

    if direct_market:
        train_probs = market_reference_probs(train_frame)
        validation_probs = market_reference_probs(validation_frame)
        test_probs = market_reference_probs(test_frame)
        model = None
        importance = feature_importance_payload(None, feature_names, groups, direct_market=True)
        calibration_mode = "direct_market_probability"
    else:
        model, calibrator = fit_gbm_model(train_frame, validation_frame, feature_names)
        if jurisdiction_calibration:
            validation_raw = model.predict_proba(feature_matrix(validation_frame, feature_names))[:, 1]
            calibrators = fit_jurisdiction_calibrators(validation_frame, validation_raw)
            train_probs = predict_with_jurisdiction_calibration(train_frame, feature_names, model, calibrators)
            validation_probs = predict_with_jurisdiction_calibration(validation_frame, feature_names, model, calibrators)
            test_probs = predict_with_jurisdiction_calibration(test_frame, feature_names, model, calibrators)
            calibration_mode = "jurisdiction_specific_isotonic"
        else:
            train_probs = predict_frame(train_frame, feature_names, model, calibrator)
            validation_probs = predict_frame(validation_frame, feature_names, model, calibrator)
            test_probs = predict_frame(test_frame, feature_names, model, calibrator)
            calibration_mode = "global_isotonic"
        importance = feature_importance_payload(model, feature_names, groups)

    market_train = market_reference_probs(train_frame)
    market_validation = market_reference_probs(validation_frame)
    market_test = market_reference_probs(test_frame)

    train_metrics = evaluate_frame(train_frame, train_probs, market_probs=market_train)
    validation_metrics = evaluate_frame(validation_frame, validation_probs, market_probs=market_validation)
    test_metrics = evaluate_frame(test_frame, test_probs, market_probs=market_test)
    jur_metrics, year_metrics = split_metrics_payload(test_frame, test_probs, market_test)
    return {
        "name": name,
        "feature_names": feature_names,
        "feature_count": len(feature_names),
        "calibration_mode": calibration_mode,
        "jurisdiction_only": jurisdiction_only,
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "test_metrics_by_jurisdiction": jur_metrics,
        "test_metrics_by_year": year_metrics,
        "overfit_warning": overfit_warning(train_metrics, validation_metrics, test_metrics),
        "feature_importance_by_group": importance["group_share"],
        "top_features": importance["top_features"],
    }


def metrics_rows_for_csv(model_result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []

    def add_row(scope: str, scope_value: str, metrics: dict[str, Any]) -> None:
        rows.append(
            {
                "model": model_result["name"],
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
        )

    add_row("split", "train", model_result["train_metrics"])
    add_row("split", "validation", model_result["validation_metrics"])
    add_row("split", "test", model_result["test_metrics"])
    for jurisdiction, metrics in model_result["test_metrics_by_jurisdiction"].items():
        add_row("jurisdiction", jurisdiction, metrics)
    for year, metrics in model_result["test_metrics_by_year"].items():
        add_row("year", year, metrics)
    return rows


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Playbook G V2 Ablation Dry Run",
        "",
        f"- Eligible races / runners: `{report['A_eligible_race_count']} / {report['B_eligible_runner_count']}`",
        f"- Best model by log loss: `{report['K_best_model_by_log_loss']}`",
        f"- Best model by Brier: `{report['L_best_model_by_brier']}`",
        f"- Best model by top-1: `{report['M_best_model_by_top1']}`",
        f"- Best model by top-3: `{report['N_best_model_by_top3']}`",
        f"- Doctrine improves market + ratings: `{report['O_doctrine_improves_market_plus_ratings']}`",
        f"- HK failure fixed or reduced: `{report['P_hk_failure_fixed_or_reduced']}`",
        f"- FR remains positive: `{report['Q_fr_remains_positive']}`",
        f"- 2025 unstable: `{report['R_2025_remains_unstable']}`",
        f"- Final verdict: `{report['S_final_pass_fail_verdict']}`",
        "",
        "## Overall Test Metrics",
    ]
    for name, result in report["ablation_results"].items():
        metrics = result["test_metrics"]
        lines.append(
            f"- `{name}`: log loss `{metrics['log_loss']:.6f}`, Brier `{metrics['brier']:.6f}`, top-1 `{metrics['top1']:.2%}`, top-3 `{metrics['top3']:.2%}`, ECE `{metrics['ece']:.5f}`"
        )
    return "\n".join(lines) + "\n"


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def main() -> None:
    groups = load_feature_groups()
    df, cohort_checks = load_cohort()
    splits = split_frames(df)

    leakage_audit = {
        "status": "pass",
        "source": "historical_doctrine_contract + prior_only_raceform_history + previously accepted full reapply leakage gate",
        "same_day_or_future_history_leakage": 0,
    }
    outcome_audit = {
        "status": "pass",
        "forbidden_feature_intersection": sorted(set(FEATURE_VECTOR_NAMES) & FORBIDDEN_FIELDS),
        "training_matrix_source": "strictly_ordered_vector only",
    }

    doctrine_variances = {
        feature: float(df[feature].var(ddof=0))
        for feature in groups["doctrine"]
    }
    dist_f_variance = float(df["dist_f"].var(ddof=0))
    race_level = (
        df.groupby("event_key")
        .agg(year=("year", "first"), jurisdiction=("jurisdiction", "first"), course=("course", "first"), field_size=("winner_flag", "size"))
        .reset_index()
    )
    random_baseline = random_baseline_metrics(race_level[race_level["year"].between(2023, 2025)])

    ablation_specs = [
        ("market_only", groups["market"], {"direct_market": True}),
        ("ratings_only", groups["ratings"], {}),
        ("doctrine_only", groups["doctrine"], {}),
        ("market_plus_ratings", groups["market"] + groups["ratings"], {}),
        ("market_plus_doctrine", groups["market"] + groups["doctrine"], {}),
        ("ratings_plus_doctrine", groups["ratings"] + groups["doctrine"], {}),
        ("market_plus_ratings_plus_doctrine", groups["market"] + groups["ratings"] + groups["doctrine"], {}),
        ("hk_only_diagnostic", groups["market"] + groups["ratings"] + groups["doctrine"], {"jurisdiction_only": "HK"}),
        ("fr_only_diagnostic", groups["market"] + groups["ratings"] + groups["doctrine"], {"jurisdiction_only": "FR"}),
        ("jurisdiction_specific_calibration", groups["market"] + groups["ratings"] + groups["doctrine"], {"jurisdiction_calibration": True}),
    ]

    ablation_results: dict[str, Any] = {}
    csv_rows: list[dict[str, Any]] = []
    for name, feature_names, kwargs in ablation_specs:
        result = evaluate_model_result(name, feature_names, splits, groups, **kwargs)
        ablation_results[name] = result
        csv_rows.extend(metrics_rows_for_csv(result))

    overall_candidates = {
        name: result
        for name, result in ablation_results.items()
        if result["jurisdiction_only"] is None
    }
    best_log_loss = min(overall_candidates.items(), key=lambda item: item[1]["test_metrics"]["log_loss"])
    best_brier = min(overall_candidates.items(), key=lambda item: item[1]["test_metrics"]["brier"])
    best_top1 = max(overall_candidates.items(), key=lambda item: item[1]["test_metrics"]["top1"])
    best_top3 = max(overall_candidates.items(), key=lambda item: item[1]["test_metrics"]["top3"])

    mr = ablation_results["market_plus_ratings"]["test_metrics"]
    mrd = ablation_results["market_plus_ratings_plus_doctrine"]["test_metrics"]
    doctrine_only = ablation_results["doctrine_only"]["test_metrics"]
    market_only = ablation_results["market_only"]["test_metrics"]
    hk_mrd = ablation_results["market_plus_ratings_plus_doctrine"]["test_metrics_by_jurisdiction"].get("HK", {})
    hk_market = ablation_results["market_only"]["test_metrics_by_jurisdiction"].get("HK", {})
    fr_mrd = ablation_results["market_plus_ratings_plus_doctrine"]["test_metrics_by_jurisdiction"].get("FR", {})
    fr_market = ablation_results["market_only"]["test_metrics_by_jurisdiction"].get("FR", {})
    y2025_mrd = ablation_results["market_plus_ratings_plus_doctrine"]["test_metrics_by_year"].get("2025", {})
    y2025_market = ablation_results["market_only"]["test_metrics_by_year"].get("2025", {})

    doctrine_nonzero_signal = (
        doctrine_only["log_loss"] is not None
        and doctrine_only["log_loss"] < random_baseline["uniform_log_loss"]
        and doctrine_only["top1"] > random_baseline["uniform_top1"]
    )
    hk_gap = hk_mrd["log_loss"] - hk_market["log_loss"]
    hk_failure_fixed_or_reduced = hk_gap <= 0 or hk_gap <= (V1_HK_LOG_LOSS_GAP * 0.5)
    fr_remains_positive = fr_mrd["log_loss"] <= fr_market["log_loss"]
    calibration_ok = mrd["ece"] <= (market_only["ece"] + 0.005)
    overfit = ablation_results["market_plus_ratings_plus_doctrine"]["overfit_warning"]
    overfit_ok = (
        overfit["level"] != "high"
        or (overfit["test_vs_train_log_loss_gap_pct"] is not None and overfit["test_vs_train_log_loss_gap_pct"] < V1_OVERFIT_TEST_TRAIN_GAP_PCT)
    )
    doctrine_improves_mr = mrd["log_loss"] < mr["log_loss"] and mrd["brier"] < mr["brier"]
    year_2025_unstable = (
        y2025_mrd.get("n_races", 0) <= 30
        or y2025_mrd.get("log_loss", 0) > y2025_market.get("log_loss", 0)
    )

    final_pass = (
        doctrine_improves_mr
        and doctrine_nonzero_signal
        and hk_failure_fixed_or_reduced
        and fr_remains_positive
        and calibration_ok
        and overfit_ok
        and not outcome_audit["forbidden_feature_intersection"]
        and leakage_audit["same_day_or_future_history_leakage"] == 0
    )

    report = {
        "A_eligible_race_count": cohort_checks["eligible_race_count"],
        "B_eligible_runner_count": cohort_checks["eligible_runner_count"],
        "C_train_validation_test_counts": {
            split_name: {
                "races": int(frame["event_key"].nunique()),
                "runners": int(frame.shape[0]),
            }
            for split_name, frame in splits.items()
        },
        "D_year_breakdown": cohort_checks["year_breakdown_races"],
        "E_jurisdiction_breakdown": cohort_checks["jurisdiction_breakdown_races"],
        "F_feature_vector_checks": {
            "vector_length_distribution": {"37": int(df.shape[0])},
            "nan_count": int(df[FEATURE_VECTOR_NAMES].isna().sum().sum()),
            "inf_count": int(np.isinf(df[FEATURE_VECTOR_NAMES].to_numpy(dtype=float)).sum()),
            "context_structural_feature_list": groups["context_other"],
        },
        "G_leakage_audit": leakage_audit,
        "H_outcome_field_exclusion_audit": outcome_audit,
        "I_doctrine_feature_variance_confirmation": doctrine_variances,
        "J_dist_f_variance_confirmation": {
            "variance": dist_f_variance,
            "min": float(df["dist_f"].min()),
            "max": float(df["dist_f"].max()),
        },
        "K_best_model_by_log_loss": best_log_loss[0],
        "L_best_model_by_brier": best_brier[0],
        "M_best_model_by_top1": best_top1[0],
        "N_best_model_by_top3": best_top3[0],
        "O_doctrine_improves_market_plus_ratings": {
            "pass": doctrine_improves_mr,
            "market_plus_ratings_test": mr,
            "market_plus_ratings_plus_doctrine_test": mrd,
            "log_loss_delta": mrd["log_loss"] - mr["log_loss"],
            "brier_delta": mrd["brier"] - mr["brier"],
        },
        "P_hk_failure_fixed_or_reduced": {
            "pass": hk_failure_fixed_or_reduced,
            "v1_hk_market_log_loss": V1_HK_MARKET_LOG_LOSS,
            "v1_hk_candidate_log_loss": V1_HK_CANDIDATE_LOG_LOSS,
            "v1_hk_gap": V1_HK_LOG_LOSS_GAP,
            "v2_hk_market_log_loss": hk_market["log_loss"],
            "v2_hk_mrd_log_loss": hk_mrd["log_loss"],
            "v2_hk_gap": hk_gap,
        },
        "Q_fr_remains_positive": {
            "pass": fr_remains_positive,
            "market_log_loss": fr_market["log_loss"],
            "mrd_log_loss": fr_mrd["log_loss"],
        },
        "R_2025_remains_unstable": {
            "status": year_2025_unstable,
            "market": y2025_market,
            "mrd": y2025_mrd,
        },
        "S_final_pass_fail_verdict": "PASS" if final_pass else "FAIL",
        "uniform_test_baseline": random_baseline,
        "ablation_results": ablation_results,
        "pass_gate_checks": {
            "mrd_beats_mr_log_loss": mrd["log_loss"] < mr["log_loss"],
            "mrd_beats_mr_brier": mrd["brier"] < mr["brier"],
            "doctrine_only_non_zero_signal": doctrine_nonzero_signal,
            "hk_failure_fixed_or_reduced": hk_failure_fixed_or_reduced,
            "fr_positive": fr_remains_positive,
            "calibration_not_materially_worse": calibration_ok,
            "overfit_improved_or_explained": overfit_ok,
            "no_leakage_fields_used": leakage_audit["same_day_or_future_history_leakage"] == 0,
            "no_outcome_fields_used": not outcome_audit["forbidden_feature_intersection"],
        },
    }

    report_jsonable = to_jsonable(report)
    JSON_OUT.write_text(json.dumps(report_jsonable, indent=2), encoding="utf-8")
    MD_OUT.write_text(build_markdown(report_jsonable), encoding="utf-8")

    with CSV_OUT.open("w", newline="", encoding="utf-8") as handle:
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
