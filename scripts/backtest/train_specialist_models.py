"""
Phase C: Train all 7 specialist models from raceform_v17_features.parquet
Each model is a focused binary/regression model on a specific signal domain.

Specialist models:
  1. improvement_model     — Is this horse about to improve? (mark_compression + release window)
  2. market_deception_model — Is this horse a market deceiver? (odds drift vs OR)
  3. release_window_model  — Is this a timed/planned run? (setup_run + cash_run + trainer timing)
  4. comment_intelligence_model — Do NLP flags predict wins? (quiet_run, jockey_switch)
  5. draw_bias_model        — Draw position adjusted win probability
  6. place_model            — Probability of top-2 finish (broader than win)
  7. longshot_model         — Overperformance at high odds (odds > 10.0)

All use: chronological split (train < 2024, test >= 2024), GBM, isotonic calibration.
Output: models/specialist/[model_name]/[model_name].pkl + metadata.json
"""
import argparse
import json
import os
import sys
import warnings
from pathlib import Path
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# ─── Config ────────────────────────────────────────────────────────────────────

MODELS_DIR = ROOT / "models" / "specialist"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_PATH = ROOT / "data" / "raceform_v17_features.parquet"

# Common GBM params (CPU-first, L001/L008 doctrine)
GBM_PARAMS = dict(
    n_estimators=300,
    learning_rate=0.05,
    max_depth=4,
    min_samples_leaf=20,
    subsample=0.8,
    random_state=42,
)

TRAIN_CUTOFF = "2024-01-01"
LIVE_USABLE  = True  # All specialist models declared LIVE-USABLE per D007


# ─── Helpers ───────────────────────────────────────────────────────────────────

def top1_accuracy(df_test: pd.DataFrame, score_col: str) -> float:
    """Race-level Top-1: fraction of races where highest-scored horse won."""
    gb = df_test.groupby("race_id")
    correct = 0
    total   = 0
    for _, g in gb:
        if g["target"].sum() == 0:
            continue
        winner_idx = g["target"].idxmax()
        best_idx   = g[score_col].idxmax()
        correct += int(winner_idx == best_idx)
        total   += 1
    return correct / total if total > 0 else 0.0


def save_model(model, name: str, features: list, metadata: dict):
    out_dir = MODELS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_dir / f"{name}.pkl")
    meta = {
        "name": name,
        "trained": datetime.utcnow().isoformat(),
        "features": features,
        "live_usable": LIVE_USABLE,
        "train_cutoff": TRAIN_CUTOFF,
        "source": str(FEATURE_PATH),
        **metadata,
    }
    with open(out_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  -> Saved: models/specialist/{name}/")


def fit_and_eval(name, df_train, df_test, features, target_col="target", label="win"):
    print(f"\n[{name}] Training on {len(df_train):,} rows, testing on {len(df_test):,}")
    X_tr = df_train[features].fillna(0)
    y_tr = df_train[target_col]
    X_te = df_test[features].fillna(0)
    y_te = df_test[target_col]

    base = GradientBoostingClassifier(**GBM_PARAMS)
    model = CalibratedClassifierCV(base, method="isotonic", cv=3)
    model.fit(X_tr, y_tr)

    proba = model.predict_proba(X_te)[:, 1]
    auc   = roc_auc_score(y_te, proba)
    ll    = log_loss(y_te, proba)

    df_test = df_test.copy()
    df_test[f"p_{name}"] = proba
    t1 = top1_accuracy(df_test, f"p_{name}")

    print(f"  AUC={auc:.4f}  LogLoss={ll:.4f}  Top-1={t1:.1%}  label={label}")

    meta = {
        "n_train": len(df_train),
        "n_test": len(df_test),
        "auc": round(auc, 4),
        "log_loss": round(ll, 4),
        "top1_accuracy": round(t1, 4),
        "target": target_col,
        "label": label,
    }
    save_model(model, name, features, meta)
    return model


# ─── Load data ─────────────────────────────────────────────────────────────────

def load_data():
    print("Loading raceform_v17_features.parquet...")
    df = pd.read_parquet(FEATURE_PATH)
    df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
    df_train = df[df["date_parsed"] < TRAIN_CUTOFF].copy()
    df_test  = df[df["date_parsed"] >= TRAIN_CUTOFF].copy()
    print(f"  Train: {len(df_train):,}  Test: {len(df_test):,}")
    return df_train, df_test


# ─── 1. Improvement model ──────────────────────────────────────────────────────

def train_improvement(df_train, df_test):
    """
    Signal: horse about to improve based on mark trajectory and release window.
    Features: mark_compression_score, curr_or_minus_best_or, curr_or_minus_last_win_or,
              release_window_score, runs_since_win, runs_since_place, trainer_timing_score
    """
    features = [
        "mark_compression_score", "curr_or_minus_best_or", "curr_or_minus_last_win_or",
        "release_window_score", "runs_since_win", "runs_since_place",
        "trainer_timing_score", "distance_fit_score", "course_fit_score",
        "or_vs_field", "rpr_vs_field", "age_num",
    ]
    return fit_and_eval("improvement_model", df_train, df_test, features, label="improvement_signal")


# ─── 2. Market deception model ─────────────────────────────────────────────────

def train_market_deception(df_train, df_test):
    """
    Signal: horse whose market position understates true ability.
    Features: implied_prob vs ratings signals → odds_resilience, odds_contraction,
              rpr_vs_field vs sp_rank discrepancy
    """
    # Create discrepancy feature: model rates better than market
    def prep(df):
        d = df.copy()
        d["rating_mkt_gap"] = d["rpr_vs_field"] - (1 - d["implied_prob"])  # higher = underrated by market
        d["or_mkt_gap"]     = d["or_vs_field"] - d["sp_rank"] / d["field_size"]
        return d

    df_tr = prep(df_train)
    df_te = prep(df_test)

    features = [
        "odds_resilience_score", "odds_contraction_score",
        "rpr_vs_field", "or_vs_field", "sp_rank", "is_fav",
        "rating_mkt_gap", "or_mkt_gap",
        "decoy_support_flag", "mark_compression_score",
        "log_sp", "field_size",
    ]
    return fit_and_eval("market_deception_model", df_tr, df_te, features, label="market_deception")


# ─── 3. Release window model ──────────────────────────────────────────────────

def train_release_window(df_train, df_test):
    """
    Signal: planned/timed run by connections.
    Features: setup_run_flag, cash_run_flag, trainer_timing_score,
              runs_since_win, runs_since_mkt_support, jockey_switch_intent
    """
    features = [
        "setup_run_flag", "cash_run_flag", "trainer_timing_score",
        "runs_since_win", "runs_since_place", "runs_since_mkt_support",
        "jockey_switch_intent", "release_window_score",
        "mark_compression_score", "odds_contraction_score",
    ]
    return fit_and_eval("release_window_model", df_train, df_test, features, label="release_window")


# ─── 4. Comment intelligence model ────────────────────────────────────────────

def train_comment_intelligence(df_train, df_test):
    """
    Signal: NLP-derived flags from horse comments predict future performance.
    Features: quiet_run_score, decoy_support_flag, jockey_switch_intent,
              setup_run_flag — combined with form context
    """
    features = [
        "quiet_run_score", "decoy_support_flag", "jockey_switch_intent",
        "setup_run_flag", "cash_run_flag",
        "runs_since_win", "runs_since_place", "runs_since_mkt_support",
        "trainer_timing_score", "course_fit_score", "going_fit_score",
    ]
    return fit_and_eval("comment_intelligence_model", df_train, df_test, features, label="comment_intel")


# ─── 5. Draw bias model ────────────────────────────────────────────────────────

def train_draw_bias(df_train, df_test):
    """
    Signal: draw position advantage, controlling for going/distance/class.
    Features: draw_pct (normalised draw position), interaction with going/is_aw/dist_f
    """
    def prep(df):
        d = df.copy()
        d["draw_going"]  = d["draw_pct"] * d["going_code"]
        d["draw_dist"]   = d["draw_pct"] * d["dist_f"]
        d["draw_aw"]     = d["draw_pct"] * d["is_aw"]
        d["draw_class"]  = d["draw_pct"] * d["class_num"]
        d["draw_size"]   = d["draw_pct"] * d["field_size"]
        return d

    df_tr = prep(df_train)
    df_te = prep(df_test)

    features = [
        "draw_pct", "draw_num", "draw_going", "draw_dist", "draw_aw",
        "draw_class", "draw_size", "going_code", "dist_f", "is_aw",
        "field_size", "class_num",
    ]
    return fit_and_eval("draw_bias_model", df_tr, df_te, features, label="draw_bias")


# ─── 6. Place model ───────────────────────────────────────────────────────────

def train_place_model(df_train, df_test):
    """
    Signal: probability of top-2 finish (wider than win, for each-way betting).
    Target: pos <= 2
    """
    def prep(df):
        d = df.copy()
        d["place_target"] = (pd.to_numeric(d.get("pos", d.get("pos", 99)), errors="coerce").fillna(99) <= 2).astype(int)
        return d

    df_tr = prep(df_train)
    df_te = prep(df_test)

    features = [
        "sp_dec", "log_sp", "implied_prob", "dist_f", "going_code", "is_aw",
        "class_num", "wgt_lbs", "or_num", "rpr_num", "ts_num",
        "or_vs_field", "rpr_vs_field", "field_size", "draw_pct", "age_num",
        "sp_rank", "is_fav",
        "runs_since_win", "runs_since_place", "mark_compression_score",
        "course_fit_score", "going_fit_score", "distance_fit_score",
    ]

    # Check place_target exists and has variance
    tr_rate = df_tr["place_target"].mean()
    te_rate = df_te["place_target"].mean()
    print(f"  Place rate: train={tr_rate:.1%} test={te_rate:.1%}")

    return fit_and_eval("place_model", df_tr, df_te, features,
                        target_col="place_target", label="top2_finish")


# ─── 7. Longshot model ────────────────────────────────────────────────────────

def train_longshot(df_train, df_test):
    """
    Signal: genuine longshot value (horse wins at odds > 10.0).
    Train on rows where sp_dec >= 10.0 only.
    """
    def prep(df):
        return df[df["sp_dec"] >= 10.0].copy()

    df_tr = prep(df_train)
    df_te = prep(df_test)

    print(f"  Longshot subset: train={len(df_tr):,} test={len(df_te):,}")

    features = [
        "log_sp", "dist_f", "going_code", "is_aw", "class_num",
        "or_vs_field", "rpr_vs_field", "field_size", "draw_pct",
        "age_num", "course_fit_score", "going_fit_score", "distance_fit_score",
        "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
        "mark_compression_score", "runs_since_win",
    ]
    return fit_and_eval("longshot_model", df_tr, df_te, features, label="longshot_value")


# ─── Main ─────────────────────────────────────────────────────────────────────

SPECIALISTS = {
    "improvement":          train_improvement,
    "market_deception":     train_market_deception,
    "release_window":       train_release_window,
    "comment_intelligence": train_comment_intelligence,
    "draw_bias":            train_draw_bias,
    "place":                train_place_model,
    "longshot":             train_longshot,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="+", choices=list(SPECIALISTS.keys()),
                        help="Train only these models (default: all)")
    args = parser.parse_args()

    targets = args.only or list(SPECIALISTS.keys())
    df_train, df_test = load_data()

    results = {}
    for name in targets:
        try:
            SPECIALISTS[name](df_train, df_test)
            results[name] = "OK"
        except Exception as e:
            print(f"  ERROR in {name}: {e}")
            results[name] = f"FAILED: {e}"

    print("\n=== Phase C Summary ===")
    for name, status in results.items():
        print(f"  {name}: {status}")
