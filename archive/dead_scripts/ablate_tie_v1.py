"""
TIE v1 Ablation — Parquet-based
================================
Tests whether TIE v1 adds lift over the current proven ensemble core
(SQPE + Place + Market Deception) on the held-out 2024+ test set.

Uses raceform_v17_features.parquet as the source — same corpus used for
training all specialist models. This is a fair comparison since the TIE
model was trained on pre-2024 data only.

Modes compared
--------------
  CORE        = Place + Market_Deception  (proxy for proven core, SQPE not in parquet)
  CORE+TIE    = Place + Market_Deception + TIE v1

For each mode: compute weighted ensemble score per runner, pick top-1 per race,
compare against actual winner (target=1).

Weights used
------------
  place_model          0.08  (as in live ensemble)
  market_deception     0.10
  tie_v1               0.08  (candidate weight — ablate before finalising)
  (weights re-normalised within active set for fair comparison)

Usage
-----
    python scripts/ablate_tie_v1.py
    python scripts/ablate_tie_v1.py --days 365   (1-year hold-out slice only)
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PARQUET      = ROOT / "data" / "raceform_v17_features.parquet"
SPECIALIST   = ROOT / "models" / "specialist"
TIE_MODEL    = ROOT / "models" / "tie_v1" / "tie_v1.pkl"
TIE_META     = ROOT / "models" / "tie_v1" / "metadata.json"
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


def load_specialist(name: str):
    path = SPECIALIST / name / f"{name}.pkl"
    if not path.exists():
        print(f"  [SKIP] {name} not found at {path}")
        return None, []
    with open(SPECIALIST / name / "metadata.json") as f:
        meta = json.load(f)
    return joblib.load(path), meta.get("features", [])


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
    df = df.drop(columns=["prev_date", "prev_class"])
    return df


def build_trainer_stats_from_train(train_df: pd.DataFrame) -> pd.DataFrame:
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


def score_specialist(model, features: list[str], df: pd.DataFrame) -> np.ndarray:
    available = [f for f in features if f in df.columns]
    X = df[available].fillna(0).copy()
    for f in features:
        if f not in X.columns:
            X[f] = 0.0
    X = X[features]
    return model.predict_proba(X)[:, 1]


def weighted_ensemble(scores: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    """Weighted sum normalised to weights that are present."""
    active = {k: v for k, v in weights.items() if k in scores}
    total_w = sum(active.values())
    if total_w == 0:
        return np.zeros(len(next(iter(scores.values()))))
    result = np.zeros(len(next(iter(scores.values()))))
    for k, w in active.items():
        result += (w / total_w) * scores[k]
    return result


def main(days: int | None = None):
    print(f"\nLoading corpus ...")
    df = pd.read_parquet(PARQUET)
    df["date_parsed"] = pd.to_datetime(df["date"])
    print(f"  Total rows: {len(df):,}")

    print("Computing per-horse TIE features ...")
    df = build_per_horse_features(df)

    train_df = df[df["date_parsed"] < TRAIN_CUTOFF].copy()
    test_df  = df[df["date_parsed"] >= TRAIN_CUTOFF].copy()

    if days is not None:
        cutoff = test_df["date_parsed"].max() - pd.Timedelta(days=days)
        test_df = test_df[test_df["date_parsed"] >= cutoff]
        print(f"  Sliced to last {days} days: {len(test_df):,} test rows")
    else:
        print(f"  Train: {len(train_df):,}  |  Test (2024+): {len(test_df):,}")

    # Trainer stats from train set only
    print("Building trainer stats from train set ...")
    trainer_stats = build_trainer_stats_from_train(train_df)
    test_df = test_df.merge(
        trainer_stats[["trainer_runs_clipped", "trainer_win_rate",
                       "trainer_recent_runs_clipped", "trainer_recent_win_rate"]],
        how="left", left_on="trainer", right_index=True,
    )
    test_df["trainer_runs_clipped"]        = test_df["trainer_runs_clipped"].fillna(0)
    test_df["trainer_win_rate"]            = test_df["trainer_win_rate"].fillna(0.0)
    test_df["trainer_recent_runs_clipped"] = test_df["trainer_recent_runs_clipped"].fillna(0)
    test_df["trainer_recent_win_rate"]     = test_df["trainer_recent_win_rate"].fillna(0.0)

    # Load specialist models
    print("Loading specialist models ...")
    place_model,   place_feats   = load_specialist("place_model")
    mktdec_model,  mktdec_feats  = load_specialist("market_deception_model")
    tie_model = joblib.load(TIE_MODEL) if TIE_MODEL.exists() else None
    if tie_model is None:
        print("  [ERROR] TIE v1 model not found. Run train_tie_v1.py first.")
        return

    # Score
    print("Scoring test set ...")
    scores = {}
    if place_model:
        scores["place"]  = score_specialist(place_model,  place_feats,  test_df)
    if mktdec_model:
        scores["mktdec"] = score_specialist(mktdec_model, mktdec_feats, test_df)

    X_tie = test_df[TIE_FEATURES].astype(float)
    scores["tie"] = tie_model.predict_proba(X_tie)[:, 1]

    # Ensemble weights (raw, normalised inside weighted_ensemble)
    WEIGHTS_CORE     = {"place": 0.08, "mktdec": 0.10}
    WEIGHTS_CORE_TIE = {"place": 0.08, "mktdec": 0.10, "tie": 0.08}

    test_df = test_df.copy()
    test_df["score_core"]     = weighted_ensemble(scores, WEIGHTS_CORE)
    test_df["score_core_tie"] = weighted_ensemble(scores, WEIGHTS_CORE_TIE)
    test_df["score_tie_only"] = scores["tie"]

    # Evaluate
    modes = {
        "CORE (Place+MktDecep)":         "score_core",
        "CORE+TIE":                      "score_core_tie",
        "TIE_ONLY":                      "score_tie_only",
    }

    print(f"\n{'='*60}")
    print(f"  TIE v1 ABLATION — test set {test_df['date_parsed'].min().date()} to {test_df['date_parsed'].max().date()}")
    print(f"{'='*60}\n")

    header = f"  {'Mode':<30} {'Races':>7} {'Top-1%':>8} {'AvgWinP':>9}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    results = {}
    for label, col in modes.items():
        acc, n_races = top1_accuracy(test_df, col)
        winner_rows = test_df[test_df["target"] == 1]
        avg_wp = winner_rows[col].mean()
        results[label] = {"top1": acc, "races": n_races, "avg_wp": avg_wp}
        print(f"  {label:<30} {n_races:>7} {acc:>7.2%} {avg_wp:>9.4f}")

    print()
    core_top1 = results["CORE (Place+MktDecep)"]["top1"]
    core_tie_top1 = results["CORE+TIE"]["top1"]
    delta = core_tie_top1 - core_top1
    print(f"  TIE lift vs core: {delta:+.2%} ({'+' if delta > 0 else ''}{delta*100:.1f} ppts)")
    if delta > 0.005:
        print("  VERDICT: TIE adds meaningful lift -- wire to ensemble")
    elif delta > 0:
        print("  VERDICT: TIE adds marginal lift -- monitor before promoting")
    else:
        print("  VERDICT: TIE does not help -- hold in lab")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None,
                        help="Slice test set to last N days (default: all 2024+)")
    args = parser.parse_args()
    main(days=args.days)
