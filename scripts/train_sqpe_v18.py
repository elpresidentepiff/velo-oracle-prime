#!/usr/bin/env python3
"""
VÉLØ Oracle — SQPE v18 Trainer
================================
v17 base (37 features) + days_since_run + class_delta.

New features:
  Temporal : days_since_run  — days between consecutive runs per horse (1–365)
  Class    : class_delta     — class_num change from previous run, clipped ±6

Both are per-horse chronological lookbacks with no lookahead.

Loads from the pre-built raceform_v17_features.parquet (1.7M rows, all v17
features already computed). Only adds the two new features then trains.

Usage:
    python scripts/train_sqpe_v18.py
    python scripts/train_sqpe_v18.py --sample 200000   # quick dev run
    python scripts/train_sqpe_v18.py --output models/sqpe_v18
"""

import json
import pickle
import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss

# ─── Feature schema ───────────────────────────────────────────────────────────
V17_FEATURES = [
    # v16 base
    "sp_dec", "log_sp", "implied_prob",
    "dist_f", "going_code", "is_aw",
    "class_num", "wgt_lbs",
    "or_num", "rpr_num", "ts_num",
    "or_vs_field", "rpr_vs_field",
    "field_size", "draw_num", "draw_pct",
    "age_num", "sp_rank", "is_fav",
    # v17 doctrine
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

V18_NEW_FEATURES = [
    "days_since_run",   # days between consecutive runs per horse
    "class_delta",      # class_num change from previous run (negative = class drop)
]

ALL_FEATURES = V17_FEATURES + V18_NEW_FEATURES  # 39 total


# ─── Feature engineering ──────────────────────────────────────────────────────
def add_v18_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add days_since_run and class_delta using per-horse chronological lookback."""
    df = df.sort_values(["horse", "date_parsed"]).reset_index(drop=True)

    prev_date = df.groupby("horse")["date_parsed"].shift(1)
    prev_class = df.groupby("horse")["class_num"].shift(1)

    raw_days = (df["date_parsed"] - prev_date).dt.days
    raw_delta = df["class_num"] - prev_class

    df["days_since_run"] = raw_days.clip(1, 365).fillna(14.0).astype(float)
    df["class_delta"] = raw_delta.clip(-6, 6).fillna(0.0).astype(float)

    return df


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Train SQPE v18")
    parser.add_argument(
        "--raceform",
        default="data/raceform_v17_features.parquet",
        help="Pre-built v17 features parquet (1.7M rows)",
    )
    parser.add_argument("--output", default="models/sqpe_v18")
    parser.add_argument("--sample", type=int, default=None,
                        help="Sample N rows for quick dev run")
    args = parser.parse_args()

    raceform_path = Path(args.raceform)
    if not raceform_path.exists():
        print(f"ERROR: {raceform_path} not found")
        return

    # ── Load ──────────────────────────────────────────────────────────────────
    print(f"\nLoading {raceform_path} ...")
    df = pd.read_parquet(raceform_path)
    print(f"  {len(df):,} rows loaded")

    # Ensure date_parsed is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["date_parsed"]):
        df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")

    # Remove non-starters / void positions
    numeric_pos = pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce")
    df = df[numeric_pos.notna()].copy()
    print(f"  {len(df):,} rows after removing non-starters")

    if args.sample:
        # Sample preserving temporal order so train/test split stays valid
        df = df.sort_values("date_parsed").head(
            min(args.sample, len(df))
        ).copy()
        print(f"  Sampled to {len(df):,} rows (first N chronologically)")

    # ── Add v18 features ──────────────────────────────────────────────────────
    print(f"\nComputing v18 features for {df['horse'].nunique():,} unique horses ...")
    df = add_v18_features(df)
    print(f"  days_since_run: mean={df['days_since_run'].mean():.1f}  "
          f"std={df['days_since_run'].std():.1f}")
    print(f"  class_delta:    mean={df['class_delta'].mean():.2f}  "
          f"std={df['class_delta'].std():.2f}")

    # ── Temporal train/test split ──────────────────────────────────────────────
    df = df.sort_values("date_parsed").reset_index(drop=True)
    train_df = df[df["date_parsed"].dt.year < 2024]
    test_df  = df[df["date_parsed"].dt.year >= 2024]
    print(f"\nTrain: {len(train_df):,}  Test: {len(test_df):,}")

    X_tr = train_df[ALL_FEATURES].fillna(0)
    X_te = test_df[ALL_FEATURES].fillna(0)
    y_tr = train_df["target"]
    y_te = test_df["target"]

    # v17 baseline for fair comparison
    X_tr_v17 = train_df[V17_FEATURES].fillna(0)
    X_te_v17 = test_df[V17_FEATURES].fillna(0)

    print(f"Win rate  train: {y_tr.mean():.4f}  test: {y_te.mean():.4f}")
    print(f"Features: v17={len(V17_FEATURES)}  v18={len(ALL_FEATURES)}  "
          f"(+{len(V18_NEW_FEATURES)} new)")

    # ── Train v18 ─────────────────────────────────────────────────────────────
    print("\nTraining SQPE v18 (GBM + isotonic calibration) ...")
    gbm_params = dict(
        n_estimators=500, learning_rate=0.04, max_depth=5,
        min_samples_leaf=50, subsample=0.8, max_features="sqrt",
        random_state=42, verbose=1,
    )
    model_v18 = CalibratedClassifierCV(
        GradientBoostingClassifier(**gbm_params),
        method="isotonic", cv=3,
    )
    model_v18.fit(X_tr, y_tr)

    # ── Train v17 baseline on same split ──────────────────────────────────────
    print("\nTraining v17 baseline on same split for fair comparison ...")
    model_v17 = CalibratedClassifierCV(
        GradientBoostingClassifier(**gbm_params),
        method="isotonic", cv=3,
    )
    model_v17.fit(X_tr_v17, y_tr)

    # ── Evaluate ──────────────────────────────────────────────────────────────
    prob_v18 = model_v18.predict_proba(X_te)[:, 1]
    prob_v17 = model_v17.predict_proba(X_te_v17)[:, 1]

    auc_v18 = roc_auc_score(y_te, prob_v18)
    auc_v17 = roc_auc_score(y_te, prob_v17)
    ll_v18  = log_loss(y_te, prob_v18)
    ll_v17  = log_loss(y_te, prob_v17)

    # Top-1 accuracy (winner ranked #1 in race)
    test_copy = test_df.copy()
    test_copy["pred_v18"] = prob_v18
    test_copy["pred_v17"] = prob_v17
    test_copy["rank_v18"] = test_copy.groupby("race_id")["pred_v18"].rank(
        ascending=False, method="min"
    )
    test_copy["rank_v17"] = test_copy.groupby("race_id")["pred_v17"].rank(
        ascending=False, method="min"
    )
    winners = test_copy[test_copy["target"] == 1]
    top1_v18 = (winners["rank_v18"] == 1).mean()
    top1_v17 = (winners["rank_v17"] == 1).mean()
    mrr_v18 = (1.0 / winners["rank_v18"]).mean()
    mrr_v17 = (1.0 / winners["rank_v17"]).mean()

    print(f"\n{'='*60}")
    print(f"  {'Metric':<20} {'v17':>10} {'v18':>10} {'Delta':>10}")
    print(f"  {'-'*50}")
    print(f"  {'AUC-ROC':<20} {auc_v17:>10.4f} {auc_v18:>10.4f} "
          f"{auc_v18-auc_v17:>+10.4f}")
    print(f"  {'Log Loss':<20} {ll_v17:>10.4f} {ll_v18:>10.4f} "
          f"{ll_v18-ll_v17:>+10.4f}")
    print(f"  {'Top-1 Acc':<20} {top1_v17*100:>9.1f}% {top1_v18*100:>9.1f}% "
          f"{(top1_v18-top1_v17)*100:>+9.1f}%")
    print(f"  {'MRR':<20} {mrr_v17:>10.4f} {mrr_v18:>10.4f} "
          f"{mrr_v18-mrr_v17:>+10.4f}")
    print(f"{'='*60}")

    verdict = "LIFT" if top1_v18 > top1_v17 else "NO LIFT"
    print(f"\nVerdict: {verdict}  (top-1 delta = {(top1_v18-top1_v17)*100:+.2f} ppts)")

    # ── Feature importance ────────────────────────────────────────────────────
    base = model_v18.calibrated_classifiers_[0].estimator
    importance = sorted(
        zip(ALL_FEATURES, base.feature_importances_), key=lambda x: -x[1]
    )
    print("\nTop 15 v18 features:")
    for feat, val in importance[:15]:
        marker = " *NEW*" if feat in V18_NEW_FEATURES else ""
        print(f"  {feat:<32} {val:.4f}{marker}")

    new_imp = {f: v for f, v in importance if f in V18_NEW_FEATURES}
    print(f"\nNew feature importances:")
    for feat, val in new_imp.items():
        rank = next(i+1 for i, (f, _) in enumerate(importance) if f == feat)
        print(f"  {feat:<32} {val:.4f}  (rank #{rank} of {len(ALL_FEATURES)})")

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = out_dir / "sqpe_v18.pkl"
    with open(model_path, "wb") as fh:
        pickle.dump(model_v18, fh)

    metadata = {
        "version": "v18.0",
        "model_type": "GradientBoostingClassifier + IsotonicCalibration",
        "trained_at": datetime.utcnow().isoformat(),
        "source": str(raceform_path),
        "n_features": len(ALL_FEATURES),
        "v17_features": V17_FEATURES,
        "v18_new_features": V18_NEW_FEATURES,
        "feature_names": ALL_FEATURES,
        "train_rows": int(len(X_tr)),
        "test_rows": int(len(X_te)),
        "auc_v18": round(float(auc_v18), 4),
        "auc_v17_baseline": round(float(auc_v17), 4),
        "auc_delta": round(float(auc_v18 - auc_v17), 4),
        "log_loss_v18": round(float(ll_v18), 4),
        "top1_v18": round(float(top1_v18), 4),
        "top1_v17_baseline": round(float(top1_v17), 4),
        "top1_delta": round(float(top1_v18 - top1_v17), 4),
        "mrr_v18": round(float(mrr_v18), 4),
        "mrr_v17_baseline": round(float(mrr_v17), 4),
        "verdict": verdict,
        "new_feature_importances": {f: round(v, 4) for f, v in new_imp.items()},
        "top_15_features": [{"feature": f, "importance": round(v, 4)}
                            for f, v in importance[:15]],
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    pd.DataFrame(importance, columns=["feature", "importance"]).to_csv(
        out_dir / "feature_importance.csv", index=False
    )

    print(f"\nSaved: {model_path}")
    print(f"       {out_dir / 'metadata.json'}")
    print(f"\n{'='*60}")
    print(f"SQPE v18 COMPLETE  AUC={auc_v18:.4f}  Top-1={top1_v18*100:.1f}%  "
          f"({verdict})")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
