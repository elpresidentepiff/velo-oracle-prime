#!/usr/bin/env python3
"""
validate_jtc_d_rolling.py
=========================
Validates new rolling-window JTC-D parquets against held-out test data.

Compares:
  OLD: data/features/jtc_d/ (all-time cumulative — confirmed leakage)
  NEW: data/features/jtc_d_rp/ (365-day rolling — temporally safe)

Reports:
  - Coverage: % of test runners with a JTC-D signal
  - AUC: with and without JTC-D on top of Challenger V1 base features
  - Leakage diagnosis: if OLD AUC >> NEW AUC, the old signal was leakage

Usage:
    PYTHONPATH=. python scripts/ops/validate_jtc_d_rolling.py

SHADOW ONLY. Results do not enter scoring pipeline.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]

TRAIN_DIR  = ROOT / "data" / "new_build" / "training"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"

# Challenger V1 test set
TEST_PATH   = TRAIN_DIR / "core_v0_or_test.parquet"
TRAIN_PATH  = TRAIN_DIR / "core_v0_or_train.parquet"
VAL_PATH    = TRAIN_DIR / "core_v0_or_val.parquet"
PASSPORT_F  = TRAIN_DIR / "passport_features.parquet"
INTENT_F    = TRAIN_DIR / "intent_features.parquet"
MODEL_PATH  = ROOT / "data" / "new_build" / "models" / "core_v0_or_passport_intent" / "model.pkl"

# JTC-D paths
OLD_DIR     = ROOT / "data" / "features" / "jtc_d"
NEW_DIR     = ROOT / "data" / "features" / "jtc_d_rp"


CORE_FEATURES = [
    "dist_f", "going_code", "is_aw", "field_size", "draw_num", "draw_pct",
    "age_num", "wgt_lbs", "or_vs_field",
    "release_window_score", "going_fit_score", "distance_fit_score",
    "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
    "setup_run_flag", "cash_run_flag", "official_rating", "is_rated",
]
PASSPORT_FEATURES = [
    "pp_career_runs", "pp_win_rate", "pp_place_rate",
    "pp_days_since_last", "pp_layoff", "pp_avg_sp_last5",
    "pp_jockey_continuity", "pp_course_seen", "pp_or_change_3",
    "pp_class_moved_up", "pp_class_moved_down",
]
INTENT_FEATURES = [
    "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "runs_since_win", "runs_since_place", "runs_since_mkt_support",
    "odds_resilience_score", "intent_trip_match", "intent_course_win_history",
    "intent_going_match", "intent_class_drop_vs_best", "intent_run_after_break",
    "intent_sp_shortening", "intent_wins_last10", "intent_top3_last6",
]
CHALLENGER_V1 = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES

JTCD_FEATURES = [
    "tj_jtc_signal", "tj_adj_sr", "tj_confidence",
    "tc_jtc_signal", "tc_adj_sr", "tc_confidence",
    "td_jtc_signal", "td_adj_sr", "td_confidence",
    "jc_jtc_signal", "jc_adj_sr", "jc_confidence",
    "jd_jtc_signal", "jd_adj_sr", "jd_confidence",
]


def _dist_to_band(dist_f) -> str:
    if pd.isna(dist_f):    return "unknown"
    if dist_f < 5.5:       return "5f"
    if dist_f < 6.5:       return "6f"
    if dist_f < 7.5:       return "7f"
    if dist_f < 8.5:       return "8f"
    if dist_f < 10.5:      return "9-10f"
    if dist_f < 12.5:      return "11-12f"
    if dist_f < 14.5:      return "13-14f"
    if dist_f < 17.5:      return "15-17f"
    return "18f+"


def _build_jtcd(df: pd.DataFrame, jtcd_dir: Path) -> pd.DataFrame:
    base = df[["race_id", "horse", "trainer", "jockey", "course", "dist_f"]].copy()
    base["dist_band"] = base["dist_f"].apply(_dist_to_band).astype("category")

    tj = pd.read_parquet(jtcd_dir / "trainer_jockey_profile.parquet").rename(columns={
        "jtc_signal": "tj_jtc_signal", "adj_sr": "tj_adj_sr", "confidence": "tj_confidence"})
    tc = pd.read_parquet(jtcd_dir / "trainer_course_profile.parquet").rename(columns={
        "jtc_signal": "tc_jtc_signal", "adj_sr": "tc_adj_sr", "confidence": "tc_confidence"})
    td = pd.read_parquet(jtcd_dir / "trainer_dist_profile.parquet").rename(columns={
        "jtc_signal": "td_jtc_signal", "adj_sr": "td_adj_sr", "confidence": "td_confidence"})
    jc = pd.read_parquet(jtcd_dir / "jockey_course_profile.parquet").rename(columns={
        "jtc_signal": "jc_jtc_signal", "adj_sr": "jc_adj_sr", "confidence": "jc_confidence"})
    jd = pd.read_parquet(jtcd_dir / "jockey_dist_profile.parquet").rename(columns={
        "jtc_signal": "jd_jtc_signal", "adj_sr": "jd_adj_sr", "confidence": "jd_confidence"})

    base = base.merge(tj[["trainer", "jockey", "tj_jtc_signal", "tj_adj_sr", "tj_confidence"]],
                      on=["trainer", "jockey"], how="left")
    base = base.merge(tc[["trainer", "course", "tc_jtc_signal", "tc_adj_sr", "tc_confidence"]],
                      on=["trainer", "course"], how="left")
    base = base.merge(td[["trainer", "dist_band", "td_jtc_signal", "td_adj_sr", "td_confidence"]],
                      on=["trainer", "dist_band"], how="left")
    base = base.merge(jc[["jockey", "course", "jc_jtc_signal", "jc_adj_sr", "jc_confidence"]],
                      on=["jockey", "course"], how="left")
    base = base.merge(jd[["jockey", "dist_band", "jd_jtc_signal", "jd_adj_sr", "jd_confidence"]],
                      on=["jockey", "dist_band"], how="left")
    return base


def _load_test() -> pd.DataFrame:
    test = pd.read_parquet(TEST_PATH)
    pp = pd.read_parquet(PASSPORT_F) if PASSPORT_F.exists() else None
    intent = pd.read_parquet(INTENT_F) if INTENT_F.exists() else None

    if pp is not None and "race_id" in pp.columns and "horse" in pp.columns:
        test = test.merge(pp, on=["race_id", "horse"], how="left", suffixes=("", "_pp"))
    if intent is not None and "race_id" in intent.columns and "horse" in intent.columns:
        test = test.merge(intent, on=["race_id", "horse"], how="left", suffixes=("", "_intent"))

    # Add course, trainer, jockey from historical dataset if not present
    if "trainer" not in test.columns or "course" not in test.columns:
        hist = pd.read_parquet(ROOT / "data" / "new_build" / "training" / "core_v0_historical_dataset.parquet")
        merge_cols = ["race_id", "horse"]
        extra = [c for c in ["trainer", "jockey", "course", "dist_f"] if c not in test.columns]
        if extra:
            test = test.merge(hist[merge_cols + extra].drop_duplicates(merge_cols),
                              on=merge_cols, how="left", suffixes=("", "_hist"))
    return test


def _coverage_report(df: pd.DataFrame, label: str) -> dict:
    result = {}
    for col in ["tj_jtc_signal", "tc_jtc_signal", "td_jtc_signal", "jc_jtc_signal", "jd_jtc_signal"]:
        if col in df.columns:
            cov = df[col].notna().mean()
            result[col] = round(cov, 4)
    any_signal = df[[c for c in JTCD_FEATURES if c in df.columns]].notna().any(axis=1).mean()
    result["any_signal"] = round(any_signal, 4)
    print(f"\n{label} coverage:")
    for k, v in result.items():
        print(f"  {k:<22} {v*100:.1f}%")
    return result


def main() -> None:
    import joblib

    print("=== JTC-D Rolling Validation ===")
    print(f"Loading test set from {TEST_PATH}...")
    test = _load_test()
    print(f"  Test rows: {len(test):,} | won rate: {test['won'].mean():.3f}")

    # Check required columns
    missing_v1 = [c for c in CORE_FEATURES if c not in test.columns]
    if missing_v1:
        print(f"  Missing V1 features: {missing_v1[:5]}... — will score JTC-D coverage only")

    print("\nLoading Challenger V1 model...")
    if not MODEL_PATH.exists():
        print(f"  Model not found: {MODEL_PATH}")
        print("  Skipping AUC — coverage report only")
        model = None
    else:
        model_pkg = joblib.load(MODEL_PATH)
        model = model_pkg["model"] if isinstance(model_pkg, dict) else model_pkg
        print("  Model loaded.")

    # --- Old JTC-D ---
    print("\nBuilding OLD JTC-D features (all-time cumulative)...")
    test_old_jtcd = _build_jtcd(test, OLD_DIR)
    cov_old = _coverage_report(test_old_jtcd.merge(test[["race_id", "horse", "won"]],
                                                    on=["race_id", "horse"], how="left"), "OLD JTC-D")

    # --- New JTC-D ---
    print("\nBuilding NEW JTC-D features (365d rolling, leakage-free)...")
    test_new_jtcd = _build_jtcd(test, NEW_DIR)
    test_new_full = test_new_jtcd.merge(test[["race_id", "horse", "won"]],
                                         on=["race_id", "horse"], how="left")
    cov_new = _coverage_report(test_new_full, "NEW JTC-D")

    # --- AUC tests: retrain on train+val, evaluate on test ---
    import lightgbm as lgb
    auc_results = {}

    print("\nLoading train+val for sidecar retrain...")
    train = pd.read_parquet(TRAIN_PATH)
    val   = pd.read_parquet(VAL_PATH)
    pp    = pd.read_parquet(PASSPORT_F) if PASSPORT_F.exists() else None
    intent = pd.read_parquet(INTENT_F) if INTENT_F.exists() else None
    hist  = pd.read_parquet(ROOT / "data" / "new_build" / "training" / "core_v0_historical_dataset.parquet")

    def _enrich(df):
        if pp is not None:
            df = df.merge(pp, on=["race_id","horse"], how="left", suffixes=("","_pp"))
        if intent is not None:
            df = df.merge(intent, on=["race_id","horse"], how="left", suffixes=("","_intent"))
        extra = [c for c in ["trainer","jockey","course","dist_f"] if c not in df.columns]
        if extra:
            df = df.merge(hist[["race_id","horse"]+extra].drop_duplicates(["race_id","horse"]),
                          on=["race_id","horse"], how="left", suffixes=("","_hist"))
        return df

    train = _enrich(train)
    val   = _enrich(val)

    LGBM_PARAMS = {
        "n_estimators": 200, "learning_rate": 0.05,
        "max_depth": 5, "num_leaves": 31,
        "verbosity": -1, "random_state": 42,
    }

    def _fit_eval(tr, va, te, feats, label_str):
        use = [f for f in feats if f in tr.columns and f in va.columns and f in te.columns]
        if not use:
            print(f"  {label_str}: no features")
            return None
        for df in (tr, va, te):
            for f in use:
                df[f] = df[f].fillna(0)
        m = lgb.LGBMClassifier(**LGBM_PARAMS)
        m.fit(tr[use], tr["won"],
              eval_set=[(va[use], va["won"])],
              callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(-1)])
        probs = m.predict_proba(te[use])[:, 1]
        auc = float(roc_auc_score(te["won"], probs))
        print(f"  {label_str:<45} AUC={auc:.4f} (n_features={len(use)})")
        return auc

    v1_feats = [c for c in CHALLENGER_V1]

    # Build JTC-D features for train/val/test
    tr_old  = _build_jtcd(train, OLD_DIR)
    va_old  = _build_jtcd(val,   OLD_DIR)
    te_old  = _build_jtcd(test,  OLD_DIR)
    tr_new  = _build_jtcd(train, NEW_DIR)
    va_new  = _build_jtcd(val,   NEW_DIR)
    te_new  = _build_jtcd(test,  NEW_DIR)

    def _attach(base, jtcd_df):
        jtcd_cols = ["race_id","horse"] + [c for c in JTCD_FEATURES if c in jtcd_df.columns]
        return base.merge(jtcd_df[jtcd_cols], on=["race_id","horse"], how="left")

    tr_old_full = _attach(train, tr_old)
    va_old_full = _attach(val,   va_old)
    te_old_full = _attach(test,  te_old)
    tr_new_full = _attach(train, tr_new)
    va_new_full = _attach(val,   va_new)
    te_new_full = _attach(test,  te_new)

    print("\nAUC validation (retrained LightGBM):")
    auc_results["v1_base"]         = _fit_eval(train, val, test, v1_feats, "Challenger V1 base")
    auc_results["v1_plus_old_jtcd"]= _fit_eval(tr_old_full, va_old_full, te_old_full,
                                                v1_feats + JTCD_FEATURES, "V1 + OLD JTC-D (all-time leaky)")
    auc_results["v1_plus_new_jtcd"]= _fit_eval(tr_new_full, va_new_full, te_new_full,
                                                v1_feats + JTCD_FEATURES, "V1 + NEW JTC-D (365d rolling)")

    if auc_results.get("v1_base") and auc_results.get("v1_plus_new_jtcd"):
        lift_new  = auc_results["v1_plus_new_jtcd"] - auc_results["v1_base"]
        lift_old  = (auc_results.get("v1_plus_old_jtcd") or 0) - auc_results["v1_base"]
        shrinkage = (auc_results.get("v1_plus_old_jtcd") or 0) - auc_results["v1_plus_new_jtcd"]
        print(f"\n  NEW JTC-D lift over base: {lift_new:+.4f}")
        print(f"  OLD JTC-D lift over base: {lift_old:+.4f}")
        print(f"  Leakage shrinkage:        {shrinkage:+.4f}")
        if shrinkage > 0.02:
            print("  VERDICT: Significant leakage confirmed in old JTC-D")
        elif lift_new > 0.002:
            print("  VERDICT: New rolling JTC-D has real signal lift")
        else:
            print("  VERDICT: JTC-D adds minimal lift even after leakage fix")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "test_rows": len(test),
        "won_rate": float(test["won"].mean()),
        "coverage_old": cov_old,
        "coverage_new": cov_new,
        "auc": auc_results,
        "leakage_status": "TEMPORALLY_SAFE",
        "shadow_only": True,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "jtc_d_rolling_validation_latest.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nReport: {out}")


if __name__ == "__main__":
    main()
