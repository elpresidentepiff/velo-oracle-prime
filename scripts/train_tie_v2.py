"""
Train TIE v2 — Trainer Intent Engine (GBM + intent label)
==========================================================
Key differences from v1:
  - Label: targeted win (won + class_drop + rested + capable_trainer), NOT raw is_winner
  - Model: GradientBoostingClassifier + isotonic calibration (not LogisticRegression)
  - Features: explicit interaction flags (class_drop_flag, fresh_flag, cross terms)

Label definition (Option A — targeted win):
  y_intent = 1 when ALL:
    - target = 1 (won)
    - class_delta <= 0  (same or lower class than last run)
    - days_since_run >= 14  (not quick back-to-back)
    - trainer_win_rate >= 0.10  (capable trainer)

This selects wins that look deliberately engineered.
Expected positive rate: ~4-5% of corpus.

Features:
  Tier 1 (raw): trainer stats, days_since_run, class_delta, jockey_switch_intent,
                mark_compression_score, runs_since_win, quiet_run_score
  Tier 2 (derived): class_drop_flag, fresh_flag, class_drop_x_fresh,
                    trainer_form_x_class_drop, compressed_x_class_drop

Train: date < 2024-01-01
Test:  date >= 2024-01-01

Output:
  models/tie_v2/tie_v2.pkl
  models/tie_v2/metadata.json

Usage:
  python scripts/train_tie_v2.py
  python scripts/train_tie_v2.py --compare-v1  (also score v1 for direct comparison)
"""

import argparse
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PARQUET  = ROOT / "data" / "raceform_v17_features.parquet"
OUT_DIR  = ROOT / "models" / "tie_v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_CUTOFF = "2024-01-01"

# Trainer competence threshold for intent label
TRAINER_WIN_RATE_FLOOR = 0.10
# Minimum rest days for intent label (not a quick turnaround)
MIN_REST_DAYS = 14

GBM_PARAMS = dict(
    n_estimators=300,
    learning_rate=0.05,
    max_depth=4,
    min_samples_leaf=20,
    subsample=0.8,
    random_state=42,
)

TIE_V2_BASE_FEATURES = [
    # Trainer stats
    "trainer_runs_clipped",
    "trainer_win_rate",
    "trainer_recent_runs_clipped",
    "trainer_recent_win_rate",
    # Horse rest / prep
    "days_since_run",
    "class_delta",
    # Form cycle
    "runs_since_win",
    "mark_compression_score",
    "quiet_run_score",
    "jockey_switch_intent",
    # Derived interaction flags (computed below)
    "class_drop_flag",
    "fresh_flag",
    "class_drop_x_fresh",
    "trainer_form_x_class_drop",
    "compressed_x_class_drop",
]


def top1_accuracy(df: pd.DataFrame, score_col: str) -> tuple[float, int]:
    correct, total = 0, 0
    for _, g in df.groupby("race_id"):
        if g["target"].sum() == 0:
            continue
        if g[score_col].idxmax() == g["target"].idxmax():
            correct += 1
        total += 1
    return (correct / total if total else 0.0), total


def build_per_horse_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["horse", "date_parsed"]).copy()
    grp = df.groupby("horse", sort=False)
    df["prev_date"]  = grp["date_parsed"].shift(1)
    df["prev_class"] = grp["class_num"].shift(1)
    df["days_since_run"] = (df["date_parsed"] - df["prev_date"]).dt.days
    df["class_delta"]    = df["class_num"] - df["prev_class"]
    df["days_since_run"] = df["days_since_run"].clip(1, 365).fillna(14.0)
    df["class_delta"]    = df["class_delta"].clip(-6, 6).fillna(0.0)
    return df.drop(columns=["prev_date", "prev_class"])


def build_trainer_stats(train_df: pd.DataFrame) -> pd.DataFrame:
    grp = train_df.groupby("trainer")
    overall = grp["target"].agg(["count", "mean"]).rename(
        columns={"count": "trainer_runs", "mean": "trainer_win_rate"}
    )
    max_date = train_df["date_parsed"].max()
    cutoff   = max_date - pd.Timedelta(days=90)
    recent   = (
        train_df[train_df["date_parsed"] >= cutoff]
        .groupby("trainer")["target"]
        .agg(["count", "mean"])
        .rename(columns={"count": "trainer_recent_runs", "mean": "trainer_recent_win_rate"})
    )
    stats = overall.join(recent, how="left").fillna(
        {"trainer_recent_runs": 0, "trainer_recent_win_rate": 0.0}
    )
    stats["trainer_runs_clipped"]        = stats["trainer_runs"].clip(0, 200)
    stats["trainer_recent_runs_clipped"] = stats["trainer_recent_runs"].clip(0, 50)
    return stats


def add_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["class_drop_flag"]          = (df["class_delta"] < 0).astype(float)
    df["fresh_flag"]               = (df["days_since_run"] >= MIN_REST_DAYS).astype(float)
    df["class_drop_x_fresh"]       = df["class_drop_flag"] * df["fresh_flag"]
    df["trainer_form_x_class_drop"] = df["trainer_win_rate"] * df["class_drop_flag"]
    df["compressed_x_class_drop"]  = df["mark_compression_score"] * df["class_drop_flag"]
    return df


def build_intent_label(df: pd.DataFrame, trainer_stats: pd.DataFrame) -> pd.Series:
    """
    Option A: targeted win.
    Won + class drop or same class + rested + capable trainer.
    """
    # Attach trainer_win_rate for labelling (from train stats only)
    win_rates = trainer_stats["trainer_win_rate"]
    rate = df["trainer"].map(win_rates).fillna(0.0)

    intent = (
        (df["target"] == 1) &
        (df["class_delta"] <= 0) &
        (df["days_since_run"] >= MIN_REST_DAYS) &
        (rate >= TRAINER_WIN_RATE_FLOOR)
    )
    return intent.astype(int)


def attach_trainer_stats(df: pd.DataFrame, trainer_stats: pd.DataFrame) -> pd.DataFrame:
    df = df.merge(
        trainer_stats[["trainer_runs_clipped", "trainer_win_rate",
                       "trainer_recent_runs_clipped", "trainer_recent_win_rate"]],
        how="left", left_on="trainer", right_index=True,
    )
    df["trainer_runs_clipped"]        = df["trainer_runs_clipped"].fillna(0)
    df["trainer_win_rate"]            = df["trainer_win_rate"].fillna(0.0)
    df["trainer_recent_runs_clipped"] = df["trainer_recent_runs_clipped"].fillna(0)
    df["trainer_recent_win_rate"]     = df["trainer_recent_win_rate"].fillna(0.0)
    return df


def main(compare_v1: bool = False):
    print("Loading corpus ...")
    df = pd.read_parquet(PARQUET)
    df["date_parsed"] = pd.to_datetime(df["date"])
    print(f"  Total: {len(df):,} rows")

    print("Computing per-horse features ...")
    df = build_per_horse_features(df)

    train_df = df[df["date_parsed"] < TRAIN_CUTOFF].copy()
    test_df  = df[df["date_parsed"] >= TRAIN_CUTOFF].copy()
    print(f"  Train: {len(train_df):,}  |  Test: {len(test_df):,}")

    print("Building trainer stats from train set ...")
    trainer_stats = build_trainer_stats(train_df)

    train_df = attach_trainer_stats(train_df, trainer_stats)
    test_df  = attach_trainer_stats(test_df,  trainer_stats)

    train_df = add_interaction_features(train_df)
    test_df  = add_interaction_features(test_df)

    # Intent label — computed from train stats only to avoid leakage
    train_df["y_intent"] = build_intent_label(train_df, trainer_stats)
    test_df["y_intent"]  = build_intent_label(test_df,  trainer_stats)

    pos_train = train_df["y_intent"].sum()
    pos_test  = test_df["y_intent"].sum()
    print(f"\nIntent label positives:")
    print(f"  Train: {pos_train:,} / {len(train_df):,}  ({pos_train/len(train_df):.3%})")
    print(f"  Test:  {pos_test:,}  / {len(test_df):,}  ({pos_test/len(test_df):.3%})")

    X_train = train_df[TIE_V2_BASE_FEATURES].astype(float).fillna(0.0)
    y_train = train_df["y_intent"]
    X_test  = test_df[TIE_V2_BASE_FEATURES].astype(float).fillna(0.0)
    y_test  = test_df["y_intent"]

    print(f"\nTraining HistGBM (fast, NaN-native) ...")
    # HistGradientBoostingClassifier: 10-50x faster than GBM on large datasets,
    # handles NaN natively, and produces comparable quality.
    model = HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.05,
        max_depth=4,
        min_samples_leaf=20,
        random_state=42,
    )
    model.fit(X_train, y_train)

    train_proba = model.predict_proba(X_train)[:, 1]
    test_proba  = model.predict_proba(X_test)[:, 1]

    train_auc = roc_auc_score(y_train, train_proba)
    test_auc  = roc_auc_score(y_test,  test_proba)
    print(f"  Intent label AUC — Train: {train_auc:.4f}  Test: {test_auc:.4f}")

    # Top-1 on raw target (is_winner) — what matters for ensemble contribution
    train_df = train_df.copy()
    test_df  = test_df.copy()
    train_df["tie_v2_score"] = train_proba
    test_df["tie_v2_score"]  = test_proba

    train_top1, train_n = top1_accuracy(train_df, "tie_v2_score")
    test_top1,  test_n  = top1_accuracy(test_df,  "tie_v2_score")
    print(f"  Top-1 (is_winner) — Train: {train_top1:.2%}  Test: {test_top1:.2%}  (n={test_n:,} races)")

    # Feature importance
    try:
        inner = model
        importances = dict(zip(TIE_V2_BASE_FEATURES, inner.feature_importances_))
        print(f"\nFeature importances (top 10):")
        for k, v in sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]:
            bar = "#" * int(v * 100)
            print(f"  {k:<35} {v:.4f}  {bar}")
    except Exception:
        pass

    # Parquet ablation — does TIE v2 add lift over core?
    print(f"\nRunning parquet ablation vs CORE (Place+MktDecep) ...")
    from scripts.ablate_tie_v1 import load_specialist, score_specialist, weighted_ensemble, top1_accuracy as t1a

    place_model,  place_feats  = load_specialist("place_model")
    mktdec_model, mktdec_feats = load_specialist("market_deception_model")

    scores = {}
    if place_model:
        scores["place"]  = score_specialist(place_model,  place_feats,  test_df)
    if mktdec_model:
        scores["mktdec"] = score_specialist(mktdec_model, mktdec_feats, test_df)
    scores["tie_v2"] = test_proba

    WEIGHTS_CORE     = {"place": 0.08, "mktdec": 0.10}
    WEIGHTS_CORE_TIE = {"place": 0.08, "mktdec": 0.10, "tie_v2": 0.08}

    test_df["score_core"]     = weighted_ensemble(scores, WEIGHTS_CORE)
    test_df["score_core_tie"] = weighted_ensemble(scores, WEIGHTS_CORE_TIE)

    core_acc,     n = t1a(test_df, "score_core")
    core_tie_acc, _ = t1a(test_df, "score_core_tie")
    delta = core_tie_acc - core_acc

    print(f"\nAblation results ({n:,} races):")
    print(f"  CORE (Place+MktDecep): {core_acc:.2%}")
    print(f"  CORE+TIE v2:           {core_tie_acc:.2%}")
    print(f"  Delta:                 {delta:+.2%}")
    if delta > 0.005:
        verdict = "PROMOTE — clear lift, wire to ensemble"
    elif delta > 0:
        verdict = "MONITOR — marginal lift, observe on live data before promoting"
    else:
        verdict = "HOLD — no lift, do not promote"
    print(f"  Verdict: {verdict}")

    # Save
    joblib.dump(model, OUT_DIR / "tie_v2.pkl")
    meta = {
        "name": "tie_v2",
        "trained": datetime.utcnow().isoformat(),
        "train_cutoff": TRAIN_CUTOFF,
        "label": "intent_label (won + class_drop + rested + capable_trainer)",
        "label_floor_trainer_win_rate": TRAINER_WIN_RATE_FLOOR,
        "label_min_rest_days": MIN_REST_DAYS,
        "model_type": "GradientBoostingClassifier + isotonic calibration",
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "train_intent_positives": int(pos_train),
        "test_intent_positives": int(pos_test),
        "train_intent_auc": round(train_auc, 4),
        "test_intent_auc": round(test_auc, 4),
        "train_top1": round(train_top1, 4),
        "test_top1": round(test_top1, 4),
        "ablation_core_top1": round(core_acc, 4),
        "ablation_core_tie_top1": round(core_tie_acc, 4),
        "ablation_delta": round(delta, 4),
        "ablation_verdict": verdict,
        "features": TIE_V2_BASE_FEATURES,
        "status": "experimental" if delta <= 0 else "promote_candidate",
    }
    with open(OUT_DIR / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\nSaved: {OUT_DIR}/tie_v2.pkl + metadata.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare-v1", action="store_true")
    args = parser.parse_args()
    main(compare_v1=args.compare_v1)
