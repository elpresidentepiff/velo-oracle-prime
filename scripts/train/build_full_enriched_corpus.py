"""
Comprehensive unified corpus build for Challenger V2.
Joins Core, Passport, Intent, and TS features across all splits.
"""
import pandas as pd
import json
from pathlib import Path

def build_full_enriched_corpus():
    ROOT = Path(".")
    TRAIN_DIR = ROOT / "data" / "new_build" / "training"
    PASSPORT_BANK = ROOT / "data" / "new_build" / "passports" / "horse_passports_v1.jsonl"
    
    # 1. Load TS features from bank
    print("Loading TS features from Passport Bank...")
    ts_data = []
    for line in PASSPORT_BANK.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        p = json.loads(line)
        ts_data.append({
            "horse": p["horse_name"],
            "pp_best_ts_last6": p.get("pp_best_ts_last6"),
            "pp_ts_trajectory": p.get("pp_ts_trajectory")
        })
    ts_df = pd.DataFrame(ts_data)

    # 2. Process each split
    splits = ["train", "val", "test"]
    all_dfs = []
    
    for split in splits:
        print(f"Processing {split} split...")
        base = pd.read_parquet(TRAIN_DIR / f"v2_challenger_{split}.parquet")
        
        # Passport features (Already joined in v2_challenger but let's be sure of intent)
        # Actually v2_challenger parquets usually have core+passport
        # Let's see if we need intent separately
        intent = pd.read_parquet(TRAIN_DIR / "intent_features.parquet")
        
        # Merge Intent
        df = base.merge(intent, on=["race_id", "horse"], how="left")
        
        # Merge TS
        df = df.merge(ts_df, on="horse", how="left")
        
        all_dfs.append(df)
        
    full_df = pd.concat(all_dfs, ignore_index=True)
    out_path = TRAIN_DIR / "v2_unified_ts_enriched_full.parquet"
    full_df.to_parquet(out_path)
    print(f"Full enriched corpus saved to {out_path} ({len(full_df):,} rows)")

if __name__ == "__main__":
    build_full_enriched_corpus()
