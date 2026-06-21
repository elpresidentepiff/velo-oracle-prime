#!/usr/bin/env python3
"""Train New Build Doctrine + Passport challenger.

Shadow-only model:
  - Uses clean RP race-shape / Velo doctrine features.
  - Adds passport memory features.
  - Explicitly bans RPR, final SP, implied probability, favourite rank, TS, and
    market-move leakage.

This does not promote, route, stake, or change live scoring.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import log_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
RP_PATH = ROOT / "data" / "raceform_v17_features.parquet"
PASSPORT_PATH = ROOT / "data" / "new_build" / "training" / "passport_features.parquet"
MODEL_DIR = ROOT / "data" / "new_build" / "models" / "doctrine_plus_passport_shadow"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"

DOCTRINE_FEATURES = [
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

BANNED_FEATURES = [
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

SUPPORTED_EXCLUDES = {
    "chantilly",
    "dusseldorf",
    "ellerslie",
    "flemington",
    "greyville",
    "happyvalley",
    "kenilworth",
    "randwick",
    "sansiro",
    "saratoga",
    "shatin",
    "tokyo",
    "turffontein",
    "vaal",
}


def norm_course(value: Any) -> str:
    v = str(value or "").lower().replace("(aw)", "").replace(" aw", "")
    return re.sub(r"[^a-z]", "", v)


def make_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=180,
        learning_rate=0.045,
        max_leaf_nodes=31,
        l2_regularization=0.03,
        random_state=42,
    )


def top1_metrics(df: pd.DataFrame, proba: np.ndarray) -> dict[str, Any]:
    tmp = df[["race_id", "target"]].copy()
    tmp["_p"] = proba
    idx = tmp.groupby("race_id")["_p"].idxmax()
    picks = tmp.loc[idx]

    mrrs = []
    for _, g in tmp.sort_values("_p", ascending=False).groupby("race_id", sort=False):
        targets = g["target"].tolist()
        try:
            rank = targets.index(1) + 1
            mrrs.append(1.0 / rank)
        except ValueError:
            pass

    return {
        "races": int(tmp["race_id"].nunique()),
        "top1": round(float(picks["target"].mean()), 4) if len(picks) else 0.0,
        "mrr": round(float(np.mean(mrrs)), 4) if mrrs else 0.0,
    }


def load_frame() -> pd.DataFrame:
    if not RP_PATH.exists():
        raise FileNotFoundError(RP_PATH)
    if not PASSPORT_PATH.exists():
        raise FileNotFoundError(PASSPORT_PATH)

    rp = pd.read_parquet(RP_PATH)
    pp = pd.read_parquet(PASSPORT_PATH)

    rp = rp.copy()
    rp["target"] = pd.to_numeric(rp["target"], errors="coerce")
    rp = rp[rp["target"].isin([0, 1])]
    rp["date_parsed"] = pd.to_datetime(rp["date_parsed"], errors="coerce")
    rp = rp[rp["date_parsed"].notna()]
    rp["_course_norm"] = rp["course"].map(norm_course)
    rp = rp[~rp["_course_norm"].isin(SUPPORTED_EXCLUDES)]
    rp = rp[~rp["course"].astype(str).str.contains(r"\([A-Z]{2,3}\)", regex=True, na=False)]

    pp = pp.drop_duplicates(["race_id", "horse"])
    df = rp.merge(pp, on=["race_id", "horse"], how="left", validate="m:1")

    for col in DOCTRINE_FEATURES + PASSPORT_FEATURES:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def train() -> dict[str, Any]:
    features = DOCTRINE_FEATURES + PASSPORT_FEATURES
    banned_used = sorted(set(features) & set(BANNED_FEATURES))
    if banned_used:
        raise RuntimeError(f"Banned features used: {banned_used}")

    df = load_frame()
    train_df = df[df["date_parsed"].dt.year <= 2024].copy()
    test_df = df[df["date_parsed"].dt.year == 2025].copy()
    train_df = train_df[train_df.groupby("race_id")["target"].transform("sum") > 0]
    test_df = test_df[test_df.groupby("race_id")["target"].transform("sum") > 0]

    model = make_model()
    model.fit(train_df[features], train_df["target"])
    proba = model.predict_proba(test_df[features])[:, 1]

    importance_sample = test_df
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
            {"feature": f, "importance": round(float(v), 6)}
            for f, v in zip(features, perm.importances_mean, strict=False)
        ],
        key=lambda row: row["importance"],
        reverse=True,
    )

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "SHADOW_ONLY_NOT_LIVE",
        "model_label": "new_build_doctrine_plus_passport_shadow",
        "source": {
            "rp_features": str(RP_PATH),
            "passport_features": str(PASSPORT_PATH),
        },
        "feature_contract": {
            "doctrine_features": DOCTRINE_FEATURES,
            "passport_features": PASSPORT_FEATURES,
            "banned_features": BANNED_FEATURES,
            "banned_features_used": banned_used,
        },
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "train_races": int(train_df["race_id"].nunique()),
        "test_races": int(test_df["race_id"].nunique()),
        "metrics_2025_holdout": {
            "auc": round(float(roc_auc_score(test_df["target"], proba)), 4),
            "logloss": round(float(log_loss(test_df["target"], np.clip(proba, 1e-6, 1 - 1e-6))), 4),
            **top1_metrics(test_df, proba),
        },
        "top_importance": importances[:16],
        "live_scoring_changed": False,
        "execution_allowed": False,
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "features": features,
            "metadata": payload,
        },
        MODEL_DIR / "model.pkl",
    )
    (MODEL_DIR / "metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (REPORT_DIR / "doctrine_plus_passport_shadow_latest.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    print(json.dumps(train(), indent=2))


if __name__ == "__main__":
    main()
