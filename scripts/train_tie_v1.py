"""
Train TIE v1 — Trainer Intent Engine (LogisticRegression)
=========================================================
Features (all pre-race usable, no look-ahead):
  - trainer_runs_clipped          capped at 200
  - trainer_win_rate              overall from train set
  - trainer_recent_runs_clipped   capped at 50 (90-day window)
  - trainer_recent_win_rate       90-day window
  - days_since_run                days from horse's previous run, capped 1–365
  - class_delta                   current class_num minus previous class_num, capped ±6
  - jockey_switch_intent          1 = jockey changed from last run (already in corpus)

Label: target (is_winner = 1)

Trainer stats are computed from the training period only to prevent test-set leakage.
days_since_run / class_delta are computed per-horse chronologically with no look-ahead.

Train: date < 2024-01-01
Test:  date >= 2024-01-01

Output:
  models/tie_v1/tie_v1.pkl
  models/tie_v1/metadata.json
"""

import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

FEATURE_PATH = ROOT / "data" / "raceform_v17_features.parquet"
OUT_DIR = ROOT / "models" / "tie_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_CUTOFF = "2024-01-01"

TIE_FEATURES = [
    "trainer_runs_clipped",
    "trainer_win_rate",
    "trainer_recent_runs_clipped",
    "trainer_recent_win_rate",
    "days_since_run",
    "class_delta",
    "jockey_switch_intent",
]


def top1_accuracy(df: pd.DataFrame, score_col: str) -> float:
    correct, total = 0, 0
    for _, g in df.groupby("race_id"):
        if g["target"].sum() == 0:
            continue
        if g[score_col].idxmax() == g["target"].idxmax():
            correct += 1
        total += 1
    return correct / total if total else 0.0


def build_per_horse_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute days_since_run and class_delta per horse using only prior runs.
    Sort by horse + date. Shift by 1 within each horse group.
    """
    df = df.sort_values(["horse", "date_parsed"]).copy()

    grp = df.groupby("horse", sort=False)

    # days_since_run: diff in days between consecutive runs per horse
    df["prev_date"] = grp["date_parsed"].shift(1)
    df["days_since_run"] = (df["date_parsed"] - df["prev_date"]).dt.days

    # class_delta: current class_num minus previous class_num
    df["prev_class"] = grp["class_num"].shift(1)
    df["class_delta"] = df["class_num"] - df["prev_class"]

    # Cap and fill
    df["days_since_run"] = df["days_since_run"].clip(1, 365).fillna(14.0)
    df["class_delta"] = df["class_delta"].clip(-6, 6).fillna(0.0)

    df = df.drop(columns=["prev_date", "prev_class"])
    return df


def build_trainer_stats(train_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build trainer aggregate stats from the training portion only.
    Returns a DataFrame indexed by trainer with four stat columns.
    """
    df = train_df.copy()
    df["date_parsed"] = pd.to_datetime(df["date_parsed"])

    grp = df.groupby("trainer")
    overall = grp["target"].agg(["count", "mean"]).rename(
        columns={"count": "trainer_runs", "mean": "trainer_win_rate"}
    )

    max_date = df["date_parsed"].max()
    cutoff = max_date - pd.Timedelta(days=90)
    recent = (
        df[df["date_parsed"] >= cutoff]
        .groupby("trainer")["target"]
        .agg(["count", "mean"])
        .rename(columns={"count": "trainer_recent_runs", "mean": "trainer_recent_win_rate"})
    )

    stats = overall.join(recent, how="left").fillna(
        {"trainer_recent_runs": 0, "trainer_recent_win_rate": 0.0}
    )
    stats["trainer_runs_clipped"] = stats["trainer_runs"].clip(0, 200)
    stats["trainer_recent_runs_clipped"] = stats["trainer_recent_runs"].clip(0, 50)
    return stats


def main():
    print(f"Loading corpus from {FEATURE_PATH} …")
    df = pd.read_parquet(FEATURE_PATH)
    print(f"  Loaded {len(df):,} rows")

    # Parse date
    df["date_parsed"] = pd.to_datetime(df["date"])

    # Per-horse features (computed chronologically, no look-ahead)
    print("Computing days_since_run and class_delta …")
    df = build_per_horse_features(df)

    # Chronological split
    train_df = df[df["date_parsed"] < TRAIN_CUTOFF].copy()
    test_df  = df[df["date_parsed"] >= TRAIN_CUTOFF].copy()
    print(f"  Train: {len(train_df):,} rows | Test: {len(test_df):,} rows")

    # Trainer stats from train set only — no test leakage
    print("Building trainer stats from train set …")
    trainer_stats = build_trainer_stats(train_df)

    def attach_trainer_stats(part: pd.DataFrame) -> pd.DataFrame:
        part = part.merge(
            trainer_stats[["trainer_runs_clipped", "trainer_win_rate",
                           "trainer_recent_runs_clipped", "trainer_recent_win_rate"]],
            how="left",
            left_on="trainer",
            right_index=True,
        )
        part["trainer_runs_clipped"] = part["trainer_runs_clipped"].fillna(0)
        part["trainer_win_rate"] = part["trainer_win_rate"].fillna(0.0)
        part["trainer_recent_runs_clipped"] = part["trainer_recent_runs_clipped"].fillna(0)
        part["trainer_recent_win_rate"] = part["trainer_recent_win_rate"].fillna(0.0)
        return part

    train_df = attach_trainer_stats(train_df)
    test_df  = attach_trainer_stats(test_df)

    X_train = train_df[TIE_FEATURES].astype(float)
    y_train = train_df["target"].astype(int)
    X_test  = test_df[TIE_FEATURES].astype(float)
    y_test  = test_df["target"].astype(int)

    print(f"  Train positives: {y_train.sum():,} / {len(y_train):,} ({y_train.mean():.3%})")
    print(f"  Test  positives: {y_test.sum():,} / {len(y_test):,} ({y_test.mean():.3%})")

    # Train
    print("Training LogisticRegression (L2, C=0.5) with isotonic calibration …")
    base = LogisticRegression(C=0.5, penalty="l2", solver="liblinear", random_state=42, max_iter=200)
    model = CalibratedClassifierCV(base, method="isotonic", cv=3)
    model.fit(X_train, y_train)

    # Evaluate
    train_proba = model.predict_proba(X_train)[:, 1]
    test_proba  = model.predict_proba(X_test)[:, 1]

    train_auc = roc_auc_score(y_train, train_proba)
    test_auc  = roc_auc_score(y_test,  test_proba)
    train_ll  = log_loss(y_train, train_proba)
    test_ll   = log_loss(y_test,  test_proba)

    train_df = train_df.copy()
    test_df  = test_df.copy()
    train_df["tie_score"] = train_proba
    test_df["tie_score"]  = test_proba

    train_top1 = top1_accuracy(train_df, "tie_score")
    test_top1  = top1_accuracy(test_df,  "tie_score")

    print(f"\n-- Results --")
    print(f"  Train  AUC={train_auc:.4f}  LogLoss={train_ll:.4f}  Top-1={train_top1:.2%}")
    print(f"  Test   AUC={test_auc:.4f}  LogLoss={test_ll:.4f}  Top-1={test_top1:.2%}")

    # Feature importance proxy (coefficients)
    try:
        inner = model.calibrated_classifiers_[0].estimator
        coefs = dict(zip(TIE_FEATURES, inner.coef_[0]))
        print(f"\n-- Feature coefficients (first calibration fold) --")
        for k, v in sorted(coefs.items(), key=lambda x: abs(x[1]), reverse=True):
            print(f"  {k:<35} {v:+.4f}")
    except Exception:
        pass

    # Save
    joblib.dump(model, OUT_DIR / "tie_v1.pkl")
    meta = {
        "name": "tie_v1",
        "trained": datetime.utcnow().isoformat(),
        "train_cutoff": TRAIN_CUTOFF,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "train_auc": round(train_auc, 4),
        "test_auc": round(test_auc, 4),
        "train_top1": round(train_top1, 4),
        "test_top1": round(test_top1, 4),
        "features": TIE_FEATURES,
        "label": "target (is_winner)",
        "model_type": "LogisticRegression + isotonic calibration",
        "status": "experimental — ablate vs core before promoting to live",
    }
    with open(OUT_DIR / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nSaved: {OUT_DIR}/tie_v1.pkl")
    print(f"Saved: {OUT_DIR}/metadata.json")
    print("\nNext: run scripts/run_ablation_backtest.py with TIE mode to verify lift before wiring to ensemble.")


if __name__ == "__main__":
    main()
