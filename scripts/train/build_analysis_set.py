import pandas as pd
import numpy as np
from pathlib import Path
import lightgbm as lgb
import json
from sklearn.metrics import roc_auc_score

def build_analysis_dataset():
    ROOT = Path(".")
    TRAIN_DIR = ROOT / "data" / "new_build" / "training"
    
    # 1. Features
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
    V1_FEATURES = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES
    
    LGBM_PARAMS = {
        "n_estimators": 300,
        "learning_rate": 0.05,
        "max_depth": 6,
        "num_leaves": 31,
        "verbosity": -1,
        "random_state": 42,
    }

    def load_unified(split):
        base = pd.read_parquet(TRAIN_DIR / f"v2_challenger_{split}.parquet")
        passport = pd.read_parquet(TRAIN_DIR / "passport_features.parquet")
        intent = pd.read_parquet(TRAIN_DIR / "intent_features.parquet")
        velocity = pd.read_parquet(TRAIN_DIR / f"v3_velocity_candidates_{split}.parquet")
        df = base.merge(passport, on=["race_id", "horse"], how="left")
        df = df.merge(intent, on=["race_id", "horse"], how="left")
        df = df.merge(velocity, on=["race_id", "horse"], how="left")
        return df

    print("Loading datasets...")
    train = load_unified('train')
    val = load_unified('val')
    test = load_unified('test')
    
    print("Pre-processing...")
    for df in [train, val, test]:
        for f in V1_FEATURES:
            df[f] = df[f].fillna(0)
    
    print("Training V1 model to generate analysis probabilities...")
    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(
        train[V1_FEATURES], train['won'],
        eval_set=[(val[V1_FEATURES], val['won'])],
        callbacks=[lgb.early_stopping(stopping_rounds=20)]
    )
    
    print("Generating predictions on test set...")
    test['v1_prob'] = model.predict_proba(test[V1_FEATURES])[:, 1]
    
    # Save the analysis set
    out_path = Path("data/new_build/v1_v3_analysis_set.parquet")
    test.to_parquet(out_path, index=False)
    print(f"Analysis set saved to {out_path} ({len(test):,} rows)")

if __name__ == "__main__":
    build_analysis_dataset()
