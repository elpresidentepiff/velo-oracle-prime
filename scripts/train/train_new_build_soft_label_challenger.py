#!/usr/bin/env python3
"""
New Build — Soft Label Challenger
==================================
Same 45-feature set as the champion (Challenger_V1 / core_v0_or_passport_intent).
Fixes the SR=16% gap by replacing the binary win label with a soft target:
  win=1.0 | placed (pos 2-3)=0.35 | else=0.0

LightGBM cross_entropy accepts soft labels directly, so the model learns to
distinguish winners AND placed horses, then at ranking time the top-1 pick
is evaluated against the hard win label.

Saves to: data/new_build/models/soft_label_challenger/
Does NOT promote, does NOT touch live scoring.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
RP_PATH = ROOT / "data" / "raceform_v17_features.parquet"
PASSPORT_PATH = ROOT / "data" / "new_build" / "training" / "passport_features.parquet"
OUTPUT_DIR = ROOT / "data" / "new_build" / "models" / "soft_label_challenger"

PLACE_WEIGHT = 0.35  # soft label for pos=2 or pos=3

CHAMPION_FEATURES = [
    "dist_f", "going_code", "is_aw", "field_size", "draw_num", "draw_pct",
    "age_num", "wgt_lbs", "or_vs_field", "release_window_score",
    "going_fit_score", "distance_fit_score", "quiet_run_score",
    "trainer_timing_score", "jockey_switch_intent", "setup_run_flag",
    "cash_run_flag", "official_rating", "is_rated",
    "pp_career_runs", "pp_win_rate", "pp_place_rate", "pp_days_since_last",
    "pp_layoff", "pp_avg_sp_last5", "pp_jockey_continuity", "pp_course_seen",
    "pp_or_change_3", "pp_class_moved_up", "pp_class_moved_down",
    "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "odds_resilience_score",
    "intent_trip_match", "intent_course_win_history", "intent_going_match",
    "intent_class_drop_vs_best", "intent_run_after_break", "intent_sp_shortening",
    "intent_wins_last10", "intent_top3_last6",
]

BANNED = {"sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
          "rpr_num", "rpr_vs_field", "ts_num"}

SUPPORTED_EXCLUDES = {
    "chantilly", "dusseldorf", "ellerslie", "flemington", "greyville",
    "happyvalley", "kenilworth", "randwick", "sansiro", "saratoga",
    "shatin", "tokyo", "turffontein", "vaal",
}


def norm_course(v):
    s = str(v or "").lower().replace("(aw)", "").replace(" aw", "")
    return re.sub(r"[^a-z]", "", s)


def top1_sr(df: pd.DataFrame, prob_col: str) -> tuple[float, int]:
    idx = df.groupby("race_id")[prob_col].idxmax()
    picks = df.loc[idx]
    races = int(picks["race_id"].nunique())
    sr = float(picks["target"].mean()) if len(picks) else 0.0
    return round(sr, 4), races


def load_data() -> pd.DataFrame:
    rp = pd.read_parquet(RP_PATH)
    pp = pd.read_parquet(PASSPORT_PATH)

    rp["date_parsed"] = pd.to_datetime(rp["date_parsed"], errors="coerce")
    rp = rp[rp["date_parsed"].notna()].copy()
    rp["_cn"] = rp["course"].map(norm_course)
    rp = rp[~rp["_cn"].isin(SUPPORTED_EXCLUDES)]
    rp = rp[~rp["course"].astype(str).str.contains(r"\([A-Z]{2,3}\)", regex=True, na=False)]

    # Numeric pos for soft label
    rp["pos_num"] = pd.to_numeric(rp["pos"].astype(str).str.strip(), errors="coerce")
    rp = rp[rp["pos_num"].notna()].copy()

    # Hard win label (1 if pos=1)
    rp["target"] = (rp["pos_num"] == 1).astype(int)

    # Soft label: 1.0 win, 0.35 placed (pos 2-3), 0 else
    rp["soft_target"] = 0.0
    rp.loc[rp["pos_num"] == 1, "soft_target"] = 1.0
    rp.loc[rp["pos_num"].isin([2, 3]), "soft_target"] = PLACE_WEIGHT

    pp = pp.drop_duplicates(["race_id", "horse"])
    df = rp.merge(pp, on=["race_id", "horse"], how="left", validate="m:1")

    for col in CHAMPION_FEATURES:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Check for leakage
    leaked = [f for f in CHAMPION_FEATURES if f in BANNED]
    assert not leaked, f"LEAKAGE: {leaked}"

    return df


def main():
    print("=" * 65)
    print("New Build — Soft Label Challenger")
    print(f"  Features : {len(CHAMPION_FEATURES)}")
    print(f"  Place weight : pos 2-3 → {PLACE_WEIGHT}")
    print("=" * 65)

    df = load_data()
    train_df = df[df["date_parsed"].dt.year <= 2024].copy()
    test_df  = df[df["date_parsed"].dt.year == 2025].copy()

    # Keep only races that have a winner
    train_df = train_df[train_df.groupby("race_id")["target"].transform("sum") > 0]
    test_df  = test_df[test_df.groupby("race_id")["target"].transform("sum") > 0]

    print(f"\nTrain: {len(train_df):,} rows  ({train_df['race_id'].nunique():,} races)")
    print(f"Test : {len(test_df):,} rows  ({test_df['race_id'].nunique():,} races)")
    print(f"Win rate train: {train_df['target'].mean():.4f}  test: {test_df['target'].mean():.4f}")
    print(f"Soft label train mean: {train_df['soft_target'].mean():.4f}")

    X_tr = train_df[CHAMPION_FEATURES].fillna(-1).values
    y_soft = train_df["soft_target"].values
    X_te = test_df[CHAMPION_FEATURES].fillna(-1).values
    y_te = test_df["target"].values

    params = {
        "objective": "cross_entropy",
        "learning_rate": 0.04,
        "max_depth": 5,
        "min_data_in_leaf": 50,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "seed": 42,
        "verbose": -1,
        "num_threads": -1,
    }

    print("\nTraining LightGBM with soft labels (native API) ...")
    dtrain = lgb.Dataset(X_tr, label=y_soft)
    booster = lgb.train(params, dtrain, num_boost_round=500,
                        valid_sets=[dtrain], callbacks=[lgb.log_evaluation(100)])

    # cross_entropy objective outputs log-odds; convert to probability
    raw = booster.predict(X_te)
    proba = 1.0 / (1.0 + np.exp(-raw)) if raw.min() < 0 else raw

    auc = roc_auc_score(y_te, proba)
    ll  = log_loss(y_te, np.clip(proba, 1e-6, 1 - 1e-6))
    test_df = test_df.copy()
    test_df["_p"] = proba
    sr, n_races = top1_sr(test_df, "_p")

    print(f"\n{'=' * 65}")
    print(f"  AUC     : {auc:.4f}")
    print(f"  LogLoss : {ll:.4f}")
    print(f"  Top-1 SR: {sr*100:.1f}%  ({n_races:,} races)")
    print(f"{'=' * 65}")

    # Feature importances
    imp = sorted(
        zip(CHAMPION_FEATURES, booster.feature_importance("gain")),
        key=lambda x: -x[1]
    )
    print("\nTop 15 features by importance:")
    for feat, val in imp[:15]:
        print(f"  {feat:<35} {val:.0f}")

    # Medians for live scoring fill
    medians = {c: float(df[c].median()) if c in df.columns else 0.0 for c in CHAMPION_FEATURES}

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    import pickle
    payload = {
        "model": booster,   # native lgb.Booster — call booster.predict(X) for scores
        "feature_cols": CHAMPION_FEATURES,
        "medians": medians,
        "model_type": "lgb_native_booster",
        "predict_note": "proba = 1/(1+exp(-booster.predict(X))) for cross_entropy objective",
    }
    with open(OUTPUT_DIR / "champion_model.pkl", "wb") as fh:
        pickle.dump(payload, fh)

    metadata = {
        "generated_at": datetime.now(UTC).isoformat(),
        "label": "soft_label_challenger",
        "version": "new_build_soft_label_v1",
        "place_weight": PLACE_WEIGHT,
        "n_features": len(CHAMPION_FEATURES),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "test_races": n_races,
        "metrics_2025_holdout": {
            "auc": round(auc, 4),
            "logloss": round(ll, 4),
            "top1_sr": sr,
            "races": n_races,
        },
        "top_15_features": [{"feature": f, "importance": int(v)} for f, v in imp[:15]],
        "champion_baseline_sr": 0.2502,
        "champion_baseline_auc": 0.6969,
        "live_scoring_changed": False,
        "paper_only": True,
    }
    (OUTPUT_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))

    print(f"\nSaved: {OUTPUT_DIR}/champion_model.pkl")
    print(f"Saved: {OUTPUT_DIR}/metadata.json")
    print(f"\nChampion baseline: AUC=0.6969  SR=25.0%")
    print(f"Soft label result: AUC={auc:.4f}  SR={sr*100:.1f}%")
    delta_sr = sr - 0.2502
    delta_auc = auc - 0.6969
    print(f"Delta            : AUC {delta_auc:+.4f}  SR {delta_sr*100:+.1f}ppts")
    if sr >= 0.2502 and auc >= 0.6969:
        verdict = "PROMOTE_CANDIDATE — beats champion on both AUC and SR"
    elif sr >= 0.2502:
        verdict = "SR_WINS — SR improvement, AUC weaker"
    elif auc >= 0.6969:
        verdict = "AUC_WINS — AUC improvement, SR weaker"
    else:
        verdict = "NO_LIFT — soft label did not improve champion"
    print(f"Verdict: {verdict}")
    metadata["verdict"] = verdict
    (OUTPUT_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))

    print(f"\n{'=' * 65}\nDONE\n{'=' * 65}")


if __name__ == "__main__":
    main()
