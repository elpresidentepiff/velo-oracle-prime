#!/usr/bin/env python3
"""Passport + Sigma training test.

Evidence-only audit:
  1. Train a post-score selector from past sigma / innovation protocol rows.
  2. Compare old RP-file features vs passport features vs combined features
     on a 2025 holdout.

No live scoring, promotion, routing, or staking changes.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "data" / "reports"
MODEL_DIR = ROOT / "models" / "sigma_selector_staging"

SIGMA_PATH = ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"
RP_PATH = ROOT / "data" / "raceform_v17_features.parquet"
PASSPORT_PATH = ROOT / "data" / "new_build" / "training" / "passport_features.parquet"

RP_SAFE_FEATURES = [
    "dist_f",
    "going_code",
    "is_aw",
    "class_num",
    "wgt_lbs",
    "or_num",
    "or_vs_field",
    "field_size",
    "draw_num",
    "draw_pct",
    "age_num",
    "runs_since_win",
    "runs_since_place",
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
    "setup_run_flag",
    "cash_run_flag",
]

RP_CORE_NO_RPR_NO_MARKET_FEATURES = [
    "dist_f",
    "going_code",
    "is_aw",
    "field_size",
    "draw_num",
    "draw_pct",
    "age_num",
    "wgt_lbs",
    "or_vs_field",
    "release_window_score",
    "going_fit_score",
    "distance_fit_score",
    "quiet_run_score",
    "trainer_timing_score",
    "jockey_switch_intent",
    "setup_run_flag",
    "cash_run_flag",
]

RP_DOCTRINE_NO_RATINGS_NO_MARKET_FEATURES = [
    "dist_f",
    "going_code",
    "is_aw",
    "class_num",
    "field_size",
    "draw_num",
    "draw_pct",
    "age_num",
    "wgt_lbs",
    "runs_since_win",
    "runs_since_place",
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
    "setup_run_flag",
    "cash_run_flag",
]

PASSPORT_FEATURES = [
    "pp_career_runs",
    "pp_win_rate",
    "pp_place_rate",
    "pp_days_since_last",
    "pp_layoff",
    "pp_avg_sp_last5",
    "pp_jockey_continuity",
    "pp_course_seen",
    "pp_or_change_3",
    "pp_class_moved_up",
    "pp_class_moved_down",
]

BANNED_RPR_MARKET_FEATURES = [
    "sp_dec",
    "log_sp",
    "implied_prob",
    "sp_rank",
    "is_fav",
    "rpr_num",
    "rpr_vs_field",
    "ts_num",
    "odds_resilience_score",
    "odds_contraction_score",
    "decoy_support_flag",
]

SIGMA_FEATURES = [
    "model_probability",
    "sp_decimal",
    "implied_probability",
    "edge",
    "field_size",
    "class_num",
    "candidate_stake",
    "router_v1_shadow_pass",
    "router_v2_class4_shadow_pass",
    "router_v6_gold_seam_watchlist",
]

SUPPORTED_EXCLUDES = {
    "saratoga",
    "happyvalley",
    "sansiro",
    "chantilly",
    "dusseldorf",
    "tokyo",
    "shatin",
    "ellerslie",
    "kenilworth",
    "greyville",
    "turffontein",
    "vaal",
    "flemington",
    "randwick",
}


def norm_course(value: Any) -> str:
    v = str(value or "").lower().replace("(aw)", "").replace(" aw", "")
    return re.sub(r"[^a-z]", "", v)


def _safe_auc(y_true: np.ndarray, proba: np.ndarray) -> float | None:
    if len(set(y_true.tolist())) < 2:
        return None
    return float(roc_auc_score(y_true, proba))


def _top1_metrics(df: pd.DataFrame, proba: np.ndarray, race_col: str = "race_id") -> dict[str, Any]:
    tmp = df[[race_col, "target"]].copy()
    tmp["_p"] = proba
    idx = tmp.groupby(race_col)["_p"].idxmax()
    picks = tmp.loc[idx]
    top1 = float(picks["target"].mean()) if len(picks) else 0.0

    mrrs = []
    for _, g in tmp.sort_values("_p", ascending=False).groupby(race_col, sort=False):
        targets = g["target"].tolist()
        try:
            rank = targets.index(1) + 1
            mrrs.append(1.0 / rank)
        except ValueError:
            pass
    return {
        "races": int(tmp[race_col].nunique()),
        "top1": round(top1, 4),
        "mrr": round(float(np.mean(mrrs)), 4) if mrrs else 0.0,
    }


def _acceptance_bands(test: pd.DataFrame, proba: np.ndarray) -> list[dict[str, Any]]:
    tmp = test.copy()
    tmp["_selector_prob"] = proba
    tmp["_baseline_prob"] = pd.to_numeric(tmp["model_probability"], errors="coerce").fillna(0.0)
    tmp["_pl"] = tmp["target"] * (pd.to_numeric(tmp["sp_decimal"], errors="coerce").fillna(0.0) - 1.0) + (1 - tmp["target"]) * -1.0
    out = []
    for label, col in [("baseline_model_probability", "_baseline_prob"), ("sigma_selector", "_selector_prob")]:
        ranked = tmp.sort_values(col, ascending=False).reset_index(drop=True)
        for frac in (0.10, 0.20, 0.30, 0.50):
            n = max(1, int(len(ranked) * frac))
            sub = ranked.head(n)
            out.append(
                {
                    "ranker": label,
                    "accept_top_pct": int(frac * 100),
                    "n": int(len(sub)),
                    "sr": round(float(sub["target"].mean()), 4),
                    "roi": round(float(sub["_pl"].sum() / len(sub)), 4),
                    "pl": round(float(sub["_pl"].sum()), 4),
                    "avg_sp": round(float(pd.to_numeric(sub["sp_decimal"], errors="coerce").mean()), 4),
                }
            )
    return out


def _make_hgb() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=180,
        learning_rate=0.045,
        max_leaf_nodes=31,
        l2_regularization=0.03,
        random_state=42,
    )


def run_sigma_selector_test() -> dict[str, Any]:
    if not SIGMA_PATH.exists():
        return {"status": "MISSING", "path": str(SIGMA_PATH)}

    df = pd.read_csv(SIGMA_PATH)
    df = df.copy()
    df["target"] = pd.to_numeric(df.get("won"), errors="coerce")
    df = df[df["target"].isin([0, 1])]
    for col in SIGMA_FEATURES:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Keep only rows with a real result and a usable model probability.
    df = df[pd.to_numeric(df["model_probability"], errors="coerce").notna()]
    if len(df) < 200 or df["target"].nunique() < 2:
        return {"status": "LOW_SAMPLE", "rows": int(len(df))}

    groups = df["race_id"].astype(str)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(splitter.split(df, df["target"], groups))
    train = df.iloc[train_idx].copy()
    test = df.iloc[test_idx].copy()

    baseline = test["model_probability"].clip(1e-6, 1 - 1e-6).to_numpy()
    model = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(train[SIGMA_FEATURES], train["target"])
    proba = model.predict_proba(test[SIGMA_FEATURES])[:, 1]
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "features": SIGMA_FEATURES,
            "trained_at": datetime.now(UTC).isoformat(),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "status": "STAGING_ONLY_NOT_LIVE",
        },
        MODEL_DIR / "sigma_selector.pkl",
    )

    return {
        "status": "PASS",
        "rows": int(len(df)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "test_races": int(test["race_id"].nunique()),
        "baseline_auc": _safe_auc(test["target"].to_numpy(), baseline),
        "selector_auc": _safe_auc(test["target"].to_numpy(), proba),
        "baseline_logloss": float(log_loss(test["target"], baseline)),
        "selector_logloss": float(log_loss(test["target"], np.clip(proba, 1e-6, 1 - 1e-6))),
        "baseline_top1": _top1_metrics(test, baseline),
        "selector_top1": _top1_metrics(test, proba),
        "acceptance_bands": _acceptance_bands(test, proba),
        "staging_model": str(MODEL_DIR / "sigma_selector.pkl"),
        "note": "Small post-score selector test from sigma/innovation protocol rows only.",
    }


def _prepare_historical_frame() -> pd.DataFrame:
    rp = pd.read_parquet(RP_PATH)
    pp = pd.read_parquet(PASSPORT_PATH)
    rp = rp.copy()
    pp = pp.copy()
    rp["target"] = pd.to_numeric(rp["target"], errors="coerce")
    rp = rp[rp["target"].isin([0, 1])]
    rp = rp[rp["date_parsed"].notna()]
    rp["date_parsed"] = pd.to_datetime(rp["date_parsed"], errors="coerce")
    rp = rp[rp["date_parsed"].notna()]

    # Keep the test aligned with VÉLØ doctrine: no obvious foreign cards.
    rp["_course_norm"] = rp["course"].map(norm_course)
    rp = rp[~rp["_course_norm"].isin(SUPPORTED_EXCLUDES)]
    rp = rp[~rp["course"].astype(str).str.contains(r"\([A-Z]{2,3}\)", regex=True, na=False)]

    pp = pp.drop_duplicates(["race_id", "horse"])
    df = rp.merge(pp, on=["race_id", "horse"], how="left", validate="m:1")

    feature_cols = sorted(
        set(
            RP_SAFE_FEATURES
            + RP_CORE_NO_RPR_NO_MARKET_FEATURES
            + RP_DOCTRINE_NO_RATINGS_NO_MARKET_FEATURES
            + PASSPORT_FEATURES
        )
    )
    for col in feature_cols:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _train_eval_feature_set(
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
    label: str,
) -> dict[str, Any]:
    model = _make_hgb()
    model.fit(train[features], train["target"])
    proba = model.predict_proba(test[features])[:, 1]
    importance_sample = test
    if len(importance_sample) > 8000:
        importance_sample = importance_sample.sample(n=8000, random_state=42)
    perm = permutation_importance(
        model,
        importance_sample[features],
        importance_sample["target"],
        n_repeats=3,
        random_state=42,
        scoring="neg_log_loss",
    )
    importances = sorted(
        [
            {
                "feature": feature,
                "importance": round(float(score), 6),
            }
            for feature, score in zip(features, perm.importances_mean, strict=False)
        ],
        key=lambda row: row["importance"],
        reverse=True,
    )
    return {
        "label": label,
        "features": len(features),
        "auc": _safe_auc(test["target"].to_numpy(), proba),
        "logloss": float(log_loss(test["target"], np.clip(proba, 1e-6, 1 - 1e-6))),
        **_top1_metrics(test, proba),
        "top_importance": importances[:12],
    }


def run_passport_vs_rp_test() -> dict[str, Any]:
    if not RP_PATH.exists() or not PASSPORT_PATH.exists():
        return {
            "status": "MISSING",
            "rp_path": str(RP_PATH),
            "passport_path": str(PASSPORT_PATH),
        }
    df = _prepare_historical_frame()
    train = df[df["date_parsed"].dt.year <= 2024].copy()
    test = df[df["date_parsed"].dt.year == 2025].copy()

    # Keep race integrity: only evaluate races with at least one target winner.
    train = train[train.groupby("race_id")["target"].transform("sum") > 0]
    test = test[test.groupby("race_id")["target"].transform("sum") > 0]

    passport_coverage = {
        col: round(float(test[col].notna().mean()), 4) for col in PASSPORT_FEATURES
    }

    results = [
        _train_eval_feature_set(train, test, RP_SAFE_FEATURES, "RP_SAFE_FILES_ONLY"),
        _train_eval_feature_set(train, test, RP_CORE_NO_RPR_NO_MARKET_FEATURES, "RP_CORE_NO_RPR_NO_MARKET"),
        _train_eval_feature_set(
            train,
            test,
            RP_DOCTRINE_NO_RATINGS_NO_MARKET_FEATURES,
            "RP_DOCTRINE_NO_RATINGS_NO_MARKET",
        ),
        _train_eval_feature_set(train, test, PASSPORT_FEATURES, "PASSPORT_ONLY"),
        _train_eval_feature_set(
            train,
            test,
            RP_CORE_NO_RPR_NO_MARKET_FEATURES + PASSPORT_FEATURES,
            "RP_CORE_PLUS_PASSPORT",
        ),
        _train_eval_feature_set(
            train,
            test,
            RP_DOCTRINE_NO_RATINGS_NO_MARKET_FEATURES + PASSPORT_FEATURES,
            "RP_DOCTRINE_PLUS_PASSPORT",
        ),
    ]

    best = max(results, key=lambda r: r["top1"])
    rp_base = next(r for r in results if r["label"] == "RP_SAFE_FILES_ONLY")
    rp_core = next(r for r in results if r["label"] == "RP_CORE_NO_RPR_NO_MARKET")
    rp_doctrine = next(r for r in results if r["label"] == "RP_DOCTRINE_NO_RATINGS_NO_MARKET")
    pp_only = next(r for r in results if r["label"] == "PASSPORT_ONLY")
    core_combined = next(r for r in results if r["label"] == "RP_CORE_PLUS_PASSPORT")
    doctrine_combined = next(r for r in results if r["label"] == "RP_DOCTRINE_PLUS_PASSPORT")
    return {
        "status": "PASS",
        "rows_after_filter": int(len(df)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_races": int(train["race_id"].nunique()),
        "test_races": int(test["race_id"].nunique()),
        "passport_coverage_2025": passport_coverage,
        "results": results,
        "best_by_top1": best["label"],
        "feature_contract": {
            "rp_safe_files_only": RP_SAFE_FEATURES,
            "rp_core_no_rpr_no_market": RP_CORE_NO_RPR_NO_MARKET_FEATURES,
            "rp_doctrine_no_ratings_no_market": RP_DOCTRINE_NO_RATINGS_NO_MARKET_FEATURES,
            "passport_features": PASSPORT_FEATURES,
            "banned_rpr_market_features": BANNED_RPR_MARKET_FEATURES,
            "banned_features_used": sorted(
                set(BANNED_RPR_MARKET_FEATURES)
                & set(
                    RP_CORE_NO_RPR_NO_MARKET_FEATURES
                    + RP_DOCTRINE_NO_RATINGS_NO_MARKET_FEATURES
                    + PASSPORT_FEATURES
                )
            ),
        },
        "passport_only_gap_vs_rp_core_top1": round(pp_only["top1"] - rp_core["top1"], 4),
        "passport_only_gap_vs_rp_core_auc": round((pp_only["auc"] or 0) - (rp_core["auc"] or 0), 4),
        "core_plus_passport_top1_lift_vs_core": round(core_combined["top1"] - rp_core["top1"], 4),
        "core_plus_passport_auc_lift_vs_core": round((core_combined["auc"] or 0) - (rp_core["auc"] or 0), 4),
        "doctrine_plus_passport_top1_lift_vs_doctrine": round(doctrine_combined["top1"] - rp_doctrine["top1"], 4),
        "doctrine_plus_passport_auc_lift_vs_doctrine": round(
            (doctrine_combined["auc"] or 0) - (rp_doctrine["auc"] or 0),
            4,
        ),
        "combined_top1_lift_vs_rp": round(core_combined["top1"] - rp_base["top1"], 4),
        "combined_auc_lift_vs_rp": round((core_combined["auc"] or 0) - (rp_base["auc"] or 0), 4),
    }


def write_report(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "passport_sigma_training_test_latest.json"
    md_path = REPORT_DIR / "passport_sigma_training_test_latest.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    sigma = payload["sigma_selector"]
    passport = payload["passport_vs_rp"]
    lines = [
        "# Passport + Sigma Training Test",
        f"Generated: {payload['generated_at']}",
        "",
        "## Sigma Selector",
        f"- Status: {sigma.get('status')}",
        f"- Rows: {sigma.get('rows')}",
        f"- Test races: {sigma.get('test_races')}",
        f"- Baseline AUC: {sigma.get('baseline_auc')}",
        f"- Selector AUC: {sigma.get('selector_auc')}",
        f"- Baseline top-1: {(sigma.get('baseline_top1') or {}).get('top1')}",
        f"- Selector top-1: {(sigma.get('selector_top1') or {}).get('top1')}",
        f"- Staging model: {sigma.get('staging_model')}",
        "",
        "### Acceptance Bands",
        "| Ranker | Accept top % | n | SR | ROI/pt | P&L | Avg SP |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sigma.get("acceptance_bands", []):
        lines.append(
            f"| {r['ranker']} | {r['accept_top_pct']} | {r['n']} | {r['sr']:.4f} | {r['roi']:.4f} | {r['pl']:.4f} | {r['avg_sp']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Passport vs RP Files",
            f"- Status: {passport.get('status')}",
            f"- Train rows: {passport.get('train_rows')}",
            f"- Test rows: {passport.get('test_rows')}",
            f"- Test races: {passport.get('test_races')}",
            "",
            "| Model | Features | AUC | LogLoss | Top-1 | MRR |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for r in passport.get("results", []):
        lines.append(
            f"| {r['label']} | {r['features']} | {r['auc']:.4f} | {r['logloss']:.4f} | {r['top1']:.4f} | {r['mrr']:.4f} |"
        )
    lines.extend(
        [
            "",
            f"- Best by top-1: {passport.get('best_by_top1')}",
            f"- Passport-only gap vs RP core top-1: {passport.get('passport_only_gap_vs_rp_core_top1')}",
            f"- Passport-only gap vs RP core AUC: {passport.get('passport_only_gap_vs_rp_core_auc')}",
            f"- RP core + passport top-1 lift vs RP core: {passport.get('core_plus_passport_top1_lift_vs_core')}",
            f"- RP core + passport AUC lift vs RP core: {passport.get('core_plus_passport_auc_lift_vs_core')}",
            f"- Doctrine + passport top-1 lift vs doctrine: {passport.get('doctrine_plus_passport_top1_lift_vs_doctrine')}",
            f"- Doctrine + passport AUC lift vs doctrine: {passport.get('doctrine_plus_passport_auc_lift_vs_doctrine')}",
            f"- Banned RPR/market features used: {(passport.get('feature_contract') or {}).get('banned_features_used')}",
            "",
            "### Top Feature Importance",
        ]
    )
    for r in passport.get("results", []):
        lines.append(f"#### {r['label']}")
        for item in r.get("top_importance", [])[:8]:
            lines.append(f"- {item['feature']}: {item['importance']}")
    lines.extend(
        [
            "",
            "## Verdict",
            payload["verdict"],
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    sigma = run_sigma_selector_test()
    passport = run_passport_vs_rp_test()
    combined_lift = passport.get("core_plus_passport_top1_lift_vs_core", 0) if passport.get("status") == "PASS" else 0
    sigma_has_signal = False
    if sigma.get("status") == "PASS":
        auc_lift = (sigma.get("selector_auc") or 0) - (sigma.get("baseline_auc") or 0)
        bands = sigma.get("acceptance_bands") or []
        selector_top20 = next(
            (b for b in bands if b.get("ranker") == "sigma_selector" and b.get("accept_top_pct") == 20),
            {},
        )
        baseline_top20 = next(
            (b for b in bands if b.get("ranker") == "baseline_model_probability" and b.get("accept_top_pct") == 20),
            {},
        )
        sigma_has_signal = (
            auc_lift > 0.05
            and selector_top20.get("roi", -1) > baseline_top20.get("roi", 1)
            and selector_top20.get("sr", 0) > baseline_top20.get("sr", 1)
        )

    verdict = (
        "PASSPORT_HELPFUL_SHADOW_ONLY"
        if combined_lift > 0
        else "PASSPORT_NOT_PROVEN_FOR_PRIMARY"
    )
    if sigma_has_signal:
        verdict += " | SIGMA_SELECTOR_HAS_SIGNAL"
    else:
        verdict += " | SIGMA_SELECTOR_NOT_PROVEN"

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "evidence_only_no_live_changes",
        "sigma_selector": sigma,
        "passport_vs_rp": passport,
        "verdict": verdict,
    }
    write_report(payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
