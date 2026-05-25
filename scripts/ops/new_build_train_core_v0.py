#!/usr/bin/env python3
"""
new_build_train_core_v0.py
Train Core V0 morning model from the safe historical dataset.
No RPR. No final SP. No post-race leakage. Archive only.
"""
import json
import os
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, brier_score_loss

TRAIN_DIR = ROOT / "data" / "new_build" / "training"
MODEL_DIR = ROOT / "data" / "new_build" / "models" / "core_v0"
RPT_DIR = ROOT / "data" / "new_build" / "reports"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
VELO_SCORING_ALLOWED = False

BANNED_IN_FEATURES = {
    "rpr_num", "rpr_vs_field", "rpr", "ts_num", "ts",
    "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
    "odds_resilience_score", "odds_contraction_score", "decoy_support_flag",
    "runs_since_mkt_support", "pos", "pos_num", "ovr_btn", "btn",
    "comment", "time", "target",
}

# Identity cols not used as features
IDENTITY_COLS = {"race_id", "date", "course", "horse", "jockey", "trainer"}
TARGET_COLS = {"won", "framed"}


def _race_level_metrics(df, prob_col, pos_col="pos_num"):
    """Compute race-level SR (top-pick wins) and frame rate (top-3 contains winner)."""
    sr_hits = 0
    frame_hits = 0
    races = 0
    for _, grp in df.groupby("race_id"):
        if len(grp) < 2:
            continue
        races += 1
        best_idx = grp[prob_col].idxmax()
        if grp.loc[best_idx, "won"] == 1:
            sr_hits += 1
        top3 = grp.nlargest(3, prob_col)
        if top3["won"].sum() >= 1:
            frame_hits += 1
    sr = sr_hits / races if races else 0
    fr = frame_hits / races if races else 0
    return round(sr, 4), round(fr, 4), races


def _or_rank_baseline(df):
    """OR-rank baseline: top-pick by or_num (highest OR = favourite)."""
    sr_hits = 0
    frame_hits = 0
    races = 0
    for _, grp in df.groupby("race_id"):
        if len(grp) < 2 or "or_vs_field" not in grp.columns:
            continue
        races += 1
        best_idx = grp["or_vs_field"].idxmax()
        if grp.loc[best_idx, "won"] == 1:
            sr_hits += 1
        top3 = grp.nlargest(3, "or_vs_field")
        if top3["won"].sum() >= 1:
            frame_hits += 1
    sr = sr_hits / races if races else 0
    fr = frame_hits / races if races else 0
    return round(sr, 4), round(fr, 4), races


def run():
    print("Loading Core V0 training dataset ...")
    train = pd.read_parquet(TRAIN_DIR / "core_v0_train.parquet")
    val   = pd.read_parquet(TRAIN_DIR / "core_v0_val.parquet")
    test  = pd.read_parquet(TRAIN_DIR / "core_v0_test.parquet")

    print(f"  Train: {len(train):,} rows  Val: {len(val):,} rows  Test: {len(test):,} rows")

    # Identify feature columns
    non_feature = IDENTITY_COLS | TARGET_COLS | {"pos_num"}
    feature_cols = [c for c in train.columns if c not in non_feature]

    # Anti-leakage assertions
    for banned in BANNED_IN_FEATURES:
        if banned in feature_cols:
            raise AssertionError(f"LEAKAGE ABORT: '{banned}' found in feature columns")
    rpr_check = [c for c in feature_cols if "rpr" in c.lower()]
    if rpr_check:
        raise AssertionError(f"RPR VIOLATION ABORT: {rpr_check} in feature columns")
    sp_check = [c for c in feature_cols if c in {"sp_dec", "log_sp", "is_fav", "sp_rank", "implied_prob"}]
    if sp_check:
        raise AssertionError(f"SP LEAKAGE ABORT: {sp_check} in feature columns")
    print(f"  Leakage check: PASS ({len(feature_cols)} features, 0 RPR, 0 SP)")

    # Drop constant columns (e.g. type="Flat" after flat-only filter)
    non_const = [c for c in feature_cols if train[c].nunique() > 1]
    dropped_const = [c for c in feature_cols if c not in non_const]
    if dropped_const:
        print(f"  Dropped constant cols: {dropped_const}")
    feature_cols = non_const

    # Encode object columns with pd.Categorical codes
    obj_cols = [c for c in feature_cols if train[c].dtype == object]
    for c in obj_cols:
        all_vals = pd.Categorical(
            pd.concat([train[c], val[c], test[c]], ignore_index=True)
        ).categories
        train[c] = pd.Categorical(train[c], categories=all_vals).codes
        val[c]   = pd.Categorical(val[c],   categories=all_vals).codes
        test[c]  = pd.Categorical(test[c],  categories=all_vals).codes
    if obj_cols:
        print(f"  Encoded object cols: {obj_cols}")

    X_train = train[feature_cols].copy()
    X_val   = val[feature_cols].copy()
    X_test  = test[feature_cols].copy()

    medians = X_train.median(numeric_only=True)
    X_train = X_train.fillna(medians)
    X_val   = X_val.fillna(medians)
    X_test  = X_test.fillna(medians)

    y_train = train["won"]
    y_val   = val["won"]

    # Try LightGBM first, fall back to sklearn GBM
    try:
        import lightgbm as lgb
        print("  Training with LightGBM ...")
        model = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            num_leaves=63, min_child_samples=50,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1, n_jobs=4,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)],
                  callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(0)])
        model_type = "LightGBM"
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        print("  LightGBM not found, training with sklearn GradientBoosting ...")
        model = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            min_samples_leaf=50, subsample=0.8, random_state=42,
        )
        model.fit(X_train, y_train)
        model_type = "GradientBoostingClassifier"

    # Val metrics
    val_probs = model.predict_proba(X_val)[:, 1]
    val_auc   = round(float(roc_auc_score(y_val, val_probs)), 4)
    val_brier = round(float(brier_score_loss(y_val, val_probs)), 4)

    val["_prob"] = val_probs
    val_sr, val_fr, val_races = _race_level_metrics(val, "_prob")
    or_sr, or_fr, _ = _or_rank_baseline(val)

    print(f"\n  Val AUC:   {val_auc}  (random~0.50, good>0.60)")
    print(f"  Val Brier: {val_brier}")
    print(f"  Val SR:    {val_sr:.1%}  (OR-rank baseline: {or_sr:.1%})")
    print(f"  Val Frame: {val_fr:.1%}  (OR-rank baseline: {or_fr:.1%})")
    print(f"  Val Races: {val_races:,}")

    # Save model
    model_path = MODEL_DIR / "core_v0_model.pkl"
    with model_path.open("wb") as f:
        pickle.dump({"model": model, "feature_cols": feature_cols, "medians": medians.to_dict()}, f)
    print(f"\n  Model saved: {model_path}")

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": VELO_SCORING_ALLOWED,
        "rpr_violation": False,
        "sp_in_features": False,
        "leakage_check": "PASS",
        "model_type": model_type,
        "feature_cols": feature_cols,
        "banned_features_confirmed_absent": list(BANNED_IN_FEATURES),
        "train_rows": len(train),
        "val_rows": len(val),
        "test_rows": len(test),
        "val_metrics": {
            "auc": val_auc,
            "brier": val_brier,
            "sr": val_sr,
            "frame_rate": val_fr,
            "races": val_races,
        },
        "or_rank_baseline": {
            "sr": or_sr,
            "frame_rate": or_fr,
        },
        "sr_lift_vs_baseline": round(val_sr - or_sr, 4),
        "frame_lift_vs_baseline": round(val_fr - or_fr, 4),
    }

    (MODEL_DIR / "core_v0_metadata.json").write_text(json.dumps(metadata, indent=2))

    # MD report
    lines = [
        "# Core V0 Training Report",
        f"Generated: {metadata['generated_at']}",
        "",
        "## Safety",
        f"- RPR violation: **{metadata['rpr_violation']}** (must be False)",
        f"- SP in features: **{metadata['sp_in_features']}** (must be False for morning model)",
        f"- Leakage check: **{metadata['leakage_check']}**",
        f"- `velo_scoring_allowed`: **{VELO_SCORING_ALLOWED}**",
        "",
        "## Model",
        f"- Type: {model_type}",
        f"- Features: {len(feature_cols)}",
        "",
        "## Validation Metrics",
        "| Metric | Core V0 | OR-Rank Baseline | Lift |",
        "|---|---|---|---|",
        f"| AUC | {val_auc} | — | — |",
        f"| Brier | {val_brier} | — | — |",
        f"| SR (top-1 win rate) | {val_sr:.1%} | {or_sr:.1%} | {val_sr - or_sr:+.1%} |",
        f"| Frame rate (top-3 contains winner) | {val_fr:.1%} | {or_fr:.1%} | {val_fr - or_fr:+.1%} |",
        f"| Races evaluated | {val_races:,} | | |",
        "",
        "## Features",
    ]
    for fc in feature_cols:
        lines.append(f"- `{fc}`")

    (RPT_DIR / "core_v0_training_latest.md").write_text("\n".join(lines))
    (RPT_DIR / "core_v0_training_latest.json").write_text(json.dumps(metadata, indent=2))
    print("  Reports written.")
    return metadata


if __name__ == "__main__":
    run()
