#!/usr/bin/env python3
"""
VÉLØ — SQPE v17 Retrain
========================
Loads pre-computed v17 features from raceform_v17_features.parquet.
Temporal split: train <= 2024, test = 2025.
Saves to models/sqpe_v17_staging/ (NOT auto-promoted to production).

Usage:
    python scripts/ops/retrain_sqpe_v17.py
    python scripts/ops/retrain_sqpe_v17.py --sample 200000   # quick dev
    python scripts/ops/retrain_sqpe_v17.py --promote          # overwrite production
"""

import argparse
import json
import pickle
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]

FEATURES_PARQUET = ROOT / "data" / "raceform_v17_features.parquet"
PRODUCTION_MODEL = ROOT / "models" / "sqpe_v17" / "sqpe_v17.pkl"
STAGING_DIR = ROOT / "models" / "sqpe_v17_staging"

V17_FEATURES = [
    "sp_dec", "log_sp", "implied_prob",
    "dist_f", "going_code", "is_aw",
    "class_num", "wgt_lbs",
    "or_num", "rpr_num", "ts_num",
    "or_vs_field", "rpr_vs_field",
    "field_size", "draw_num", "draw_pct",
    "age_num", "sp_rank", "is_fav",
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "mark_compression_score", "release_window_score",
    "course_fit_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "odds_resilience_score", "odds_contraction_score", "decoy_support_flag",
    "setup_run_flag", "cash_run_flag",
]


def _race_metrics(df, prob_col, target_col="target"):
    """Compute Top-1 accuracy and MRR across races."""
    top1_hits = 0
    mrr_sum = 0.0
    races = 0
    for _, grp in df.groupby("race_id"):
        if len(grp) < 2:
            continue
        races += 1
        ranked = grp.sort_values(prob_col, ascending=False).reset_index(drop=True)
        winner_rows = ranked[ranked[target_col] == 1]
        if len(winner_rows) == 0:
            continue
        rank = ranked.index[ranked[target_col] == 1][0] + 1
        if rank == 1:
            top1_hits += 1
        mrr_sum += 1.0 / rank
    top1 = top1_hits / races if races else 0.0
    mrr = mrr_sum / races if races else 0.0
    return round(top1, 4), round(mrr, 4), races


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", default=str(FEATURES_PARQUET))
    parser.add_argument("--output", default=str(STAGING_DIR))
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--promote", action="store_true",
                        help="Overwrite production model after training (requires --promote flag)")
    parser.add_argument("--train-cutoff", type=int, default=2025,
                        help="Exclusive year cutoff for train set (default: 2025 = train <=2024)")
    args = parser.parse_args()

    print("=" * 65)
    print("VÉLØ — SQPE v17 Retrain")
    print(f"  Source  : {args.features}")
    print(f"  Output  : {args.output}")
    print(f"  Split   : train < {args.train_cutoff}, test >= {args.train_cutoff}")
    print("=" * 65)

    # ── Load ──────────────────────────────────────────────────────────────────
    print(f"\nLoading features parquet ...")
    df = pd.read_parquet(args.features)
    print(f"  {len(df):,} rows loaded")

    if not pd.api.types.is_datetime64_any_dtype(df["date_parsed"]):
        df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")

    # Remove non-starters
    numeric_pos = pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce")
    df = df[numeric_pos.notna()].copy()
    print(f"  {len(df):,} rows after removing non-starters")

    if args.sample:
        df = df.sample(n=min(args.sample, len(df)), random_state=42).copy()
        print(f"  Sampled to {len(df):,} rows (random, year distribution preserved)")

    # ── Verify all features present ───────────────────────────────────────────
    missing = [f for f in V17_FEATURES if f not in df.columns]
    if missing:
        print(f"\nERROR: Missing features in parquet: {missing}")
        return

    # ── Temporal split ────────────────────────────────────────────────────────
    df = df.sort_values("date_parsed").reset_index(drop=True)
    train_df = df[df["date_parsed"].dt.year < args.train_cutoff]
    test_df = df[df["date_parsed"].dt.year >= args.train_cutoff]
    print(f"\nTrain: {len(train_df):,}  Test: {len(test_df):,}")
    print(f"  Train years: {train_df['date_parsed'].dt.year.min()} – "
          f"{train_df['date_parsed'].dt.year.max()}")
    print(f"  Test  years: {test_df['date_parsed'].dt.year.min()} – "
          f"{test_df['date_parsed'].dt.year.max()}")

    X_tr = train_df[V17_FEATURES].fillna(0)
    X_te = test_df[V17_FEATURES].fillna(0)
    y_tr = train_df["target"]
    y_te = test_df["target"]

    print(f"\nWin rate  train: {y_tr.mean():.4f}  test: {y_te.mean():.4f}")
    print(f"Features: {len(V17_FEATURES)}")

    # ── Train ─────────────────────────────────────────────────────────────────
    print("\nTraining GBM + isotonic calibration ...")
    model = CalibratedClassifierCV(
        GradientBoostingClassifier(
            n_estimators=500, learning_rate=0.04, max_depth=5,
            min_samples_leaf=50, subsample=0.8, max_features="sqrt",
            random_state=42, verbose=1,
        ),
        method="isotonic", cv=3,
    )
    model.fit(X_tr, y_tr)

    # ── Evaluate ──────────────────────────────────────────────────────────────
    probs = model.predict_proba(X_te)[:, 1]
    auc = roc_auc_score(y_te, probs)
    ll = log_loss(y_te, probs)

    test_copy = test_df.copy()
    test_copy["pred"] = probs
    top1, mrr, n_races = _race_metrics(test_copy, "pred")

    print(f"\n{'=' * 55}")
    print(f"  AUC-ROC   : {auc:.4f}")
    print(f"  Log Loss  : {ll:.4f}")
    print(f"  Top-1 Acc : {top1 * 100:.1f}%  (winner ranked #1)")
    print(f"  MRR       : {mrr:.4f}")
    print(f"  Races eval: {n_races:,}")
    print(f"{'=' * 55}")

    # Compare with current production model
    prod_meta_path = PRODUCTION_MODEL.parent / "metadata.json"
    if prod_meta_path.exists():
        prod_meta = json.loads(prod_meta_path.read_text())
        prod_auc = prod_meta.get("auc", "?")
        print(f"\nProduction model AUC: {prod_auc}  vs  Retrained AUC: {auc:.4f}")
        print(f"Production train rows: {prod_meta.get('train_rows', '?')}  vs  "
              f"Retrained: {len(X_tr):,}")
        print(f"Production trained_at: {prod_meta.get('trained_at', '?')}")

    # ── Feature importance ────────────────────────────────────────────────────
    base = model.calibrated_classifiers_[0].estimator
    importance = sorted(
        zip(V17_FEATURES, base.feature_importances_), key=lambda x: -x[1]
    )
    print("\nTop 15 features:")
    for feat, val in importance[:15]:
        print(f"  {feat:<32} {val:.4f}")

    # ── Save to staging ───────────────────────────────────────────────────────
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = out_dir / "sqpe_v17.pkl"
    with open(model_path, "wb") as fh:
        pickle.dump(model, fh)

    metadata = {
        "version": "v17.1",
        "model_type": "GradientBoostingClassifier + IsotonicCalibration",
        "trained_at": datetime.utcnow().isoformat(),
        "source": str(args.features),
        "train_cutoff_year": args.train_cutoff,
        "n_features": len(V17_FEATURES),
        "feature_names": V17_FEATURES,
        "train_rows": int(len(X_tr)),
        "test_rows": int(len(X_te)),
        "test_races": n_races,
        "auc": round(float(auc), 4),
        "log_loss": round(float(ll), 4),
        "top1_accuracy": round(float(top1), 4),
        "mrr": round(float(mrr), 4),
        "train_win_rate": round(float(y_tr.mean()), 4),
        "test_win_rate": round(float(y_te.mean()), 4),
        "top_15_features": [{"feature": f, "importance": round(v, 4)}
                            for f, v in importance[:15]],
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    pd.DataFrame(importance, columns=["feature", "importance"]).to_csv(
        out_dir / "feature_importance.csv", index=False
    )

    print(f"\nStaging model : {model_path}")
    print(f"Metadata      : {out_dir / 'metadata.json'}")

    # ── Optional promote ──────────────────────────────────────────────────────
    if args.promote:
        prod_dir = PRODUCTION_MODEL.parent
        prod_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(model_path, PRODUCTION_MODEL)
        meta_dest = prod_dir / "metadata.json"
        metadata["version"] = "v17.1"
        metadata["promoted_at"] = datetime.utcnow().isoformat()
        meta_dest.write_text(json.dumps(metadata, indent=2))
        print(f"\nPROMOTED → {PRODUCTION_MODEL}")
    else:
        print(f"\nTo promote: python {__file__} --promote")

    print(f"\n{'=' * 55}")
    print(f"DONE  AUC={auc:.4f}  Top-1={top1 * 100:.1f}%  MRR={mrr:.4f}")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()
