import pandas as pd
import numpy as np
from pathlib import Path

def generate_v3_velocity_features_v2():
    ROOT = Path(".")
    TRAIN_DIR = ROOT / "data" / "new_build" / "training"
    RACEFORM_PATH = ROOT / "data" / "raceform_clean.parquet"
    
    print(f"Loading full history from {RACEFORM_PATH}...")
    # Load full history to ensure no gaps in rolling stats
    full_history = pd.read_parquet(RACEFORM_PATH, columns=['horse', 'date', 'pos', 'race_id'])
    full_history['date'] = pd.to_datetime(full_history['date'])
    
    # Derive won and framed for the full history
    full_history['won'] = full_history['pos'].astype(str).str.strip() == '1'
    # For framed, we'll be conservative and only count 1,2,3
    full_history['framed'] = full_history['pos'].astype(str).str.strip().isin(['1', '2', '3'])
    
    # Sort by horse and date
    full_history = full_history.sort_values(['horse', 'date'])
    
    print("Calculating windowed velocity on full history (shift(1) enforced)...")
    
    # Win Rate Last 3
    full_history['win_rate_last3'] = (
        full_history.groupby('horse')['won']
        .shift(1)
        .groupby(full_history['horse'])
        .rolling(window=3, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    
    # Place Rate Last 3
    full_history['place_rate_last3'] = (
        full_history.groupby('horse')['framed']
        .shift(1)
        .groupby(full_history['horse'])
        .rolling(window=3, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    
    # Win Rate Last 6
    full_history['win_rate_last6'] = (
        full_history.groupby('horse')['won']
        .shift(1)
        .groupby(full_history['horse'])
        .rolling(window=6, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    
    v3_features = ['win_rate_last3', 'place_rate_last3', 'win_rate_last6']
    
    # Map back to training splits
    print("Mapping features to training splits...")
    for s in ['train', 'val', 'test']:
        path = TRAIN_DIR / f"core_v0_or_{s}.parquet"
        print(f"  Processing {s} split...")
        split_df = pd.read_parquet(path)
        
        # We join on race_id and horse to be 100% specific
        # (Though race_id should be enough if unique)
        out = split_df.merge(
            full_history[['race_id', 'horse'] + v3_features],
            on=['race_id', 'horse'],
            how='left'
        )
        
        out_path = TRAIN_DIR / f"v3_velocity_candidates_{s}.parquet"
        out[['race_id', 'horse'] + v3_features].to_parquet(out_path, index=False)
        print(f"  Saved {len(out):,} rows to {out_path}")

if __name__ == "__main__":
    generate_v3_velocity_features_v2()
