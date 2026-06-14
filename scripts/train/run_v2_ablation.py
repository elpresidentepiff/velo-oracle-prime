"""
Challenger V2 Ablation Run.
Evaluates 3 new features (pp_aw_vs_turf_delta, or_vs_career_best, pp_fresh_or_drop)
against the Challenger V1 baseline (0.6969 AUC).
"""
import json
import os
import sys
from datetime import datetime, UTC
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(".")
TRAIN_DIR = ROOT / "data" / "new_build" / "training"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"

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

V2_NEW_FEATURES = [
    "pp_aw_vs_turf_delta",
    "or_vs_career_best",
    "pp_fresh_or_drop"
]

LGBM_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 6,
    "num_leaves": 31,
    "verbosity": -1,
    "random_state": 42,
}

V1_AUC_BASELINE = 0.6969
V2_GATE = 0.6999

def run_v2_ablation():
    print(f"--- Challenger V2 Ablation ({datetime.now(UTC).isoformat()}) ---")
    
    # 1. Load Data
    print("Loading data...")
    splits = {}
    for s in ['train', 'val', 'test']:
        df = pd.read_parquet(TRAIN_DIR / f"v2_challenger_{s}.parquet")
        
        # Join V1 features
        passport = pd.read_parquet(TRAIN_DIR / "passport_features.parquet", columns=["race_id", "horse"] + PASSPORT_FEATURES)
        intent = pd.read_parquet(TRAIN_DIR / "intent_features.parquet", columns=["race_id", "horse"] + INTENT_FEATURES)
        
        df = df.merge(passport, on=["race_id", "horse"], how="left")
        df = df.merge(intent, on=["race_id", "horse"], how="left")
        
        splits[s] = df
        print(f"  {s}: {len(df):,} rows")

    # 2. Preprocessing
    # USER RULE: Null-fill new features with training-set medians
    train = splits['train']
    medians = {}
    for f in V2_NEW_FEATURES:
        if f == "pp_fresh_or_drop":
            # Boolean/Binary - median or mode? User said median.
            val = train[f].astype(float).median()
        else:
            val = train[f].median()
        medians[f] = val
        print(f"  Median for {f}: {val}")

    for name, df in splits.items():
        # Fill new features
        for f, val in medians.items():
            df[f] = df[f].fillna(val)
        
        # Fill existing features (0-fill as per V1 review script)
        all_v1_f = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES
        for f in all_v1_f:
            if f in df.columns:
                df[f] = df[f].fillna(0)
        
        # Ensure boolean is float for LGBM
        df['pp_fresh_or_drop'] = df['pp_fresh_or_drop'].astype(float)
        splits[name] = df

    # 3. Train
    print("\nTraining Challenger V2 model...")
    all_v2_f = CORE_FEATURES + PASSPORT_FEATURES + INTENT_FEATURES + V2_NEW_FEATURES
    
    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(
        splits['train'][all_v2_f],
        splits['train']['won'],
        eval_set=[(splits['val'][all_v2_f], splits['val']['won'])],
        callbacks=[lgb.early_stopping(stopping_rounds=20)]
    )

    # 4. Evaluate
    print("\nEvaluating on held-out 2025 test set...")
    test = splits['test']
    probs = model.predict_proba(test[all_v2_f])[:, 1]
    auc = roc_auc_score(test['won'], probs)
    
    # Calculate SR and Frame
    tmp = test[['race_id', 'won']].copy()
    tmp['prob'] = probs
    
    top1 = tmp.sort_values(['race_id', 'prob'], ascending=[True, False]).groupby('race_id').head(1)
    sr = top1['won'].mean()
    
    top3 = tmp.sort_values(['race_id', 'prob'], ascending=[True, False]).groupby('race_id').head(3)
    frame = top3.groupby('race_id')['won'].max().mean()

    print(f"V1 AUC:   {V1_AUC_BASELINE:.4f}")
    print(f"V2 AUC:   {auc:.4f}")
    print(f"Lift:     {auc - V1_AUC_BASELINE:+.4f}")
    print(f"V2 SR:    {sr:.4f}")
    print(f"V2 Frame: {frame:.4f}")

    # 5. Feature Importance
    print("\nNew Feature Importance (LGBM Gain):")
    importances = pd.DataFrame({
        'feature': all_v2_f,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    new_fi = importances[importances['feature'].isin(V2_NEW_FEATURES)]
    for _, row in new_fi.iterrows():
        rank = importances['feature'].tolist().index(row['feature']) + 1
        print(f"  #{rank:<2} {row['feature']:<25} | {row['importance']:,}")

    # 6. Save Report
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "baseline": {"auc": V1_AUC_BASELINE},
        "v2_results": {
            "auc": round(float(auc), 4),
            "sr": round(float(sr), 4),
            "frame": round(float(frame), 4),
            "lift": round(float(auc - V1_AUC_BASELINE), 4)
        },
        "gate_passed": auc > V2_GATE,
        "new_feature_importances": new_fi.set_index('feature')['importance'].to_dict(),
        "hyperparameters": LGBM_PARAMS,
        "features": all_v2_f
    }
    
    report_path = REPORT_DIR / "challenger_v2_ablation_results.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport saved to {report_path}")

if __name__ == "__main__":
    run_v2_ablation()
