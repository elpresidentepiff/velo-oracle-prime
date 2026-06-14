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

# 45 original features (V1)
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

V1_AUC_TARGET = 0.6969
V2_GATE = 0.6999

def load_unified_v2(split):
    """Perform a rigorous join of all feature sources."""
    # 1. Base (Core + New features)
    base = pd.read_parquet(TRAIN_DIR / f"v2_challenger_{split}.parquet")
    # 2. Aux - Full coverage files
    passport = pd.read_parquet(TRAIN_DIR / "passport_features.parquet")
    intent = pd.read_parquet(TRAIN_DIR / "intent_features.parquet")
    # 3. Join on race_id and horse
    df = base.merge(passport, on=["race_id", "horse"], how="left")
    df = df.merge(intent, on=["race_id", "horse"], how="left")
    return df

def run_master_ablation():
    print(f"--- Challenger V2 MASTER ABLATION ({datetime.now(UTC).isoformat()}) ---")
    
    # 1. Load Data
    print("Loading data splits...")
    train = load_unified_v2('train')
    val = load_unified_v2('val')
    test = load_unified_v2('test')
    
    print(f"  Train: {len(train):,} rows")
    print(f"  Val:   {len(val):,} rows")
    print(f"  Test:  {len(test):,} rows")
    
    # 2. Correlation & Redundancy Check
    print("\n--- Step 1: Redundancy Audit ---")
    mask = train['or_vs_career_best'].notna() & train['curr_or_minus_best_or'].notna()
    corr = train.loc[mask, 'or_vs_career_best'].corr(train.loc[mask, 'curr_or_minus_best_or'])
    print(f"Correlation(or_vs_career_best, curr_or_minus_best_or): {corr:.4f}")
    
    # Final V2 Candidate Set (Dropping redundant or_vs_career_best)
    v2_candidates = ["pp_aw_vs_turf_delta", "pp_fresh_or_drop"]
    print(f"V2 Candidate features: {v2_candidates}")
    
    # 3. Null-filling (Median-fill new, 0-fill old)
    print("\n--- Step 2: Preprocessing ---")
    medians = {f: train[f].median() for f in v2_candidates}
    print(f"Medians for new features: {medians}")
    
    def preprocess(df):
        for f, val in medians.items():
            df[f] = df[f].fillna(val)
        for f in V1_FEATURES:
            df[f] = df[f].fillna(0)
        if 'pp_fresh_or_drop' in df.columns:
            df['pp_fresh_or_drop'] = df['pp_fresh_or_drop'].astype(float)
        return df

    train = preprocess(train)
    val = preprocess(val)
    test = preprocess(test)
    
    # 4. Reproduce V1 Baseline
    print("\n--- Step 3: Reproduce V1 Baseline (45 features) ---")
    v1_model = lgb.LGBMClassifier(**LGBM_PARAMS)
    v1_model.fit(
        train[V1_FEATURES], train['won'],
        eval_set=[(val[V1_FEATURES], val['won'])],
        callbacks=[lgb.early_stopping(stopping_rounds=20)]
    )
    v1_probs = v1_model.predict_proba(test[V1_FEATURES])[:, 1]
    v1_auc = roc_auc_score(test['won'], v1_probs)
    print(f"Reproduced V1 AUC: {v1_auc:.4f} (Target: {V1_AUC_TARGET} ± 0.005)")
    
    if abs(v1_auc - V1_AUC_TARGET) > 0.005:
        print("FAIL: Baseline reproduction exceeded tolerance.")
    else:
        print("PASS: Baseline reproduction successful.")

    # 5. Execute V2 Challenge
    print("\n--- Step 4: Execute V2 Challenge (47 features) ---")
    v2_features = V1_FEATURES + v2_candidates
    v2_model = lgb.LGBMClassifier(**LGBM_PARAMS)
    v2_model.fit(
        train[v2_features], train['won'],
        eval_set=[(val[v2_features], val['won'])],
        callbacks=[lgb.early_stopping(stopping_rounds=20)]
    )
    v2_probs = v2_model.predict_proba(test[v2_features])[:, 1]
    v2_auc = roc_auc_score(test['won'], v2_probs)
    
    # Calculate SR/Frame for V2
    tmp = test[['race_id', 'won']].copy()
    tmp['prob'] = v2_probs
    top1 = tmp.sort_values(['race_id', 'prob'], ascending=[True, False]).groupby('race_id').head(1)
    v2_sr = top1['won'].mean()
    top3 = tmp.sort_values(['race_id', 'prob'], ascending=[True, False]).groupby('race_id').head(3)
    v2_frame = top3.groupby('race_id')['won'].max().mean()

    print(f"\nV1 Baseline AUC: {v1_auc:.4f}")
    print(f"V2 Challenger AUC: {v2_auc:.4f}")
    print(f"Lift:             {v2_auc - v1_auc:+.4f}")
    print(f"V2 SR:            {v2_sr:.4f}")
    print(f"V2 Frame:         {v2_frame:.4f}")

    # 6. Feature Importance
    print("\nNew Feature Importance (Gain):")
    importances = pd.DataFrame({
        'feature': v2_features,
        'importance': v2_model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    new_fi = importances[importances['feature'].isin(v2_candidates)]
    for _, row in new_fi.iterrows():
        rank = importances['feature'].tolist().index(row['feature']) + 1
        print(f"  #{rank:<2} {row['feature']:<25} | {row['importance']:,}")

    # 7. Final Verdict
    gate_passed = v2_auc > V2_GATE
    print(f"\nPROMOTION VERDICT: {'PASSED' if gate_passed else 'REJECTED'} (Target: > {V2_GATE})")

    # 8. Save Report
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "baseline_v1": {
            "target": V1_AUC_TARGET,
            "reproduced": round(float(v1_auc), 4),
            "status": "PASS" if abs(v1_auc - V1_AUC_TARGET) <= 0.005 else "FAIL"
        },
        "v2_results": {
            "auc": round(float(v2_auc), 4),
            "sr": round(float(v2_sr), 4),
            "frame": round(float(v2_frame), 4),
            "lift": round(float(v2_auc - v1_auc), 4)
        },
        "gate_passed": gate_passed,
        "new_feature_importances": new_fi.set_index('feature')['importance'].to_dict(),
        "n_features": len(v2_features)
    }
    
    report_path = REPORT_DIR / "challenger_v2_final_audit.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Audit report saved to {report_path}")

if __name__ == "__main__":
    run_master_ablation()
