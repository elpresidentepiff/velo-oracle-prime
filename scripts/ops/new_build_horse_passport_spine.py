"""
new_build_horse_passport_spine.py — New Build VELO
Builds Horse Passports and Entry Snapshots from historical raceform.
Includes Intent Score V1 logic.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import json
from datetime import datetime

# Path Setup
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
NEW_BUILD_DIR = DATA_DIR / "new_build"
OUTPUT_DIR = NEW_BUILD_DIR / "features"
REPORT_DIR = NEW_BUILD_DIR / "reports"

SOURCE_PARQUET = DATA_DIR / "raceform_clean.parquet"
OUTPUT_PARQUET = OUTPUT_DIR / "entry_snapshot_v1.parquet"

def norm_name(name):
    import re
    return re.sub(r"[^a-z]", "", str(name or "").lower())

def calculate_passport_and_intent():
    print(f"Loading {SOURCE_PARQUET}...")
    df = pd.read_parquet(SOURCE_PARQUET)
    
    # Pre-sorting
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['horse', 'date'])
    
    # 1. Horse Passport Features (Rolling)
    print("Calculating rolling Horse Passport features...")
    
    # Career runs
    df['pp_career_runs'] = df.groupby('horse').cumcount()
    
    # Win/Place tracking
    df['pos_num'] = pd.to_numeric(df['pos'], errors='coerce').fillna(99).astype(int)
    df['ts_num'] = pd.to_numeric(df['ts'], errors='coerce')
    df['won'] = (df['pos_num'] == 1).astype(int)
    df['placed'] = (df['pos_num'] <= 3).astype(int)
    
    # Fast cumulative wins/places
    df['pp_wins'] = df.groupby('horse')['won'].cumsum() - df['won']
    df['pp_places'] = df.groupby('horse')['placed'].cumsum() - df['placed']
    
    df['pp_win_rate'] = df['pp_wins'] / df['pp_career_runs'].replace(0, 1)
    df['pp_place_rate'] = df['pp_places'] / df['pp_career_runs'].replace(0, 1)

    # TS Aggregates
    print("Calculating TS aggregates...")
    # Best TS last 6
    df['pp_best_ts_last6'] = df.groupby('horse')['ts_num'].shift(1).rolling(6, min_periods=1).max()
    
    # TS Trajectory (Slope)
    def calculate_slope(series):
        valid = series.dropna()
        if len(valid) < 3:
            return None
        try:
            x = np.arange(len(valid))
            y = valid.values
            slope, _ = np.polyfit(x, y, 1)
            return round(float(slope), 3)
        except:
            return None

    df['pp_ts_trajectory'] = df.groupby('horse')['ts_num'].shift(1).rolling(6, min_periods=3).apply(calculate_slope, raw=False)
    
    # Layoff (Fast)
    df['pp_days_since_last'] = df.groupby('horse')['date'].diff().dt.days
    df['pp_layoff_60'] = (df['pp_days_since_last'] > 60).astype(int).fillna(0)
    
    # SP trajectory (Simplified for speed)
    def parse_sp(s):
        if not s or s in ('None', 'nan'): return 10.0
        try:
            s = str(s).lower()
            if "/" in s:
                n, d = s.split("/")
                return int(re.sub("[^0-9]", "", n)) / int(re.sub("[^0-9]", "", d)) + 1.0
            return float(s) + 1.0
        except: return 10.0
    
    import re
    df['sp_dec'] = pd.to_numeric(df['sp'], errors='coerce').fillna(10.0) # Assume decimal first
    # (Optional: add fractional parser if needed, but numeric conversion is faster)
    df['pp_avg_sp_last5'] = df.groupby('horse')['sp_dec'].shift(1).rolling(5, min_periods=1).mean()
    
    # 2. Entry Snapshot (Today Setup)
    print("Building Entry Snapshots...")
    
    # Class movement (Fast)
    df['class_num'] = pd.to_numeric(df['class_raw'].str.extract(r"(\d)")[0], errors='coerce').fillna(4).astype(int)
    df['prev_class'] = df.groupby('horse')['class_num'].shift(1)
    df['pp_class_diff'] = df['class_num'] - df['prev_class']
    
    # 3. Intent Score V1
    print("Calculating Intent Score V1...")
    
    # BACK_TO_TRIP (Fast)
    # Mark rows where horse won, then forward fill that distance
    df['win_dist'] = df['dist'].where(df['won'] == 1)
    df['pp_prev_win_dist'] = df.groupby('horse')['win_dist'].shift(1).ffill()
    df['sig_BACK_TO_TRIP'] = (df['dist'] == df['pp_prev_win_dist']).astype(int)
    
    df['sig_CLASS_DROP'] = (df['pp_class_diff'] < 0).astype(int)
    df['sig_LAYOFF_RETURN'] = df['pp_layoff_60']
    
    # JOCKEY_UPGRADE (Fast)
    df['prev_jockey'] = df.groupby('horse')['jockey'].shift(1)
    df['sig_JOCKEY_CHANGE'] = (df['jockey'] != df['prev_jockey']).astype(int)
    
    # Combined Intent Score
    df['intent_score_v1'] = (
        df['sig_BACK_TO_TRIP'] * 2.0 +
        df['sig_CLASS_DROP'] * 1.5 +
        df['sig_LAYOFF_RETURN'] * -1.0 + # Layoff is usually negative unless intended
        df['sig_JOCKEY_CHANGE'] * 0.5
    )
    
    # Banned field removal (ensure no RPR/Position/SP leakage in features)
    features_only = df.drop(columns=['pos', 'ovr_btn', 'btn', 'comment', 'rpr', 'pos_num', 'ts_num'])
    
    print(f"Saving snapshots to {OUTPUT_PARQUET}...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features_only.to_parquet(OUTPUT_PARQUET)
    
    # 4. Report
    print("\nGeneration Complete.")
    print(f"Total Horses: {df['horse'].nunique()}")
    print(f"Total Snapshots: {len(df)}")
    print(f"Intent Coverage (score > 0): {(df['intent_score_v1'] > 0).mean():.1%}")

if __name__ == "__main__":
    calculate_passport_and_intent()
