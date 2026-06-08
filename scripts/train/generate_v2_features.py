import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

def generate_v2_features():
    ROOT = Path(".")
    RACEFORM_PATH = ROOT / "data" / "raceform_clean.parquet"
    TRAIN_DIR = ROOT / "data" / "new_build" / "training"
    
    print(f"Loading {RACEFORM_PATH}...")
    df = pd.read_parquet(RACEFORM_PATH)
    
    # Standardize types and sort
    df['date'] = pd.to_datetime(df['date'])
    df['or_rating'] = pd.to_numeric(df['or_rating'], errors='coerce')
    df = df.sort_values(['horse', 'date'])
    
    # Helper to identify AW
    df['is_aw'] = df['course'].str.contains('AW', case=False) | df['course'].str.contains('All-Weather', case=False)
    df['won'] = df['pos'].astype(str) == '1'
    
    print("Calculating rolling features...")
    
    # Initialize V2 columns
    df['pp_aw_vs_turf_delta'] = np.nan
    df['or_vs_career_best'] = np.nan
    df['pp_fresh_or_drop'] = False
    
    # Group by horse and calculate
    # To avoid slow loop, we use shifts and cumsums
    
    # 1. OR vs Career Best
    # Peak OR seen *strictly before* today
    df['prior_max_or'] = df.groupby('horse')['or_rating'].shift(1).groupby(df['horse']).cummax()
    # today_or - prior_max_or
    mask = df['or_rating'].notna() & df['prior_max_or'].notna()
    df.loc[mask, 'or_vs_career_best'] = df.loc[mask, 'or_rating'] - df.loc[mask, 'prior_max_or']
    
    # 2. pp_fresh_or_drop
    df['last_date'] = df.groupby('horse')['date'].shift(1)
    df['days_since_last'] = (df['date'] - df['last_date']).dt.days
    df['last_or'] = df.groupby('horse')['or_rating'].shift(1)
    
    df['pp_fresh_or_drop'] = (
        (df['days_since_last'] >= 60) & 
        (df['or_rating'].notna()) & 
        (df['last_or'].notna()) & 
        (df['or_rating'] < df['last_or'])
    )
    
    # 3. pp_aw_vs_turf_delta
    # AW Wins and Runs seen *strictly before* today
    df['prior_aw_runs'] = df.groupby('horse')['is_aw'].shift(1).fillna(False).astype(int).groupby(df['horse']).cumsum()
    df['prior_aw_wins'] = ((df.groupby('horse')['is_aw'].shift(1).fillna(False)) & (df.groupby('horse')['won'].shift(1).fillna(False))).astype(int).groupby(df['horse']).cumsum()
    
    # Turf Wins and Runs
    df['is_turf'] = ~df['is_aw']
    df['prior_turf_runs'] = df.groupby('horse')['is_turf'].shift(1).fillna(False).astype(int).groupby(df['horse']).cumsum()
    df['prior_turf_wins'] = ((df.groupby('horse')['is_turf'].shift(1).fillna(False)) & (df.groupby('horse')['won'].shift(1).fillna(False))).astype(int).groupby(df['horse']).cumsum()
    
    # Delta (min 3 runs each)
    aw_mask = df['prior_aw_runs'] >= 3
    turf_mask = df['prior_turf_runs'] >= 3
    full_mask = aw_mask & turf_mask
    
    df.loc[full_mask, 'pp_aw_vs_turf_delta'] = (df['prior_aw_wins'] / df['prior_aw_runs']) - (df['prior_turf_wins'] / df['prior_turf_runs'])
    
    # Save a small subset for leakage verification
    sample_horses = df['horse'].unique()[:100] # Get some horses
    # Try to find some with data in all features
    rich_horses = df[df['pp_aw_vs_turf_delta'].notna()]['horse'].unique()[:5]
    
    verify_df = df[df['horse'].isin(rich_horses)][['horse', 'date', 'or_rating', 'prior_max_or', 'or_vs_career_best', 'pp_aw_vs_turf_delta', 'pp_fresh_or_drop']]
    verify_df.to_csv("data/new_build/v2_leakage_check.csv", index=False)
    
    # Map back to training sets
    print("Mapping to training sets...")
    v2_features = ['pp_aw_vs_turf_delta', 'or_vs_career_best', 'pp_fresh_or_drop']
    
    # Create lookup map (horse, date) -> features
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    lookup = df.set_index(['horse', 'date_str'])[v2_features].reset_index()
    lookup = lookup.rename(columns={'date_str': 'date'})
    
    for split in ['train', 'val', 'test']:
        path = TRAIN_DIR / f"core_v0_or_{split}.parquet"
        print(f"  Processing {path}...")
        split_df = pd.read_parquet(path)
        
        # Merge
        result = split_df.merge(lookup, on=['horse', 'date'], how='left')
        
        # Save V2 version
        out_path = TRAIN_DIR / f"v2_challenger_{split}.parquet"
        result.to_parquet(out_path, index=False)
        print(f"  Saved {len(result)} rows to {out_path}")

if __name__ == "__main__":
    generate_v2_features()
