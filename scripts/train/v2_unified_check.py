import pandas as pd
import numpy as np
from pathlib import Path

def unified_join_and_check():
    ROOT = Path(".")
    TRAIN_DIR = ROOT / "data" / "new_build" / "training"
    
    print("Loading component parquets...")
    # 1. Base V2 parquets (contain Core + 3 new features)
    train_v2_base = pd.read_parquet(TRAIN_DIR / "v2_challenger_train.parquet")
    
    # 2. V1 aux features
    passport = pd.read_parquet(TRAIN_DIR / "passport_features.parquet")
    intent = pd.read_parquet(TRAIN_DIR / "intent_features.parquet")
    
    # 3. Join
    print("Performing unified join...")
    df = train_v2_base.merge(passport, on=["race_id", "horse"], how="left")
    df = df.merge(intent, on=["race_id", "horse"], how="left")
    
    # 4. Correlation Check
    print("\n--- Correlation Audit ---")
    if 'or_vs_career_best' in df.columns and 'curr_or_minus_best_or' in df.columns:
        # Need to handle nulls for correlation
        mask = df['or_vs_career_best'].notna() & df['curr_or_minus_best_or'].notna()
        corr = df.loc[mask, 'or_vs_career_best'].corr(df.loc[mask, 'curr_or_minus_best_or'])
        print(f"Correlation(or_vs_career_best, curr_or_minus_best_or): {corr:.4f}")
        
        if corr > 0.90:
            print("VERDICT: Redundancy detected (>0.90). or_vs_career_best should be DROPPED.")
        else:
            print("VERDICT: No extreme redundancy. or_vs_career_best is distinct enough.")
    else:
        print("Error: Required columns for correlation check not found.")
        print(f"Columns found: {df.columns.tolist()}")

    # 5. Save unified training set for ablation
    out_path = TRAIN_DIR / "v2_unified_train_full.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nUnified training set saved to {out_path} ({len(df):,} rows)")

if __name__ == "__main__":
    unified_join_and_check()
