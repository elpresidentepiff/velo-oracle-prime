#!/usr/bin/env python3
"""
VÉLØ — SQPE No-RPR Retrain
============================
Removes ALL Racing Post performance ratings (RPR, TS) and ALL final SP
from the feature set. Tests whether a year of doctrine feature engineering
produces a model that beats an OR-rank baseline without relying on RP's
own ratings or post-race market prices.

Three models trained on the same split, evaluated head-to-head:
  - OR baseline     : or_vs_field only (what a punter with a form book can do)
  - No-RPR model    : 26 features — OR + form + doctrine, zero RPR, zero SP
  - Reference prod  : 37-feature production model (RPR+SP included, reference only)

Train: year < 2025  |  Test: year >= 2025  (identical split to v17.1 production)

Usage:
    python scripts/ops/retrain_sqpe_no_rpr.py
    python scripts/ops/retrain_sqpe_no_rpr.py --sample 300000   # quick dev
    python scripts/ops/retrain_sqpe_no_rpr.py --promote          # write to production
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
STAGING_DIR      = ROOT / "models" / "sqpe_v17_no_rpr_staging"
PRODUCTION_MODEL = ROOT / "models" / "sqpe_v17" / "sqpe_v17.pkl"

# ── Features removed: RPR, TS, final SP, and all SP-derived doctrine features ──
RPR_BANNED   = {"rpr_num", "rpr_vs_field"}
SP_BANNED    = {"sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav"}
SP_DOCTRINE  = {"odds_resilience_score", "odds_contraction_score",
                "decoy_support_flag", "runs_since_mkt_support"}
TS_BANNED    = {"ts_num"}

ALL_BANNED = RPR_BANNED | SP_BANNED | SP_DOCTRINE | TS_BANNED

# ── Feature sets ──────────────────────────────────────────────────────────────
OR_BASELINE_FEATURES = ["or_vs_field"]

NO_RPR_FEATURES = [
    # Race conditions
    "dist_f", "going_code", "is_aw", "class_num", "wgt_lbs",
    # OR metrics (not RPR)
    "or_num", "or_vs_field",
    # Field
    "field_size", "draw_num", "draw_pct", "age_num",
    # Doctrine — release/plot
    "runs_since_win", "runs_since_place",
    "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "mark_compression_score", "release_window_score",
    # Doctrine — fit
    "course_fit_score", "going_fit_score", "distance_fit_score",
    # Doctrine — intent
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    # Doctrine — execution
    "setup_run_flag", "cash_run_flag",
]

PRODUCTION_FEATURES = [
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
    mrr  = mrr_sum  / races if races else 0.0
    return round(top1, 4), round(mrr, 4), races


def _or_rank_baseline(df):
    """Top-1 rate when picking by highest or_vs_field (OR handicap rank)."""
    hits = races = 0
    for _, grp in df.groupby("race_id"):
        if len(grp) < 2 or "or_vs_field" not in grp.columns:
            continue
        races += 1
        if grp.sort_values("or_vs_field", ascending=False).iloc[0]["target"] == 1:
            hits += 1
    return round(hits / races, 4) if races else 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", default=str(FEATURES_PARQUET))
    parser.add_argument("--output",   default=str(STAGING_DIR))
    parser.add_argument("--sample",   type=int, default=None)
    parser.add_argument("--promote",  action="store_true",
                        help="Overwrite production model if no-RPR beats production AUC")
    args = parser.parse_args()

    print("=" * 65)
    print("VELO — SQPE No-RPR Retrain")
    print(f"  Banned features : {sorted(ALL_BANNED)}")
    print(f"  No-RPR features : {len(NO_RPR_FEATURES)}")
    print(f"  Source          : {args.features}")
    print("=" * 65)

    # ── Load ──────────────────────────────────────────────────────────────────
    print("\nLoading features parquet ...")
    df = pd.read_parquet(args.features)
    if not pd.api.types.is_datetime64_any_dtype(df["date_parsed"]):
        df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
    numeric_pos = pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce")
    df = df[numeric_pos.notna()].copy()
    print(f"  {len(df):,} rows after removing non-starters")

    if args.sample:
        df = df.sample(n=min(args.sample, len(df)), random_state=42).copy()
        print(f"  Sampled to {len(df):,} rows")

    # Verify no banned features leak into no-RPR set
    leaked = [f for f in NO_RPR_FEATURES if f in ALL_BANNED]
    if leaked:
        raise AssertionError(f"LEAKAGE: {leaked} found in NO_RPR_FEATURES")
    print(f"  Leakage check: PASS (0 banned features in no-RPR set)")

    # ── Temporal split ────────────────────────────────────────────────────────
    df = df.sort_values("date_parsed").reset_index(drop=True)
    train_df = df[df["date_parsed"].dt.year < 2025].copy()
    test_df  = df[df["date_parsed"].dt.year >= 2025].copy()
    print(f"\nTrain: {len(train_df):,}  Test: {len(test_df):,}")
    print(f"  Train: {train_df['date_parsed'].dt.year.min()} - "
          f"{train_df['date_parsed'].dt.year.max()}")
    print(f"  Test : {test_df['date_parsed'].dt.year.min()} - "
          f"{test_df['date_parsed'].dt.year.max()}")

    y_tr = train_df["target"]
    y_te = test_df["target"]
    print(f"\nWin rate  train: {y_tr.mean():.4f}  test: {y_te.mean():.4f}")

    # ── OR-rank baseline (no model needed) ───────────────────────────────────
    or_top1 = _or_rank_baseline(test_df)
    print(f"\nOR-rank baseline top-1: {or_top1 * 100:.1f}%  "
          f"(pick highest OR in every race)")

    # ── GBM hyperparams ──────────────────────────────────────────────────────
    gbm_params = dict(
        n_estimators=500, learning_rate=0.04, max_depth=5,
        min_samples_leaf=50, subsample=0.8, max_features="sqrt",
        random_state=42, verbose=1,
    )

    results = {}

    # ── Train OR baseline model (1 feature) ──────────────────────────────────
    print(f"\n{'-'*55}")
    print(f"Training OR baseline model (1 feature: or_vs_field) ...")
    X_or_tr = train_df[OR_BASELINE_FEATURES].fillna(0)
    X_or_te = test_df[OR_BASELINE_FEATURES].fillna(0)
    m_or = CalibratedClassifierCV(
        GradientBoostingClassifier(**gbm_params),
        method="isotonic", cv=3,
    )
    m_or.fit(X_or_tr, y_tr)
    p_or = m_or.predict_proba(X_or_te)[:, 1]
    auc_or = roc_auc_score(y_te, p_or)
    ll_or  = log_loss(y_te, p_or)
    test_df["pred_or"] = p_or
    top1_or, mrr_or, n_races = _race_metrics(test_df, "pred_or")
    results["or_model"] = dict(auc=auc_or, ll=ll_or, top1=top1_or, mrr=mrr_or)
    print(f"  AUC={auc_or:.4f}  Top-1={top1_or*100:.1f}%  MRR={mrr_or:.4f}")

    # ── Train No-RPR model (26 features) ─────────────────────────────────────
    print(f"\n{'-'*55}")
    print(f"Training No-RPR model ({len(NO_RPR_FEATURES)} features, zero RPR, zero SP) ...")
    X_nr_tr = train_df[NO_RPR_FEATURES].fillna(0)
    X_nr_te = test_df[NO_RPR_FEATURES].fillna(0)
    m_nr = CalibratedClassifierCV(
        GradientBoostingClassifier(**gbm_params),
        method="isotonic", cv=3,
    )
    m_nr.fit(X_nr_tr, y_tr)
    p_nr = m_nr.predict_proba(X_nr_te)[:, 1]
    auc_nr = roc_auc_score(y_te, p_nr)
    ll_nr  = log_loss(y_te, p_nr)
    test_df["pred_nr"] = p_nr
    top1_nr, mrr_nr, _ = _race_metrics(test_df, "pred_nr")
    results["no_rpr_model"] = dict(auc=auc_nr, ll=ll_nr, top1=top1_nr, mrr=mrr_nr)
    print(f"  AUC={auc_nr:.4f}  Top-1={top1_nr*100:.1f}%  MRR={mrr_nr:.4f}")

    # Feature importance breakdown for no-RPR model
    base_nr = m_nr.calibrated_classifiers_[0].estimator
    imp_nr = sorted(
        zip(NO_RPR_FEATURES, base_nr.feature_importances_), key=lambda x: -x[1]
    )

    # ── Reference: production model (RPR+SP included) ────────────────────────
    print(f"\n{'-'*55}")
    print(f"Evaluating production model ({len(PRODUCTION_FEATURES)} features, RPR+SP included) ...")
    prod_pkl = PRODUCTION_MODEL
    if prod_pkl.exists():
        m_prod = pickle.load(open(prod_pkl, "rb"))
        X_prod_te = test_df[PRODUCTION_FEATURES].fillna(0)
        p_prod = m_prod.predict_proba(X_prod_te)[:, 1]
        auc_prod = roc_auc_score(y_te, p_prod)
        ll_prod  = log_loss(y_te, p_prod)
        test_df["pred_prod"] = p_prod
        top1_prod, mrr_prod, _ = _race_metrics(test_df, "pred_prod")
        results["production_model"] = dict(auc=auc_prod, ll=ll_prod,
                                           top1=top1_prod, mrr=mrr_prod)
        print(f"  AUC={auc_prod:.4f}  Top-1={top1_prod*100:.1f}%  MRR={mrr_prod:.4f}")
    else:
        print("  Production model not found, skipping reference")
        results["production_model"] = None

    # ── Head-to-head summary ──────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print(f"  {'Model':<28} {'AUC':>7} {'LogLoss':>9} {'Top-1':>7} {'MRR':>7}")
    print(f"  {'-' * 62}")
    print(f"  {'OR-rank (naive)':28}  {'—':>7}  {'—':>9}  {or_top1*100:>6.1f}%  {'—':>7}")
    print(f"  {'OR baseline model (1 feat)':28}  "
          f"{results['or_model']['auc']:>7.4f}  "
          f"{results['or_model']['ll']:>9.4f}  "
          f"{results['or_model']['top1']*100:>6.1f}%  "
          f"{results['or_model']['mrr']:>7.4f}")
    print(f"  {'No-RPR model (26 feat)':28}  "
          f"{results['no_rpr_model']['auc']:>7.4f}  "
          f"{results['no_rpr_model']['ll']:>9.4f}  "
          f"{results['no_rpr_model']['top1']*100:>6.1f}%  "
          f"{results['no_rpr_model']['mrr']:>7.4f}")
    if results.get("production_model"):
        print(f"  {'Production (37 feat, RPR+SP)':28}  "
              f"{results['production_model']['auc']:>7.4f}  "
              f"{results['production_model']['ll']:>9.4f}  "
              f"{results['production_model']['top1']*100:>6.1f}%  "
              f"{results['production_model']['mrr']:>7.4f}")
    print(f"{'=' * 65}")

    # Verdict
    lift_vs_or_model = results["no_rpr_model"]["top1"] - results["or_model"]["top1"]
    lift_vs_or_naive = results["no_rpr_model"]["top1"] - or_top1
    print(f"\nDoctrine lift vs OR-rank naive   : {lift_vs_or_naive*100:+.2f} ppts top-1")
    print(f"Doctrine lift vs OR model (1-feat): {lift_vs_or_model*100:+.2f} ppts top-1")

    if lift_vs_or_model > 0.005:
        verdict = "DOCTRINE FEATURES PROVEN — significant lift over OR baseline"
    elif lift_vs_or_model > 0.0:
        verdict = "MARGINAL LIFT — doctrine features help but narrowly"
    else:
        verdict = "NO LIFT — doctrine features do not beat OR baseline alone"
    print(f"\nVerdict: {verdict}")

    # Feature importance for no-RPR model
    print(f"\nNo-RPR model — top 15 features:")
    for feat, val in imp_nr[:15]:
        print(f"  {feat:<35} {val:.4f}")

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = out_dir / "sqpe_v17_no_rpr.pkl"
    with open(model_path, "wb") as fh:
        pickle.dump(m_nr, fh)

    metadata = {
        "version": "v17.2-no-rpr",
        "model_type": "GradientBoostingClassifier + IsotonicCalibration",
        "trained_at": datetime.utcnow().isoformat(),
        "source": str(args.features),
        "banned_features": sorted(ALL_BANNED),
        "no_rpr_features": NO_RPR_FEATURES,
        "n_features": len(NO_RPR_FEATURES),
        "train_rows": int(len(X_nr_tr)),
        "test_rows": int(len(X_nr_te)),
        "test_races": n_races,
        "metrics": {
            "or_naive_top1": or_top1,
            "or_model": results["or_model"],
            "no_rpr_model": results["no_rpr_model"],
            "production_model": results.get("production_model"),
        },
        "doctrine_lift_vs_or_model_top1": round(lift_vs_or_model, 4),
        "doctrine_lift_vs_or_naive_top1": round(lift_vs_or_naive, 4),
        "verdict": verdict,
        "top_15_features": [{"feature": f, "importance": round(v, 4)}
                            for f, v in imp_nr[:15]],
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    pd.DataFrame(imp_nr, columns=["feature", "importance"]).to_csv(
        out_dir / "feature_importance.csv", index=False
    )

    print(f"\nStaging model : {model_path}")
    print(f"Metadata      : {out_dir / 'metadata.json'}")

    # ── Promote if requested and if no-RPR model is good enough ──────────────
    if args.promote:
        prod_dir = PRODUCTION_MODEL.parent
        prod_dir.mkdir(parents=True, exist_ok=True)
        dest = prod_dir / "sqpe_v17.pkl"
        shutil.copy2(model_path, dest)
        meta_dest = prod_dir / "metadata.json"
        metadata["promoted_at"] = datetime.utcnow().isoformat()
        meta_dest.write_text(json.dumps(metadata, indent=2))
        print(f"\nPROMOTED (no-RPR model) -> {dest}")
    else:
        print(f"\nTo promote: python {Path(__file__).name} --promote")

    print(f"\n{'=' * 65}")
    print(f"DONE  AUC={auc_nr:.4f}  Top-1={top1_nr*100:.1f}%  Verdict: {verdict}")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    main()
