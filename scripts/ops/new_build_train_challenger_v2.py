#!/usr/bin/env python3
"""
new_build_train_challenger_v2.py
Train Challenger V2 model using pp_best_ts_last6 and pp_ts_trajectory.
"""
import json
import os
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, brier_score_loss

TRAIN_DIR = ROOT / "data" / "new_build" / "training"
MODEL_DIR = ROOT / "data" / "new_build" / "models" / "challenger_v2"
RPT_DIR = ROOT / "data" / "new_build" / "reports"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Fixed Baseline
V1_AUC_BASELINE = 0.6969

BANNED_IN_FEATURES = {
    "rpr_num", "rpr_vs_field", "rpr", "ts_num", "ts",
    "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav",
    "odds_contraction_score", "decoy_support_flag",
    "runs_since_mkt_support", "pos", "pos_num", "ovr_btn", "btn",
    "comment", "time", "target", "won", "framed"
}

def _race_level_metrics(df, prob_col):
    sr_hits = 0
    frame_hits = 0
    races = 0
    for _, grp in df.groupby("race_id"):
        if len(grp) < 2: continue
        races += 1
        best_idx = grp[prob_col].idxmax()
        if grp.loc[best_idx, "won"] == 1:
            sr_hits += 1
        top3 = grp.nlargest(3, prob_col)
        if top3["won"].sum() >= 1:
            frame_hits += 1
    return (sr_hits / races if races else 0), (frame_hits / races if races else 0), races

def run():
    print("Loading full enriched FIXED V2 Unified training corpus (1.16M rows)...")
    corpus_path = TRAIN_DIR / "v2_unified_ts_enriched_full_FIXED.parquet"
    if not corpus_path.exists():
        print(f"Error: {corpus_path} not found.")
        return

    df = pd.read_parquet(corpus_path)
    
    # 2025 as test
    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
    train_df = df[df['date'] < "2025-01-01"].copy()
    test_df = df[df['date'] >= "2025-01-01"].copy()
    
    # Define features (Consolidated V1 + TS)
    CORE = [
        "dist_f", "going_code", "is_aw", "field_size", "draw_num", "draw_pct",
        "age_num", "wgt_lbs", "or_vs_field", "official_rating", "is_rated"
    ]
    PASSPORT = [
        "pp_career_runs", "pp_win_rate", "pp_place_rate",
        "pp_days_since_last", "pp_layoff", "pp_avg_sp_last5",
        "pp_jockey_continuity", "pp_course_seen", "pp_or_change_3",
        "pp_class_moved_up", "pp_class_moved_down"
    ]
    INTENT = [
        "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
        "runs_since_win", "runs_since_place", "odds_resilience_score", 
        "intent_trip_match", "intent_course_win_history",
        "intent_going_match", "intent_class_drop_vs_best", "intent_run_after_break",
        "intent_sp_shortening", "intent_wins_last10", "intent_top3_last6"
    ]
    TS_FEATURES = ["pp_best_ts_last6", "pp_ts_trajectory"]
    
    feature_cols = CORE + PASSPORT + INTENT + TS_FEATURES
    
    # Validation
    for f in feature_cols:
        if f in BANNED_IN_FEATURES:
            raise AssertionError(f"Leakage detected: {f}")
    
    print(f"Training Challenger V2 with {len(feature_cols)} features...")
    print(f"  Train: {len(train_df):,} rows | Test (2025+): {len(test_df):,} rows")

    import lightgbm as lgb
    medians = train_df[feature_cols].median()
    X_train = train_df[feature_cols].fillna(medians)
    X_test = test_df[feature_cols].fillna(medians)
    y_train = train_df["won"]
    y_test = test_df["won"]

    model = lgb.LGBMClassifier(
        n_estimators=300, learning_rate=0.05, max_depth=6,
        num_leaves=31, verbosity=-1, random_state=42
    )
    model.fit(X_train, y_train)

    # Metrics
    test_probs = model.predict_proba(X_test)[:, 1]
    test_auc = round(float(roc_auc_score(y_test, test_probs)), 4)
    test_sr, test_fr, test_races = _race_level_metrics(test_df.assign(_prob=test_probs), "_prob")

    # Feature Importance
    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    
    print(f"\nRESULTS:")
    print(f"  V1 Baseline AUC: {V1_AUC_BASELINE}")
    print(f"  V2 Challenger AUC: {test_auc} (Lift: {test_auc - V1_AUC_BASELINE:+.4f})")
    print(f"  V2 SR: {test_sr:.1%} | Frame: {test_fr:.1%}")
    
    print(f"\nTOP 10 FEATURES:")
    print(importances.head(10))
    
    print(f"\nTS FEATURE RANK:")
    for f in TS_FEATURES:
        rank = importances.index.get_loc(f) + 1
        print(f"  {f}: Rank {rank} / {len(feature_cols)}")

    # Save
    model_path = MODEL_DIR / "challenger_v2.pkl"
    with model_path.open("wb") as f:
        pickle.dump({"model": model, "feature_cols": feature_cols, "medians": medians.to_dict()}, f)
    
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "auc": test_auc,
        "auc_lift": round(test_auc - V1_AUC_BASELINE, 4),
        "sr": test_sr,
        "frame_rate": test_fr,
        "top_features": importances.head(10).to_dict(),
        "ts_feature_ranks": {f: int(importances.index.get_loc(f) + 1) for f in TS_FEATURES}
    }
    (MODEL_DIR / "challenger_v2_metadata.json").write_text(json.dumps(meta, indent=2))

if __name__ == "__main__":
    run()
