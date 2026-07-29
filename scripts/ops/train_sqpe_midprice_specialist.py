#!/usr/bin/env python3
"""
VÉLØ — SQPE Mid-Price Specialist (LAB_EXPERIMENT, additive, not live)
========================================================================
Old VELO and No-RPR shadow tie exactly at 24.0% top-1 SR in the mid-priced
band (winner SP 3.0-10.0 decimal) on the 1,442-race model comparison
ledger -- both models are dominated by RPR/market-consensus features that
have nothing extra to say once the market itself is already split. This
trains a model on ONLY mid-priced races, doctrine-clean (no RPR, no final
SP/market fields), to test whether narrowing both the training population
and the feature set produces real lift specifically in the band that's
actually costing money.

Does NOT touch Old VELO, No-RPR shadow, New Build, or Champion Intent.
Not wired into any scoring path. Follows the sqpe_v18 LAB_EXPERIMENT
pattern: report, do not auto-promote.

Usage:
    python scripts/ops/train_sqpe_midprice_specialist.py
    python scripts/ops/train_sqpe_midprice_specialist.py --sample 300000
"""
import argparse
import json
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
FEATURES_PARQUET = ROOT / "data" / "raceform_v17_features.parquet"
STAGING_DIR = ROOT / "models" / "sqpe_v17_midprice_specialist_staging"

MID_PRICE_LOW, MID_PRICE_HIGH = 3.0, 10.0  # decimal SP band, matches sigma's own miss classifier

# Same doctrine-clean feature set as the no-RPR shadow model, for consistency.
BANNED = {
    "rpr_num", "rpr_vs_field", "ts_num",
    "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
    "odds_resilience_score", "odds_contraction_score",
    "decoy_support_flag", "runs_since_mkt_support",
}
SPECIALIST_FEATURES = [
    "dist_f", "going_code", "is_aw", "class_num", "wgt_lbs",
    "or_num", "or_vs_field",
    "field_size", "draw_num", "draw_pct", "age_num",
    "runs_since_win", "runs_since_place",
    "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "mark_compression_score", "release_window_score",
    "course_fit_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "setup_run_flag", "cash_run_flag",
]


def _race_metrics(df, prob_col, target_col="target"):
    top1_hits = mrr_sum = races = 0
    for _, grp in df.groupby("race_id"):
        if len(grp) < 2:
            continue
        races += 1
        ranked = grp.sort_values(prob_col, ascending=False).reset_index(drop=True)
        winner_pos = ranked.index[ranked[target_col] == 1]
        if len(winner_pos) == 0:
            continue
        rank = int(winner_pos[0]) + 1
        if rank == 1:
            top1_hits += 1
        mrr_sum += 1.0 / rank
    top1 = top1_hits / races if races else 0.0
    mrr = mrr_sum / races if races else 0.0
    return round(top1, 4), round(mrr, 4), races


def tag_mid_price_races(df: pd.DataFrame) -> pd.Series:
    """Return a boolean Series (indexed like df) marking every ROW belonging
    to a race whose actual winner's SP fell in the mid-price band."""
    winner_sp = (
        df[df["target"] == 1]
        .groupby("race_id")["sp_dec"]
        .first()
    )
    mid_race_ids = winner_sp[(winner_sp > MID_PRICE_LOW) & (winner_sp <= MID_PRICE_HIGH)].index
    return df["race_id"].isin(mid_race_ids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=str(FEATURES_PARQUET))
    ap.add_argument("--sample", type=int, default=None)
    args = ap.parse_args()

    print("=" * 65)
    print("VELO — SQPE Mid-Price Specialist (LAB_EXPERIMENT)")
    print(f"  Band: SP {MID_PRICE_LOW}-{MID_PRICE_HIGH} decimal")
    print(f"  Banned features: {sorted(BANNED)}")
    print(f"  Specialist features: {len(SPECIALIST_FEATURES)}")
    print("=" * 65)

    leaked = [f for f in SPECIALIST_FEATURES if f in BANNED]
    if leaked:
        raise AssertionError(f"LEAKAGE: {leaked} found in SPECIALIST_FEATURES")
    print("Leakage check: PASS")

    print("\nLoading features parquet ...")
    df = pd.read_parquet(args.features)
    if not pd.api.types.is_datetime64_any_dtype(df["date_parsed"]):
        df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
    numeric_pos = pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce")
    df = df[numeric_pos.notna()].copy()
    print(f"  {len(df):,} rows after removing non-starters")

    if args.sample:
        df = df.sample(n=min(args.sample, len(df)), random_state=42).copy()

    df = df.sort_values("date_parsed").reset_index(drop=True)
    train_all = df[df["date_parsed"].dt.year < 2025].copy()
    test_all = df[df["date_parsed"].dt.year >= 2025].copy()

    mid_mask_train = tag_mid_price_races(train_all)
    mid_mask_test = tag_mid_price_races(test_all)
    train_df = train_all[mid_mask_train].copy()
    test_df = test_all[mid_mask_test].copy()

    n_races_train = train_df["race_id"].nunique()
    n_races_test = test_df["race_id"].nunique()
    print(f"\nMid-price races -- train: {n_races_train:,} ({len(train_df):,} rows)  "
          f"test: {n_races_test:,} ({len(test_df):,} rows)")
    print(f"(out of {train_all['race_id'].nunique():,} / {test_all['race_id'].nunique():,} total races)")

    y_tr = train_df["target"]
    y_te = test_df["target"]

    X_tr = train_df[SPECIALIST_FEATURES].fillna(0)
    X_te = test_df[SPECIALIST_FEATURES].fillna(0)

    gbm_params = dict(
        n_estimators=500, learning_rate=0.04, max_depth=5,
        min_samples_leaf=50, subsample=0.8, max_features="sqrt",
        random_state=42, verbose=1,
    )

    print(f"\nTraining mid-price specialist ({len(SPECIALIST_FEATURES)} features, "
          f"{len(train_df):,} rows) ...")
    model = CalibratedClassifierCV(GradientBoostingClassifier(**gbm_params), method="isotonic", cv=3)
    model.fit(X_tr, y_tr)

    p_te = model.predict_proba(X_te)[:, 1]
    auc = roc_auc_score(y_te, p_te)
    ll = log_loss(y_te, p_te)
    test_df = test_df.copy()
    test_df["pred"] = p_te
    top1, mrr, n_races_eval = _race_metrics(test_df, "pred")

    # Comparators, same mid-price test population:
    or_top1, or_mrr, _ = _race_metrics(
        test_df.assign(pred_or=test_df["or_vs_field"].fillna(0)), "pred_or"
    )

    print("\n" + "=" * 65)
    print("RESULTS (mid-price test races only)")
    print("=" * 65)
    print(f"  Specialist model : AUC={auc:.4f}  Top-1={top1*100:.1f}%  MRR={mrr:.4f}  n={n_races_eval}")
    print(f"  OR-rank baseline : Top-1={or_top1*100:.1f}%  MRR={or_mrr:.4f}")
    print("  Old VELO (live)  : Top-1=24.0% (from 1,442-race ledger, mid-price slice, separate eval)")
    print("  No-RPR shadow    : Top-1=24.0% (from 1,442-race ledger, mid-price slice, separate eval)")

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    with open(STAGING_DIR / "sqpe_v17_midprice_specialist.pkl", "wb") as f:
        pickle.dump(model, f)

    base_est = model.calibrated_classifiers_[0]
    base = base_est.estimator if hasattr(base_est, "estimator") else base_est.base_estimator
    importances = sorted(zip(SPECIALIST_FEATURES, base.feature_importances_), key=lambda x: -x[1])
    pd.DataFrame(importances, columns=["feature", "importance"]).to_csv(
        STAGING_DIR / "feature_importance.csv", index=False
    )

    metadata = {
        "version": "v1-midprice-specialist",
        "classification": "LAB_EXPERIMENT",
        "model_type": "GradientBoostingClassifier + IsotonicCalibration",
        "trained_at": datetime.now().isoformat(),
        "source": str(args.features),
        "mid_price_band": [MID_PRICE_LOW, MID_PRICE_HIGH],
        "train_races": n_races_train,
        "test_races": n_races_test,
        "banned_features": sorted(BANNED),
        "specialist_features": SPECIALIST_FEATURES,
        "results": {
            "auc": round(float(auc), 4),
            "log_loss": round(float(ll), 4),
            "top1": top1,
            "mrr": mrr,
            "or_baseline_top1": or_top1,
            "old_velo_midprice_top1_reference": 0.24,
            "no_rpr_midprice_top1_reference": 0.24,
        },
        "promotion_status": "NOT_PROMOTED — LAB_EXPERIMENT only, requires n>=100 evidence gate + operator sign-off",
        "not_wired_to": ["run_prime_today.py", "run_radical_shadow_today.py", "new_build_two_lane_score.py",
                          "build_current_card_intent_features.py"],
    }
    (STAGING_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))

    print(f"\nWritten: {STAGING_DIR}/")
    print("Feature importance:")
    for feat, imp in importances[:10]:
        print(f"  {feat:25s} {imp:.4f}")


if __name__ == "__main__":
    main()
