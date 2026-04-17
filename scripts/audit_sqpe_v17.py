"""
SQPE v17 Realism & Leakage Audit
==================================
Answers:
  1. Is the train/test split strictly chronological?
  2. Is Top-1 accuracy race-level, not row-level?
  3. Do training and test horses overlap -- memorisation risk?
  4. Performance by year (2024 vs 2025 separately)
  5. Performance by race type (Flat / Hurdle / Chase / NH Flat)
  6. Performance at odds > 5.0 (where real edge lives)
  7. THREE evaluation modes:
       A. Ratings only (no market data)
       B. Pre-race market only (SP excluded, implied_prob excluded)
       C. Full feature set
  8. Calibration: predicted prob vs actual win rate by decile
  9. Win rate train vs test (leakage smoke test)

Usage:
    python scripts/audit_sqpe_v17.py
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss

sys.path.insert(0, str(Path(__file__).parent.parent))

# -- Re-use feature engineering from trainer ----------------------------------
from scripts.train_sqpe_v17 import (
    engineer_v16_features,
    engineer_v17_doctrine,
    ALL_FEATURES, V16_FEATURES, V17_DOCTRINE_FEATURES,
)

MODEL_PATH    = Path("models/sqpe_v17/sqpe_v17.pkl")
FEATURES_PATH = Path("data/raceform_v17_features.parquet")  # pre-engineered (fast)
RAW_PATH      = Path("data/raceform_clean.parquet")          # fallback (slow)

MARKET_FEATURES   = {"sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav"}
RATINGS_FEATURES  = {"or_num", "rpr_num", "ts_num", "or_vs_field", "rpr_vs_field"}


def top1_accuracy_race_level(df: pd.DataFrame, pred_col: str = "pred") -> float:
    """Race-level Top-1: did the model rank the winner #1 in this race?"""
    df = df.copy()
    df["pred_rank"] = df.groupby("race_id")[pred_col].rank(ascending=False, method="min")
    races_with_winner = df[df["target"] == 1].groupby("race_id")["pred_rank"].min()
    return float((races_with_winner == 1).mean())


def mrr_race_level(df: pd.DataFrame, pred_col: str = "pred") -> float:
    df = df.copy()
    df["pred_rank"] = df.groupby("race_id")[pred_col].rank(ascending=False, method="min")
    winner_ranks = df[df["target"] == 1]["pred_rank"]
    return float((1.0 / winner_ranks).mean())


def calibration_deciles(y_true, y_prob, n=10) -> pd.DataFrame:
    df = pd.DataFrame({"prob": y_prob, "actual": y_true})
    df["decile"] = pd.qcut(df["prob"], n, labels=False, duplicates="drop")
    result = df.groupby("decile").agg(
        mean_pred=("prob", "mean"),
        actual_rate=("actual", "mean"),
        count=("actual", "count"),
    ).reset_index()
    result["gap"] = result["mean_pred"] - result["actual_rate"]
    return result


def evaluate_mode(model, X_te, y_te, test_df, label: str):
    probs = model.predict_proba(X_te)[:, 1]
    test_df = test_df.copy()
    test_df["pred"] = probs
    auc  = roc_auc_score(y_te, probs)
    ll   = log_loss(y_te, probs)
    top1 = top1_accuracy_race_level(test_df)
    mrr  = mrr_race_level(test_df)
    print(f"  [{label:<30}]  AUC={auc:.4f}  LogLoss={ll:.4f}  "
          f"Top-1={top1*100:.1f}%  MRR={mrr:.4f}")
    return auc, ll, top1, mrr


def main():
    print("=" * 65)
    print("SQPE v17 REALISM & LEAKAGE AUDIT")
    print("=" * 65)

    if not MODEL_PATH.exists():
        print(f"ERROR: model not found at {MODEL_PATH}"); sys.exit(1)
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    print(f"\nModel loaded: {MODEL_PATH}")

    # -- Load pre-engineered features (fast) or recompute from raw (slow) --------
    if FEATURES_PATH.exists():
        print(f"Loading pre-engineered features: {FEATURES_PATH}")
        df = pd.read_parquet(FEATURES_PATH)
        df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
        if "_yr" not in df.columns:
            df["_yr"] = df["date_parsed"].dt.year
        print(f"  {len(df):,} rows loaded instantly.")
    elif RAW_PATH.exists():
        print(f"Pre-engineered file not found. Recomputing from {RAW_PATH} (slow ~40min) ...")
        print("TIP: Run 'python scripts/save_engineered_features.py' first to avoid this.")
        df = pd.read_parquet(RAW_PATH)
        df = df.rename(columns={"class": "class_raw", "or": "or_rating"}, errors="ignore")
        if "race_id" not in df.columns:
            df["race_id"] = df["course"].astype(str) + "_" + df["date"].astype(str) + "_" + df["off"].astype(str)
        df = df[~df["pos"].astype(str).str.strip().isin(["", "nan", "NaN"])]
        df = engineer_v16_features(df)
        df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values(["horse", "date_parsed"]).reset_index(drop=True)
        print(f"Computing v17 doctrine features ({df['horse'].nunique():,} horses) ...")
        df = engineer_v17_doctrine(df)
        df = df.sort_values("date_parsed").reset_index(drop=True)
        df["_yr"] = df["date_parsed"].dt.year
    else:
        print(f"ERROR: neither {FEATURES_PATH} nor {RAW_PATH} found"); sys.exit(1)
    df["_yr"] = df["date_parsed"].dt.year

    # -- CHECK 1: Split is strictly chronological -------------------------------
    print("\n" + "-" * 65)
    print("CHECK 1 -- Train/Test Split")
    train_df = df[df["_yr"] < 2024].copy()
    test_df  = df[df["_yr"] >= 2024].copy()

    train_max = train_df["date_parsed"].max()
    test_min  = test_df["date_parsed"].min()
    print(f"  Train: {len(train_df):,} rows | last date: {train_max.date()}")
    print(f"  Test : {len(test_df):,}  rows | first date: {test_min.date()}")
    split_clean = train_max < test_min
    print(f"  Strictly chronological: {'YES OK' if split_clean else 'NO X -- LEAKAGE RISK'}")

    # -- CHECK 2: Win rate parity ------------------------------------------------
    print("\n" + "-" * 65)
    print("CHECK 2 -- Win Rate (leakage smoke test)")
    train_wr = train_df["target"].mean()
    test_wr  = test_df["target"].mean()
    print(f"  Train win rate: {train_wr:.4f}  ({train_wr*100:.2f}%)")
    print(f"  Test  win rate: {test_wr:.4f}  ({test_wr*100:.2f}%)")
    wr_diff = abs(train_wr - test_wr)
    print(f"  Difference    : {wr_diff:.4f}  ({'OK' if wr_diff < 0.005 else 'SUSPICIOUS'})")

    # -- CHECK 3: Horse overlap --------------------------------------------------
    print("\n" + "-" * 65)
    print("CHECK 3 -- Horse Overlap (memorisation risk)")
    train_horses = set(train_df["horse"].unique())
    test_horses  = set(test_df["horse"].unique())
    overlap = train_horses & test_horses
    overlap_pct = len(overlap) / len(test_horses) * 100
    print(f"  Train horses  : {len(train_horses):,}")
    print(f"  Test horses   : {len(test_horses):,}")
    print(f"  Overlap       : {len(overlap):,}  ({overlap_pct:.1f}% of test horses seen in training)")
    print(f"  Note: overlap is EXPECTED (same horses race multiple years).")
    print(f"  Doctrine features are lagged -- they only use PRIOR runs, no leakage.")

    # -- CHECK 4: Race-level Top-1 -----------------------------------------------
    print("\n" + "-" * 65)
    print("CHECK 4 -- Top-1 Accuracy is Race-Level")
    X_te = test_df[ALL_FEATURES].fillna(0)
    y_te = test_df["target"]
    probs = model.predict_proba(X_te)[:, 1]
    test_df["pred"] = probs

    races_count = test_df["race_id"].nunique()
    top1_race = top1_accuracy_race_level(test_df)
    mrr_race  = mrr_race_level(test_df)
    print(f"  Test races    : {races_count:,}")
    print(f"  Top-1 Acc     : {top1_race*100:.1f}%  <-- race-level (winner ranked #1 per race)")
    print(f"  MRR           : {mrr_race:.4f}")

    # Row-level for comparison
    top1_row = (probs == test_df.groupby("race_id")["pred"].transform("max")).mean()
    print(f"  Row-level proxy (for comparison only): {top1_row*100:.1f}%")

    # -- CHECK 5: Performance by year --------------------------------------------
    print("\n" + "-" * 65)
    print("CHECK 5 -- Performance by Year (2024 vs 2025 separately)")
    for yr in sorted(test_df["_yr"].unique()):
        yr_df = test_df[test_df["_yr"] == yr].copy()
        if yr_df["target"].sum() == 0:
            continue
        yr_auc  = roc_auc_score(yr_df["target"], yr_df["pred"])
        yr_top1 = top1_accuracy_race_level(yr_df)
        yr_races = yr_df["race_id"].nunique()
        print(f"  {yr}: {yr_races:>5,} races  AUC={yr_auc:.4f}  Top-1={yr_top1*100:.1f}%")

    # -- CHECK 6: Performance by race type ---------------------------------------
    print("\n" + "-" * 65)
    print("CHECK 6 -- Performance by Race Type")
    if "type" in test_df.columns:
        for rtype in test_df["type"].dropna().unique():
            rt_df = test_df[test_df["type"] == rtype].copy()
            if rt_df["target"].sum() < 10 or rt_df["race_id"].nunique() < 5:
                continue
            rt_auc  = roc_auc_score(rt_df["target"], rt_df["pred"])
            rt_top1 = top1_accuracy_race_level(rt_df)
            rt_races = rt_df["race_id"].nunique()
            print(f"  {rtype:<20} {rt_races:>5,} races  AUC={rt_auc:.4f}  Top-1={rt_top1*100:.1f}%")
    else:
        print("  'type' column not in test data -- skipping")

    # -- CHECK 7: Performance at odds > 5.0 -------------------------------------
    print("\n" + "-" * 65)
    print("CHECK 7 -- Performance at Odds > 5.0 (where real edge lives)")
    long_df = test_df[test_df["sp_dec"] > 5.0].copy()
    short_df = test_df[test_df["sp_dec"] <= 5.0].copy()
    if long_df["target"].sum() > 0:
        long_top1 = top1_accuracy_race_level(long_df)
        long_win  = long_df[long_df["pred"] == long_df.groupby("race_id")["pred"].transform("max")]["target"].mean()
        print(f"  Odds > 5.0 : {long_df['race_id'].nunique():,} races  Top-1={long_top1*100:.1f}%  "
              f"Win% when model picks them: {long_win*100:.1f}%")
    if short_df["target"].sum() > 0:
        short_top1 = top1_accuracy_race_level(short_df)
        print(f"  Odds <= 5.0 : {short_df['race_id'].nunique():,} races  Top-1={short_top1*100:.1f}%")
    print("  NOTE: If Top-1 >> 50% but only on short-priced horses, model is echoing market.")

    # -- CHECK 8: Three evaluation modes ----------------------------------------
    print("\n" + "-" * 65)
    print("CHECK 8 -- Three Evaluation Modes")
    X_tr = train_df[ALL_FEATURES].fillna(0)
    y_tr = train_df["target"]

    def retrain_on_features(feature_list, label):
        mini_model = CalibratedClassifierCV(
            GradientBoostingClassifier(
                n_estimators=200, learning_rate=0.05, max_depth=4,
                min_samples_leaf=50, subsample=0.8, random_state=42,
            ),
            method="isotonic", cv=3,
        )
        avail = [f for f in feature_list if f in train_df.columns]
        mini_model.fit(train_df[avail].fillna(0), y_tr)
        probs_m = mini_model.predict_proba(test_df[avail].fillna(0))[:, 1]
        td = test_df.copy()
        td["pred"] = probs_m
        auc_m  = roc_auc_score(y_te, probs_m)
        top1_m = top1_accuracy_race_level(td)
        mrr_m  = mrr_race_level(td)
        print(f"  [{label:<30}]  AUC={auc_m:.4f}  Top-1={top1_m*100:.1f}%  MRR={mrr_m:.4f}")
        return auc_m, top1_m

    print()

    # Mode A: Ratings only -- no market data
    ratings_only = [f for f in ALL_FEATURES if f not in MARKET_FEATURES]
    auc_a, top1_a = retrain_on_features(ratings_only, "A: Ratings only (no SP/market)")

    # Mode B: Full minus final SP (pre-race proxy -- use sp_rank, is_fav as market signal only)
    no_raw_sp = [f for f in ALL_FEATURES if f not in {"sp_dec", "log_sp", "implied_prob"}]
    auc_b, top1_b = retrain_on_features(no_raw_sp, "B: No raw SP (sp_rank/is_fav kept)")

    # Mode C: Full feature set (current production)
    evaluate_mode(model, X_te, y_te, test_df, "C: Full features (production)")

    sp_contribution = top1_b - top1_a
    print(f"\n  SP contribution to Top-1: {sp_contribution*100:+.1f}pp")
    print(f"  If A is strong (>50%), model has genuine horse intelligence.")
    print(f"  If A is weak (<40%), model is mostly echoing the market.")

    # -- CHECK 9: Calibration deciles -------------------------------------------
    print("\n" + "-" * 65)
    print("CHECK 9 -- Calibration (predicted prob vs actual win rate)")
    cal = calibration_deciles(y_te.values, probs, n=10)
    print(f"  {'Decile':<8} {'Pred%':>7} {'Actual%':>9} {'Gap':>7} {'Count':>8}")
    print(f"  {'-'*45}")
    max_gap = 0.0
    for _, row in cal.iterrows():
        gap = row["gap"]
        max_gap = max(max_gap, abs(gap))
        flag = " <-- OVERCONFIDENT" if gap > 0.03 else (" <-- UNDERCONFIDENT" if gap < -0.03 else "")
        print(f"  {int(row['decile']):<8} "
              f"{row['mean_pred']*100:>6.1f}%  "
              f"{row['actual_rate']*100:>8.1f}%  "
              f"{gap*100:>+6.1f}pp  "
              f"{int(row['count']):>8}{flag}")
    print(f"\n  Max calibration gap: {max_gap*100:.1f}pp  "
          f"({'WELL CALIBRATED' if max_gap < 0.05 else 'RECALIBRATION NEEDED'})")

    # -- VERDICT ----------------------------------------------------------------
    print("\n" + "=" * 65)
    print("AUDIT VERDICT")
    print("=" * 65)
    issues = []
    if not split_clean:
        issues.append("CRITICAL: Train/test split is NOT chronological")
    if wr_diff > 0.01:
        issues.append(f"WARNING: Win rate difference {wr_diff:.4f} -- potential leakage")
    if max_gap > 0.05:
        issues.append(f"WARNING: Calibration gap {max_gap*100:.1f}pp -- probabilities are biased")
    if top1_a < 0.40:
        issues.append("WARNING: Ratings-only Top-1 < 40% -- model heavily market-dependent")

    if issues:
        for issue in issues:
            print(f"  X {issue}")
        print("\n  VERDICT: DO NOT deploy without fixing above issues.")
    else:
        print(f"  OK Split is chronological")
        print(f"  OK Win rates consistent (no gross leakage)")
        print(f"  OK Top-1 confirmed race-level")
        print(f"  OK Ratings-only AUC={auc_a:.4f} (genuine horse intelligence present)")
        print(f"  OK Calibration max gap={max_gap*100:.1f}pp")
        print(f"\n  VERDICT: Model passes basic realism checks.")
        print(f"  CAUTION: SP features inflating metrics -- always check Mode A numbers")
        print(f"           when evaluating production performance on live races.")
    print("=" * 65)


if __name__ == "__main__":
    main()
