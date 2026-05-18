#!/usr/bin/env python3.11
"""
RUNNER_MASTER_SHADOW_MODEL_V1
==================================
Train three shadow models on runner_master_training_dataset_latest.parquet.

Governance:
  NO_SCORING_CHANGE | NO_MODEL_PROMOTION | NO_ROUTER_CHANGE
  NO_STAKING_CHANGE | NO_LIVE_STATE_MUTATION

Models:
  A — Logistic Regression
  B — LightGBM (gradient boosting)
  C — Rank ensemble (average of A + B probs)

Feature whitelist (user-approved, no SP, no post-race leakage):
  velo_prime_prob, trainer_jockey_sr, tj_high_today20_flag,
  current_or (→ ofr_api), or_drop_from_peak, ts_slope_6, or_slope_6,
  rpr_slope_6, ts_vs_or_gap, class_num, is_flat, is_jumps, field_size,
  mds_high_flag, dist_band_f

Hard exclusions (leakage / post-race / governance):
  sp_decimal, actual_sp, profit_loss_1pt, result_position, won, placed,
  silent_improver_flag, rating_rebound_flag, exposed_regression_flag

Mission: Can VP + TJ_TOP20 + current_or + last-six scalar trends beat VP alone?

Outputs:
  data/models/runner_master_shadow_model_v1.pkl
  data/reports/runner_master_shadow_model_v1_latest.json
  data/reports/runner_master_shadow_model_v1_latest.md
  data/training/runner_master_shadow_predictions_latest.parquet
"""

import json
import pickle
import warnings
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
TRAINING_PATH = ROOT / "data" / "training" / "runner_master_training_dataset_latest.parquet"
MODEL_DIR = ROOT / "data" / "models"
REPORT_DIR = ROOT / "data" / "reports"
PRED_PATH = ROOT / "data" / "training" / "runner_master_shadow_predictions_latest.parquet"

MODEL_DIR.mkdir(parents=True, exist_ok=True)

GOVERNANCE = "NO_SCORING_CHANGE | NO_MODEL_PROMOTION | NO_ROUTER_CHANGE | NO_STAKING_CHANGE | NO_LIVE_STATE_MUTATION"
QUARANTINE = "SHADOW_QUARANTINE — not wired to scoring, router, or staking"

# ─── Feature mapping ──────────────────────────────────────────────────────────

# Map user-facing names to actual dataset column names
FEATURE_MAP = {
    "velo_prime_prob":       "velo_prime_prob",
    "trainer_jockey_sr":     "trainer_jockey_sr",
    "tj_high_today20_flag":  "_tj_high_today20",    # derived below
    "current_or":            "ofr_api",
    "or_drop_from_peak":     "or_drop_from_peak",
    "ts_slope_6":            "ts_slope_6",
    "or_slope_6":            "or_slope_6",
    "rpr_slope_6":           "rpr_slope_6",
    "ts_vs_or_gap":          "ts_vs_or_gap",
    "class_num":             "class_num",
    "is_flat":               "is_flat",             # race_type substitute (race_type 98% null)
    "is_jumps":              "is_jumps",
    "field_size":            "field_size",
    "mds_high_flag":         "mds_high_flag",
    "dist_band_f":           "dist_band_f",
}

# Hard-excluded columns (leakage / post-race)
HARD_EXCLUDE = {
    "sp_decimal", "actual_sp", "profit_loss_1pt", "result_position",
    "won", "placed", "silent_improver_flag", "rating_rebound_flag",
    "exposed_regression_flag",
}

TARGETS = ["won", "placed", "profit_loss_1pt"]
TARGET_WIN = "won"

# ─── Null imputation strategy ─────────────────────────────────────────────────
# trainer_jockey_sr → 0 (unknown partnership = neutral, not average)
# slope features → 0 (no trend = neutral)
# or_drop_from_peak → 0 (no drop = neutral)
# ts_vs_or_gap → train median
# ofr_api → train median
# class_num → 0 (unknown class)
# field_size → train median
# bool flags → False

IMPUTE_ZERO = {
    "trainer_jockey_sr", "ts_slope_6", "or_slope_6", "rpr_slope_6",
    "or_drop_from_peak", "_tj_high_today20", "class_num",
}
IMPUTE_MEDIAN = {"ofr_api", "ts_vs_or_gap", "field_size"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_int(val) -> int | None:
    try:
        v = int(val)
        return v if not np.isnan(v) else None
    except Exception:
        return None


class _NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):   return int(obj)
        if isinstance(obj, (np.floating,)):  return float(obj)
        if isinstance(obj, (np.bool_,)):     return bool(obj)
        return super().default(obj)


def _roi(mask: pd.Series, sp: pd.Series, won: pd.Series) -> float:
    n = mask.sum()
    if n == 0:
        return float("nan")
    pl = np.where(won[mask], sp[mask] - 1, -1.0)
    return float(pl.mean())


def _wr(mask: pd.Series, won: pd.Series) -> float:
    n = mask.sum()
    if n == 0:
        return float("nan")
    return float(won[mask].mean())


def _strip_top_winner_roi(probs: np.ndarray, won: np.ndarray, sp: np.ndarray, n_strip: int = 1) -> float:
    """Remove highest-prob winner, re-compute ROI — tests if returns concentrate on one horse."""
    idx = np.argsort(probs)[::-1]
    win_indices = np.where(won == 1)[0]
    if len(win_indices) == 0:
        return float("nan")
    # find top-prob winner
    for i in idx:
        if won[i] == 1:
            mask = np.ones(len(probs), dtype=bool)
            mask[i] = False
            pl = np.where(won[mask], sp[mask] - 1, -1.0)
            return float(pl.mean()) if mask.sum() > 0 else float("nan")
    return float("nan")


def _decile_analysis(probs: np.ndarray, won: np.ndarray, sp: np.ndarray, n_deciles: int = 10) -> list[dict]:
    df = pd.DataFrame({"prob": probs, "won": won, "sp": sp})
    df["decile"] = pd.qcut(df["prob"], n_deciles, labels=False, duplicates="drop")
    rows = []
    for d, g in df.groupby("decile"):
        pl = np.where(g["won"], g["sp"] - 1, -1.0)
        rows.append({
            "decile": int(d) + 1,
            "n": len(g),
            "win_rate": round(g["won"].mean(), 4),
            "roi": round(pl.mean(), 4),
            "prob_min": round(g["prob"].min(), 4),
            "prob_max": round(g["prob"].max(), 4),
        })
    return rows


def _sp_band_diagnostics(probs: np.ndarray, won: np.ndarray, sp: np.ndarray) -> list[dict]:
    bands = [
        ("EW_SP_under_3", sp < 3.0),
        ("SP_3_to_6",     (sp >= 3.0) & (sp < 6.0)),
        ("SP_6_to_10",    (sp >= 6.0) & (sp < 10.0)),
        ("SP_10_plus",    sp >= 10.0),
    ]
    rows = []
    for label, mask in bands:
        if mask.sum() == 0:
            continue
        top_mask = mask & (probs >= np.quantile(probs[mask], 0.80))
        pl_all   = np.where(won[mask], sp[mask] - 1, -1.0)
        pl_top   = np.where(won[top_mask], sp[top_mask] - 1, -1.0) if top_mask.sum() > 0 else np.array([])
        rows.append({
            "band": label,
            "n": int(mask.sum()),
            "win_rate": round(won[mask].mean(), 4),
            "roi_all": round(pl_all.mean(), 4),
            "n_top20pct": int(top_mask.sum()),
            "roi_top20pct": round(pl_top.mean(), 4) if len(pl_top) > 0 else None,
        })
    return rows


def _calibration_audit(probs: np.ndarray, won: np.ndarray, n_bins: int = 5) -> dict:
    brier = float(brier_score_loss(won, probs))
    df = pd.DataFrame({"prob": probs, "won": won})
    df["bin"] = pd.cut(df["prob"], bins=n_bins, labels=False)
    bins = []
    for b, g in df.groupby("bin"):
        bins.append({
            "bin": int(b),
            "mean_prob": round(g["prob"].mean(), 4),
            "actual_wr": round(g["won"].mean(), 4),
            "n": len(g),
        })
    return {"brier_score": brier, "bins": bins}


def _return_concentration(probs: np.ndarray, won: np.ndarray, sp: np.ndarray) -> dict:
    """Gini of P&L across deciles — high Gini means returns concentrated in top band."""
    deciles = np.array_split(np.argsort(probs)[::-1], 10)
    pl_by_decile = []
    for dec in deciles:
        pl = np.where(won[dec], sp[dec] - 1, -1.0)
        pl_by_decile.append(float(pl.sum()))
    total = sum(pl_by_decile)
    if total == 0:
        return {"gini": None, "top_decile_pct_of_pl": None}
    cumul = np.cumsum(pl_by_decile)
    xs = np.linspace(0, 1, len(cumul))
    gini = float(1 - 2 * np.trapezoid(cumul / total, xs))
    top_pct = pl_by_decile[0] / total if total != 0 else None
    return {
        "gini": round(gini, 4),
        "top_decile_pct_of_pl": round(top_pct, 4) if top_pct is not None else None,
        "pl_by_decile": [round(x, 4) for x in pl_by_decile],
    }


def _evaluate_model(name: str, probs: np.ndarray, won: np.ndarray,
                    sp: np.ndarray, placed: np.ndarray) -> dict:
    auc = float(roc_auc_score(won, probs))
    # top decile
    thresh = np.quantile(probs, 0.90)
    top_mask = probs >= thresh
    top_wr   = _wr(pd.Series(top_mask), pd.Series(won))
    top_roi  = _roi(pd.Series(top_mask), pd.Series(sp), pd.Series(won))
    baseline_wr = float(won.mean())
    top_lift = top_wr - baseline_wr
    # strip-top-winner
    strip_roi = _strip_top_winner_roi(probs, won, sp)
    # full-field ROI at top decile
    deciles  = _decile_analysis(probs, won, sp)
    sp_bands = _sp_band_diagnostics(probs, won, sp)
    calib    = _calibration_audit(probs, won)
    conc     = _return_concentration(probs, won, sp)
    # top-20% placed ROI
    thresh20 = np.quantile(probs, 0.80)
    top20_mask = probs >= thresh20
    placed_roi_top20 = _roi(pd.Series(top20_mask), pd.Series(sp), pd.Series(placed))
    return {
        "model": name,
        "n_test": int(len(won)),
        "n_winners": int(won.sum()),
        "baseline_wr": round(baseline_wr, 4),
        "auc": round(auc, 4),
        "top_decile_wr": round(top_wr, 4),
        "top_decile_lift": round(top_lift, 4),
        "top_decile_roi": round(top_roi, 4),
        "strip_top_winner_roi": round(strip_roi, 4) if not np.isnan(strip_roi) else None,
        "placed_roi_top20pct": round(placed_roi_top20, 4) if not np.isnan(placed_roi_top20) else None,
        "calibration": calib,
        "return_concentration": conc,
        "decile_breakdown": deciles,
        "sp_band_diagnostics": sp_bands,
    }


# ─── Build features ──────────────────────────────────────────────────────────

def build_feature_matrix(df: pd.DataFrame, impute_vals: dict | None,
                          tj_p80: float | None) -> tuple[pd.DataFrame, dict]:
    """
    Build feature matrix from df.
    If impute_vals is None, compute from df (training set mode).
    If tj_p80 is None, compute from df (training set mode).
    Returns (X, impute_vals_computed).
    """
    X = pd.DataFrame(index=df.index)

    # Derive TJ_HIGH_TODAY20
    if tj_p80 is None:
        tj_p80 = float(df["trainer_jockey_sr"].quantile(0.80))
    X["_tj_high_today20"] = (
        df["trainer_jockey_sr"].notna() &
        (df["trainer_jockey_sr"] >= tj_p80)
    ).astype(float)

    # Copy raw cols
    raw_cols = [
        "velo_prime_prob", "trainer_jockey_sr", "ofr_api",
        "or_drop_from_peak", "ts_slope_6", "or_slope_6", "rpr_slope_6",
        "ts_vs_or_gap", "class_num", "is_flat", "is_jumps",
        "field_size", "mds_high_flag", "dist_band_f",
    ]
    for c in raw_cols:
        if c in df.columns:
            X[c] = df[c].values
        else:
            X[c] = np.nan

    # Convert bools to float
    for c in ["is_flat", "is_jumps", "mds_high_flag"]:
        X[c] = X[c].astype(float)

    # Compute imputation values from training data
    computed_impute = {}
    for c in IMPUTE_ZERO:
        computed_impute[c] = 0.0
    for c in IMPUTE_MEDIAN:
        computed_impute[c] = float(X[c].median()) if X[c].notna().any() else 0.0

    use_impute = impute_vals if impute_vals is not None else computed_impute

    # Apply imputation
    for c, val in use_impute.items():
        if c in X.columns:
            X[c] = X[c].fillna(val)

    # Remaining nulls → 0
    X = X.fillna(0.0)

    # Leakage check
    for exc in HARD_EXCLUDE:
        assert exc not in X.columns, f"LEAKAGE: {exc} in feature matrix"

    return X, (computed_impute if impute_vals is None else use_impute), tj_p80


def get_feature_cols() -> list[str]:
    return [
        "_tj_high_today20", "velo_prime_prob", "trainer_jockey_sr",
        "ofr_api", "or_drop_from_peak", "ts_slope_6", "or_slope_6",
        "rpr_slope_6", "ts_vs_or_gap", "class_num", "is_flat",
        "is_jumps", "field_size", "mds_high_flag", "dist_band_f",
    ]


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("RUNNER_MASTER_SHADOW_MODEL_V1 — " + str(date.today()))
    print("=" * 62)
    print(f"Governance: {GOVERNANCE}")
    print(f"Status: {QUARANTINE}")
    print()

    # ── Load ─────────────────────────────────────────────────────────────────
    df = pd.read_parquet(TRAINING_PATH)
    print(f"Dataset: {len(df)} rows | {df['won'].sum()} winners | WR={df['won'].mean():.2%}")

    # ── Rolling date split ────────────────────────────────────────────────────
    dates_sorted = sorted(df["date"].unique())
    n_dates = len(dates_sorted)
    split_idx = int(n_dates * 0.70)
    cutoff_date = dates_sorted[split_idx]

    train_mask = df["date"] < cutoff_date
    test_mask  = df["date"] >= cutoff_date

    df_train = df[train_mask].copy().reset_index(drop=True)
    df_test  = df[test_mask].copy().reset_index(drop=True)

    print(f"Rolling split at {cutoff_date}: train={len(df_train)} ({df_train['won'].mean():.2%} WR) "
          f"| test={len(df_test)} ({df_test['won'].mean():.2%} WR)")
    print(f"Train dates: {dates_sorted[0]} → {dates_sorted[split_idx-1]}")
    print(f"Test dates:  {cutoff_date} → {dates_sorted[-1]}")
    print()

    # ── Build feature matrices ────────────────────────────────────────────────
    X_train, impute_vals, tj_p80 = build_feature_matrix(df_train, None, None)
    X_test,  _,           _      = build_feature_matrix(df_test, impute_vals, tj_p80)

    print(f"TJ_HIGH_TODAY20 threshold (train p80): {tj_p80:.4f}")
    n_tj_high_train = int((X_train["_tj_high_today20"] == 1).sum())
    n_tj_high_test  = int((X_test["_tj_high_today20"] == 1).sum())
    print(f"TJ_HIGH flagged — train: {n_tj_high_train}/{len(df_train)} ({100*n_tj_high_train/len(df_train):.1f}%)")
    print(f"TJ_HIGH flagged — test:  {n_tj_high_test}/{len(df_test)} ({100*n_tj_high_test/len(df_test):.1f}%)")
    print()

    FEATURE_COLS = get_feature_cols()
    X_tr = X_train[FEATURE_COLS].values
    X_te = X_test[FEATURE_COLS].values
    y_tr = df_train["won"].astype(int).values
    y_te = df_test["won"].astype(int).values
    sp_te = df_test["actual_sp"].fillna(df_test["sp_decimal"]).fillna(10.0).values
    placed_te = df_test["placed"].astype(int).values

    # ── VP Baseline ───────────────────────────────────────────────────────────
    print("Computing VP baseline (velo_prime_prob alone)...")
    vp_probs = df_test["velo_prime_prob"].values
    baseline_eval = _evaluate_model("VP_BASELINE", vp_probs, y_te, sp_te, placed_te)
    print(f"  VP AUC={baseline_eval['auc']:.4f} | top-decile lift={baseline_eval['top_decile_lift']:+.4f} "
          f"| top-decile ROI={baseline_eval['top_decile_roi']:+.4f}")
    print()

    # ── Model A: Logistic Regression ─────────────────────────────────────────
    print("Training Model A: Logistic Regression...")
    scaler = StandardScaler()
    X_tr_scaled = scaler.fit_transform(X_tr)
    X_te_scaled = scaler.transform(X_te)

    lr = LogisticRegression(
        C=0.5,
        class_weight="balanced",
        max_iter=500,
        random_state=42,
        solver="lbfgs",
    )
    lr.fit(X_tr_scaled, y_tr)
    probs_a_train = lr.predict_proba(X_tr_scaled)[:, 1]
    probs_a_test  = lr.predict_proba(X_te_scaled)[:, 1]
    eval_a = _evaluate_model("Model_A_LogReg", probs_a_test, y_te, sp_te, placed_te)
    print(f"  LogReg AUC={eval_a['auc']:.4f} | top-decile lift={eval_a['top_decile_lift']:+.4f} "
          f"| top-decile ROI={eval_a['top_decile_roi']:+.4f}")

    # Logistic feature weights
    lr_coefs = dict(zip(FEATURE_COLS, [round(float(c), 4) for c in lr.coef_[0]]))

    # ── Model B: LightGBM ────────────────────────────────────────────────────
    print("Training Model B: LightGBM...")
    lgb_train = lgb.Dataset(X_tr, label=y_tr)
    lgb_params = {
        "objective":        "binary",
        "metric":           "auc",
        "learning_rate":    0.05,
        "num_leaves":       16,
        "min_data_in_leaf": 20,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq":     5,
        "lambda_l1":        0.1,
        "lambda_l2":        0.1,
        "verbose":          -1,
        "seed":             42,
    }
    lgb_model = lgb.train(
        lgb_params,
        lgb_train,
        num_boost_round=200,
        valid_sets=[lgb_train],
        callbacks=[lgb.log_evaluation(period=-1)],
    )
    probs_b_train = lgb_model.predict(X_tr)
    probs_b_test  = lgb_model.predict(X_te)
    eval_b = _evaluate_model("Model_B_LightGBM", probs_b_test, y_te, sp_te, placed_te)
    print(f"  LightGBM AUC={eval_b['auc']:.4f} | top-decile lift={eval_b['top_decile_lift']:+.4f} "
          f"| top-decile ROI={eval_b['top_decile_roi']:+.4f}")

    # LightGBM feature importance (gain)
    lgb_importance = {
        FEATURE_COLS[i]: round(float(v), 2)
        for i, v in enumerate(lgb_model.feature_importance(importance_type="gain"))
    }

    # ── Model C: Rank Ensemble ────────────────────────────────────────────────
    print("Computing Model C: rank ensemble (avg A + B)...")
    probs_c_test = (probs_a_test + probs_b_test) / 2.0
    eval_c = _evaluate_model("Model_C_Ensemble", probs_c_test, y_te, sp_te, placed_te)
    print(f"  Ensemble  AUC={eval_c['auc']:.4f} | top-decile lift={eval_c['top_decile_lift']:+.4f} "
          f"| top-decile ROI={eval_c['top_decile_roi']:+.4f}")
    print()

    # ── Verdict ───────────────────────────────────────────────────────────────
    def _verdict(ev: dict, baseline: dict) -> str:
        auc_beats  = ev["auc"] > baseline["auc"]
        roi_beats  = ev["top_decile_roi"] > baseline["top_decile_roi"]
        strip_ok   = ev["strip_top_winner_roi"] is not None and ev["strip_top_winner_roi"] > -0.30
        if auc_beats and roi_beats and strip_ok:
            return "PASS_QUARANTINE"
        if auc_beats and roi_beats:
            return "PASS_STRIP_RISK"
        if auc_beats:
            return "AUC_ONLY"
        return "FAIL"

    verdict_a = _verdict(eval_a, baseline_eval)
    verdict_b = _verdict(eval_b, baseline_eval)
    verdict_c = _verdict(eval_c, baseline_eval)

    print("── Verdict Summary ─────────────────────────────────────────")
    print(f"  VP Baseline:  AUC={baseline_eval['auc']:.4f}  top-decile ROI={baseline_eval['top_decile_roi']:+.4f}")
    print(f"  Model A:      {verdict_a}")
    print(f"  Model B:      {verdict_b}")
    print(f"  Model C:      {verdict_c}")
    print()

    # Best model: prefer PASS_QUARANTINE, then PASS_STRIP_RISK, then AUC_ONLY, then highest AUC
    VERDICT_RANK = {"PASS_QUARANTINE": 0, "PASS_STRIP_RISK": 1, "AUC_ONLY": 2, "FAIL": 3}
    models_ranked = sorted(
        [(eval_a, probs_a_test, "A_LogReg", verdict_a),
         (eval_b, probs_b_test, "B_LightGBM", verdict_b),
         (eval_c, probs_c_test, "C_Ensemble", verdict_c)],
        key=lambda x: (VERDICT_RANK.get(x[3], 9), -x[0]["auc"]),
    )
    best_ev, best_probs, best_name, best_verdict = models_ranked[0]

    # ── Save model artifact ───────────────────────────────────────────────────
    model_artifact = {
        "version": "RUNNER_MASTER_SHADOW_MODEL_V1",
        "trained_date": str(date.today()),
        "governance": GOVERNANCE,
        "status": QUARANTINE,
        "rolling_split_cutoff": cutoff_date,
        "tj_p80_train": tj_p80,
        "impute_vals": {k: float(v) for k, v in impute_vals.items()},
        "feature_cols": FEATURE_COLS,
        "model_a": {"type": "LogisticRegression", "scaler": scaler, "model": lr},
        "model_b": {"type": "LightGBM", "model": lgb_model},
        "model_c": {"type": "RankEnsemble", "weights": [0.5, 0.5]},
        "best_model": best_name,
    }
    pkl_path = MODEL_DIR / "runner_master_shadow_model_v1.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(model_artifact, f)
    print(f"Model artifact saved: {pkl_path}")

    # ── Save predictions parquet ─────────────────────────────────────────────
    pred_df = df_test[["date", "race_id", "horse_id", "horse", "course",
                        "off_time", "velo_prime_prob", "won", "placed",
                        "actual_sp", "sp_decimal"]].copy()
    pred_df["shadow_score_a"] = probs_a_test
    pred_df["shadow_score_b"] = probs_b_test
    pred_df["shadow_score_c"] = probs_c_test
    pred_df["shadow_best"] = best_probs
    pred_df["best_model"] = best_name
    pred_df["vp_rank"] = pred_df.groupby("race_id")["velo_prime_prob"].rank(ascending=False, method="min")
    pred_df["shadow_rank"] = pred_df.groupby("race_id")["shadow_best"].rank(ascending=False, method="min")
    pred_df.to_parquet(PRED_PATH, index=False)
    print(f"Predictions saved: {PRED_PATH}")

    # ── Build report ──────────────────────────────────────────────────────────
    report = {
        "generated": str(date.today()),
        "governance": GOVERNANCE,
        "status": QUARANTINE,
        "dataset": {
            "total_rows": len(df),
            "total_winners": int(df["won"].sum()),
            "baseline_wr": round(float(df["won"].mean()), 4),
        },
        "rolling_split": {
            "cutoff_date": cutoff_date,
            "n_train": len(df_train),
            "n_test":  len(df_test),
            "train_wr": round(float(df_train["won"].mean()), 4),
            "test_wr":  round(float(df_test["won"].mean()), 4),
            "train_dates": f"{dates_sorted[0]} to {dates_sorted[split_idx-1]}",
            "test_dates":  f"{cutoff_date} to {dates_sorted[-1]}",
        },
        "tj_threshold": {
            "train_p80": round(tj_p80, 4),
            "n_high_train": n_tj_high_train,
            "pct_covered_train": round(100 * n_tj_high_train / len(df_train), 1),
            "n_high_test": n_tj_high_test,
            "pct_covered_test": round(100 * n_tj_high_test / len(df_test), 1),
        },
        "feature_cols": FEATURE_COLS,
        "impute_strategy": {c: float(v) for c, v in impute_vals.items()},
        "vp_baseline": baseline_eval,
        "model_a": {**eval_a, "verdict": verdict_a, "feature_coefs": lr_coefs},
        "model_b": {**eval_b, "verdict": verdict_b, "feature_importance_gain": lgb_importance},
        "model_c": {**eval_c, "verdict": verdict_c},
        "best_model": {
            "name": best_name,
            "verdict": best_verdict,
            "auc": best_ev["auc"],
            "top_decile_roi": best_ev["top_decile_roi"],
            "beats_vp_auc": best_ev["auc"] > baseline_eval["auc"],
            "beats_vp_top_decile_roi": best_ev["top_decile_roi"] > baseline_eval["top_decile_roi"],
        },
        "mission_answer": (
            "YES — VP + TJ_TOP20 + current_or + last-six scalar trends beat VP alone"
            if best_ev["auc"] > baseline_eval["auc"] and best_ev["top_decile_roi"] > baseline_eval["top_decile_roi"]
            else "NO — model does not beat VP alone on both AUC and top-decile ROI"
        ),
    }

    # Save JSON
    json_path = REPORT_DIR / "runner_master_shadow_model_v1_latest.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, cls=_NpEncoder)
    print(f"JSON report: {json_path.name}")

    # ── Markdown report ───────────────────────────────────────────────────────
    def _fmt_row(label, val):
        return f"| {label} | {val} |"

    md_lines = [
        "# Runner Master Shadow Model V1",
        f"**Generated:** {date.today()}  ",
        f"**Governance:** {GOVERNANCE}  ",
        f"**Status:** {QUARANTINE}",
        "",
        "---",
        "",
        "## Mission",
        "> Can VP + TJ_TOP20 + current_or + last-six scalar trends beat VP alone without using SP?",
        "",
        f"**Answer: {report['mission_answer']}**",
        "",
        "---",
        "",
        "## Rolling Date Split",
        "| | |",
        "|---|---|",
        f"| Cutoff | {cutoff_date} |",
        f"| Train | {len(df_train)} rows ({df_train['won'].mean():.2%} WR) |",
        f"| Test  | {len(df_test)} rows ({df_test['won'].mean():.2%} WR) |",
        f"| Train dates | {dates_sorted[0]} → {dates_sorted[split_idx-1]} |",
        f"| Test dates  | {cutoff_date} → {dates_sorted[-1]} |",
        "",
        "---",
        "",
        "## TJ Threshold (Training Set P80)",
        "| | |",
        "|---|---|",
        f"| Threshold | {tj_p80:.4f} |",
        f"| TJ_HIGH in train | {n_tj_high_train}/{len(df_train)} ({100*n_tj_high_train/len(df_train):.1f}%) |",
        f"| TJ_HIGH in test  | {n_tj_high_test}/{len(df_test)} ({100*n_tj_high_test/len(df_test):.1f}%) |",
        "",
        "---",
        "",
        "## Model Comparison",
        "",
        "| Model | AUC | Top-decile WR | Top-decile lift | Top-decile ROI | Strip ROI | Verdict |",
        "|---|---|---|---|---|---|---|",
        f"| VP Baseline | {baseline_eval['auc']:.4f} | {baseline_eval['top_decile_wr']:.2%} | {baseline_eval['top_decile_lift']:+.4f} | {baseline_eval['top_decile_roi']:+.4f} | {baseline_eval['strip_top_winner_roi'] or 'N/A'} | BASELINE |",
        f"| Model A (LogReg) | {eval_a['auc']:.4f} | {eval_a['top_decile_wr']:.2%} | {eval_a['top_decile_lift']:+.4f} | {eval_a['top_decile_roi']:+.4f} | {eval_a['strip_top_winner_roi'] or 'N/A'} | **{verdict_a}** |",
        f"| Model B (LightGBM) | {eval_b['auc']:.4f} | {eval_b['top_decile_wr']:.2%} | {eval_b['top_decile_lift']:+.4f} | {eval_b['top_decile_roi']:+.4f} | {eval_b['strip_top_winner_roi'] or 'N/A'} | **{verdict_b}** |",
        f"| Model C (Ensemble) | {eval_c['auc']:.4f} | {eval_c['top_decile_wr']:.2%} | {eval_c['top_decile_lift']:+.4f} | {eval_c['top_decile_roi']:+.4f} | {eval_c['strip_top_winner_roi'] or 'N/A'} | **{verdict_c}** |",
        "",
        "---",
        "",
        "## Feature Importance (LightGBM — gain)",
        "",
        "| Feature | Gain |",
        "|---|---|",
    ]
    for feat, gain in sorted(lgb_importance.items(), key=lambda x: -x[1]):
        md_lines.append(f"| {feat} | {gain:.2f} |")

    md_lines += [
        "",
        "## Logistic Regression Coefficients",
        "",
        "| Feature | Coefficient |",
        "|---|---|",
    ]
    for feat, coef in sorted(lr_coefs.items(), key=lambda x: -abs(x[1])):
        md_lines.append(f"| {feat} | {coef:+.4f} |")

    md_lines += [
        "",
        "---",
        "",
        "## Calibration (Best Model)",
        "",
        "| Bin | Mean prob | Actual WR | n |",
        "|---|---|---|---|",
    ]
    for b in best_ev["calibration"]["bins"]:
        md_lines.append(f"| {b['bin']+1} | {b['mean_prob']:.3f} | {b['actual_wr']:.3f} | {b['n']} |")

    brier = best_ev["calibration"]["brier_score"]
    md_lines += [
        "",
        f"Brier score: {brier:.4f}",
        "",
        "---",
        "",
        "## SP-Band Diagnostics (test set, top-20% by model score)",
        "_Diagnostic only — SP is post-race, not a feature_",
        "",
        "| SP Band | n | WR | ROI all | n top20% | ROI top20% |",
        "|---|---|---|---|---|---|",
    ]
    for b in best_ev["sp_band_diagnostics"]:
        roi_top = f"{b['roi_top20pct']:+.4f}" if b["roi_top20pct"] is not None else "—"
        md_lines.append(
            f"| {b['band']} | {b['n']} | {b['win_rate']:.2%} | {b['roi_all']:+.4f} | {b['n_top20pct']} | {roi_top} |"
        )

    md_lines += [
        "",
        "---",
        "",
        "## Return Concentration (Best Model)",
        f"Gini: {best_ev['return_concentration']['gini']}  ",
        f"Top-decile % of total P&L: {best_ev['return_concentration']['top_decile_pct_of_pl']}",
        "",
        "---",
        "",
        "## Hard Governance",
        "```",
        "Model is in SHADOW_QUARANTINE.",
        "Not wired to: scoring pipeline, router, Telegram, staking, paper ledger.",
        "Promotion requires: evidence review, operator decision.",
        "NO_SCORING_CHANGE | NO_MODEL_PROMOTION | NO_ROUTER_CHANGE",
        "NO_STAKING_CHANGE | NO_LIVE_STATE_MUTATION",
        "```",
    ]

    md_path = REPORT_DIR / "runner_master_shadow_model_v1_latest.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"MD report:   {md_path.name}")

    print()
    print("RUNNER_MASTER_SHADOW_MODEL_V1 complete.")
    print(f"Governance: {GOVERNANCE}")
    print(f"Best model: {best_name} | AUC={best_ev['auc']:.4f} | top-decile ROI={best_ev['top_decile_roi']:+.4f}")
    print(f"Mission answer: {report['mission_answer']}")


if __name__ == "__main__":
    main()
